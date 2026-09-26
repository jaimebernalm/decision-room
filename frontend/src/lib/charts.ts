import type { ChartData } from "./types";
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
