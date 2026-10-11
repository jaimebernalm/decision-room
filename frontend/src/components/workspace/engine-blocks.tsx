import { translate as tr, useLanguage } from "@/lib/i18n";
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
import { REPORT_LOCALE, formatNumber, naturalDecimals, signed, withUnit } from "@/lib/blocks-format";
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

/** Same platform palette, spread from dark to light so neighbouring series stay distinguishable. */
const BY_LIGHTNESS = [...CHART_SERIES_PALETTE].sort(
  (a, b) => lightness(a) - lightness(b),
);
function lightness(hex: string) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return 0.299 * r + 0.587 * g + 0.114 * b;
}
export function seriesColor(i: number, count: number) {
  if (count <= 1) return CHART_SERIES_PALETTE[0];
  if (count > BY_LIGHTNESS.length) return CHART_SERIES_PALETTE[i % CHART_SERIES_PALETTE.length];
  // The lightest tone is kept for six series only: it is faint as a line on white.
  const last = count >= BY_LIGHTNESS.length ? BY_LIGHTNESS.length - 1 : BY_LIGHTNESS.length - 2;
  return BY_LIGHTNESS[Math.round((i * last) / (count - 1))];
}

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

/** A stack total names what it adds up: hidden series or gaps make it visible or partial. */
export function stackTotalLabel(chart: ChartBlock, category: number, seriesHidden: boolean) {
  if (seriesHidden) return tr("Total visible");
  return chart.series.some((s) => s.values[category] === null) ? tr("Total parcial") : tr("Total");
}

function BlockChartBody({ chart }: { chart: ChartBlock }) {
  useLanguage();
  const rows = chartRows(chart);
  const color = (i: number) => seriesColor(i, chart.series.length);
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
    new Intl.NumberFormat(REPORT_LOCALE, { notation: "compact" }).format(v);
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
        // In a stack a missing part is shown as a gap ("—"), never silently left out.
        const items: { label: string; value: string; color?: string }[] = (stacked ? shown : present).map(
          ({ s, i }) => ({
            label: s.name,
            value:
              withUnit(s.values[c], chart.decimals, chart.unit) +
              (s.details?.[c] ? ` · ${s.details[c]}` : ""),
            color: color(i),
          }),
        );
        if (stacked && present.length > 0 && shown.length > 1)
          items.push({
            label: stackTotalLabel(chart, c, hidden.size > 0),
            value: withUnit(
              present.reduce((sum, { s }) => sum + (s.values[c] as number), 0),
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

const TABLE_PREVIEW_ROWS = 8;

export function BlockTable({ block }: { block: TableBlock }) {
  useLanguage();
  // Reader-side sorting and folding only; the author's order is the default.
  const [sort, setSort] = useState<{ column: number; descending: boolean } | null>(null);
  const [expanded, setExpanded] = useState(false);
  const rows = block.rows.map((row, index) => ({ row, index }));
  if (sort)
    rows.sort((a, b) => {
      const x = a.row[sort.column];
      const y = b.row[sort.column];
      if (x === null || y === null) return x === y ? a.index - b.index : x === null ? 1 : -1;
      const order =
        typeof x === "number" && typeof y === "number"
          ? x - y
          : String(x).localeCompare(String(y), REPORT_LOCALE, { numeric: true });
      return (sort.descending ? -order : order) || a.index - b.index;
    });
  const folded = !expanded && rows.length > TABLE_PREVIEW_ROWS;
  const visible = folded ? rows.slice(0, TABLE_PREVIEW_ROWS) : rows;
  const cycle = (column: number) =>
    setSort((current) =>
      current?.column !== column
        ? { column, descending: block.rows.some((r) => typeof r[column] === "number") }
        : current.descending === block.rows.some((r) => typeof r[column] === "number")
          ? { column, descending: !current.descending }
          : null,
    );
  return (
    <div className="space-y-2">
      {block.title && <h4 className="text-sm font-medium">{block.title}</h4>}
      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              {block.columns.map((c, i) => (
                <TableHead
                  key={i}
                  aria-sort={
                    sort?.column === i ? (sort.descending ? "descending" : "ascending") : undefined
                  }
                >
                  <button
                    type="button"
                    onClick={() => cycle(i)}
                    title={tr("Ordenar por esta columna")}
                    className="inline-flex items-center gap-1 rounded hover:text-foreground"
                  >
                    {c.title}
                    {c.unit ? ` (${c.unit})` : ""}
                    <span aria-hidden className="text-[10px] text-muted-foreground">
                      {sort?.column === i ? (sort.descending ? "▼" : "▲") : ""}
                    </span>
                  </button>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {visible.map(({ row, index }) => (
              <TableRow key={index}>
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
      {rows.length > TABLE_PREVIEW_ROWS && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="text-xs font-medium text-primary hover:underline"
        >
          {expanded
            ? tr("Ver menos filas")
            : tr("Ver las {0} filas", { "0": formatNumber(rows.length, 0) })}
        </button>
      )}
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
                    "Se examinaron {0} de los {1} números citados en las prioridades; {2} coincidieron al recalcularlos con los datos.",
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
