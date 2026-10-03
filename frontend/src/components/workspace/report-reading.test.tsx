import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, afterEach, it, expect, vi } from "vitest";
import { ReportView } from "./report";
import type { Report } from "@/lib/types";
const selection = vi.hoisted(() => ({
  active: false,
  toggle: vi.fn(),
  register: vi.fn(() => () => {}),
}));
vi.mock("@/lib/assistant", async (original) => ({
  ...(await original<typeof import("@/lib/assistant")>()),
  useAssistant: () =>
    selection.active
      ? {
          selecting: true,
          selected: [],
          toggle: selection.toggle,
          register: selection.register,
        }
      : null,
}));
const report: Report = {
  report_id: "review",
  report_version: "v1",
  title: "Ventas revisadas",
  partial: true,
  summary: "Resumen íntegro. No demuestra causalidad.",
  scope: {
    period: "Septiembre",
    coverage: "Solo registros disponibles",
    question: "¿Qué ha cambiado?",
  },
  limitations: ["Sin costes, no permite calcular margen"],
  highlights: Array.from({ length: 4 }, (_, i) => ({
    key: `metric-${i}`,
    label: `Ventas del segmento ${i}`,
    value: `${10 + i}`,
    unit: "EUR",
    claim_key: "sales",
  })),
  claims: [
    {
      key: "sales",
      title: "Ventas del periodo",
      statement:
        "Las ventas suben a 20.005 EUR. No demuestra un cambio de demanda.",
      interpretation: "Interpretación íntegra",
      method: "Suma de importes",
      next_step: "Comprobar días de apertura",
      evidence_details: {
        files: ["ventas.csv"],
        metrics: [{ label: "Total original", value: "20005" }],
        operations: ["Sumar registros disponibles"],
      },
    },
    {
      key: "context",
      title: "Hallazgo sin gráfico",
      statement: "No hay suficiente evidencia visual",
      interpretation: "Detalle sin gráfico",
    },
  ],
  charts: [
    {
      key: "daily",
      kind: "line",
      claim_key: "sales",
      title: "Ventas diarias",
      unit: "EUR",
      caption: "Importes registrados. No incluye devoluciones.",
      points: [
        {
          label: "2026-09-01",
          value: "20005",
          formatted: "20.005",
          original_label: "día-1",
        },
      ],
    },
    {
      key: "total-table",
      kind: "table",
      claim_key: "sales",
      title: "Tabla de ventas",
      unit: "EUR",
      caption: "Cifras revisadas",
      points: [{ label: "Septiembre", value: "20005", formatted: "20.005" }],
    },
  ],
};
beforeEach(() => {
  history.replaceState(null, "", "#report/job");
  selection.active = false;
  selection.toggle.mockClear();
});
afterEach(() => history.replaceState(null, "", "#home"));
it("shows the complete reviewed summary once before navigation and preserves a long period", () => {
  const period =
    "Periodo observado, con una descripción larga de las fechas disponibles y sus condiciones de cobertura";
  render(
    <ReportView
      report={{ ...report, scope: { ...report.scope, period } }}
      compact
    />,
  );
  const summary = screen.getByText(report.summary!);
  expect(summary).toBeVisible();
  expect(screen.getAllByText(report.summary!)).toHaveLength(1);
  expect(
    summary.compareDocumentPosition(screen.getByRole("navigation")) &
      Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy();
  expect(screen.getByText(period)).toHaveClass(
    "whitespace-normal",
    "max-w-full",
  );
});
it("navigates by keyboard within its own report without opening details, changing the route or fetching", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  const { container } = render(
    <>
      <ReportView report={report} compact />
      <ReportView report={report} compact />
    </>,
  );
  const navigation = screen.getAllByRole("navigation", {
    name: "En este informe",
  })[1];
  const destination =
    container.querySelectorAll<HTMLElement>("#finding-context")[1];
  const button = within(navigation).getByRole("button", {
    name: "Hallazgo sin gráfico",
  });
  button.focus();
  await userEvent.keyboard("{Enter}");
  expect(destination).toHaveFocus();
  expect(
    within(destination).getByRole("button", {
      name: "Datos y fuentes: Hallazgo sin gráfico",
    }),
  ).toHaveAttribute("aria-expanded", "false");
  expect(location.hash).toBe("#report/job");
  expect(fetch).not.toHaveBeenCalled();
});
it("keeps multiple visuals in the finding card before keyboard-opened details", async () => {
  const { container } = render(<ReportView report={report} />);
  const finding = container.querySelector<HTMLElement>("#finding-sales")!;
  const scoped = within(finding);
  const chartTitle = scoped.getByText("Ventas diarias");
  const tableTitle = scoped.getByText("Tabla de ventas");
  const trigger = scoped.getByRole("button", {
    name: "Datos y fuentes: Ventas del periodo",
  });
  expect(
    chartTitle.compareDocumentPosition(trigger) &
      Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy();
  expect(
    tableTitle.compareDocumentPosition(trigger) &
      Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy();
  expect(scoped.getByRole("table")).toBeVisible();
  expect(screen.queryByText("Interpretación íntegra")).toBeNull();
  trigger.focus();
  await userEvent.keyboard("{Enter}");
  const detail = scoped.getByText("Interpretación íntegra");
  expect(trigger).toHaveAttribute("aria-expanded", "true");
  expect(
    chartTitle.compareDocumentPosition(detail) &
      Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy();
  expect(scoped.getByText(/Comprobar días de apertura/)).toBeVisible();
  expect(scoped.getByText("Suma de importes")).toBeVisible();
  expect(scoped.getByText("Total original: 20005")).toBeVisible();
  expect(scoped.getByText("día-1")).toBeVisible();
  expect(scoped.getByText("Código original")).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", {
      name: "Datos y fuentes: Hallazgo sin gráfico",
    }),
  );
  expect(screen.getByText("Detalle sin gráfico")).toBeVisible();
});
it("keeps reviewed conditions complete and limits visible while moving context into the header", async () => {
  render(<ReportView report={report} />);
  expect(screen.getByText(report.claims[0].statement)).toBeVisible();
  expect(screen.getByText(report.charts[0].caption)).toBeVisible();
  expect(screen.getByText(report.limitations[0])).toBeVisible();
  expect(screen.getByText("Entrega parcial")).toBeVisible();
  expect(screen.queryByText("Contexto y alcance")).toBeNull();
  expect(screen.queryByText("Solo registros disponibles")).toBeNull();
  expect(screen.queryByText("Ventas del segmento 3")).toBeNull();
  await userEvent.click(
    screen.getByRole("button", { name: "Sobre este informe" }),
  );
  expect(screen.getByText(report.summary!)).toBeVisible();
  expect(screen.getByText("Solo registros disponibles")).toBeVisible();
  expect(screen.getByText("ventas.csv")).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", { name: "Más indicadores del informe" }),
  );
  expect(screen.getByText("Ventas del segmento 3")).toBeVisible();
});
it("opens and focuses the exact linked finding only in the expected reviewed version", () => {
  history.replaceState(null, "", "#report/job/finding/sales/review/v1");
  const { container } = render(<ReportView report={report} />);
  expect(
    screen.getByRole("button", {
      name: "Ocultar datos y fuentes: Ventas del periodo",
    }),
  ).toHaveAttribute("aria-expanded", "true");
  expect(container.querySelector("#finding-sales")).toHaveFocus();
});
it("does not substitute a missing or changed finding when following an old card", () => {
  history.replaceState(
    null,
    "",
    "#report/job/finding/sales/review/old-version",
  );
  render(<ReportView report={report} />);
  expect(screen.getByRole("status")).toHaveTextContent("otra revisión");
  expect(
    screen.getByRole("button", { name: "Datos y fuentes: Ventas del periodo" }),
  ).toHaveAttribute("aria-expanded", "false");
});
it("keeps distinct chart and finding references for contextual chat selection", async () => {
  selection.active = true;
  render(<ReportView report={report} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Seleccionar: Ventas diarias" }),
  );
  expect(selection.toggle).toHaveBeenLastCalledWith(
    expect.objectContaining({
      report_id: "review",
      report_version: "v1",
      kind: "chart",
      element_key: "daily",
      period: "Septiembre",
      href: "#report/job",
    }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Seleccionar: Ventas del periodo" }),
  );
  expect(selection.toggle).toHaveBeenLastCalledWith(
    expect.objectContaining({
      report_id: "review",
      report_version: "v1",
      kind: "insight",
      element_key: "sales",
    }),
  );
});
