import { render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { ReportChartTooltip } from "./report-chart-tooltip";

it("shows full category and units once while preserving exact values for every series", () => {
  const unit =
    "unidades registradas; cambios como diferencia posterior menos anterior";
  const title =
    "Café de la casa 250 g con una descripción extensa del producto";
  render(
    <ReportChartTooltip
      title={title}
      unit={unit}
      items={[
        { label: "junio", value: "473", color: "#367da5" },
        { label: "julio", value: "598", color: "#89bbd7" },
        { label: "agosto", value: "707", color: "#28658a" },
      ]}
    />,
  );
  const tooltip = within(screen.getByRole("tooltip"));
  expect(tooltip.getByText(title)).toBeVisible();
  expect(tooltip.getAllByText(unit)).toHaveLength(1);
  for (const text of ["junio", "473", "julio", "598", "agosto", "707"])
    expect(tooltip.getByText(text)).toBeVisible();
});
it("preserves a long series name and decimal string without rounding or truncating", () => {
  const exact = "9.007.199.254.740.993,01";
  const series =
    "Una categoría muy larga que debe seguir siendo legible en una tarjeta estrecha";
  render(
    <ReportChartTooltip
      title="Comparación"
      unit="EUR"
      items={[{ label: series, value: exact }]}
    />,
  );
  expect(screen.getByText(series)).toBeVisible();
  expect(screen.getByText(exact)).toBeVisible();
});
