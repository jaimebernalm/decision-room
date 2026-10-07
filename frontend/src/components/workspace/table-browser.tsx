import { useEffect, useRef, useState } from "react";
import { Search, SlidersHorizontal, ArrowRight, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { translate as tr, useLanguage } from "@/lib/i18n";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loading, Notice } from "./shared";

type Filter = { column: string; op: string; value: string };
export type TableBlock = {
  tables: {
    id: string;
    name: string;
    row_count: number;
    column_count: number;
  }[];
  table_id: string;
  columns: string[];
  column_names: string[];
  rows: { number: number; values: (string | null)[] }[];
  offset: number;
  column_offset: number;
  page_rows: number;
  page_columns: number;
  filtered: boolean;
  has_more: boolean;
  next_after: number;
};
const ROW_HEIGHT = 40;
const BLOCK = 50;
const SEGMENT = 50_000; // Stay below browser scroll-height limits, even at 10M rows.
const CACHE_BLOCKS = 6;
const selectClass = "h-8 min-w-0 rounded-lg border bg-background px-2 text-xs";

export function TableBrowser({ endpoint }: { endpoint: string }) {
  useLanguage();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [showFilter, setShowFilter] = useState(false);
  const [draft, setDraft] = useState<Filter>({
    column: "",
    op: "contains",
    value: "",
  });
  const [filter, setFilter] = useState<Filter | null>(null);
  const [columns, setColumns] = useState<string[]>([]);
  const [columnOffset, setColumnOffset] = useState(0);
  useEffect(() => {
    const timer = setTimeout(() => setQuery(search), 350);
    return () => clearTimeout(timer);
  }, [search]);
  const params = new URLSearchParams({ column_offset: String(columnOffset) });
  if (query) params.set("q", query);
  if (filter) {
    params.set("filter_column", filter.column);
    params.set("filter_op", filter.op);
    params.set("filter_value", filter.value);
  }
  return (
    <div className="min-w-0 space-y-3">
      <div className="flex items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <Search
            className="pointer-events-none absolute top-2 left-2.5 size-4 text-muted-foreground"
            aria-hidden
          />
          <Input
            aria-label={tr("Buscar en la tabla")}
            placeholder={tr("Buscar en la tabla")}
            className="pl-8"
            value={search}
            maxLength={200}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Button
          type="button"
          size="sm"
          variant={filter ? "secondary" : "outline"}
          aria-expanded={showFilter}
          onClick={() => setShowFilter(!showFilter)}
        >
          <SlidersHorizontal className="size-4" />
          {tr("Filtrar")}
          {filter && <span className="size-1.5 rounded-full bg-primary" />}
        </Button>
        {(search || filter) && (
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            aria-label={tr("Quitar búsqueda y filtros")}
            onClick={() => {
              setSearch("");
              setQuery("");
              setFilter(null);
              setShowFilter(false);
            }}
          >
            <X className="size-4" />
          </Button>
        )}
      </div>
      {showFilter && (
        <form
          className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 sm:flex sm:flex-wrap"
          onSubmit={(e) => {
            e.preventDefault();
            if (draft.column) {
              setFilter({ ...draft });
              setShowFilter(false);
            }
          }}
        >
          <select
            className={`${selectClass} flex-1`}
            aria-label={tr("Columna")}
            value={draft.column}
            onChange={(e) => setDraft({ ...draft, column: e.target.value })}
          >
            <option value="">{tr("Columna")}</option>
            {columns.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
          <select
            className={selectClass}
            aria-label={tr("Condición")}
            value={draft.op}
            onChange={(e) => setDraft({ ...draft, op: e.target.value })}
          >
            <option value="contains">{tr("Contiene")}</option>
            <option value="equals">{tr("Es igual a")}</option>
            <option value="empty">{tr("Sin valor")}</option>
            <option value="not_empty">{tr("Con valor")}</option>
          </select>
          {["contains", "equals"].includes(draft.op) && (
            <Input
              className="w-full min-w-0 sm:w-36 sm:flex-1"
              aria-label={tr("Valor del filtro")}
              maxLength={200}
              value={draft.value}
              onChange={(e) => setDraft({ ...draft, value: e.target.value })}
            />
          )}
          <Button type="submit" size="sm" disabled={!draft.column}>
            {tr("Aplicar")}
          </Button>
        </form>
      )}
      {filter && (
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="max-w-full text-xs"
          onClick={() => {
            setDraft(filter);
            setShowFilter(true);
          }}
        >
          <span className="truncate">
            {filter.column} ·{" "}
            {tr(
              {
                contains: "Contiene",
                equals: "Es igual a",
                empty: "Sin valor",
                not_empty: "Con valor",
              }[filter.op] || "Contiene",
            )}{" "}
            {!["empty", "not_empty"].includes(filter.op) && filter.value}
          </span>
        </Button>
      )}
      <TableWindow
        key={`${endpoint}?${params}`}
        endpoint={endpoint}
        params={params.toString()}
        filtered={!!(query || filter)}
        onColumns={setColumns}
        columnOffset={columnOffset}
        onColumnOffset={setColumnOffset}
      />
    </div>
  );
}

function TableWindow({
  endpoint,
  params,
  filtered,
  onColumns,
  columnOffset,
  onColumnOffset,
}: {
  endpoint: string;
  params: string;
  filtered: boolean;
  onColumns: (names: string[]) => void;
  columnOffset: number;
  onColumnOffset: (offset: number) => void;
}) {
  const pages = useRef(new Map<number, TableBlock>());
  const cursors = useRef(new Map<number, number>([[0, 0]]));
  const resultEnd = useRef<number | null>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const [meta, setMeta] = useState<TableBlock | null>(null);
  const [extent, setExtent] = useState(0);
  const [base, setBase] = useState(0);
  const [top, setTop] = useState(0);
  const [jump, setJump] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const selected = meta?.tables.find((t) => t.id === meta.table_id);
  const total = filtered ? extent : selected?.row_count || 0;
  const segmentRows = Math.min(SEGMENT, Math.max(0, total - base));
  const start = base + Math.max(0, Math.floor(top / ROW_HEIGHT) - 5);
  const end = Math.min(base + segmentRows, start + 24);
  const firstBlock = Math.floor(start / BLOCK);
  const lastBlock = Math.floor(Math.max(start, end - 1) / BLOCK);
  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      setBusy(true);
      setError("");
      try {
        const needed = meta ? [firstBlock, lastBlock] : [0];
        for (const index of [...new Set(needed)]) {
          if (
            pages.current.has(index) ||
            (filtered && !cursors.current.has(index))
          )
            continue;
          const query = new URLSearchParams(params);
          query.set("offset", String(filtered ? 0 : index * BLOCK));
          if (filtered) query.set("after", String(cursors.current.get(index)));
          const block = await api<TableBlock>(
            `${endpoint}?${query}`,
            undefined,
            controller.signal,
          );
          if (controller.signal.aborted) return;
          pages.current.set(index, block);
          while (pages.current.size > CACHE_BLOCKS)
            pages.current.delete(pages.current.keys().next().value!);
          if (block.has_more) cursors.current.set(index + 1, block.next_after);
          else cursors.current.delete(index + 1);
          if (filtered) {
            if (!block.has_more)
              resultEnd.current = index * BLOCK + block.rows.length;
            setExtent(
              (old) =>
                resultEnd.current ??
                Math.max(old, index * BLOCK + block.rows.length + BLOCK),
            );
          }
          setMeta(block);
          onColumns(block.column_names || block.columns);
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          setError((e as Error).message);
          if (
            e instanceof ApiError &&
            [401, 403, 404, 409].includes(e.status)
          ) {
            pages.current.clear();
            cursors.current = new Map([[0, 0]]);
            resultEnd.current = null;
            setExtent(0);
            setMeta(null);
          }
        }
      } finally {
        if (!controller.signal.aborted) setBusy(false);
      }
    };
    void load();
    return () => controller.abort();
    // Metadata changes don't initiate requests: visible block indices do.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint, params, firstBlock, lastBlock, filtered, onColumns, revision]);
  const move = (row: number) => {
    const nextBase = Math.floor(row / SEGMENT) * SEGMENT;
    setBase(nextBase);
    const nextTop = (row - nextBase) * ROW_HEIGHT;
    setTop(nextTop);
    requestAnimationFrame(() => {
      if (viewport.current) viewport.current.scrollTop = nextTop;
    });
  };
  return (
    <div className="min-w-0 space-y-2">
      <Notice error>{error}</Notice>
      {error && (
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => {
            if (!meta) {
              setBase(0);
              setTop(0);
            }
            setRevision((n) => n + 1);
          }}
        >
          {tr("Reintentar vista de datos")}
        </Button>
      )}
      {!meta && !error && <Loading />}
      {meta && selected && (
        <>
          <p className="text-xs text-muted-foreground">
            {selected.row_count.toLocaleString()} {tr("filas")} ·{" "}
            {selected.column_count} {tr("columnas")}
          </p>
          <div
            ref={viewport}
            tabIndex={0}
            role="region"
            aria-label={tr("Filas del archivo")}
            aria-busy={busy}
            className="min-w-0 overflow-auto rounded-lg border"
            style={{
              height: segmentRows
                ? Math.min(360, (segmentRows + 1) * ROW_HEIGHT + 2)
                : 120,
              maxHeight: "45dvh",
            }}
            onScroll={(e) => setTop(e.currentTarget.scrollTop)}
          >
            <table
              className="w-full table-fixed text-left text-xs"
              style={{ minWidth: meta.columns.length * 150 + 64 }}
              aria-rowcount={filtered ? -1 : selected.row_count + 1}
            >
              <caption className="sr-only">
                {tr("Datos de ")}
                {selected.name}
              </caption>
              <thead className="sticky top-0 z-10 bg-muted">
                <tr style={{ height: ROW_HEIGHT }}>
                  <th scope="col" className="w-16 px-3">
                    {tr("Fila")}
                  </th>
                  {meta.columns.map((c) => (
                    <th key={c} scope="col" className="px-3">
                      <span className="block truncate" title={c}>
                        {c}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {start > base && (
                  <tr aria-hidden>
                    <td
                      colSpan={meta.columns.length + 1}
                      style={{
                        height: (start - base) * ROW_HEIGHT,
                        padding: 0,
                      }}
                    />
                  </tr>
                )}
                {Array.from({ length: Math.max(0, end - start) }, (_, i) => {
                  const index = start + i;
                  const row = pages.current.get(Math.floor(index / BLOCK))
                    ?.rows[index % BLOCK];
                  return (
                    <tr
                      key={index}
                      aria-rowindex={index + 2}
                      className="border-t"
                      style={{ height: ROW_HEIGHT }}
                    >
                      <th
                        scope="row"
                        className="px-3 font-normal text-muted-foreground"
                      >
                        {row?.number ?? "…"}
                      </th>
                      {meta.columns.map((c, col) => (
                        <td key={c} className="px-3">
                          <span
                            className="block truncate"
                            title={row?.values[col] ?? undefined}
                          >
                            {!row ? (
                              "…"
                            ) : row.values[col] === null ? (
                              <span className="text-muted-foreground">
                                {tr("Vacío")}
                              </span>
                            ) : row.values[col] === "" ? (
                              <span className="text-muted-foreground">
                                {tr("Texto vacío")}
                              </span>
                            ) : (
                              row.values[col]
                            )}
                          </span>
                        </td>
                      ))}
                    </tr>
                  );
                })}
                {base + segmentRows > end && (
                  <tr aria-hidden>
                    <td
                      colSpan={meta.columns.length + 1}
                      style={{
                        height: (base + segmentRows - end) * ROW_HEIGHT,
                        padding: 0,
                      }}
                    />
                  </tr>
                )}
              </tbody>
            </table>
            {filtered && !extent && (
              <p className="p-6 text-sm text-muted-foreground">
                {tr("No hay resultados.")}
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
            <span role="status">
              {busy
                ? tr("Cargando filas…")
                : filtered
                  ? resultEnd.current === null
                    ? tr("Resultados")
                    : tr("{0} resultados", {
                        0: resultEnd.current.toLocaleString(),
                      })
                  : tr("Filas {0}–{1} de {2}", {
                      0: total
                        ? Math.min(
                            selected.row_count,
                            base + Math.floor(top / ROW_HEIGHT) + 1,
                          ).toLocaleString()
                        : 0,
                      1: Math.min(
                        total,
                        base + Math.floor(top / ROW_HEIGHT) + 9,
                      ).toLocaleString(),
                      2: selected.row_count.toLocaleString(),
                    })}
            </span>
            {!filtered && selected.row_count > BLOCK && (
              <form
                className="flex items-center gap-1"
                onSubmit={(e) => {
                  e.preventDefault();
                  const row = Number(jump);
                  if (
                    Number.isInteger(row) &&
                    row >= 1 &&
                    row <= selected.row_count
                  )
                    move(row - 1);
                }}
              >
                <Input
                  className="w-24"
                  type="number"
                  min={1}
                  max={selected.row_count}
                  placeholder={tr("Ir a fila")}
                  aria-label={tr("Ir a fila")}
                  value={jump}
                  onChange={(e) => setJump(e.target.value)}
                />
                <Button
                  size="icon-sm"
                  variant="outline"
                  type="submit"
                  aria-label={tr("Ir a fila")}
                >
                  <ArrowRight className="size-4" />
                </Button>
              </form>
            )}
          </div>
          {(base > 0 || total > base + SEGMENT) && (
            <div className="flex gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={!base}
                onClick={() => move(base - SEGMENT)}
              >
                {tr("Filas anteriores")}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={total <= base + SEGMENT}
                onClick={() => move(base + SEGMENT)}
              >
                {tr("Filas siguientes")}
              </Button>
            </div>
          )}
          {selected.column_count > meta.page_columns && (
            <div className="flex items-center justify-end gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={!columnOffset}
                onClick={() =>
                  onColumnOffset(Math.max(0, columnOffset - meta.page_columns))
                }
              >
                {tr("Columnas anteriores")}
              </Button>
              <span className="text-xs">
                {columnOffset + 1}–{columnOffset + meta.columns.length}
              </span>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={
                  columnOffset + meta.columns.length >= selected.column_count
                }
                onClick={() => onColumnOffset(columnOffset + meta.page_columns)}
              >
                {tr("Columnas siguientes")}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
