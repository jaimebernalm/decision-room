import { displayNumber } from "@/lib/presentation";
import { translate as tr, useLanguage, locale } from "@/lib/i18n";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  XAxis,
  YAxis,
  ReferenceLine,
} from "recharts";
import { EyeOff } from "lucide-react";
import { ChartContainer, ChartTooltip } from "@/components/ui/chart";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Selectable } from "./context-selection";
import { Disclosure } from "./shared";
import {
  CHART_PALETTE,
  categoryLabelLines,
  categoryRowHeight,
  groupedPoints,
  seriesColor,
  chartPoints,
  periodAxis,
  periodLabel,
} from "@/lib/charts";
import { findingTarget } from "@/lib/report-navigation";
import { PresentationEditor } from "./presentation-editor";
import { ReportSection } from "./report-section";
import { ReportChartTooltip } from "./report-chart-tooltip";
import type {
  ChartData,
  ChartPanel,
  Report as ReportData,
  ContextAttachment,
} from "@/lib/types";
const config = { value: { label: "Valor", color: CHART_PALETTE[0] } };
function GroupedBars({
  chart,
  panel,
}: {
  chart: ChartData;
  panel: ChartPanel;
}) {
  useLanguage();
  const rows = groupedPoints(chart, panel);
  const series = panel.series_order.map((name, i) => ({
    key: `s${i}`,
    name,
    color: CHART_PALETTE.includes(panel.colors?.[name] || "")
      ? panel.colors![name]
      : seriesColor(name),
  }));
  const extent = Math.max(
    ...rows.flatMap((row) =>
      series.map((s) => Math.abs(Number(row[s.key] ?? 0))),
    ),
    1,
  );
  return (
    <section
      className="min-w-0 space-y-3"
      aria-label={panel.title || chart.title}
    >
      {panel.title && <h4 className="text-sm font-medium">{panel.title}</h4>}
      <ul
        className="flex flex-wrap gap-x-5 gap-y-2 text-xs"
        aria-label={tr("Leyenda: {0}", { "0": panel.series_title })}
      >
        {series.map((s) => (
          <li key={s.key} className="flex items-center gap-2">
            <span
              aria-hidden
              className="size-2.5 rounded-sm"
              style={{ background: s.color }}
            />
            {s.name}
          </li>
        ))}
      </ul>
      <p className="sr-only">
        {tr(
          "Pulsa una serie para ocultarla o mostrarla. Debe quedar al menos una visible.",
        )}
      </p>
      <ChartContainer
        config={Object.fromEntries(
          series.map((s) => [s.key, { label: s.name, color: s.color }]),
        )}
        className="w-full"
        style={{
          containerType: "inline-size",
          height: Math.max(
            240,
            rows.length *
              Math.max(
                series.length * 22 + 28,
                categoryRowHeight(rows.map((row) => String(row.category))),
              ) +
              32,
          ),
        }}
        aria-label={panel.title || chart.title}
      >
        <BarChart
          layout="vertical"
          data={rows}
          accessibilityLayer
          margin={{ left: 0, right: 16 }}
          barGap={3}
          barCategoryGap={14}
        >
          <CartesianGrid horizontal={false} />
          <XAxis
            type="number"
            tickLine={false}
            axisLine={false}
            ticks={
              panel.measure === "change"
                ? [-extent, -extent / 2, 0, extent / 2, extent]
                : undefined
            }
            domain={
              panel.measure === "change"
                ? [-extent, extent]
                : [
                    (v: number) =>
                      chart.scale === "data" ? v : Math.min(0, v),
                    (v: number) =>
                      chart.scale === "data" ? v : Math.max(0, v),
                  ]
            }
            tickFormatter={(v) =>
              new Intl.NumberFormat(locale(), { notation: "compact" }).format(v)
            }
          />
          <YAxis
            dataKey="category"
            type="category"
            width={145}
            interval={0}
            tickLine={false}
            axisLine={false}
            tick={<CategoryTick />}
          />
          <ReferenceLine x={0} stroke="var(--muted-foreground)" />
          <ChartTooltip
            allowEscapeViewBox={{ x: false, y: false }}
            position={{ x: 8 }}
            content={({ active, payload }) =>
              active && payload?.length ? (
                <ReportChartTooltip
                  title={String(payload[0].payload.category)}
                  unit={chart.unit}
                  items={payload
                    .filter((item) => item.value != null)
                    .map((item) => ({
                      label: String(item.name),
                      value: String(item.payload[`${item.dataKey}Exact`]),
                      color: item.color,
                    }))}
                />
              ) : null
            }
          />
          {series.map((s) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.name}
              fill={s.color}
              radius={3}
              maxBarSize={20}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ChartContainer>
    </section>
  );
}
export function DecisionGuidance({
  claim,
}: {
  claim: ReportData["claims"][number];
}) {
  useLanguage();
  const value = claim.orientation;
  if (!value)
    return claim.next_step ? (
      <p className="rounded-lg bg-muted p-3">
        <strong>{tr("Siguiente comprobación:")} </strong>
        {claim.next_step}
      </p>
    ) : null;
  return (
    <div className="mt-4 space-y-3">
      <p className="text-xs text-muted-foreground">
        {value.segment} · {value.period}
      </p>
      {value.signal !== claim.statement && <p>{value.signal}</p>}
      <p>
        <strong>{tr("Por qué merece atención:")} </strong>
        {value.relative_priority}
      </p>
      <div className="grid gap-3 lg:grid-cols-2">
        <div className="space-y-2 rounded-lg bg-muted/50 p-4">
          {value.next_check && (
            <>
              <p className="text-xs font-semibold text-primary">
                {tr("Siguiente comprobación:")}
              </p>
              <p>{value.next_check}</p>
            </>
          )}
          <p className="text-muted-foreground">{value.decision_value}</p>
        </div>
        {value.reactions.length > 0 && (
          <div className="space-y-2 rounded-lg border p-4">
            <p className="text-xs font-semibold">
              {tr("Según lo que encuentres")}
            </p>
            <ul className="divide-y">
              {value.reactions.map((r, i) => (
                <li key={i} className="space-y-1 py-2 first:pt-0 last:pb-0">
                  <p className="font-medium">
                    {/^(si|if)\b/i.test(r.condition.trimStart())
                      ? r.condition +
                        (r.condition.trimEnd().endsWith(":") ? "" : ":")
                      : tr("Si {0}:", { "0": r.condition })}
                  </p>
                  <p className="text-muted-foreground">{r.reaction}</p>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      {value.reaction_summary && (
        <p>
          <strong>{tr("En los casos descritos")}: </strong>
          {value.reaction_summary}
        </p>
      )}
      {value.limitation && (
        <p className="text-muted-foreground">{value.limitation}</p>
      )}
    </div>
  );
}
function navigateToDetail(key: string, chart = false) {
  const target = document.getElementById(
    `${chart ? "chart" : "finding"}-${key}`,
  );
  if (!target) return;
  target.scrollIntoView({ block: "start" });
  const trigger = target.querySelector<HTMLButtonElement>(
    'button[aria-expanded="false"]',
  );
  trigger?.click();
  (trigger ?? target).focus();
}
function ExactValues({ chart }: { chart: ChartData }) {
  if (!chart.panels?.length)
    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Periodo / categoría</TableHead>
            <TableHead className="text-right">{chart.unit}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {chart.points.map((p) => (
            <TableRow key={p.label}>
              <TableCell>{p.label}</TableCell>
              <TableCell className="text-right font-mono">
                {displayNumber(p.formatted)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  return (
    <>
      {chart.panels.map((panel, i) => (
        <Table key={i}>
          <TableHeader>
            <TableRow>
              <TableHead>{panel.category_title}</TableHead>
              {panel.series_order.map((s) => (
                <TableHead key={s} className="text-right">
                  {s}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {groupedPoints(chart, panel)
              .filter((r) => r.category)
              .map((row) => (
                <TableRow key={String(row.category)}>
                  <TableCell>{row.category}</TableCell>
                  {panel.series_order.map((s, j) => (
                    <TableCell key={s} className="text-right font-mono">
                      {String(row[`s${j}Exact`])}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
          </TableBody>
        </Table>
      ))}
    </>
  );
}
function tooltipDetails(chart: ChartData, labels: string[]) {
  return (chart.details ?? [])
    .filter((d) => labels.includes(d.point_label))
    .flatMap((d) =>
      d.values.map((v) => ({
        label: v.label,
        value: `${displayNumber(v.formatted)} ${v.unit}`,
      })),
    );
}
function GroupedLines({
  chart,
  panel,
  onSelect,
}: {
  chart: ChartData;
  panel: ChartPanel;
  onSelect: (label: string) => void;
}) {
  useLanguage();
  const rows = groupedPoints(chart, panel);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [hovered, setHovered] = useState<string | null>(null);
  const [focused, setFocused] = useState<string | null>(null);
  const highlighted =
    [hovered, focused].find((key) => key && !hidden.has(key)) ?? null;
  const series = panel.series_order.map((name, i) => ({
    key: `s${i}`,
    name,
    color: panel.colors?.[name] ?? seriesColor(name),
    style: panel.styles?.[name],
  }));
  return (
    <section aria-label={panel.title || chart.title} className="space-y-3">
      <div
        role="group"
        aria-label={tr("Series: {0}", { "0": panel.series_title })}
        className="flex flex-wrap gap-2"
      >
        {series.map((s) => (
          <button
            type="button"
            key={s.key}
            aria-pressed={!hidden.has(s.key)}
            aria-label={`${s.name} ${hidden.has(s.key) ? tr("Oculta") : tr("Visible")}`}
            disabled={!hidden.has(s.key) && hidden.size === series.length - 1}
            title={
              hidden.has(s.key)
                ? tr("Mostrar {0}", { "0": s.name })
                : hidden.size === series.length - 1
                  ? tr("Debe quedar al menos una serie visible")
                  : tr("Ocultar {0}", { "0": s.name })
            }
            data-highlighted={highlighted === s.key ? "true" : undefined}
            onMouseEnter={() => setHovered(s.key)}
            onMouseLeave={() => setHovered(null)}
            onFocus={(e) => {
              if (e.currentTarget.matches(":focus-visible")) setFocused(s.key);
            }}
            onBlur={() => setFocused(null)}
            className={`inline-flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-xs transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring data-[highlighted=true]:bg-muted disabled:cursor-default motion-reduce:transition-none ${
              hidden.has(s.key) ? "text-muted-foreground" : "text-foreground"
            }`}
            onClick={() =>
              setHidden((previous) => {
                const next = new Set(previous);
                if (next.has(s.key)) next.delete(s.key);
                else next.add(s.key);
                return next;
              })
            }
          >
            <span
              aria-hidden
              className="size-2 shrink-0 rounded-full"
              style={{ backgroundColor: s.color }}
            />
            <span>{s.name}</span>
            {hidden.has(s.key) && <EyeOff aria-hidden className="size-3.5" />}
            <span className="sr-only">
              {" "}
              {hidden.has(s.key) ? tr("Oculta") : tr("Visible")}
            </span>
          </button>
        ))}
      </div>
      <p className="sr-only">
        {tr(
          "Pulsa una serie para ocultarla o mostrarla. Debe quedar al menos una visible.",
        )}
      </p>
      <ChartContainer
        config={Object.fromEntries(
          series.map((s) => [s.key, { label: s.name, color: s.color }]),
        )}
        className="h-72 w-full"
        style={{ containerType: "inline-size" }}
      >
        <LineChart
          onClick={(state) => {
            const row = rows[Number(state.activeTooltipIndex)];
            if (row?.category) onSelect(String(row.category));
          }}
          data={rows}
          accessibilityLayer
          margin={{ left: 0, right: 24, top: 12, bottom: 12 }}
        >
          <CartesianGrid vertical={false} />
          <XAxis
            dataKey="axis"
            padding={{ left: 12, right: 12 }}
            interval="preserveStartEnd"
            tick={{ fontSize: 11 }}
            type="number"
            domain={["dataMin", "dataMax"]}
            ticks={rows.filter((r) => r.category).map((r) => Number(r.axis))}
            tickFormatter={(axis) =>
              periodLabel(
                String(rows.find((r) => r.axis === axis)?.category ?? ""),
                panel.temporal_grain ?? undefined,
              )
            }
            minTickGap={32}
          />
          <YAxis
            width={64}
            domain={[
              (v: number) => (chart.scale === "data" ? v : Math.min(0, v)),
              (v: number) => (chart.scale === "data" ? v : Math.max(0, v)),
            ]}
            tickFormatter={(v) =>
              new Intl.NumberFormat(locale(), { notation: "compact" }).format(v)
            }
          />
          <ChartTooltip
            allowEscapeViewBox={{ x: false, y: false }}
            position={{ x: 8 }}
            content={({ active, payload }) =>
              active && payload?.length ? (
                <ReportChartTooltip
                  title={periodLabel(
                    String(payload[0].payload.category),
                    panel.temporal_grain ?? undefined,
                  )}
                  unit={chart.unit}
                  items={[
                    ...series
                      .filter((s) => payload[0].payload[s.key] != null)
                      .map((s) => ({
                        label:
                          s.name + (hidden.has(s.key) ? tr(" (oculta)") : ""),
                        value: String(payload[0].payload[`${s.key}Exact`]),
                        color: s.color,
                      })),
                    ...tooltipDetails(
                      chart,
                      panel.coordinates
                        .filter(
                          (c) => c.category === payload[0].payload.category,
                        )
                        .map((c) => c.label),
                    ),
                  ]}
                />
              ) : null
            }
          />
          {series.map((s) => (
            <Line
              key={s.key}
              dataKey={s.key}
              hide={hidden.has(s.key)}
              stroke={
                highlighted === s.key
                  ? `color-mix(in srgb, ${s.color} 70%, var(--foreground))`
                  : s.color
              }
              strokeWidth={
                highlighted === s.key
                  ? 3
                  : s.style?.weight === "emphasis"
                    ? 2.8
                    : 1.5
              }
              strokeDasharray={
                s.style?.style === "dashed"
                  ? "6 4"
                  : s.style?.style === "dotted"
                    ? "2 3"
                    : undefined
              }
              strokeOpacity={highlighted && highlighted !== s.key ? 0.35 : 1}
              onMouseEnter={() => setHovered(s.key)}
              onMouseLeave={() => setHovered(null)}
              type="linear"
              connectNulls={false}
              dot={{
                r: 3,
                opacity: highlighted && highlighted !== s.key ? 0.35 : 1,
                onMouseEnter: () => setHovered(s.key),
                onMouseLeave: () => setHovered(null),
              }}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ChartContainer>
    </section>
  );
}
function CategoryTick({
  x,
  y,
  payload,
}: {
  x?: string | number;
  y?: string | number;
  payload?: { value: string };
}) {
  const label = String(payload?.value ?? "");
  const lines = categoryLabelLines(label);
  return (
    <text
      x={x}
      y={y}
      textAnchor="end"
      fill="var(--muted-foreground)"
      fontSize={11}
      aria-label={label}
    >
      {lines.map((line, i) => (
        <tspan key={i} x={x} dy={i === 0 ? -(lines.length - 1) * 7 + 4 : 14}>
          {line}
        </tspan>
      ))}
    </text>
  );
}

export function EvidenceChart({
  chart,
  actions,
  footer,
  sourceHref,
  embedded = false,
  lead,
}: {
  chart: ChartData;
  actions?: ReactNode;
  footer?: ReactNode;
  sourceHref?: string;
  embedded?: boolean;
  lead?: ReactNode;
}) {
  useLanguage();
  const [selected, setSelected] = useState("");
  const periods = chart.panels?.length
    ? [
        ...new Set(
          chart.panels.flatMap((p) => p.coordinates.map((c) => c.category)),
        ),
      ]
    : chart.points.map((p) => p.label);
  const selectedLabels = chart.panels?.length
    ? chart.panels.flatMap((p) =>
        p.coordinates
          .filter((c) => c.category === selected)
          .map((c) => c.label),
      )
    : [selected];
  const detail =
    chart.details?.filter((d) => selectedLabels.includes(d.point_label)) ?? [];
  const bars = chart.kind === "bar";
  const temporal = chart.kind === "line";
  const displayPeriod = (label: string) =>
    temporal
      ? periodLabel(
          label,
          chart.panels?.find((p) =>
            p.coordinates.some((c) => c.category === label),
          )?.temporal_grain ??
            chart.temporal_grain ??
            undefined,
        )
      : label;
  const points = chartPoints(chart);
  const axes = (
    <>
      <CartesianGrid vertical={bars} horizontal={!bars} />
      <XAxis
        padding={!bars ? { left: 12, right: 12 } : undefined}
        interval={!bars ? "preserveStartEnd" : undefined}
        dataKey={bars ? "value" : "axis"}
        ticks={
          temporal
            ? chart.points.map((p) =>
                periodAxis(p.label, chart.temporal_grain ?? undefined),
              )
            : undefined
        }
        type={bars || temporal ? "number" : "category"}
        domain={
          bars
            ? [
                (minimum: number) =>
                  chart.scale === "data" ? minimum : Math.min(0, minimum),
                (maximum: number) =>
                  chart.scale === "data" ? maximum : Math.max(0, maximum),
              ]
            : temporal
              ? ["dataMin", "dataMax"]
              : undefined
        }
        tickFormatter={(v) =>
          bars
            ? new Intl.NumberFormat(locale(), { notation: "compact" }).format(v)
            : temporal
              ? displayPeriod(
                  String(
                    chart.points.find(
                      (p) =>
                        periodAxis(
                          p.label,
                          chart.temporal_grain ?? undefined,
                        ) === v,
                    )?.label ?? "",
                  ),
                )
              : String(v)
        }
        tickLine={false}
        axisLine={false}
        minTickGap={32}
      />
      <YAxis
        width={bars ? 136 : 64}
        dataKey={bars ? "axis" : undefined}
        type={bars ? "category" : "number"}
        interval={bars ? 0 : undefined}
        domain={
          bars
            ? undefined
            : [
                (minimum: number) =>
                  chart.scale === "data" ? minimum : Math.min(0, minimum),
                (maximum: number) =>
                  chart.scale === "data" ? maximum : Math.max(0, maximum),
              ]
        }
        tickLine={false}
        axisLine={false}
        tick={bars ? <CategoryTick /> : undefined}
        tickFormatter={
          bars
            ? undefined
            : (v) =>
                new Intl.NumberFormat(locale(), { notation: "compact" }).format(
                  v,
                )
        }
      />
      <ReferenceLine {...(bars ? { x: 0 } : { y: 0 })} stroke="var(--border)" />
      <ChartTooltip
        allowEscapeViewBox={{ x: false, y: false }}
        position={{ x: 8 }}
        content={({ active, payload }) =>
          active && payload?.length ? (
            <ReportChartTooltip
              title={displayPeriod(String(payload[0].payload.label))}
              unit={chart.unit}
              items={[
                ...payload
                  .filter((item) => item.value != null)
                  .map((item) => ({
                    label: tr("Valor"),
                    value: displayNumber(String(item.payload.formatted)),
                    color: item.color,
                  })),
                ...tooltipDetails(chart, [String(payload[0].payload.label)]),
              ]}
            />
          ) : null
        }
      />
    </>
  );
  return (
    <Card
      id={`chart-${chart.key}`}
      tabIndex={-1}
      className={
        embedded ? "gap-3 rounded-none py-0 shadow-none ring-0" : "shadow-none"
      }
    >
      <CardHeader className={embedded ? "px-0" : undefined}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-2">
            <CardTitle>{chart.title}</CardTitle>
            <CardDescription>{chart.unit}</CardDescription>
            {chart.unit_origin === "owner" && (
              <p className="text-xs text-muted-foreground">
                {tr("Unidad visible indicada por ti. Unidad del análisis:")}{" "}
                {chart.original_unit}.
              </p>
            )}
          </div>
          {actions}
        </div>
      </CardHeader>
      <CardContent className={embedded ? "px-0" : undefined}>
        {lead}
        {chart.kind === "line" &&
          Boolean(chart.panels?.length) &&
          chart.panels!.map((panel, i) => (
            <GroupedLines
              key={i}
              chart={chart}
              panel={panel}
              onSelect={setSelected}
            />
          ))}
        {chart.kind === "bar" && Boolean(chart.panels?.length) && (
          <div className="space-y-8">
            {chart.panels!.map((panel, i) => (
              <GroupedBars key={i} chart={chart} panel={panel} />
            ))}
          </div>
        )}
        {chart.kind !== "table" && !chart.panels?.length && (
          <ChartContainer
            config={{
              value: { ...config.value, label: tr(config.value.label) },
            }}
            className="w-full"
            style={{
              containerType: "inline-size",
              height: bars
                ? Math.max(
                    256,
                    chart.points.length *
                      categoryRowHeight(chart.points.map((p) => p.label)) +
                      32,
                  )
                : 256,
            }}
            aria-label={chart.title}
          >
            {chart.kind === "line" ? (
              <LineChart
                onClick={(state) => {
                  const point = points[Number(state.activeTooltipIndex)];
                  if (point?.label) setSelected(point.label);
                }}
                accessibilityLayer
                data={points}
                margin={{ left: 0, right: 24, top: 12, bottom: 12 }}
              >
                {axes}
                <Line
                  dataKey="value"
                  type="linear"
                  stroke="var(--color-value)"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              </LineChart>
            ) : (
              <BarChart
                layout="vertical"
                accessibilityLayer
                data={points}
                margin={{ left: 0, right: 12 }}
              >
                {axes}
                <Bar
                  dataKey="value"
                  fill="var(--color-value)"
                  radius={4}
                  isAnimationActive={false}
                />
              </BarChart>
            )}
          </ChartContainer>
        )}
        <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
          {chart.caption}
        </p>
        {(!embedded || chart.kind === "table") && <ChartValues chart={chart} />}
        {Boolean(chart.details?.length) && (
          <Disclosure title={tr("Ver desglose por periodo")}>
            <div className="space-y-3">
              <label className="flex flex-wrap items-center gap-2 text-xs">
                {tr("Ver periodo o categoría")}
                <select
                  aria-label={tr("Periodo o categoría de {0}", {
                    "0": chart.title,
                  })}
                  value={selected}
                  onChange={(e) => setSelected(e.target.value)}
                  className="max-w-full rounded border bg-background px-3 py-2 text-foreground focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value="">
                    {tr("Elige un periodo con desglose")}
                  </option>
                  {periods.map((p) => (
                    <option value={p} key={p}>
                      {displayPeriod(p)}
                    </option>
                  ))}
                </select>
              </label>
              {selected && (
                <div
                  aria-live="polite"
                  className="space-y-2 rounded-lg bg-muted p-3 text-sm"
                >
                  <strong>{displayPeriod(selected)}</strong>
                  {chart.points
                    .filter((p) => selectedLabels.includes(p.label))
                    .map((p) => (
                      <p key={p.label}>
                        {chart.panels
                          ?.flatMap((panel) => panel.coordinates)
                          .find((c) => c.label === p.label)?.series ?? p.label}
                        : {displayNumber(p.formatted)} {chart.unit}
                      </p>
                    ))}
                  {detail
                    .flatMap((d) => d.values)
                    .map((v, i) => (
                      <p key={i}>
                        {v.label}: {displayNumber(v.formatted)} {v.unit}
                      </p>
                    ))}
                  {sourceHref ? (
                    <a href={sourceHref} className="text-primary underline">
                      {tr("Ver hallazgo y detalle en el informe")}
                    </a>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="text-primary underline focus-visible:ring-2 focus-visible:ring-ring"
                        onClick={() =>
                          navigateToDetail(
                            detail.find((d) => d.claim_key)?.claim_key ??
                              chart.claim_key,
                          )
                        }
                      >
                        {tr("Ver hallazgo y siguiente comprobación")}
                      </button>
                      {detail
                        .filter((d) => d.detail_chart_key)
                        .map((d) => (
                          <button
                            type="button"
                            key={d.point_label}
                            className="ml-3 text-primary underline focus-visible:ring-2 focus-visible:ring-ring"
                            onClick={() =>
                              navigateToDetail(d.detail_chart_key!, true)
                            }
                          >
                            {tr("Ver desglose de este punto")}
                          </button>
                        ))}
                    </>
                  )}
                </div>
              )}
            </div>
          </Disclosure>
        )}
        {footer}
      </CardContent>
    </Card>
  );
}
export function ChartValues({
  chart,
  inline = false,
}: {
  chart: ChartData;
  inline?: boolean;
}) {
  useLanguage();
  if (chart.owner_presentation && chart.kind !== "table") return null;
  const values = (
    <>
      {chart.unit_origin === "owner" && (
        <p className="mb-3 text-xs text-muted-foreground">
          {tr("Unidad visible indicada por ti. Unidad del análisis:")}{" "}
          {chart.original_unit}.
        </p>
      )}
      {chart.panels?.length ? (
        <ExactValues chart={chart} />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="whitespace-normal">
                {tr("Periodo / categoría")}
              </TableHead>
              {!chart.owner_presentation &&
                chart.points.some(
                  (p) => p.original_label && p.original_label !== p.label,
                ) && <TableHead>{tr("Código original")}</TableHead>}
              <TableHead className="text-right whitespace-normal">
                {chart.unit}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {chart.points.map((p, i) => (
              <TableRow key={i}>
                <TableCell>{p.label}</TableCell>
                {!chart.owner_presentation &&
                  chart.points.some(
                    (x) => x.original_label && x.original_label !== x.label,
                  ) && (
                    <TableCell className="font-mono text-xs">
                      {p.original_label || p.label}
                    </TableCell>
                  )}
                <TableCell className="text-right font-mono tabular-nums">
                  {displayNumber(p.formatted)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </>
  );
  return inline ? (
    <div className="overflow-x-auto">{values}</div>
  ) : (
    <div className="mt-4">
      <Disclosure
        title={tr("Ver valores exactos")}
        defaultOpen={chart.kind === "table"}
      >
        {values}
      </Disclosure>
    </div>
  );
}

export function ReportView({
  report,
  compact = false,
}: {
  report: ReportData;
  compact?: boolean;
}) {
  useLanguage();
  const root = useRef<HTMLDivElement>(null);
  const target = findingTarget(location.hash);
  const matchingTarget =
    target &&
    target.reportId === report.report_id &&
    target.version === report.report_version;
  const targetExists =
    matchingTarget && report.claims.some((claim) => claim.key === target.key);
  const targetKey = target?.key;
  useEffect(() => {
    if (!compact && targetExists && targetKey) {
      const finding = Array.from(
        root.current?.querySelectorAll<HTMLElement>("[id]") ?? [],
      ).find((element) => element.id === `finding-${targetKey}`);
      finding?.scrollIntoView?.({ block: "start" });
      finding?.focus();
    }
  }, [compact, targetExists, targetKey]);
  const edit = (
    kind: "report" | "metric" | "chart" | "insight",
    key: string,
    title: string,
  ) =>
    !compact && report.presentation ? (
      <PresentationEditor
        presentation={report.presentation}
        target={{ kind, key, title }}
      />
    ) : null;
  const item = (
    kind: "chart" | "metric" | "insight" | "section",
    key: string,
    content: NonNullable<ContextAttachment["content"]>,
  ): ContextAttachment | undefined =>
    report.report_id && report.report_version && !compact
      ? {
          report_id: report.report_id,
          report_version: report.report_version,
          kind,
          element_key: key,
          title:
            "title" in content
              ? content.title
              : "label" in content
                ? content.label
                : key,
          period: report.scope.period,
          report_title: report.title,
          href: location.hash,
          content,
        }
      : undefined;
  const files = [
    ...new Set(
      report.claims.flatMap((claim) => claim.evidence_details?.files ?? []),
    ),
  ];
  const limitations = report.limitations.length > 0 && (
    <Selectable
      item={item("section", "limitations", {
        key: "limitations",
        title: tr("Limitaciones"),
        statement: report.limitations.join("\n"),
      })}
    >
      <div className="rounded-xl border-l-2 border-primary/30 bg-muted/40 px-4 py-3 text-xs leading-6">
        <p className="font-medium">{tr("Para interpretar este informe")}</p>
        <ul className="list-disc pl-4">
          {report.limitations.map((text, i) => (
            <li key={i}>{text}</li>
          ))}
        </ul>
      </div>
    </Selectable>
  );
  const metrics = (highlights: ReportData["highlights"]) => (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {highlights.map((h, i) => (
        <Selectable
          key={h.key || i}
          item={h.key ? item("metric", h.key, h) : undefined}
        >
          <Card className="shadow-none">
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between gap-2">
                <CardDescription>{h.label}</CardDescription>
                {h.key && edit("metric", h.key, h.label)}
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold tracking-tight tabular-nums">
                {displayNumber(h.value)}
                <span className="mt-2 block text-xs font-normal tracking-normal text-muted-foreground">
                  {h.unit}
                </span>
              </p>
            </CardContent>
          </Card>
        </Selectable>
      ))}{" "}
    </div>
  );
  return (
    <div ref={root} className="space-y-6">
      <div>
        <div className="mb-3 flex flex-wrap gap-2">
          <Badge
            variant="outline"
            className="h-auto max-w-full whitespace-normal break-words"
          >
            {report.scope.period}
          </Badge>
          <Badge variant="secondary">{tr("Revisado")}</Badge>
          {report.partial && !report.owner_presentation && (
            <Badge variant="outline">{tr("Entrega parcial")}</Badge>
          )}
          {report.presentation && report.presentation.revision > 0 && (
            <Badge variant="outline">
              {tr("Presentación · v")}
              {report.presentation.revision}
            </Badge>
          )}
          {edit("report", "title", tr("título del informe"))}
        </div>
        <h2
          className={
            compact
              ? "text-xl font-semibold tracking-tight"
              : "text-2xl font-semibold tracking-tight"
          }
        >
          {report.title}
        </h2>
        {report.summary && (
          <div className="mt-3 max-w-3xl text-sm leading-7 text-muted-foreground">
            <Selectable
              item={item("section", "summary", {
                key: "summary",
                title: tr("Resumen"),
                statement: report.summary,
              })}
            >
              <p>{report.summary}</p>
            </Selectable>
          </div>
        )}
        {report.claims.length > 1 && (
          <nav aria-label={tr("En este informe")} className="mt-4">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              {tr("En este informe")}
            </p>
            <ol className="flex flex-wrap gap-2">
              {report.claims.map((claim, i) => (
                <li key={claim.key} className="max-w-full">
                  <button
                    type="button"
                    className="flex max-w-full items-baseline gap-2 rounded-lg border px-3 py-2 text-left text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    onClick={() => {
                      const finding = Array.from(
                        root.current?.querySelectorAll<HTMLElement>("[id]") ??
                          [],
                      ).find(
                        (element) => element.id === `finding-${claim.key}`,
                      );
                      finding?.scrollIntoView?.({ block: "start" });
                      finding?.focus();
                    }}
                  >
                    <span
                      aria-hidden
                      className="shrink-0 text-xs tabular-nums text-muted-foreground"
                    >
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="min-w-0 break-words">{claim.title}</span>
                  </button>
                </li>
              ))}
            </ol>
          </nav>
        )}
        <div className="mt-3 max-w-3xl">
          <Disclosure title={tr("Sobre este informe")} subtle>
            {report.scope.business && <p>{report.scope.business}</p>}
            {report.scope.question && (
              <p>
                <strong>{tr("Pregunta: ")}</strong>
                {report.scope.question}
              </p>
            )}
            <Selectable
              item={item("section", "scope", {
                key: "scope",
                title: tr("Alcance"),
                statement: report.scope.coverage,
              })}
            >
              <p>{report.scope.coverage}</p>
            </Selectable>
            {files.length > 0 && (
              <p>
                <strong>{tr("Archivos: ")}</strong>
                {files.join(" · ")}
              </p>
            )}
          </Disclosure>
        </div>
      </div>
      {!compact && target && !targetExists && (
        <p role="status" className="rounded-xl bg-muted p-4 text-sm">
          {tr(
            "El hallazgo enlazado pertenece a otra revisión o ya no está disponible. Se muestra el informe disponible; no se ha sustituido la referencia del chat.",
          )}
        </p>
      )}
      {!report.owner_presentation && limitations}
      {metrics(report.highlights.slice(0, 3))}
      {report.highlights.length > 3 && (
        <Disclosure title={tr("Más indicadores del informe")}>
          {metrics(report.highlights.slice(3))}
        </Disclosure>
      )}
      {!report.charts?.length && report.no_chart_reason && (
        <p className="text-sm text-muted-foreground">
          {report.no_chart_reason}
        </p>
      )}
      <div className="space-y-4">
        {report.claims.map((claim, i) => (
          <section key={claim.key}>
            <ReportSection
              key={`${report.report_id}:${report.report_version}:${claim.key}`}
              id={`finding-${claim.key}`}
              title={claim.title}
              hasDetails={Boolean(
                claim.interpretation ||
                claim.source_summary ||
                (!report.owner_presentation &&
                  (claim.method || claim.evidence_details)) ||
                report.charts?.some(
                  (c) => c.claim_key === claim.key && c.kind !== "table",
                ),
              )}
              number={String(i + 1).padStart(2, "0")}
              actions={edit("insight", claim.key, claim.title)}
              defaultOpen={Boolean(
                !compact && targetExists && target?.key === claim.key,
              )}
              lead={
                <Selectable item={item("insight", claim.key, claim)}>
                  <p className="text-muted-foreground">{claim.statement}</p>
                  <DecisionGuidance claim={claim} />
                </Selectable>
              }
              visual={report.charts
                ?.filter((c) => c.claim_key === claim.key)
                .map((c) => (
                  <Selectable key={c.key} item={item("chart", c.key, c)}>
                    <EvidenceChart
                      chart={c}
                      embedded
                      actions={edit("chart", c.key, c.title)}
                    />
                  </Selectable>
                ))}
            >
              {claim.interpretation && (
                <p className="text-muted-foreground">{claim.interpretation}</p>
              )}
              {report.owner_presentation && claim.source_summary && (
                <p className="text-sm text-muted-foreground">
                  {claim.source_summary}
                </p>
              )}
              {!report.owner_presentation && claim.method && (
                <div className="space-y-2">
                  <h4 className="text-xs font-medium text-muted-foreground">
                    {tr("Base del análisis")}
                  </h4>
                  <p>{claim.method}</p>
                </div>
              )}
              {!report.owner_presentation && claim.evidence_details && (
                <div className="space-y-2">
                  <h4 className="text-xs font-medium text-muted-foreground">
                    {tr("Fuentes y evidencia")}
                  </h4>
                  <p>{claim.evidence_details.files.join(" · ")}</p>
                  {claim.evidence_details.metrics.map((m, j) => (
                    <p key={j} className="font-mono text-xs">
                      {m.label}: {m.value}
                    </p>
                  ))}
                  {claim.evidence_details.operations.map((o, j) => (
                    <p key={j}>{o}</p>
                  ))}
                </div>
              )}
              {report.charts
                ?.filter(
                  (c) =>
                    !report.owner_presentation &&
                    c.claim_key === claim.key &&
                    c.kind !== "table",
                )
                .map((c) => (
                  <div key={c.key}>
                    <h4 className="font-medium">{c.title}</h4>
                    <ChartValues chart={c} inline />
                  </div>
                ))}
            </ReportSection>
          </section>
        ))}
      </div>
      {report.charts
        ?.filter(
          (c) => !report.claims.some((claim) => claim.key === c.claim_key),
        )
        .map((c) => (
          <Selectable key={c.key} item={item("chart", c.key, c)}>
            <EvidenceChart chart={c} actions={edit("chart", c.key, c.title)} />
          </Selectable>
        ))}
      {report.owner_presentation && limitations}
    </div>
  );
}
