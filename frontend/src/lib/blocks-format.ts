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

export function withUnit(value: number | null, decimals: number, unit: string | null) {
  const text = formatNumber(value, decimals);
  if (value === null || !unit) return text;
  return unit === "%" ? `${text} %` : `${text} ${unit}`;
}

export function signed(value: number, decimals: number, unit: string | null) {
  return (value > 0 ? "+" : "") + withUnit(value, decimals, unit);
}
