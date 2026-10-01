import { useState, type ReactNode } from "react";
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
import { ArrowUpRight } from "lucide-react";
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
import {
  Sources,
  SourcesTrigger,
  SourcesContent,
} from "@/components/ai-elements/sources";
import { Selectable } from "./context-selection";
import { Disclosure } from "./shared";
import {
  CHART_PALETTE,
  groupedPoints,
  seriesColor,
  chartPoints,
  periodAxis,
} from "@/lib/charts";
import { ReportSection, reportLead } from "./report-section";
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
        aria-label={`Leyenda: ${panel.series_title}`}
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
      <ChartContainer
        config={Object.fromEntries(
          series.map((s) => [s.key, { label: s.name, color: s.color }]),
        )}
        className="w-full"
        style={{
          containerType: "inline-size",
          height: Math.max(240, rows.length * (series.length * 22 + 28) + 32),
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
              new Intl.NumberFormat("es", { notation: "compact" }).format(v)
            }
          />
          <YAxis
            dataKey="category"
            type="category"
            width={145}
            interval={0}
            tickLine={false}
            axisLine={false}
            tick={({ x, y, payload }) => (
              <g transform={`translate(${x},${y})`}>
                <foreignObject x={-140} y={-26} width={132} height={52}>
                  <div className="flex h-full items-center justify-end text-right text-xs leading-tight text-muted-foreground break-words">
                    {payload.value}
                  </div>
                </foreignObject>
              </g>
            )}
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
  const value = claim.orientation;
  if (!value)
    return claim.next_step ? (
      <p className="rounded-lg bg-muted p-3">
        <strong>Siguiente comprobación: </strong>
        {claim.next_step}
      </p>
    ) : null;
  return (
    <div className="space-y-3 border-l-2 border-primary/40 pl-4">
      <p className="text-xs text-muted-foreground">
        {value.segment} · {value.period}
      </p>
      {value.signal !== claim.statement && <p>{value.signal}</p>}
      <p>
        <strong>Por qué merece atención: </strong>
        {value.relative_priority}
      </p>
      {value.next_check && (
        <p>
          <strong>Siguiente comprobación: </strong>
          {value.next_check}
        </p>
      )}
      <p className="text-muted-foreground">{value.decision_value}</p>
      {value.reactions.map((r, i) => (
        <p key={i}>
          <strong>Si {r.condition}: </strong>
          {r.reaction}
        </p>
      ))}
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
                {p.formatted}
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
        value: `${v.formatted} ${v.unit}`,
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
  const rows = groupedPoints(chart, panel);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const series = panel.series_order.map((name, i) => ({
    key: `s${i}`,
    name,
    color: panel.colors?.[name] ?? seriesColor(name),
  }));
  return (
    <section aria-label={panel.title || chart.title} className="space-y-3">
      <div
        role="group"
        aria-label={`Series: ${panel.series_title}`}
        className="flex flex-wrap gap-2"
      >
        {series.map((s) => (
          <button
            type="button"
            key={s.key}
            aria-pressed={!hidden.has(s.key)}
            disabled={!hidden.has(s.key) && hidden.size === series.length - 1}
            className="rounded border px-3 py-2 text-xs focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() =>
              setHidden((previous) => {
                const next = new Set(previous);
                if (next.has(s.key)) next.delete(s.key);
                else next.add(s.key);
                return next;
              })
            }
          >
            <span aria-hidden style={{ color: s.color }}>
              ●{" "}
            </span>
            {s.name}
          </button>
        ))}
      </div>
      <ChartContainer
        config={Object.fromEntries(
          series.map((s) => [s.key, { label: s.name, color: s.color }]),
        )}
        className="h-72 w-full"
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
              String(rows.find((r) => r.axis === axis)?.category ?? "")
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
              new Intl.NumberFormat("es", { notation: "compact" }).format(v)
            }
          />
          <ChartTooltip
            content={({ active, payload }) =>
              active && payload?.length ? (
                <ReportChartTooltip
                  title={String(payload[0].payload.category)}
                  unit={chart.unit}
                  items={[
                    ...series
                      .filter((s) => payload[0].payload[s.key] != null)
                      .map((s) => ({
                        label: s.name + (hidden.has(s.key) ? " (oculta)" : ""),
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
              stroke={s.color}
              type="linear"
              connectNulls={false}
              dot={{ r: 3 }}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ChartContainer>
    </section>
  );
}
export function EvidenceChart({
  chart,
  actions,
  footer,
  sourceHref,
}: {
  chart: ChartData;
  actions?: ReactNode;
  footer?: ReactNode;
  sourceHref?: string;
}) {
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
            ? new Intl.NumberFormat("es", { notation: "compact" }).format(v)
            : temporal
              ? String(
                  chart.points.find(
                    (p) =>
                      periodAxis(p.label, chart.temporal_grain ?? undefined) ===
                      v,
                  )?.label ?? "",
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
        tickFormatter={(v) =>
          bars
            ? String(v).length > 21
              ? String(v).slice(0, 20) + "…"
              : String(v)
            : new Intl.NumberFormat("es", { notation: "compact" }).format(v)
        }
      />
      <ReferenceLine {...(bars ? { x: 0 } : { y: 0 })} stroke="var(--border)" />
      <ChartTooltip
        allowEscapeViewBox={{ x: false, y: false }}
        position={{ x: 8 }}
        content={({ active, payload }) =>
          active && payload?.length ? (
            <ReportChartTooltip
              title={String(payload[0].payload.label)}
              unit={chart.unit}
              items={[
                ...payload
                  .filter((item) => item.value != null)
                  .map((item) => ({
                    label: "Valor",
                    value: String(item.payload.formatted),
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
    <Card id={`chart-${chart.key}`} tabIndex={-1} className="shadow-none">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-2">
            <CardTitle>{chart.title}</CardTitle>
            <CardDescription>{chart.unit}</CardDescription>
          </div>
          {actions}
        </div>
      </CardHeader>
      <CardContent>
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
            config={config}
            className="w-full"
            style={{
              containerType: "inline-size",
              height: bars ? Math.max(256, chart.points.length * 36) : 256,
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
                margin={{ left: 0, right: 12 }}
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
        <div className="mt-4">
          <Disclosure
            title="Ver valores exactos"
            defaultOpen={chart.kind === "table"}
          >
            <ExactValues chart={chart} />
          </Disclosure>
        </div>
        <div className="mt-4 space-y-3">
          <label className="flex flex-wrap items-center gap-2 text-xs">
            Ver periodo o categoría
            <select
              aria-label={`Periodo o categoría de ${chart.title}`}
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="max-w-full rounded border bg-background px-3 py-2 text-foreground focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="">Selecciona un punto</option>
              {periods.map((p) => (
                <option value={p} key={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          {selected && (
            <div
              aria-live="polite"
              className="space-y-2 rounded-lg bg-muted p-3 text-sm"
            >
              <strong>{selected}</strong>
              {chart.points
                .filter((p) => selectedLabels.includes(p.label))
                .map((p) => (
                  <p key={p.label}>
                    {chart.panels
                      ?.flatMap((panel) => panel.coordinates)
                      .find((c) => c.label === p.label)?.series ?? p.label}
                    : {p.formatted} {chart.unit}
                  </p>
                ))}
              {detail
                .flatMap((d) => d.values)
                .map((v, i) => (
                  <p key={i}>
                    {v.label}: {v.formatted} {v.unit}
                  </p>
                ))}
              {sourceHref ? (
                <a href={sourceHref} className="text-primary underline">
                  Ver hallazgo y detalle en el informe
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
                    Ver hallazgo y siguiente comprobación
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
                        Ver desglose de este punto
                      </button>
                    ))}
                </>
              )}
            </div>
          )}
        </div>
        {footer}
      </CardContent>
    </Card>
  );
}
export function ReportView({
  report,
  compact = false,
}: {
  report: ReportData;
  compact?: boolean;
}) {
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
  return (
    <div className="space-y-6">
      <div>
        <div className="mb-3 flex flex-wrap gap-2">
          <Badge variant="outline">{report.scope.period}</Badge>
          <Badge variant="secondary">Revisado</Badge>
          {report.partial && <Badge variant="outline">Entrega parcial</Badge>}
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
          <Selectable
            item={item("section", "summary", {
              key: "summary",
              title: "Resumen",
              statement: report.summary,
            })}
          >
            <p className="mt-3 max-w-3xl text-sm leading-7 text-muted-foreground">
              {reportLead(report.summary)}
            </p>
          </Selectable>
        )}
      </div>
      {report.highlights?.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {report.highlights.map((h, i) => (
            <Selectable
              key={h.key || i}
              item={h.key ? item("metric", h.key, h) : undefined}
            >
              <Card className="shadow-none">
                <CardHeader className="pb-2">
                  <CardDescription>{h.label}</CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-semibold tracking-tight tabular-nums">
                    {h.value}
                    <span className="mt-2 block text-xs font-normal tracking-normal text-muted-foreground">
                      {h.unit}
                    </span>
                  </p>
                </CardContent>
              </Card>
            </Selectable>
          ))}
        </div>
      )}
      <ReportSection
        title="Contexto y alcance"
        preview="Sobre el negocio, los datos y el objetivo del análisis"
      >
        {report.summary && <p>{report.summary}</p>}
        <Selectable
          item={item("section", "scope", {
            key: "scope",
            title: "Alcance",
            statement: report.scope.coverage,
          })}
        >
          <p className="text-muted-foreground">{report.scope.coverage}</p>
        </Selectable>
        {report.scope.question && (
          <p>
            <strong>Pregunta: </strong>
            {report.scope.question}
          </p>
        )}
        {report.limitations.length > 0 && (
          <Selectable
            item={item("section", "limitations", {
              key: "limitations",
              title: "Limitaciones",
              statement: report.limitations.join("\n"),
            })}
          >
            <h3 className="font-medium">Limitaciones</h3>
            <ul className="list-disc space-y-2 pl-5 text-muted-foreground">
              {report.limitations.map((l, i) => (
                <li key={i}>{l}</li>
              ))}
            </ul>
          </Selectable>
        )}
      </ReportSection>
      {!report.charts?.length && report.no_chart_reason && (
        <p className="text-sm text-muted-foreground">
          {report.no_chart_reason}
        </p>
      )}
      <div className="space-y-4">
        {report.claims.map((claim, i) => (
          <section key={claim.key} className="space-y-4">
            <Selectable item={item("insight", claim.key, claim)}>
              <ReportSection
                id={`finding-${claim.key}`}
                title={claim.title}
                number={String(i + 1).padStart(2, "0")}
                preview={reportLead(claim.statement)}
                lead={<DecisionGuidance claim={claim} />}
              >
                <p>{claim.statement}</p>
                {claim.interpretation && (
                  <p className="text-muted-foreground">
                    {claim.interpretation}
                  </p>
                )}
                {claim.method && (
                  <Disclosure title="Cómo se ha calculado">
                    <p>{claim.method}</p>
                  </Disclosure>
                )}
                {claim.evidence_details && (
                  <Sources>
                    <SourcesTrigger count={claim.evidence_details.files.length}>
                      <span>Fuentes y evidencia</span>
                      <ArrowUpRight className="size-4" />
                    </SourcesTrigger>
                    <SourcesContent>
                      <div className="rounded-lg border p-4 space-y-3">
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
                    </SourcesContent>
                  </Sources>
                )}
              </ReportSection>
            </Selectable>
            <div className="grid gap-5">
              {report.charts
                ?.filter((c) => c.claim_key === claim.key)
                .map((c) => (
                  <Selectable key={c.key} item={item("chart", c.key, c)}>
                    <EvidenceChart chart={c} />
                  </Selectable>
                ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
