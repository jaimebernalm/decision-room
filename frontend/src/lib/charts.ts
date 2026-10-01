import { translate as tr } from "@/lib/i18n";
import { displayNumber } from "./presentation";
import palette from "../../../decision_room/chart_palette.json";
import type { ChartData } from "./types";
export const CHART_SERIES_PALETTE: readonly string[] = palette.series;
export const CHART_NEUTRALS = palette.neutrals;
export const CHART_PALETTE: readonly string[] = [
  ...CHART_SERIES_PALETTE,
  ...Object.values(CHART_NEUTRALS),
];
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
    const axis = temporal ? Date.parse(point.label) : point.label;
    if (
      temporal &&
      index &&
      Number(axis) - Date.parse(chart.points[index - 1].label) > 86400000
    ) {
      // Break the line without asserting a zero or an interpolated value for a missing date.
      points.push({
        label: "",
        value: null,
        formatted: "",
        axis: Date.parse(chart.points[index - 1].label) + 86400000,
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
  return categories.map((category) => {
    const row: Record<string, string | number | null> = { category };
    panel.series_order.forEach((series, index) => {
      const coordinate = panel.coordinates.find(
        (c) => c.category === category && c.series === series,
      );
      const point = coordinate ? saved.get(coordinate.label) : undefined;
      row[`s${index}`] = point ? Number(point.value) : null;
      row[`s${index}Exact`] = point ? displayNumber(point.formatted) : tr("Sin dato");
    });
    return row;
  });
}
