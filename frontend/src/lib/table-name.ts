/** Presentation only: source names and identifiers remain unchanged. */
export function tableName(source: string): string {
  const sheet = source.match(/\.(?:xlsx|xlsm|xls) \[(.+)\]\.csv$/i);
  const name = sheet
    ? sheet[1]
    : source
        .replace(/\.(?:csv|xlsx|xlsm|xls)$/i, "")
        .split(/[\\/]/)
        .pop() || source;
  return name.charAt(0).toLocaleUpperCase() + name.slice(1);
}
