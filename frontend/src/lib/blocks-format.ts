import { locale } from "@/lib/i18n";

/** Platform formatting of agent numbers; the agent never supplies formatted strings. */
export function formatNumber(value: number | null, decimals: number) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat(locale(), {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    // Same grouping as the canonical text: 4.918, not 4918 (Spanish default).
    useGrouping: "always",
  } as Intl.NumberFormatOptions)
    .format(value)
    .replace("-", "−");
}

/** Up to 2 decimals as delivered, or more so a nonzero value never shows as 0 (same rule as the projector). */
export function naturalDecimals(value: number) {
  const text = String(value);
  const places = text.includes("e-")
    ? Number(text.split("e-")[1])
    : (text.split(".")[1] || "").length;
  let decimals = Math.min(places, 2);
  if (value !== 0 && Math.abs(value) < 0.5 * 10 ** -decimals)
    decimals = Math.min(15, Math.ceil(-Math.log10(Math.abs(value))));
  return decimals;
}

export function withUnit(value: number | null, decimals: number, unit: string | null) {
  const text = formatNumber(value, decimals);
  if (value === null || !unit) return text;
  return unit === "%" ? `${text} %` : `${text} ${unit}`;
}

export function signed(value: number, decimals: number, unit: string | null) {
  return (value > 0 ? "+" : "") + withUnit(value, decimals, unit);
}
