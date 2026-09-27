import { useId, useState, type ReactNode } from "react";
import { GitBranch, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useResource, useAction } from "@/lib/hooks";
import { api } from "@/lib/api";
import { Notice, Loading, Disclosure } from "./shared";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid min-w-0 gap-2">
      <span className="text-sm font-medium">{label}</span>
      {children}
    </label>
  );
}

type Column = {
  name: string;
  logical_type: string;
  missing: number;
  distinct: number;
  duplicate_nonempty: number;
  date_parseable: number;
  period: { from: string; until: string } | null;
  key_candidate: boolean;
  meaning: string;
  unit: string;
  conversion: string;
};
type Table = {
  id: string;
  name: string;
  row_count: number;
  duplicate_rows: number;
  description: string;
  grain: string;
  columns: Column[];
  candidate_keys: string[][];
  declared_keys: { columns: string[]; valid: boolean }[];
};
type Counts = {
  rows: number;
  missing_rows: number;
  duplicate_keys: number;
  duplicate_rows: number;
};
type Relation = {
  id: string;
  source: string;
  target: string;
  source_columns: string[];
  target_columns: string[];
  description: string;
  cardinality: string;
  semantic_status: string;
  verification: string;
  origin: string;
  evidence: {
    source: Counts;
    target: Counts;
    unmatched_rows: number;
    inner_join_rows: number;
    left_join_rows: number;
    extra_rows: number;
    coverage: number | null;
  };
};
type Metric = {
  key: string;
  name: string;
  definition: string;
  unit: string;
  table_ids: string[];
  period: { from: string | null; until: string | null };
};
export type DataModel = {
  analysis_id: string;
  revision: number;
  body: { tables: Table[]; relations: Relation[]; metrics: Metric[] };
};
type Response = {
  model: DataModel | null;
  history: { revision: number; reason: string; created_at: string }[];
  editable: boolean;
  needs_refresh?: boolean;
  affected_reports: { review_id: string }[];
};
type Save = (action: string, payload: unknown) => Promise<void>;
const labels: Record<string, string> = {
  proposed: "Por confirmar",
  confirmed: "Significado confirmado",
  rejected: "Descartada",
};
const cardinalities: Record<string, string> = {
  "one-to-one": "Uno a uno",
  "one-to-many": "Uno a muchos",
  "many-to-one": "Muchos a uno",
  "many-to-many": "Muchos a muchos",
};
const selectClass =
  "h-10 min-w-0 w-full rounded-md border bg-background px-3 text-sm";

export function DataModelPanel({
  business,
  analysis,
}: {
  business: string;
  analysis: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <section className="min-w-0 max-w-full space-y-4">
      <Button
        variant="outline"
        size="sm"
        onClick={() => setOpen(!open)}
        className="h-auto max-w-full whitespace-normal text-left"
        aria-expanded={open}
      >
        <GitBranch />
        {open
          ? "Ocultar relaciones"
          : "Ver relaciones y cómo entendemos los datos"}
      </Button>
      {open && (
        <ModelContent
          key={`${business}/${analysis}`}
          business={business}
          analysis={analysis}
        />
      )}
    </section>
  );
}
function ModelContent({
  business,
  analysis,
}: {
  business: string;
  analysis: string;
}) {
  const [revision, setRevision] = useState("");
  const resource = useResource<Response>(
      `/api/business/data-model?analysis_id=${analysis}${revision ? `&revision=${revision}` : ""}`,
    ),
    action = useAction();
  const [selected, setSelected] = useState(""),
    [edge, setEdge] = useState(""),
    [filter, setFilter] = useState(""),
    [focus, setFocus] = useState(false),
    [form, setForm] = useState("");
  const save: Save = async (kind, payload) => {
    await action.run(async () => {
      await api("/api/business/data-model", {
        business_id: business,
        analysis_id: analysis,
        expected_revision: resource.data?.model?.revision,
        action: kind,
        payload,
      });
      setForm("");
      resource.refresh();
    });
  };
  if (!resource.data)
    return (
      <>
        <Notice error>{resource.error}</Notice>
        {!resource.error && <Loading />}
      </>
    );
  const { model, history, editable, affected_reports, needs_refresh } =
    resource.data;
  if (!model)
    return (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Prepara el mapa de estas tablas para consultar sus relaciones y
          guardar lo que significan.
        </p>
        <Notice error>{action.error}</Notice>
        <Button
          disabled={action.busy || !editable}
          onClick={() => void save("prepare", {})}
        >
          {action.busy ? "Comprobando las tablas…" : "Preparar modelo de datos"}
        </Button>
      </div>
    );
  const { tables, relations, metrics } = model.body,
    table = tables.find((t) => t.id === selected),
    relation = relations.find((r) => r.id === edge);
  const canEdit = editable && !revision && !needs_refresh,
    names = Object.fromEntries(tables.map((t) => [t.id, t.name]));
  const neighbors = new Set(
    relations
      .filter((r) => [r.source, r.target].includes(selected))
      .flatMap((r) => [r.source, r.target]),
  );
  neighbors.add(selected);
  const matching = tables.filter(
      (t) =>
        t.name.toLowerCase().includes(filter.toLowerCase()) &&
        (!focus || !selected || neighbors.has(t.id)),
    ),
    visible = matching.slice(0, 12);
  const chooseTable = (id: string) => {
    setSelected(id);
    setEdge("");
    setForm("");
  };
  return (
    <Card className="min-w-0 max-w-full shadow-none">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle>Cómo se conectan tus datos</CardTitle>
          <Badge variant="outline">Modelo · revisión {model.revision}</Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          {tables.length} tablas · {relations.length} relaciones propuestas o
          comprobadas. Las comprobaciones técnicas y el significado de negocio
          se revisan por separado.
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
        <Notice error>{resource.error || action.error}</Notice>
        {needs_refresh && (
          <Notice>
            Este modelo corresponde a una preparación anterior. Vuelve a
            comprobar las tablas antes de reutilizar sus relaciones.{" "}
            {editable && (
              <Button
                size="sm"
                variant="outline"
                disabled={action.busy}
                onClick={() => void save("prepare", {})}
              >
                Volver a comprobar las tablas
              </Button>
            )}
          </Notice>
        )}
        {!!affected_reports.length && (
          <Notice>
            {affected_reports.length} informes necesitan una nueva revisión tras
            cambios de contexto. Sus resultados anteriores se conservan.
          </Notice>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Buscar tabla">
            <Input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Nombre de la tabla"
            />
          </Field>
          <Field label="Historial del modelo">
            <select
              className={selectClass}
              value={revision}
              onChange={(e) => {
                setRevision(e.target.value);
                setForm("");
              }}
            >
              <option value="">Revisión vigente</option>
              {history.map((h) => (
                <option key={h.revision} value={h.revision}>
                  Revisión {h.revision} ·{" "}
                  {new Date(h.created_at).toLocaleDateString()}
                </option>
              ))}
            </select>
          </Field>
        </div>
        {table && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setFocus(!focus);
              if (!focus) setFilter("");
            }}
          >
            {focus
              ? "Ver todas las tablas"
              : "Centrar en esta tabla y sus conexiones"}
          </Button>
        )}
        <ERDiagram
          tables={visible}
          relations={relations}
          selected={selected}
          edge={edge}
          chooseTable={chooseTable}
          chooseEdge={(id) => {
            setEdge(id);
            setForm("");
          }}
        />
        {matching.length > 12 && (
          <p className="text-sm text-muted-foreground">
            Se muestran 12 de {matching.length} tablas. Busca o selecciona una
            tabla para centrar el mapa.
          </p>
        )}
        <div
          className="flex max-h-36 flex-wrap gap-2 overflow-auto"
          aria-label="Todas las tablas"
        >
          {matching.map((t) => (
            <Button
              key={t.id}
              className="h-auto max-w-full whitespace-normal py-1"
              size="sm"
              variant={selected === t.id ? "default" : "outline"}
              onClick={() => chooseTable(t.id)}
            >
              {t.name}
            </Button>
          ))}
        </div>
        <Disclosure title="Conexiones y comprobaciones" defaultOpen={!!edge}>
          <div className="space-y-2">
            {relations
              .filter(
                (r) => !selected || [r.source, r.target].includes(selected),
              )
              .map((r) => (
                <button
                  type="button"
                  key={r.id}
                  onClick={() => {
                    setEdge(r.id);
                    setForm("");
                  }}
                  className="block w-full rounded-lg border p-3 text-left text-sm hover:bg-muted"
                >
                  <span className="break-all">
                    {names[r.source]} → {names[r.target]}
                  </span>
                  <span className="mt-1 block text-xs text-muted-foreground">
                    {cardinalities[r.cardinality]} · {labels[r.semantic_status]}{" "}
                    ·{" "}
                    {r.verification === "checked"
                      ? "Claves comprobadas"
                      : "Revisar claves o cobertura"}
                  </span>
                </button>
              ))}
            {!relations.length && (
              <p className="text-sm text-muted-foreground">
                No se han inferido enlaces inequívocos por nombre de entidad.
                Puedes añadir conexiones, incluidas claves compuestas.
              </p>
            )}
          </div>
        </Disclosure>
        {table && !relation && (
          <div className="space-y-3 rounded-xl border p-4">
            <h3 className="font-semibold break-all">{table.name}</h3>
            <p className="text-sm">
              {table.row_count.toLocaleString()} filas ·{" "}
              {table.duplicate_rows.toLocaleString()} filas duplicadas
            </p>
            <p className="text-sm">
              {table.description || "Descripción pendiente de aclarar."}
            </p>
            <p className="text-sm">
              <strong>Cada fila representa: </strong>
              {table.grain || "Todavía no está confirmado."}
            </p>
            <Disclosure title="Columnas, tipos y cobertura">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr>
                      <th className="p-2">Columna</th>
                      <th className="p-2">Tipo observado</th>
                      <th className="p-2">Vacíos</th>
                      <th className="p-2">Distintos</th>
                      <th className="p-2">Definición / periodo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {table.columns.map((c) => (
                      <tr key={c.name} className="border-t">
                        <td className="p-2">
                          {c.name}
                          {c.key_candidate ? " · clave candidata" : ""}
                        </td>
                        <td className="p-2">{c.logical_type}</td>
                        <td className="p-2">{c.missing}</td>
                        <td className="p-2">{c.distinct}</td>
                        <td className="p-2">
                          {c.meaning || "Sin confirmar"}
                          {c.unit && ` · ${c.unit}`}
                          {c.period &&
                            ` · ${c.period.from} — ${c.period.until} (${c.date_parseable}/${table.row_count - c.missing} valores con fecha válida)`}
                          {c.conversion &&
                            ` · Conversión declarada: ${c.conversion}`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Comprobación sobre todas las filas. Los valores originales se
                conservan como texto; los tipos observados no aplican
                conversiones.
              </p>
            </Disclosure>
            {table.declared_keys.map((k, i) => (
              <p key={i} className="text-sm">
                Clave declarada ({k.columns.join(", ")}):{" "}
                {k.valid ? "única y completa" : "contiene duplicados o vacíos"}
              </p>
            ))}
            {canEdit && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setForm("table")}
              >
                Corregir o aclarar esta tabla
              </Button>
            )}
          </div>
        )}
        {relation && (
          <div className="space-y-3 rounded-xl border p-4">
            <h3 className="font-semibold break-all">
              {names[relation.source]} → {names[relation.target]}
            </h3>
            <p className="text-sm break-all">
              {relation.source_columns.join(" + ")} ={" "}
              {relation.target_columns.join(" + ")}
            </p>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">
                {cardinalities[relation.cardinality]}
              </Badge>
              <Badge variant="outline">
                {labels[relation.semantic_status]}
              </Badge>
            </div>
            <p className="text-sm">
              {relation.description ||
                "El significado de este enlace aún necesita confirmación."}
            </p>
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt>Claves duplicadas (origen / destino)</dt>
              <dd>
                {relation.evidence.source.duplicate_keys} /{" "}
                {relation.evidence.target.duplicate_keys}
              </dd>
              <dt>Filas sin clave (origen / destino)</dt>
              <dd>
                {relation.evidence.source.missing_rows} /{" "}
                {relation.evidence.target.missing_rows}
              </dd>
              <dt>Filas sin correspondencia</dt>
              <dd>{relation.evidence.unmatched_rows}</dd>
              <dt>Filas tras unión izquierda</dt>
              <dd>{relation.evidence.left_join_rows.toLocaleString()}</dd>
              <dt>Filas adicionales por multiplicación</dt>
              <dd>{relation.evidence.extra_rows.toLocaleString()}</dd>
            </dl>
            <p className="text-sm text-muted-foreground">
              Origen:{" "}
              {relation.origin === "owner"
                ? "declaración del usuario"
                : "inferencia por nombre de entidad"}
              . Comparación exacta, sin convertir valores. Confirma el
              significado y la granularidad antes de sumar: las medidas de la
              tabla padre pueden repetirse al unirlas con sus detalles.
            </p>
            {canEdit && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setForm("relation")}
              >
                Corregir o confirmar relación
              </Button>
            )}
          </div>
        )}
        <section className="space-y-3">
          <h3 className="font-medium">Cómo entendemos las métricas</h3>
          {metrics.map((m) => (
            <div key={m.key} className="rounded-lg border p-3 text-sm">
              <strong>{m.name || m.key}</strong>
              <p>{m.definition}</p>
              <p className="text-xs text-muted-foreground">
                {m.unit || "Unidad no indicada"} ·{" "}
                {m.period.from || "Inicio no acotado"} —{" "}
                {m.period.until || "Fin no acotado"} · Declarado por ti
              </p>
              {canEdit && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setForm(`metric:${m.key}`)}
                >
                  Corregir definición
                </Button>
              )}
            </div>
          ))}
          {!metrics.length && (
            <p className="text-sm text-muted-foreground">
              Todavía no has definido métricas aquí. Las definiciones guardadas
              en la memoria del negocio también se consultan, respetando su
              ámbito y periodo.
            </p>
          )}
        </section>
        {canEdit && (
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setEdge("");
                setForm("relation");
              }}
            >
              <Plus />
              Añadir relación
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setForm("metric:")}
            >
              <Plus />
              Definir métrica
            </Button>
          </div>
        )}
        {form && canEdit && (
          <div
            className="space-y-3 border-t pt-5"
            key={`${form}/${selected}/${edge}`}
          >
            <p className="text-sm text-muted-foreground">
              Se guardará una nueva revisión. Los informes que usaban este
              modelo quedarán pendientes de revisar.
            </p>
            {form === "table" && table && (
              <TableForm table={table} save={save} busy={action.busy} />
            )}{" "}
            {form === "relation" && (
              <RelationForm
                tables={tables}
                relation={relation}
                save={save}
                busy={action.busy}
              />
            )}{" "}
            {form.startsWith("metric:") && (
              <MetricForm
                tables={tables}
                metric={metrics.find((m) => m.key === form.slice(7))}
                save={save}
                busy={action.busy}
              />
            )}
            <Button variant="ghost" size="sm" onClick={() => setForm("")}>
              Cancelar
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function ERDiagram({
  tables,
  relations,
  selected,
  edge,
  chooseTable,
  chooseEdge,
}: {
  tables: Table[];
  relations: Relation[];
  selected: string;
  edge: string;
  chooseTable: (id: string) => void;
  chooseEdge: (id: string) => void;
}) {
  const marker = useId();
  const positions = new Map(
    tables.map((t, i) => [
      t.id,
      { x: 30 + (i % 3) * 310, y: 40 + Math.floor(i / 3) * 150 },
    ]),
  );
  const links = relations.filter(
    (r) => positions.has(r.source) && positions.has(r.target),
  );
  return (
    <div
      className="min-w-0 w-full overflow-x-auto rounded-xl border bg-muted/20"
      style={{ contain: "inline-size" }}
    >
      <svg
        role="group"
        aria-label="Diagrama ER de esta revisión del modelo"
        viewBox={`0 0 960 ${Math.max(210, Math.ceil(tables.length / 3) * 150 + 60)}`}
        className="min-w-[640px] w-full"
      >
        <defs>
          <marker
            id={marker}
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
          </marker>
        </defs>
        {links.map((r, i) => {
          const a = positions.get(r.source)!,
            b = positions.get(r.target)!,
            y = 15 + (i % 4) * 5;
          return (
            <g
              key={r.id}
              role="button"
              tabIndex={0}
              aria-label={`Relación ${tables.find((t) => t.id === r.source)!.name} con ${tables.find((t) => t.id === r.target)!.name}`}
              onClick={() => chooseEdge(r.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  chooseEdge(r.id);
                }
              }}
              className="cursor-pointer text-primary"
            >
              <title>
                {cardinalities[r.cardinality]} · {labels[r.semantic_status]}
              </title>
              <path
                d={`M ${a.x + 120} ${a.y} C ${a.x + 120} ${a.y - y - 25}, ${b.x + 120} ${b.y - y - 25}, ${b.x + 120} ${b.y}`}
                fill="none"
                stroke="currentColor"
                strokeWidth={edge === r.id ? 4 : 2}
                strokeDasharray={
                  r.semantic_status === "confirmed" ? undefined : "6 4"
                }
                opacity={r.semantic_status === "rejected" ? 0.3 : 0.75}
                markerEnd={`url(#${marker})`}
              />
              <path
                d={`M ${a.x + 120} ${a.y} C ${a.x + 120} ${a.y - y - 25}, ${b.x + 120} ${b.y - y - 25}, ${b.x + 120} ${b.y}`}
                fill="none"
                stroke="transparent"
                strokeWidth="14"
              />
            </g>
          );
        })}
        {tables.map((t) => {
          const p = positions.get(t.id)!;
          return (
            <g
              key={t.id}
              role="button"
              tabIndex={0}
              aria-label={`Tabla ${t.name}`}
              onClick={() => chooseTable(t.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  chooseTable(t.id);
                }
              }}
              className="cursor-pointer"
            >
              <rect
                x={p.x}
                y={p.y}
                width="270"
                height="94"
                rx="12"
                className="fill-background stroke-border"
                style={{
                  stroke: selected === t.id ? "var(--primary)" : undefined,
                  strokeWidth: selected === t.id ? 3 : 1,
                }}
              />
              <text
                x={p.x + 14}
                y={p.y + 30}
                className="fill-foreground"
                fontSize="13"
                fontWeight="600"
              >
                {t.name.length > 32 ? t.name.slice(0, 29) + "…" : t.name}
              </text>
              <text
                x={p.x + 14}
                y={p.y + 52}
                className="fill-muted-foreground"
                fontSize="12"
              >
                {t.row_count.toLocaleString()} filas · {t.columns.length}{" "}
                columnas
              </text>
              <text
                x={p.x + 14}
                y={p.y + 75}
                className="fill-muted-foreground"
                fontSize="11"
              >
                {t.grain
                  ? "Granularidad declarada"
                  : "Granularidad por confirmar"}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="p-3 text-xs text-muted-foreground">
        Flecha: origen → destino. Línea discontinua: significado pendiente o
        descartado. Selecciona una conexión para ver su cardinalidad y
        comprobaciones.
      </p>
    </div>
  );
}

function TableForm({
  table,
  save,
  busy,
}: {
  table: Table;
  save: Save;
  busy: boolean;
}) {
  const [description, setDescription] = useState(table.description),
    [grain, setGrain] = useState(table.grain),
    [column, setColumn] = useState(table.columns[0]?.name || ""),
    [columns, setColumns] = useState(table.columns),
    [keys, setKeys] = useState(table.declared_keys.map((k) => k.columns));
  const c = columns.find((c) => c.name === column);
  const edit = (key: string, value: string) =>
    setColumns(
      columns.map((c) => (c.name === column ? { ...c, [key]: value } : c)),
    );
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        void save("table", {
          id: table.id,
          description,
          grain,
          columns: columns
            .filter(
              (c, i) =>
                c.meaning !== table.columns[i].meaning ||
                c.unit !== table.columns[i].unit ||
                c.conversion !== table.columns[i].conversion,
            )
            .map(({ name, meaning, unit, conversion }) => ({
              name,
              meaning,
              unit,
              conversion,
            })),
          declared_keys: keys,
        });
      }}
    >
      <Field label="Qué contiene esta tabla">
        <Textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={2000}
        />
      </Field>
      <Field label="Qué representa cada fila">
        <Input
          value={grain}
          onChange={(e) => setGrain(e.target.value)}
          maxLength={2000}
          placeholder="Por ejemplo: una línea de una factura"
        />
      </Field>
      <Field label="Columna a aclarar">
        <select
          className={selectClass}
          value={column}
          onChange={(e) => setColumn(e.target.value)}
        >
          {columns.map((c) => (
            <option key={c.name}>{c.name}</option>
          ))}
        </select>
      </Field>
      {c && (
        <>
          <Field label="Significado de la columna">
            <Input
              value={c.meaning}
              onChange={(e) => edit("meaning", e.target.value)}
            />
          </Field>
          <Field label="Unidad">
            <Input
              value={c.unit}
              onChange={(e) => edit("unit", e.target.value)}
              placeholder="EUR, unidades…"
            />
          </Field>
          <Field label="Conversión necesaria, si existe">
            <Input
              value={c.conversion}
              onChange={(e) => edit("conversion", e.target.value)}
              placeholder="Describe la regla; no se ejecutará automáticamente"
            />
          </Field>
        </>
      )}
      <Disclosure title="Claves compuestas o declaradas">
        {keys.map((key, i) => (
          <div key={i} className="space-y-2 py-2">
            <ColumnsSelect
              columns={table.columns}
              value={key}
              onChange={(next) =>
                setKeys(keys.map((k, j) => (i === j ? next : k)))
              }
            />
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setKeys(keys.filter((_, j) => j !== i))}
            >
              Quitar clave
            </Button>
          </div>
        ))}
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => setKeys([...keys, []])}
        >
          Añadir clave
        </Button>
      </Disclosure>
      <Button disabled={busy} type="submit">
        Guardar aclaraciones
      </Button>
    </form>
  );
}
function ColumnsSelect({
  columns,
  value,
  onChange,
}: {
  columns: Column[];
  value: string[];
  onChange: (v: string[]) => void;
}) {
  return (
    <div className="flex flex-wrap gap-3">
      {columns.map((c) => (
        <label className="flex items-center gap-1 text-sm" key={c.name}>
          <input
            type="checkbox"
            checked={value.includes(c.name)}
            onChange={(e) =>
              onChange(
                e.target.checked
                  ? [...value, c.name]
                  : value.filter((v) => v !== c.name),
              )
            }
          />
          {c.name}
        </label>
      ))}
      <span className="w-full text-xs text-muted-foreground">
        Orden de la clave: {value.join(" + ") || "selecciona columnas"}
      </span>
    </div>
  );
}
function RelationForm({
  tables,
  relation,
  save,
  busy,
}: {
  tables: Table[];
  relation?: Relation;
  save: Save;
  busy: boolean;
}) {
  const [source, setSource] = useState(relation?.source || tables[0]?.id || ""),
    [target, setTarget] = useState(
      relation?.target || tables[1]?.id || tables[0]?.id || "",
    ),
    [sc, setSc] = useState(relation?.source_columns || []),
    [tc, setTc] = useState(relation?.target_columns || []),
    [description, setDescription] = useState(relation?.description || ""),
    [status, setStatus] = useState(relation?.semantic_status || "proposed");
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        void save("relation", {
          source,
          target,
          source_columns: sc,
          target_columns: tc,
          description,
          semantic_status: status,
        });
      }}
    >
      <Field label="Tabla de origen">
        <select
          className={selectClass}
          value={source}
          onChange={(e) => {
            setSource(e.target.value);
            setSc([]);
          }}
        >
          {tables.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </Field>
      <ColumnsSelect
        columns={tables.find((t) => t.id === source)?.columns || []}
        value={sc}
        onChange={setSc}
      />
      <Field label="Tabla de destino">
        <select
          className={selectClass}
          value={target}
          onChange={(e) => {
            setTarget(e.target.value);
            setTc([]);
          }}
        >
          {tables.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </Field>
      <ColumnsSelect
        columns={tables.find((t) => t.id === target)?.columns || []}
        value={tc}
        onChange={setTc}
      />
      <p className="text-xs text-muted-foreground">
        Las columnas se emparejan en el orden seleccionado. Se comprobarán todas
        las filas, también en claves compuestas.
      </p>
      <Field label="Qué significa esta relación">
        <Textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={2000}
        />
      </Field>
      <Field label="Estado del significado">
        <select
          className={selectClass}
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          {Object.entries(labels).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </Field>
      <Button disabled={busy || !sc.length || sc.length !== tc.length}>
        Comprobar y guardar relación
      </Button>
    </form>
  );
}
function MetricForm({
  tables,
  metric,
  save,
  busy,
}: {
  tables: Table[];
  metric?: Metric;
  save: Save;
  busy: boolean;
}) {
  const [name, setName] = useState(metric?.name || ""),
    [definition, setDefinition] = useState(metric?.definition || ""),
    [unit, setUnit] = useState(metric?.unit || ""),
    [ids, setIds] = useState(metric?.table_ids || []),
    [from, setFrom] = useState(metric?.period.from || ""),
    [until, setUntil] = useState(metric?.period.until || "");
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        void save("metric", {
          key: metric?.key || crypto.randomUUID(),
          name,
          definition,
          unit,
          table_ids: ids,
          period_from: from || null,
          period_until: until || null,
        });
      }}
    >
      <Field label="Nombre de la métrica">
        <Input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={180}
        />
      </Field>
      <Field label="Cómo se define y calcula">
        <Textarea
          required
          value={definition}
          onChange={(e) => setDefinition(e.target.value)}
          maxLength={4000}
          placeholder="Por ejemplo: ventas netas = importe de línea menos impuestos; incluye devoluciones con su signo."
        />
      </Field>
      <Field label="Unidad">
        <Input
          value={unit}
          onChange={(e) => setUnit(e.target.value)}
          maxLength={180}
        />
      </Field>
      <fieldset className="space-y-2">
        <legend className="text-sm">Tablas a las que aplica</legend>
        {tables.map((t) => (
          <label key={t.id} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={ids.includes(t.id)}
              onChange={(e) =>
                setIds(
                  e.target.checked
                    ? [...ids, t.id]
                    : ids.filter((id) => id !== t.id),
                )
              }
            />
            {t.name}
          </label>
        ))}
      </fieldset>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Desde (opcional)">
          <Input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </Field>
        <Field label="Hasta (opcional)">
          <Input
            type="date"
            value={until}
            onChange={(e) => setUntil(e.target.value)}
          />
        </Field>
      </div>
      <Button disabled={busy || !ids.length}>Guardar definición</Button>
    </form>
  );
}
