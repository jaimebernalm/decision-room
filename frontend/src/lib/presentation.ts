/** Exact decimal preview with the server's half-up rounding; no float conversion. */
export function presentationNumber(raw: string, decimals: number): string {
  const match = /^([+-]?)(\d+)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/.exec(raw);
  if (!match) return raw;
  const exponent = Number(match[4] || 0);
  if (!Number.isInteger(exponent) || Math.abs(exponent) > 120) return raw;
  const digits = BigInt(match[2] + (match[3] || ""));
  const shift = exponent - (match[3]?.length || 0) + decimals;
  let rounded: bigint;
  if (shift >= 0) rounded = digits * 10n ** BigInt(shift);
  else {
    const factor = 10n ** BigInt(-shift);
    rounded = digits / factor + ((digits % factor) * 2n >= factor ? 1n : 0n);
  }
  const value = rounded.toString().padStart(decimals + 1, "0");
  const integer = decimals ? value.slice(0, -decimals) : value;
  return (
    (match[1] === "-" ? "-" : "") +
    integer.replace(/\B(?=(\d{3})+(?!\d))/g, ".") +
    (decimals ? "," + value.slice(-decimals) : "")
  );
}
