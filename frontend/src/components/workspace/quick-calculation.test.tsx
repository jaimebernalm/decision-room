import { it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { setLanguage } from "@/lib/i18n";
import { QuickCalculations } from "./quick-calculation";
import type { QuickCalculation } from "@/lib/types";

const item: QuickCalculation = {
  calculation_id: "c",
  execution_id: "e",
  label: "Cálculo rápido, sin comprobación independiente",
  purpose: "Unidades vendidas en enero",
  code: "print('<script>alert(1)</script>')\nwrite_result({'unidades': 180})",
  tables: [{ alias: "ventas", names: ["ventas.csv"] }],
  metrics: { unidades: "180", "importe (EUR)": "1234.50" },
  evidence: [],
  evidence_omitted: 0,
  notes: ["Excluye devoluciones."],
  notes_omitted: 0,
};

it("keeps the no-check label visible and shows the code as inert text", async () => {
  setLanguage("es");
  render(<QuickCalculations items={[item]} />);
  expect(
    screen.getByText("Cálculo rápido, sin comprobación independiente"),
  ).toBeInTheDocument();
  expect(screen.getByText("1234.50")).toBeInTheDocument();
  expect(screen.queryByText(/write_result/)).toBeNull();
  await userEvent.click(screen.getByText("Ver el código y las tablas"));
  expect(screen.getByText(/write_result/).closest("pre")).not.toBeNull();
  expect(document.querySelector("script")).toBeNull();
  expect(screen.getByText(/ventas \(ventas\.csv\)/)).toBeInTheDocument();
});

it("translates the label in English", () => {
  setLanguage("en");
  render(<QuickCalculations items={[item]} />);
  expect(
    screen.getByText("Quick calculation, no independent check"),
  ).toBeInTheDocument();
  setLanguage("es");
});
