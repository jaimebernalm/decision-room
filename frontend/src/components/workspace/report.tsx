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
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
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
import { chartPoints } from "@/lib/charts";
import type {
  ChartData,
  Report as ReportData,
  ContextAttachment,
} from "@/lib/types";
const config = { value: { label: "Valor", color: "var(--chart-1)" } };
export function EvidenceChart({
  chart,
  actions,
  footer,
}: {
  chart: ChartData;
  actions?: ReactNode;
  footer?: ReactNode;
}) {
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
            ? new Intl.NumberFormat("es", { notation: "compact" }).format(v)
            : temporal
              ? new Date(v).toLocaleDateString("es", {
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
            : new Intl.NumberFormat("es", { notation: "compact" }).format(v)
        }
      />
      <ReferenceLine {...(bars ? { x: 0 } : { y: 0 })} stroke="var(--border)" />
      <ChartTooltip
        content={
          <ChartTooltipContent
            className="max-w-[calc(100vw-3rem)]"
            labelFormatter={(_, payload) => payload[0]?.payload?.label}
            formatter={(_, __, item) => (
              <span className="font-mono tabular-nums">
                {item.payload.formatted} {chart.unit}
              </span>
            )}
          />
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
        {chart.kind !== "table" && (
          <ChartContainer
            config={config}
            className="w-full"
            style={{
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
            title="Ver valores exactos"
            defaultOpen={chart.kind === "table"}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="whitespace-normal">
                    Periodo / categoría
                  </TableHead>
                  <TableHead className="text-right whitespace-normal">
                    {chart.unit}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {chart.points.map((p, i) => (
                  <TableRow key={i}>
                    <TableCell>{p.label}</TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {p.formatted}
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
  const item = (
    kind: ContextAttachment["kind"],
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
              {report.summary}
            </p>
          </Selectable>
        )}
        <Selectable
          item={item("section", "scope", {
            key: "scope",
            title: "Alcance",
            statement: report.scope.coverage,
          })}
        >
          <p className="mt-2 text-xs text-muted-foreground">
            {report.scope.coverage}
          </p>
        </Selectable>
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
      {report.scope.question && (
        <p className="text-sm">
          <strong>Pregunta: </strong>
          {report.scope.question}
        </p>
      )}
      {!report.charts?.length && report.no_chart_reason && (
        <p className="text-sm text-muted-foreground">
          {report.no_chart_reason}
        </p>
      )}
      <div className="grid gap-5 xl:grid-cols-2">
        {report.charts?.map((c) => (
          <Selectable key={c.key} item={item("chart", c.key, c)}>
            <EvidenceChart chart={c} />
          </Selectable>
        ))}
      </div>
      <div className="space-y-4">
        {report.claims.map((claim, i) => (
          <Selectable key={claim.key} item={item("insight", claim.key, claim)}>
            <Card id={`finding-${claim.key}`} className="shadow-none">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs text-muted-foreground">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <CardTitle>{claim.title}</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm leading-7">
                <p>{claim.statement}</p>
                {claim.interpretation && (
                  <p className="text-muted-foreground">
                    {claim.interpretation}
                  </p>
                )}
                {claim.next_step && (
                  <p className="rounded-lg bg-muted p-4">
                    <strong>Siguiente comprobación: </strong>
                    {claim.next_step}
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
              </CardContent>
            </Card>
          </Selectable>
        ))}
      </div>
      {report.limitations?.length > 0 && (
        <Selectable
          item={item("section", "limitations", {
            key: "limitations",
            title: "Limitaciones",
            statement: report.limitations.join("\n"),
          })}
        >
          <Disclosure title="Alcance y límites del informe">
            <ul className="list-disc space-y-2 pl-5 text-muted-foreground">
              {report.limitations.map((l, i) => (
                <li key={i}>{l}</li>
              ))}
            </ul>
          </Disclosure>
        </Selectable>
      )}
    </div>
  );
}
