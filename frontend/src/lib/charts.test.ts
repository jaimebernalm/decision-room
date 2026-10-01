import { it, expect } from "vitest";
import {
  CHART_PALETTE,
  CHART_SERIES_PALETTE,
  CHART_NEUTRALS,
  chartPoints,
  groupedPoints,
  seriesColor,
} from "./charts";
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

it("keeps every fallback series within the product's fixed palette", () => {
  expect(CHART_PALETTE).toEqual([
    ...CHART_SERIES_PALETTE,
    ...Object.values(CHART_NEUTRALS),
  ]);
  expect(Object.keys(CHART_NEUTRALS)).toEqual([
    "reference",
    "secondary",
    "muted",
  ]);
  for (const series of [
    "junio",
    "2026-06",
    "cambio julio-agosto",
    ...Array.from({ length: 40 }, (_, i) => `series-${i}`),
  ])
    expect(CHART_SERIES_PALETTE).toContain(seriesColor(series));
});

it("connects consecutive months and preserves whole missing months as gaps", () => {
  const points = chartPoints({
    ...chart,
    temporal_grain: "month",
    points: [
      { label: "2026-06", value: "10", formatted: "10" },
      { label: "2026-07", value: "12", formatted: "12" },
      { label: "2026-09", value: "14", formatted: "14" },
    ],
  });
  expect(points.map((p) => p.value)).toEqual([10, 12, null, 14]);
  expect(points.map((p) => p.label).filter(Boolean)).toEqual([
    "2026-06",
    "2026-07",
    "2026-09",
  ]);
});
it("multi-series temporal views break missing cells without changing saved values", () => {
  const monthly = {
    ...chart,
    temporal_grain: "month" as const,
    points: [
      { label: "a", value: "10.005", formatted: "10,01" },
      { label: "b", value: "20", formatted: "20,00" },
    ],
  };
  const rows = groupedPoints(monthly, {
    title: "",
    category_title: "Mes",
    series_title: "Canal",
    measure: "level",
    temporal_grain: "month",
    series_order: ["A", "B"],
    coordinates: [
      { label: "a", category: "2026-06", series: "A" },
      { label: "b", category: "2026-08", series: "B" },
    ],
  });
  expect(rows.map((r) => [r.s0, r.s1])).toEqual([
    [10.005, null],
    [null, null],
    [null, 20],
  ]);
  expect(rows[0].s0Exact).toBe("10,01");
  expect(monthly.points.length).toBe(2);
});
