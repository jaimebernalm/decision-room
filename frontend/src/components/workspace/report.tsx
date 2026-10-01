import { displayNumber } from "@/lib/presentation";
import { translate as tr, useLanguage, locale } from "@/lib/i18n";
import type { ReactNode } from "react";
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
} from "@/lib/charts";
import { PresentationEditor } from "./presentation-editor";
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
                : [(v: number) => Math.min(0, v), (v: number) => Math.max(0, v)]
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
            tick={({ x, y, payload }) => (
              <g transform={`translate(${x},${y})`}>
                <foreignObject x={-140} y={-26} width={132} height={52}>
                  <div className="flex h-full items-center justify-end text-right text-xs leading-tight text-muted-foreground break-words">
                    {displayNumber(payload.value)}
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
export function EvidenceChart({
  chart,
  actions,
  footer,
}: {
  chart: ChartData;
  actions?: ReactNode;
  footer?: ReactNode;
}) {
  useLanguage();
  const bars = chart.kind === "bar";
  const temporal =
    chart.kind === "line" &&
    chart.points.every(
      (p) =>
        /^\d{4}-\d{2}-\d{2}/.test(p.label) &&
        Number.isFinite(Date.parse(p.label)),
    );
  const points = chartPoints(chart);
  const axes = (
    <>
      <CartesianGrid vertical={bars} horizontal={!bars} />
      <XAxis
        dataKey={bars ? "value" : "axis"}
        ticks={
          temporal ? chart.points.map((p) => Date.parse(p.label)) : undefined
        }
        type={bars || temporal ? "number" : "category"}
        domain={
          bars
            ? [
                (minimum: number) => Math.min(0, minimum),
                (maximum: number) => Math.max(0, maximum),
              ]
            : temporal
              ? ["dataMin", "dataMax"]
              : undefined
        }
        tickFormatter={(v) =>
          bars
            ? new Intl.NumberFormat(locale(), { notation: "compact" }).format(v)
            : temporal
              ? new Date(v).toLocaleDateString(locale(), {
                  month: "short",
                  day: "numeric",
                  timeZone: "UTC",
                })
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
                (minimum: number) => Math.min(0, minimum),
                (maximum: number) => Math.max(0, maximum),
              ]
        }
        tickLine={false}
        axisLine={false}
        tickFormatter={(v) =>
          bars
            ? String(v).length > 21
              ? String(v).slice(0, 20) + "…"
              : String(v)
            : new Intl.NumberFormat(locale(), { notation: "compact" }).format(v)
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
              items={payload
                .filter((item) => item.value != null)
                .map((item) => ({
                  label: tr("Valor"),
                  value: displayNumber(String(item.payload.formatted)),
                  color: item.color,
                }))}
            />
          ) : null
        }
      />
    </>
  );
  return (
    <Card className="shadow-none">
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
        {chart.kind === "bar" && Boolean(chart.panels?.length) && (
          <div className="space-y-8">
            {chart.panels!.map((panel, i) => (
              <GroupedBars key={i} chart={chart} panel={panel} />
            ))}
          </div>
        )}
        {chart.kind !== "table" && !chart.panels?.length && (
          <ChartContainer
            config={{ value: { ...config.value, label: tr(config.value.label) } }}
            className="w-full"
            style={{
              containerType: "inline-size",
              height: bars ? Math.max(256, chart.points.length * 36) : 256,
            }}
            aria-label={chart.title}
          >
            {chart.kind === "line" ? (
              <LineChart
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
            title={tr("Ver valores exactos")}
            defaultOpen={chart.kind === "table"}
          >
            {chart.unit_origin === "owner" && (
              <p className="mb-3 text-xs text-muted-foreground">
                {tr("Unidad visible indicada por ti. Unidad del análisis:")}{" "}
                {chart.original_unit}.
              </p>
            )}
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="whitespace-normal">
                    {tr("Periodo / categoría")}
                  </TableHead>
                  {chart.points.some(
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
                    {chart.points.some(
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
          </Disclosure>
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
  useLanguage();
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
  return (
    <div className="space-y-6">
      <div>
        <div className="mb-3 flex flex-wrap gap-2">
          <Badge variant="outline">{report.scope.period}</Badge>
          <Badge variant="secondary">{tr("Revisado")}</Badge>
          {report.partial && (
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
          <Selectable
            item={item("section", "summary", {
              key: "summary",
              title: tr("Resumen"),
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
          ))}
        </div>
      )}
      <ReportSection
        title={tr("Contexto y alcance")}
        preview={tr("Sobre el negocio, los datos y el objetivo del análisis")}
      >
        {report.summary && <p>{report.summary}</p>}
        <Selectable
          item={item("section", "scope", {
            key: "scope",
            title: tr("Alcance"),
            statement: report.scope.coverage,
          })}
        >
          <p className="text-muted-foreground">{report.scope.coverage}</p>
        </Selectable>
        {report.scope.question && (
          <p>
            <strong>{tr("Pregunta: ")}</strong>
            {report.scope.question}
          </p>
        )}
        {report.limitations.length > 0 && (
          <Selectable
            item={item("section", "limitations", {
              key: "limitations",
              title: tr("Limitaciones"),
              statement: report.limitations.join("\n"),
            })}
          >
            <h3 className="font-medium">{tr("Limitaciones")}</h3>
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
                actions={edit("insight", claim.key, claim.title)}
                preview={reportLead(claim.statement)}
              >
                <p>{claim.statement}</p>
                {claim.interpretation && (
                  <p className="text-muted-foreground">
                    {claim.interpretation}
                  </p>
                )}
                {claim.next_step && (
                  <p className="rounded-lg bg-muted p-4">
                    <strong>{tr("Siguiente comprobación: ")}</strong>
                    {claim.next_step}
                  </p>
                )}
                {claim.method && (
                  <Disclosure title={tr("Cómo se ha calculado")}>
                    <p>{claim.method}</p>
                  </Disclosure>
                )}
                {claim.evidence_details && (
                  <Sources>
                    <SourcesTrigger count={claim.evidence_details.files.length}>
                      <span>{tr("Fuentes y evidencia")}</span>
                      <ArrowUpRight className="size-4" />
                    </SourcesTrigger>
                    <SourcesContent>
                      <div className="rounded-lg border p-4 space-y-3">
                        <p>{claim.evidence_details.files.join(" · ")}</p>
                        {claim.evidence_details.metrics.map((m, j) => (
                          <p key={j} className="font-mono text-xs">
                            {m.label}: {displayNumber(m.value)}
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
                    <EvidenceChart
                      chart={c}
                      actions={edit("chart", c.key, c.title)}
                    />
                  </Selectable>
                ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
