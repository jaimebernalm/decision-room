import type { ReactNode } from "react";

const graphemes = new Intl.Segmenter(undefined, { granularity: "grapheme" });
const fold = (text: string) =>
  text
    .toLowerCase()
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .replace(/ß/g, "ss")
    .replace(/ς/g, "σ");

export function SearchHighlight({
  text,
  query,
}: {
  text: string;
  query: string;
}) {
  const needle = fold(query.trim());
  if (!needle) return text;
  let normalized = "";
  const offsets: { start: number; end: number }[] = [];
  for (const { segment, index } of graphemes.segment(text)) {
    const value = fold(segment);
    normalized += value;
    for (let i = 0; i < value.length; i++)
      offsets.push({ start: index, end: index + segment.length });
  }
  const parts: ReactNode[] = [];
  let cursor = 0;
  for (
    let match = normalized.indexOf(needle);
    match !== -1;
    match = normalized.indexOf(needle, match + needle.length)
  ) {
    const start = offsets[match].start;
    const end = offsets[match + needle.length - 1].end;
    if (start < cursor) continue;
    parts.push(text.slice(cursor, start));
    parts.push(
      <strong key={start} className="font-semibold text-foreground">
        {text.slice(start, end)}
      </strong>,
    );
    cursor = end;
  }
  parts.push(text.slice(cursor));
  return parts;
}
