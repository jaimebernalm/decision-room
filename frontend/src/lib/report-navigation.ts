import type { HomeItem } from "./types";

/** The link identifies both the reviewed report and the finding; it is not a filter. */
export function findingHref(item: HomeItem) {
  const key =
    item.kind === "insight" ? item.content.key : item.content.claim_key;
  return `${item.source.href}/finding/${encodeURIComponent(key)}/${encodeURIComponent(item.source.report_id)}/${encodeURIComponent(item.source.version)}`;
}

export function findingTarget(hash: string) {
  const parts = hash.split("/");
  const index = parts.indexOf("finding");
  if (index < 0 || parts.length !== index + 4) return null;
  try {
    const [key, reportId, version] = parts
      .slice(index + 1)
      .map(decodeURIComponent);
    return key && reportId && version ? { key, reportId, version } : null;
  } catch {
    return null;
  }
}

export function relatedFinding(items: HomeItem[], chart: HomeItem) {
  if (chart.kind !== "chart") return undefined;
  return items.find(
    (item): item is HomeItem & { kind: "insight" } =>
      item.kind === "insight" &&
      item.content.key === chart.content.claim_key &&
      item.source.report_id === chart.source.report_id &&
      item.source.version === chart.source.version &&
      item.source.job_id === chart.source.job_id &&
      item.source.presentation?.revision ===
        chart.source.presentation?.revision,
  );
}
