/** Chart-local width prevents clipping in report cards, side panels and mobile. */
export function ReportChartTooltip({
  title,
  unit,
  items,
}: {
  title: string;
  unit: string;
  items: { label: string; value: string; color?: string }[];
}) {
  return (
    <div
      role="tooltip"
      className="grid min-w-0 gap-3 rounded-lg border border-border/50 bg-background p-3 text-xs whitespace-normal shadow-lg [overflow-wrap:anywhere]"
      style={{ width: "min(20rem, calc(100cqi - 1rem))" }}
    >
      <div className="min-w-0 space-y-1">
        <p className="font-medium leading-snug">{title}</p>
        <p className="leading-relaxed text-muted-foreground">{unit}</p>
      </div>
      <dl className="grid min-w-0 grid-cols-[minmax(0,1fr)_fit-content(45%)] gap-x-4 gap-y-2">
        {items.map((item, index) => (
          <div key={index} className="contents">
            <dt className="flex min-w-0 items-start gap-2 leading-relaxed">
              {item.color && (
                <span
                  aria-hidden
                  className="mt-1 size-2 shrink-0 rounded-sm"
                  style={{ background: item.color }}
                />
              )}
              <span className="min-w-0">{item.label}</span>
            </dt>
            <dd className="min-w-0 text-right font-mono leading-relaxed tabular-nums">
              {item.value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
