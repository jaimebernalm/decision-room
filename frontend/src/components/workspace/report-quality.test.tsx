import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { it, expect, vi } from "vitest";
import { ReportView, EvidenceChart } from "./report";
import type { Report, ChartData } from "@/lib/types";
import { setLanguage } from "@/lib/i18n";

const chart: ChartData = {
  key: "trend",
  claim_key: "focus",
  kind: "line",
  title: "Canales por mes",
  unit: "unidades",
  caption: "Sin imputar ausencias",
  temporal_grain: "month",
  points: [
    {
      label: "j_a",
      value: "9007199254740993.01",
      formatted: "9.007.199.254.740.993,01",
    },
    { label: "j_b", value: "20", formatted: "20" },
    { label: "a_a", value: "30", formatted: "30" },
  ],
  panels: [
    {
      title: "",
      category_title: "Mes",
      series_title: "Canal",
      measure: "level",
      temporal_grain: "month",
      series_order: ["A", "B"],
      coordinates: [
        { label: "j_a", category: "2026-07", series: "A" },
        { label: "j_b", category: "2026-07", series: "B" },
        { label: "a_a", category: "2026-08", series: "A" },
      ],
    },
  ],
  details: [
    {
      point_label: "a_a",
      claim_key: "focus",
      values: [
        { label: "Cambio guardado", formatted: "-93", unit: "unidades" },
      ],
    },
  ],
};
const report: Report = {
  title: "Prueba sintética",
  summary: "Resumen revisado.",
  scope: { period: "Julio–agosto", coverage: "Solo registros observados" },
  highlights: [],
  charts: [chart],
  limitations: [],
  claims: [
    {
      key: "focus",
      title: "Prioridad del canal",
      statement: "Señal focal revisada.",
      method: "Método completo",
      orientation: {
        segment: "Canal A",
        period: "Julio–agosto",
        signal: "Señal focal revisada.",
        relative_priority: "Diverge del resto de canales.",
        knowledge: "calculated",
        next_check: "Revisar disponibilidad en agosto para Canal A.",
        decision_value: "Distinguir disponibilidad de actividad.",
        reactions: [
          {
            condition: "se documenta falta de producto",
            reaction: "Revisar reposición.",
          },
        ],
        limitation: "La disponibilidad no consta.",
      },
    },
  ],
};
it("preserves an already conditional sentence without adding a second condition prefix", () => {
  const condition = "Si un calendario documenta una diferencia de apertura";
  const original = report.claims[0];
  render(
    <ReportView
      report={{
        ...report,
        claims: [
          {
            ...original,
            orientation: {
              ...original.orientation!,
              reactions: [{ condition, reaction: "Separar exposición." }],
            },
          },
        ],
      }}
      compact
    />,
  );
  expect(screen.getByText(condition + ":")).toBeVisible();
  expect(screen.queryByText("Si " + condition + ":")).toBeNull();
});

it("localizes decision controls and period labels while preserving saved evidence and conditions", async () => {
  const saved = JSON.stringify(report);
  act(() => setLanguage("en"));
  render(<ReportView report={report} compact />);
  expect(screen.getByText("Next check:")).toBeVisible();
  expect(screen.getByText("If se documenta falta de producto:")).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", { name: "View breakdown by period" }),
  );
  const select = screen.getByRole("combobox", {
    name: "Period or category for Canales por mes",
  });
  expect(within(select).getByRole("option", { name: "Jul 2026" })).toHaveValue(
    "2026-07",
  );
  await userEvent.selectOptions(select, "2026-07");
  expect(
    screen.getByText("A: 9,007,199,254,740,993.01 unidades"),
  ).toBeVisible();
  expect(JSON.stringify(report)).toBe(saved);
  act(() => setLanguage("es"));
  expect(select).toHaveValue("2026-07");
  expect(
    screen.getByText("A: 9.007.199.254.740.993,01 unidades"),
  ).toBeVisible();
  expect(screen.getByText("Si se documenta falta de producto:")).toBeVisible();
});

it("makes priority/check/condition visible before opening methodological detail", () => {
  render(<ReportView report={report} compact />);
  expect(
    screen.getByText("Revisar disponibilidad en agosto para Canal A.", {
      exact: false,
    }),
  ).toBeVisible();
  expect(
    screen.getByText("Revisar reposición.", { exact: false }),
  ).toBeVisible();
  expect(screen.getByText("La disponibilidad no consta.")).toBeVisible();
  expect(screen.queryByText("Método completo")).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /Prioridad del canal/ }),
  ).toHaveAttribute("aria-expanded", "false");
});
it("keeps the full conclusion and decision guidance with its chart while detail stays collapsed", async () => {
  const conclusion =
    "El canal cambia en agosto. La segunda frase explica su importancia.";
  render(
    <ReportView
      report={{
        ...report,
        claims: [{ ...report.claims[0], statement: conclusion }],
      }}
      compact
    />,
  );
  expect(screen.getByText(conclusion)).toBeVisible();
  expect(
    screen.getAllByText("Revisar reposición.", { exact: false }),
  ).toHaveLength(1);
  expect(screen.getByRole("group", { name: "Series: Canal" })).toBeVisible();
  expect(screen.queryByText("Método completo")).not.toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: /Prioridad del canal/ }),
  );
  expect(await screen.findByText("Método completo")).toBeVisible();
  expect(screen.getByText("9.007.199.254.740.993,01")).toBeVisible();
  expect(screen.getByText("Sin dato")).toBeVisible();
  expect(screen.getAllByText(conclusion)).toHaveLength(1);
});
it("selects exact saved values with keyboard and activates the linked finding without fetch", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  render(<ReportView report={report} compact />);
  await userEvent.click(
    screen.getByRole("button", { name: "Ver desglose por periodo" }),
  );
  const select = screen.getByRole("combobox", { name: /Periodo o categoría/ });
  select.focus();
  await userEvent.selectOptions(select, "2026-08");
  expect(screen.getByText("Cambio guardado: -93 unidades")).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", {
      name: "Ver hallazgo y siguiente comprobación",
    }),
  );
  expect(
    screen.getByRole("button", { name: /Prioridad del canal/ }),
  ).toHaveAttribute("aria-expanded", "true");
  expect(fetch).not.toHaveBeenCalled();
});
it("toggles series without removing exact evidence and preserves absent cells", async () => {
  render(<EvidenceChart chart={chart} />);
  const group = within(screen.getByRole("group", { name: "Series: Canal" }));
  const a = group.getByRole("button", { name: "A Visible" });
  const b = group.getByRole("button", { name: "B Visible" });
  b.focus();
  await userEvent.keyboard("{Enter}");
  expect(b).toHaveAttribute("aria-pressed", "false");
  expect(b).toHaveAccessibleName("B Oculta");
  expect(b).toHaveAttribute("title", "Mostrar B");
  expect(a).toBeDisabled();
  await userEvent.click(screen.getByText("Ver valores exactos"));
  expect(screen.getByText("9.007.199.254.740.993,01")).toBeVisible();
  expect(screen.getByText("Sin dato")).toBeVisible();
  expect(chart.points).toHaveLength(3);
});
it("home charts link to their approved source and remounting preserves evidence", async () => {
  const first = render(
    <EvidenceChart chart={chart} sourceHref="#report/synthetic" />,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Ver desglose por periodo" }),
  );
  await userEvent.selectOptions(screen.getByRole("combobox"), "2026-08");
  expect(
    screen.getByRole("link", { name: /Ver hallazgo y detalle/ }),
  ).toHaveAttribute("href", "#report/synthetic");
  first.unmount();
  render(<EvidenceChart chart={chart} />);
  expect(screen.queryByRole("combobox")).toBeNull();
  await userEvent.click(
    screen.getByRole("button", { name: "Ver desglose por periodo" }),
  );
  expect(screen.getByRole("combobox")).toHaveValue("");
  await userEvent.click(screen.getByText("Ver valores exactos"));
  expect(screen.getByText("9.007.199.254.740.993,01")).toBeVisible();
});

it("omits redundant point controls when no saved breakdown exists", () => {
  render(<EvidenceChart chart={{ ...chart, details: [] }} />);
  expect(screen.queryByRole("combobox")).toBeNull();
  expect(
    screen.queryByRole("button", { name: "Ver desglose por periodo" }),
  ).toBeNull();
  expect(
    screen.getByRole("button", { name: "Ver valores exactos" }),
  ).toBeVisible();
});
it("restores a hidden series by keyboard with clear show and hide actions", async () => {
  render(<EvidenceChart chart={chart} />);
  const b = screen.getByRole("button", { name: "B Visible" });
  expect(b).toHaveAttribute("title", "Ocultar B");
  b.focus();
  await userEvent.keyboard("{Enter}");
  expect(b).toHaveAccessibleName("B Oculta");
  await userEvent.keyboard("{Enter}");
  expect(b).toHaveAccessibleName("B Visible");
  expect(b).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "A Visible" })).toBeEnabled();
});

it("highlights hovered visible series and clears emphasis without changing evidence", async () => {
  const saved = JSON.stringify(chart);
  render(<EvidenceChart chart={chart} />);
  const a = screen.getByRole("button", { name: "A Visible" });
  const b = screen.getByRole("button", { name: "B Visible" });
  await userEvent.hover(a);
  expect(a).toHaveAttribute("data-highlighted", "true");
  expect(b).not.toHaveAttribute("data-highlighted");
  await userEvent.unhover(a);
  expect(a).not.toHaveAttribute("data-highlighted");
  await userEvent.click(b);
  await userEvent.hover(b);
  expect(b).not.toHaveAttribute("data-highlighted");
  expect(b).toHaveAttribute("aria-pressed", "false");
  expect(JSON.stringify(chart)).toBe(saved);
});
it("shows method, sources and exact values together after one data disclosure", async () => {
  render(<ReportView report={report} compact />);
  expect(screen.queryByText("Método completo")).toBeNull();
  await userEvent.click(
    screen.getByRole("button", {
      name: "Datos y fuentes: Prioridad del canal",
    }),
  );
  expect(screen.getByText("Método completo")).toBeVisible();
  expect(screen.getByText("9.007.199.254.740.993,01")).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Cómo se ha calculado" }),
  ).toBeNull();
  expect(
    screen.queryByRole("button", { name: "Ver valores exactos" }),
  ).toBeNull();
});
it("omits an empty data disclosure for a finding without supporting detail", () => {
  render(
    <ReportView
      report={{
        ...report,
        charts: [],
        claims: [
          {
            key: "plain",
            title: "Conclusión sencilla",
            statement: "Conclusión completa.",
          },
        ],
      }}
      compact
    />,
  );
  expect(
    screen.getByRole("heading", { name: "Conclusión sencilla" }),
  ).toBeVisible();
  expect(screen.queryByRole("button", { name: /Datos y fuentes:/ })).toBeNull();
});
