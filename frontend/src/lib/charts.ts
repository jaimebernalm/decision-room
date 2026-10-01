import palette from "../../../decision_room/chart_palette.json";
import type { ChartData, TemporalGrain } from "./types";
export const CHART_SERIES_PALETTE: readonly string[] = palette.series;
export const CHART_NEUTRALS = palette.neutrals;
export const CHART_PALETTE: readonly string[] = [
  ...CHART_SERIES_PALETTE,
  ...Object.values(CHART_NEUTRALS),
];
export function periodGrain(label: string): TemporalGrain {
  return /^\d{4}$/.test(label)
    ? "year"
    : label.includes("Q")
      ? "quarter"
      : label.length === 7
        ? "month"
        : "day";
}
export function periodIndex(label: string, grain = periodGrain(label)) {
  if (grain === "month")
    return Number(label.slice(0, 4)) * 12 + Number(label.slice(5));
  if (grain === "quarter")
    return Number(label.slice(0, 4)) * 4 + Number(label.slice(-1));
  if (grain === "year") return Number(label);
  return Date.parse(label) / 86400000;
}
export function periodAxis(label: string, grain = periodGrain(label)) {
  if (grain === "quarter")
    return Date.parse(
      `${label.slice(0, 4)}-${String((Number(label.slice(-1)) - 1) * 3 + 1).padStart(2, "0")}-01`,
    );
  if (grain === "year") return Date.parse(`${label}-01-01`);
  return Date.parse(label);
}
/** Numeric coordinates are for drawing only; display keeps the server's decimal strings. */
export function chartPoints(chart: ChartData) {
  const temporal = chart.kind === "line";
  const points: {
    label: string;
    value: number | null;
    formatted: string;
    axis: number | string;
  }[] = [];
  chart.points.forEach((point, index) => {
    const axis = temporal
      ? periodAxis(point.label, chart.temporal_grain ?? undefined)
      : point.label;
    if (
      temporal &&
      index &&
      periodIndex(point.label, chart.temporal_grain ?? undefined) -
        periodIndex(
          chart.points[index - 1].label,
          chart.temporal_grain ?? undefined,
        ) >
        1
    ) {
      // Break the line without asserting a zero or an interpolated value for a missing date.
      points.push({
        label: "",
        value: null,
        formatted: "",
        axis:
          (Number(axis) +
            periodAxis(
              chart.points[index - 1].label,
              chart.temporal_grain ?? undefined,
            )) /
          2,
      });
    }
    points.push({ ...point, value: Number(point.value), axis });
  });
  return points;
}

/** Stable across charts, independent of the order of categories or missing cells. */
export function seriesColor(series: string) {
  const month = /^(?:\d{4}-)(0[1-9]|1[0-2])$/.exec(series);
  const months =
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(
      " ",
    );
  const index = month ? Number(month[1]) - 1 : months.indexOf(series);
  const hash =
    index >= 0
      ? index
      : [...series].reduce((n, c) => (n * 31 + c.charCodeAt(0)) >>> 0, 0);
  return CHART_SERIES_PALETTE[hash % CHART_SERIES_PALETTE.length];
}
export function groupedPoints(
  chart: ChartData,
  panel: NonNullable<ChartData["panels"]>[number],
) {
  const saved = new Map(chart.points.map((p) => [p.label, p]));
  const categories = [...new Set(panel.coordinates.map((p) => p.category))];
  const rows = categories.map((category) => {
    const row: Record<string, string | number | null> = {
      category,
      ...(chart.kind === "line"
        ? { axis: periodAxis(category, panel.temporal_grain ?? undefined) }
        : {}),
    };
    panel.series_order.forEach((series, index) => {
      const coordinate = panel.coordinates.find(
        (c) => c.category === category && c.series === series,
      );
      const point = coordinate ? saved.get(coordinate.label) : undefined;
      row[`s${index}`] = point ? Number(point.value) : null;
      row[`s${index}Exact`] = point?.formatted ?? "Sin dato";
    });
    return row;
  });
  if (chart.kind !== "line") return rows;
  return rows.flatMap((row, index) => {
    if (
      index &&
      periodIndex(String(row.category), panel.temporal_grain ?? undefined) -
        periodIndex(
          String(rows[index - 1].category),
          panel.temporal_grain ?? undefined,
        ) >
        1
    ) {
      return [
        {
          category: "",
          axis: (Number(row.axis) + Number(rows[index - 1].axis)) / 2,
          ...Object.fromEntries(
            panel.series_order.map((_, i) => [`s${i}`, null]),
          ),
        },
        row,
      ];
    }
    return [row];
  });
}
