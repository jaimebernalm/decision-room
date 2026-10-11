import { translate as tr, useLanguage, locale } from "@/lib/i18n";
import { Fragment, useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  XAxis,
  YAxis,
} from "recharts";
import { ChartContainer, ChartTooltip } from "@/components/ui/chart";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { CHART_NEUTRALS, CHART_SERIES_PALETTE } from "@/lib/charts";
import { Disclosure, Notice } from "./shared";
import { ReportChartTooltip } from "./report-chart-tooltip";
import { formatNumber, naturalDecimals, signed, withUnit } from "@/lib/blocks-format";
import type {
  BlockCheck,
  BlockChecks,
  BlockContent,
  BlockSpan,
  BlocksProjection,
  ReportBlock,
} from "@/lib/types";

type ChartBlock = Extract<ReportBlock, { type: "chart" }>;
type TableBlock = Extract<ReportBlock, { type: "table" }>;
type FigureBlock = Extract<ReportBlock, { type: "figure" }>;
type Wrap = (block: ReportBlock, node: ReactNode) => ReactNode;

function Spans({ spans }: { spans: BlockSpan[] }) {
  return (
    <>
      {spans.map((s, i) => {
        let node: ReactNode = s.text;
        if (s.italic) node = <em>{node}</em>;
        if (s.bold) node = <strong>{node}</strong>;
        return <Fragment key={i}>{node}</Fragment>;
      })}
    </>
  );
}

export function BlockText({ content }: { content: BlockContent[] }) {
  return (
    <div className="space-y-3 text-sm leading-7">
      {content.map((node, i) =>
        node.kind === "paragraph" ? (
          <p key={i} className="whitespace-pre-line">
            <Spans spans={node.spans} />
          </p>
        ) : node.ordered ? (
          <ol key={i} className="list-decimal space-y-1 pl-5">
            {node.items.map((item, j) => (
              <li key={j}>
                <Spans spans={item} />
              </li>
            ))}
          </ol>
        ) : (
          <ul key={i} className="list-disc space-y-1 pl-5">
            {node.items.map((item, j) => (
              <li key={j}>
                <Spans spans={item} />
              </li>
            ))}
          </ul>
        ),
      )}
    </div>
  );
}

function Figure({ block }: { block: FigureBlock }) {
  useLanguage();
  return (
    <Card className="shadow-none">
      <CardHeader className="pb-2">
        <CardDescription>{block.label}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-1">
        <p className="text-3xl font-semibold tracking-tight tabular-nums">
          {withUnit(block.value, block.decimals, block.unit)}
        </p>
        {block.period && (
          <p className="text-xs text-muted-foreground">{block.period}</p>
        )}
        {block.previous && (
          <p className="text-xs text-muted-foreground tabular-nums">
            {tr("Antes")}:{" "}
            {withUnit(block.previous.value, block.decimals, block.unit)}
            {block.previous.period ? ` (${block.previous.period})` : ""}
            {block.change !== null && (
              <>
                {" · "}
                <span
                  className={
                    block.change < 0
                      ? "text-destructive"
                      : block.change > 0
                        ? "text-foreground"
                        : undefined
                  }
                >
                  {signed(block.change, block.decimals, block.unit)}
                  {block.change_pct !== null &&
                    ` (${block.change_pct > 0 ? "+" : ""}${formatNumber(block.change_pct, 1)} %)`}
                </span>
              </>
            )}
          </p>
        )}
        {block.note && (
          <p className="pt-1 text-xs text-muted-foreground">{block.note}</p>
        )}
      </CardContent>
    </Card>
  );
}

const color = (i: number) =>
  CHART_SERIES_PALETTE[i % CHART_SERIES_PALETTE.length];

function chartRows(chart: ChartBlock) {
  return chart.categories.map((category, c) => {
    const row: Record<string, string | number | null> = { category };
    chart.series.forEach((s, i) => {
      row[`s${i}`] = s.values[c];
    });
    return row;
  });
}

function ChartValues({ chart }: { chart: ChartBlock }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{chart.category_title || tr("Categoría")}</TableHead>
          {chart.series.map((s) => (
            <TableHead key={s.name} className="text-right">
              {s.name}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {chart.categories.map((category, c) => (
          <TableRow key={category}>
            <TableCell>{category}</TableCell>
            {chart.series.map((s) => (
              <TableCell
                key={s.name}
                className="text-right font-mono tabular-nums"
              >
                {withUnit(s.values[c], chart.decimals, chart.unit)}
                {s.details?.[c] && (
                  <span className="block text-xs text-muted-foreground">
                    {s.details[c]}
                  </span>
                )}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function BlockChartBody({ chart }: { chart: ChartBlock }) {
  useLanguage();
  const rows = chartRows(chart);
  const stacked = chart.kind === "stacked_column" || chart.kind === "stacked_bar";
  const horizontal = chart.kind === "bar" || chart.kind === "change" || chart.kind === "stacked_bar";
  // Series hidden from the legend; at least one always stays visible.
  const [hidden, setHidden] = useState<ReadonlySet<number>>(new Set());
  const shown = chart.series.map((s, i) => ({ s, i })).filter(({ i }) => !hidden.has(i));
  const toggle = (i: number) =>
    setHidden((current) => {
      const next = new Set(current);
      if (next.has(i)) next.delete(i);
      else if (shown.length > 1) next.add(i);
      return next;
    });
  const values = stacked
    ? chart.categories.map((_, c) => shown.reduce((sum, { s }) => sum + (s.values[c] ?? 0), 0))
    : shown.flatMap(({ s }) => s.values.filter((v): v is number => v !== null));
  const extent = Math.max(...values.map(Math.abs), 1);
  const compact = (v: number) =>
    new Intl.NumberFormat(locale(), { notation: "compact" }).format(v);
  const valueDomain: [number | ((v: number) => number), number | ((v: number) => number)] =
    chart.kind === "change"
      ? [-extent, extent]
      : [(v: number) => Math.min(0, v), (v: number) => Math.max(0, v)];
  const tooltip = (
    <ChartTooltip
      allowEscapeViewBox={{ x: false, y: false }}
      position={horizontal ? { x: 8 } : undefined}
      content={({ active, payload }) => {
        if (!active || !payload?.length) return null;
        const category = String(payload[0].payload.category);
        const c = chart.categories.indexOf(category);
        const present = shown.filter(({ s }) => s.values[c] !== null);
        const items: { label: string; value: string; color?: string }[] = present.map(({ s, i }) => ({
          label: s.name,
          value:
            withUnit(s.values[c], chart.decimals, chart.unit) +
            (s.details?.[c] ? ` · ${s.details[c]}` : ""),
          color: color(i),
        }));
        if (stacked && present.length > 1)
          items.push({
            label: tr("Total"),
            value: withUnit(
              present.reduce((sum, { s }) => sum + (s.values[c] ?? 0), 0),
              chart.decimals,
              chart.unit,
            ),
          });
        return <ReportChartTooltip title={category} unit={chart.unit || ""} items={items} />;
      }}
    />
  );
  const legend = chart.series.length > 1 && (
    <ul className="flex flex-wrap gap-x-2 gap-y-1 text-xs" aria-label={tr("Leyenda")}>
      {chart.series.map((s, i) => (
        <li key={s.name}>
          <button
            type="button"
            aria-pressed={!hidden.has(i)}
            title={hidden.has(i) ? tr("Mostrar serie") : tr("Ocultar serie")}
            onClick={() => toggle(i)}
            className="flex items-center gap-2 rounded-md px-2 py-1 hover:bg-muted aria-[pressed=false]:text-muted-foreground aria-[pressed=false]:line-through"
          >
            <span
              aria-hidden
              className="size-2.5 rounded-sm"
              style={{ background: hidden.has(i) ? "var(--muted-foreground)" : color(i) }}
            />
            {s.name}
          </button>
        </li>
      ))}
    </ul>
  );
  const config = Object.fromEntries(
    chart.series.map((s, i) => [`s${i}`, { label: s.name, color: color(i) }]),
  );
  const height = horizontal
    ? Math.max(240, rows.length * ((stacked ? 1 : shown.length) * 22 + 26) + 40)
    : 280;
  const signColor = (v: number | null, i: number) =>
    chart.kind === "change" && chart.series.length === 1
      ? (v ?? 0) < 0
        ? CHART_NEUTRALS.reference
        : color(0)
      : color(i);
  return (
    <div className="space-y-3">
      {legend}
      <ChartContainer
        config={config}
        className="w-full"
        style={{ containerType: "inline-size", height }}
        aria-label={chart.title}
      >
        {chart.kind === "line" ? (
          <LineChart data={rows} accessibilityLayer margin={{ left: 4, right: 16 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="category" tickLine={false} axisLine={false} minTickGap={16} />
            <YAxis
              width={64}
              tickLine={false}
              axisLine={false}
              domain={valueDomain}
              tickFormatter={compact}
            />
            <ReferenceLine y={0} stroke="var(--border)" />
            {tooltip}
            {shown.map(({ s, i }) => (
              <Line
                key={s.name}
                dataKey={`s${i}`}
                name={s.name}
                stroke={color(i)}
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        ) : (
          <BarChart
            layout={horizontal ? "vertical" : "horizontal"}
            data={rows}
            accessibilityLayer
            margin={{ left: 0, right: 16 }}
            barGap={3}
            barCategoryGap={horizontal ? 14 : "20%"}
          >
            <CartesianGrid horizontal={!horizontal} vertical={horizontal} />
            {horizontal ? (
              <>
                <XAxis
                  type="number"
                  tickLine={false}
                  axisLine={false}
                  domain={valueDomain}
                  ticks={
                    chart.kind === "change"
                      ? [-extent, -extent / 2, 0, extent / 2, extent]
                      : undefined
                  }
                  tickFormatter={compact}
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
              </>
            ) : (
              <>
                <XAxis dataKey="category" tickLine={false} axisLine={false} interval={0} minTickGap={4} />
                <YAxis
                  width={64}
                  tickLine={false}
                  axisLine={false}
                  domain={valueDomain}
                  tickFormatter={compact}
                />
                <ReferenceLine y={0} stroke="var(--muted-foreground)" />
              </>
            )}
            {tooltip}
            {shown.map(({ s, i }) => (
              <Bar
                key={s.name}
                dataKey={`s${i}`}
                name={s.name}
                fill={color(i)}
                stackId={stacked ? "total" : undefined}
                radius={stacked ? 0 : 3}
                maxBarSize={horizontal ? 20 : 36}
                isAnimationActive={false}
              >
                {chart.kind === "change" &&
                  chart.series.length === 1 &&
                  rows.map((row, r) => (
                    <Cell key={r} fill={signColor(row[`s${i}`] as number | null, i)} />
                  ))}
              </Bar>
            ))}
          </BarChart>
        )}
      </ChartContainer>
    </div>
  );
}

export function BlockChart({ chart }: { chart: ChartBlock }) {
  useLanguage();
  const table = chart.kind === "table";
  return (
    <Card className="shadow-none">
      <CardHeader>
        <CardTitle>{chart.title}</CardTitle>
        {(chart.unit || chart.value_title) && (
          <CardDescription>
            {chart.value_title && chart.unit && chart.value_title.includes(chart.unit)
              ? chart.value_title
              : [chart.value_title, chart.unit].filter(Boolean).join(" · ")}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {table ? <ChartValues chart={chart} /> : <BlockChartBody chart={chart} />}
        {chart.note && (
          <p className="text-xs text-muted-foreground">{chart.note}</p>
        )}
        {!table && (
          <Disclosure title={tr("Ver valores")} subtle>
            <ChartValues chart={chart} />
          </Disclosure>
        )}
      </CardContent>
    </Card>
  );
}

export function BlockTable({ block }: { block: TableBlock }) {
  useLanguage();
  return (
    <div className="space-y-2">
      {block.title && <h4 className="text-sm font-medium">{block.title}</h4>}
      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              {block.columns.map((c, i) => (
                <TableHead key={i}>
                  {c.title}
                  {c.unit ? ` (${c.unit})` : ""}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {block.rows.map((row, r) => (
              <TableRow key={r}>
                {row.map((cell, c) => (
                  <TableCell
                    key={c}
                    className={
                      typeof cell === "number"
                        ? "text-right font-mono tabular-nums"
                        : undefined
                    }
                  >
                    {typeof cell === "number"
                      ? formatNumber(cell, block.columns[c].decimals ?? naturalDecimals(cell))
                      : cell ?? "—"}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {block.note && (
        <p className="text-xs text-muted-foreground">{block.note}</p>
      )}
    </div>
  );
}

/** Independent-check outcome for one block. Never a confirmation mark (P5). */
function CheckNotices({ items }: { items: BlockCheck[] }) {
  useLanguage();
  const disputed = items.filter((c) => c.status === "discrepancy");
  if (!disputed.length) return null;
  return (
    <div role="note" className="rounded-lg border border-amber-500/50 bg-amber-500/10 p-3 text-sm">
      <p className="font-medium">
        {tr("Cifra en revisión: una comprobación independiente no obtuvo el mismo resultado. Revísala antes de decidir.")}
      </p>
      <ul className="mt-2 space-y-1">
        {disputed.map((c, i) => (
          <li key={i}>
            «{c.quote}»
            {c.independent_value && (
              <>
                {" — "}
                {tr("cálculo independiente")}: {c.independent_value}
              </>
            )}
            {c.message && (
              <span className="block text-xs text-muted-foreground">{c.message}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Blocks({
  blocks,
  depth,
  checks,
  wrap,
  numbers,
}: {
  blocks: ReportBlock[];
  depth: number;
  checks: Map<string, BlockCheck[]>;
  wrap: Wrap;
  numbers: Map<string, number>;
}) {
  const out: ReactNode[] = [];
  let figures: FigureBlock[] = [];
  const flush = () => {
    if (!figures.length) return;
    const group = figures;
    figures = [];
    out.push(
      <div key={`figures-${group[0].id}`} className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {group.map((f) => (
          <Fragment key={f.id}>
            {wrap(f, <Figure block={f} />)}
          </Fragment>
        ))}
      </div>,
    );
    for (const f of group)
      if (checks.get(f.id)) out.push(<CheckNotices key={`check-${f.id}`} items={checks.get(f.id)!} />);
  };
  for (const block of blocks) {
    if (block.type === "figure") {
      figures.push(block);
      continue;
    }
    flush();
    out.push(
      <Fragment key={block.id}>
        <Block block={block} depth={depth} checks={checks} wrap={wrap} numbers={numbers} />
      </Fragment>,
    );
  }
  flush();
  return <div className="space-y-5">{out}</div>;
}

function Block({
  block,
  depth,
  checks,
  wrap,
  numbers,
}: {
  block: ReportBlock;
  depth: number;
  checks: Map<string, BlockCheck[]>;
  wrap: Wrap;
  numbers: Map<string, number>;
}) {
  const own = checks.get(block.id) ?? [];
  const notices = own.length ? <CheckNotices items={own} /> : null;
  switch (block.type) {
    case "section": {
      const Heading = depth === 0 ? "h3" : "h4";
      return (
        <section id={`block-${block.id}`} className="space-y-4">
          {wrap(
            block,
            <Heading className={depth === 0 ? "text-xl font-semibold tracking-tight" : "text-base font-semibold"}>
              {block.title}
            </Heading>,
          )}
          <Blocks blocks={block.blocks} depth={depth + 1} checks={checks} wrap={wrap} numbers={numbers} />
        </section>
      );
    }
    case "priority": {
      return (
        <section id={`block-${block.id}`}>
          {wrap(
            block,
            <Card className="gap-0 py-0 shadow-none">
              <div className="flex items-start gap-3 p-5">
                <span
                  aria-hidden
                  className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground"
                >
                  {String(numbers.get(block.id) ?? 0).padStart(2, "0")}
                </span>
                <div className="min-w-0 flex-1 space-y-4">
                  <h3 className="text-base font-semibold leading-snug">
                    <span className="sr-only">{tr("Prioridad")}: </span>
                    {block.title}
                  </h3>
                  {notices}
                  <Blocks blocks={block.blocks} depth={depth + 1} checks={checks} wrap={wrap} numbers={numbers} />
                </div>
              </div>
            </Card>,
          )}
        </section>
      );
    }
    case "text":
      return (
        <>
          {wrap(block, <BlockText content={block.content} />)}
          {notices}
        </>
      );
    case "notice":
      return wrap(
        block,
        <Notice>
          <BlockText content={block.content} />
        </Notice>,
      );
    case "chart":
      return (
        <>
          {wrap(block, <BlockChart chart={block} />)}
          {notices}
        </>
      );
    case "table":
      return (
        <>
          {wrap(block, <BlockTable block={block} />)}
          {notices}
        </>
      );
    case "figure":
      return (
        <>
          {wrap(block, <Figure block={block} />)}
          {notices}
        </>
      );
  }
}

export function BlocksReport({
  projection,
  checks,
  wrap = (_, node) => node,
}: {
  projection: BlocksProjection;
  checks?: BlockChecks;
  wrap?: Wrap;
}) {
  useLanguage();
  const byBlock = new Map<string, BlockCheck[]>();
  for (const item of checks?.items ?? [])
    byBlock.set(item.block_id, [...(byBlock.get(item.block_id) ?? []), item]);
  const numbers = new Map<string, number>();
  const number = (blocks: ReportBlock[]) => {
    for (const b of blocks) {
      if (b.type === "priority") numbers.set(b.id, numbers.size + 1);
      if ("blocks" in b) number(b.blocks);
    }
  };
  number(projection.blocks);
  const unverifiable = (checks?.items ?? []).filter(
    (c) => c.status === "unverifiable" && !c.coverage,
  );
  const uncovered = (checks?.items ?? []).filter((c) => c.coverage);
  const coverage = checks?.coverage;
  return (
    <div className="space-y-6">
      <Blocks blocks={projection.blocks} depth={0} checks={byBlock} wrap={wrap} numbers={numbers} />
      {(unverifiable.length > 0 || uncovered.length > 0) && (
        // Limits of the independent check: one plain summary, folded away. The per-priority
        // coverage messages stay in the data and the chat, never repeated here (no extra text).
        <Disclosure title={tr("Detalles de la comprobación independiente")} subtle>
          <div className="space-y-2 text-sm">
            <p className="text-muted-foreground">
              {coverage && coverage.numeric_spans > 0
                ? tr(
                    "Se recalcularon con los datos {0} de las {1} cifras de las prioridades; {2} coinciden con el informe.",
                    {
                      "0": formatNumber(coverage.addressed_spans, 0),
                      "1": formatNumber(coverage.numeric_spans, 0),
                      "2": formatNumber(coverage.confirmed_spans, 0),
                    },
                  )
                : null}{" "}
              {tr("Una cifra sin recalcular no está marcada como errónea; solo no se revisó por separado.")}
            </p>
            {unverifiable.length > 0 && (
              <>
                <p className="font-medium">{tr("Cifras que no se pudieron recalcular")}</p>
                <ul className="space-y-1">
                  {unverifiable.map((c, i) => (
                    <li key={i}>
                      «{c.quote}»
                      {c.message && <span className="block text-xs text-muted-foreground">{c.message}</span>}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </Disclosure>
      )}
      {checks?.state === "incomplete" && (
        <Notice>
          {tr("La comprobación independiente de cifras no se pudo completar para este informe.")}
        </Notice>
      )}
      {checks?.state === "pending" && (
        <Notice>{tr("La comprobación independiente de cifras está en curso.")}</Notice>
      )}
    </div>
  );
}
