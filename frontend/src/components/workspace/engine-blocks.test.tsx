import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { it, expect } from "vitest";
import { BlocksReport } from "./engine-blocks";
import { formatNumber } from "@/lib/blocks-format";
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
  expect(screen.queryByText("Cifras que no se pudieron comprobar")).toBeNull(); // folded away
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

it("summarizes unaddressed numeric spans without quoting them as disputed", async () => {
  render(
    <BlocksReport
      projection={projection}
      checks={{
        state: "complete",
        items: [
          { block_id: "b4", quote: "2026", status: "unverifiable", coverage: true,
            message: "3 fragmentos numéricos de esta prioridad quedaron sin comprobación explícita." },
        ],
      }}
    />,
  );
  expect(screen.queryByText(/3 fragmentos numéricos/)).toBeNull(); // inside the folded details
  await userEvent.click(screen.getByText("Detalles de la comprobación independiente"));
  expect(screen.getByText(/3 fragmentos numéricos/)).toBeVisible();
  expect(screen.queryByText("Cifras que no se pudieron comprobar")).toBeNull();
  expect(screen.queryByText("«2026»")).toBeNull();
});
