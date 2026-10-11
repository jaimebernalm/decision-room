import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { it, expect } from "vitest";
import { BlocksReport, judged, seriesColors, stackTotalLabel } from "./engine-blocks";
import { CHART_SEMANTIC } from "@/lib/charts";
import { exactDecimals, formatNumber } from "@/lib/blocks-format";
import { ReportView } from "./report";
import fixture from "@/test-fixtures/blocks-report.json";
import type { BlocksProjection, Report } from "@/lib/types";

const projection = fixture as unknown as BlocksProjection;

it("renders free blocks natively with platform formatting and no agent markup", () => {
  const { container } = render(<BlocksReport projection={projection} />);
  expect(container.querySelector("script, iframe")).toBeNull();
  expect(screen.getByText("La web crece.")).toBeInTheDocument();
  expect(screen.getByText("Importe neto")).toBeInTheDocument();
  expect(screen.getByText("39.918,54 €")).toBeInTheDocument();
  // Change and percentage are computed by the platform, never by the agent.
  expect(screen.getByText(/\+4\.918,54 € \(\+14,1 %\)/)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Canales" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /Validar Distribuidores/ })).toBeInTheDocument();
  expect(screen.getByText("342 unidades").tagName).toBe("STRONG");
  expect(screen.getByText("facturas").tagName).toBe("EM");
  expect(screen.getByText("Faltan registros del 4 al 26 de julio.")).toBeInTheDocument();
  const table = screen.getByRole("heading", { name: "Detalle" }).parentElement!;
  expect(within(table).getByText("Magnesio")).toBeInTheDocument();
  expect(within(table).getByText("—")).toBeInTheDocument();
});

it("keeps unknown chart kinds as tables and gaps as gaps", async () => {
  render(<BlocksReport projection={projection} />);
  const fallback = screen.getByText("Sin tipo").closest("[data-slot=card]") as HTMLElement;
  expect(within(fallback).getByRole("table")).toBeInTheDocument();
  const line = screen.getByText("Tasa mensual").closest("[data-slot=card]") as HTMLElement;
  await userEvent.click(within(line).getByText("Ver valores"));
  expect(within(line).getByText("13,7 %")).toBeVisible();
  expect(within(line).getByText("17 de 124")).toBeVisible();
  expect(within(line).getAllByText("—").length).toBeGreaterThan(0);
});

it("shows disputed figures next to their block and never a verified mark", () => {
  render(
    <BlocksReport
      projection={projection}
      checks={{
        state: "complete",
        items: [
          { block_id: "b4", quote: "342 unidades", status: "discrepancy", independent_value: "336" },
          { block_id: "b2", quote: "39.918,54 €", status: "unverifiable", message: "Falta el detalle de devoluciones." },
        ],
      }}
    />,
  );
  const priority = screen.getByRole("heading", { name: /Validar Distribuidores/ }).closest("section")!;
  expect(within(priority).getByRole("note")).toHaveTextContent("Cifra en revisión");
  expect(within(priority).getByRole("note")).toHaveTextContent("cálculo independiente: 336");
  expect(screen.getByText("Detalles de la comprobación independiente")).toBeInTheDocument();
  expect(screen.queryByText("Cifras que no se pudieron recalcular")).toBeNull(); // folded away
  expect(screen.queryByText(/Revisado|Verificado/)).toBeNull();
});

it("formats negatives with a true minus sign", () => {
  expect(formatNumber(-15630.29, 2)).toBe("−15.630,29");
  expect(formatNumber(null, 2)).toBe("—");
});

it("renders an engine_blocks report through the common report view", () => {
  const report: Report = {
    origin: "engine_blocks",
    title: "Cómo va el año",
    scope: { period: "", coverage: "" },
    claims: [],
    charts: [],
    highlights: [],
    limitations: [],
    engine_report: {
      document_id: "d",
      revision_id: "r",
      state: "current",
      is_current: true,
      run_status: "delivered",
      raw_sha256: "a".repeat(64),
      raw_bytes: 10,
      profile_version: "blocks-v1",
      history: [],
    },
    view: {
      mode: "blocks",
      policy_version: "blocks-escaped-1",
      receipt: "allowed",
      reason: null,
      canonical_text: "Cómo va el año",
      blocks: projection,
      checks: { state: "complete", items: [] },
    },
  };
  const { container } = render(<ReportView report={report} />);
  expect(container.querySelector("iframe")).toBeNull();
  expect(screen.getByText("La web crece.")).toBeInTheDocument();
});

it("summarizes the check in one plain sentence instead of repeating technical notes", async () => {
  render(
    <BlocksReport
      projection={projection}
      checks={{
        state: "complete",
        coverage: { numeric_spans: 31, addressed_spans: 26, confirmed_spans: 26 },
        items: [
          { block_id: "b4", quote: "2026", status: "unverifiable", coverage: true,
            message: "3 cifras de esta prioridad no se recalcularon de forma independiente." },
          { block_id: "b2", quote: "2025", status: "unverifiable", coverage: true,
            message: "2 cifras de esta prioridad no se recalcularon de forma independiente." },
        ],
      }}
    />,
  );
  expect(screen.queryByText(/Se examinaron/)).toBeNull(); // inside the folded details
  await userEvent.click(screen.getByText("Detalles de la comprobación independiente"));
  expect(screen.getByText(/Se examinaron 26 de los 31 números citados/)).toBeVisible();
  expect(screen.getByText(/no está marcada como errónea/)).toBeVisible();
  expect(screen.queryByText(/no se recalcularon de forma independiente/)).toBeNull();
  expect(screen.queryByText("Cifras que no se pudieron recalcular")).toBeNull();
  expect(screen.queryByText("«2026»")).toBeNull();
});

it("stacks parts of a total and lets the reader hide a series from the legend", async () => {
  const stacked: BlocksProjection = {
    ...projection,
    blocks: [
      {
        id: "b1", type: "chart", kind: "stacked_column", requested_kind: "apiladas", fallback: false,
        title: "Citas por estado", categories: ["ene", "feb"],
        series: [
          { name: "Realizadas", values: [100, 120], details: null },
          { name: "Canceladas", values: [10, 12], details: null },
        ],
        unit: null, decimals: 0, category_title: null, value_title: null, note: null,
      },
    ],
  };
  render(<BlocksReport projection={stacked} />);
  const hide = screen.getByRole("button", { name: "Canceladas" });
  expect(hide).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(hide);
  expect(hide).toHaveAttribute("aria-pressed", "false");
  // The last visible series cannot be hidden.
  const keep = screen.getByRole("button", { name: "Realizadas" });
  await userEvent.click(keep);
  expect(keep).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(screen.getByText("Ver valores"));
  expect(screen.getByText("120")).toBeVisible();
});

it("lets the reader sort a table and unfold long ones, keeping the author's order by default", async () => {
  const rows = Array.from({ length: 10 }, (_, i) => [`Producto ${i + 1}`, (i * 7) % 10] as (string | number)[]);
  const table: BlocksProjection = {
    ...projection,
    blocks: [
      {
        id: "b1", type: "table", title: "Ventas por producto", note: null, rows,
        columns: [{ title: "Producto", unit: null, decimals: null }, { title: "Unidades", unit: null, decimals: 0 }],
      },
    ],
  };
  render(<BlocksReport projection={table} />);
  const firstCells = () => screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[0].textContent);
  expect(firstCells()).toHaveLength(8);
  expect(firstCells()[0]).toBe("Producto 1");
  await userEvent.click(screen.getByRole("button", { name: /Unidades/ }));
  expect(screen.getByRole("columnheader", { name: /Unidades/ })).toHaveAttribute("aria-sort", "descending");
  expect(firstCells()[0]).toBe("Producto 8"); // 49 % 10 = 9, the largest
  await userEvent.click(screen.getByRole("button", { name: "Ver las 10 filas" }));
  expect(firstCells()).toHaveLength(10);
});

it("names stack totals with gaps or hidden series instead of treating a gap as zero", () => {
  const chart = {
    id: "b1", type: "chart", kind: "stacked_column", requested_kind: "apiladas", fallback: false,
    title: "Huecos", categories: ["Completa", "Parcial"],
    series: [
      { name: "A", values: [2, 2], details: null },
      { name: "B", values: [3, null], details: null },
    ],
    unit: null, decimals: 0, category_title: null, value_title: null, note: null,
  } as const;
  expect(stackTotalLabel(chart as never, 0, false)).toBe("Total");
  expect(stackTotalLabel(chart as never, 1, false)).toBe("Total parcial");
  expect(stackTotalLabel(chart as never, 0, true)).toBe("Total visible");
});

it("keeps every delivered decimal for exact values", () => {
  expect(exactDecimals(0.1234, 2)).toBe(4);
  expect(exactDecimals(13.7, 1)).toBe(1);
  expect(exactDecimals(12, 1)).toBe(1);
  expect(exactDecimals(1.5e-7, 0)).toBe(8);
  expect(exactDecimals(null, 2)).toBe(2);
  expect(exactDecimals(1.123e-15, 0)).toBe(18);
  expect(formatNumber(1.123e-15, exactDecimals(1.123e-15, 0))).toBe("0,000000000000001123");
});

it("shows the report's own title", () => {
  render(<BlocksReport projection={projection} />);
  expect(screen.getByRole("heading", { level: 2, name: projection.title })).toBeInTheDocument();
});

it("colors a change only when the report says which direction is good", () => {
  expect(judged(-110, "down")).toBe("positive");
  expect(judged(110, "down")).toBe("negative");
  expect(judged(110, null)).toBeNull();
  expect(judged(0, "up")).toBeNull();
  const tones = seriesColors([{ tone: "positive" }, {}, { tone: "negative" }, {}]);
  expect(tones[0]).toBe(CHART_SEMANTIC.positive);
  expect(tones[2]).toBe(CHART_SEMANTIC.negative);
  expect(tones[1]).not.toBe(tones[3]);
});

it("shows signed table changes, colored and attributed only when declared", () => {
  const report: BlocksProjection = {
    ...projection,
    blocks: [
      { id: "b1", type: "figure", label: "Cancelaciones", value: 446, unit: null, decimals: 0, period: null,
        previous: { value: 336, period: null }, change: 110, change_pct: 32.7, note: null, good: "down" },
      { id: "b2", type: "figure", label: "Citas", value: 5700, unit: null, decimals: 0, period: null,
        previous: { value: 4831, period: null }, change: 869, change_pct: 18, note: null },
      { id: "b3", type: "table", title: null, note: null,
        columns: [{ title: "Canal", unit: null, decimals: null },
                  { title: "Cambio", unit: null, decimals: 0, signed: true, good: "up" },
                  { title: "Nivel", unit: null, decimals: 0, signed: true }],
        rows: [["Web", 4951, 10], ["Distribuidores", -1187, 20]] },
      { id: "b4", type: "notice", content: [{ kind: "paragraph", spans: [{ text: "Prioridad del trimestre", bold: false, italic: false }] }] },
    ],
  };
  render(<BlocksReport projection={report} />);
  const worse = screen.getByText(/\+110 \(\+32,7 %\)/);
  expect(worse).toHaveAttribute("title", "Según el informe, es mejor que baje");
  expect(worse.style.color).not.toBe("");
  expect(screen.getByText(/\+869 \(\+18,0 %\)/).style.color).toBe("");
  const up = screen.getByText("+4.951");
  expect(up).toHaveAttribute("title", "Según el informe, es mejor que suba");
  expect(screen.getByText("−1.187").style.color).not.toBe("");
  expect(screen.getByText("+10").style.color).toBe(""); // signed but no declared meaning
  expect(screen.getByText("Prioridad del trimestre").closest("aside")).toHaveClass("border-l-4");
});
