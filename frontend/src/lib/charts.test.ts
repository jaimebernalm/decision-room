import { it, expect } from "vitest";
import { chartPoints } from "./charts";
import type { ChartData } from "./types";
const chart: ChartData = {
  key: "x",
  claim_key: "sales",
  kind: "line",
  title: "Ventas",
  unit: "EUR",
  caption: "",
  points: [
    { label: "2026-01-01", value: "10.001", formatted: "10,00" },
    { label: "2026-01-03", value: "20.005", formatted: "20,01" },
  ],
};
it("leaves missing dates unconnected without inventing zero observations", () => {
  const points = chartPoints(chart);
  expect(points.map((p) => p.value)).toEqual([10.001, null, 20.005]);
  expect(points[2].axis).toBe(Date.parse("2026-01-03"));
  expect(chart.points.length).toBe(2);
});
it("preserves reviewed decimal formatting even beyond floating point precision", () => {
  const exact = "9007199254740993.01";
  const points = chartPoints({
    ...chart,
    kind: "bar",
    points: [
      { label: "Total", value: exact, formatted: "9.007.199.254.740.993,01" },
    ],
  });
  expect(points[0].formatted).toBe("9.007.199.254.740.993,01");
  expect(points[0].axis).toBe("Total");
});

import { groupedPoints, seriesColor } from "./charts";
it("groups exact values with missing cells absent, never synthesized zero", () => {
  const grouped = {
    ...chart,
    kind: "bar" as const,
    panels: [
      {
        title: "",
        category_title: "Producto",
        series_title: "Mes",
        measure: "level" as const,
        series_order: ["2026-06", "2026-07"],
        coordinates: [
          { label: "2026-01-01", category: "A", series: "2026-06" },
          { label: "2026-01-03", category: "B", series: "2026-07" },
        ],
      },
    ],
  };
  const rows = groupedPoints(grouped, grouped.panels[0]);
  expect(rows.map((r) => [r.s0, r.s1])).toEqual([
    [10.001, null],
    [null, 20.005],
  ]);
  expect(rows[1].s1Exact).toBe("20,01");
  expect(seriesColor("junio")).toBe(seriesColor("2026-06"));
  expect(seriesColor("2026-07")).not.toBe(seriesColor("2026-06"));
});
