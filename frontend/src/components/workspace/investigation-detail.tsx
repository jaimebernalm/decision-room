import { translate as tr, useLanguage, locale } from "@/lib/i18n";
import { useState } from "react";

type RecordValue = Record<string, unknown>;
function record(value: unknown): RecordValue {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as RecordValue)
    : {};
}
const names: Record<string, string> = {
  action: "Decisión",
  summary: "Resumen",
  synthesis: "Síntesis",
  rationale: "Justificación",
  instructions: "Siguientes pasos",
  question: "Pregunta",
  text: "Mensaje",
  statement: "Observación",
  objective: "Objetivo",
  decision: "Decisión que se quiere tomar",
  assumptions: "Supuestos",
  exclusions: "Fuera del alcance",
  deliverables: "Entrega prevista",
  known_context: "Contexto disponible",
  brief: "Encargo",
  findings: "Hallazgos",
  report: "Informe propuesto",
  claims: "Conclusiones propuestas",
  title: "Título",
  method: "Método",
  limitations: "Limitaciones",
  reason: "Motivo",
  issues: "Objeciones",
  approved: "Aprobada",
  evidence: "Evidencia",
  metrics: "Medidas",
  notes: "Observaciones",
  operation: "Comprobación",
  metric: "Medida",
  value: "Valor",
  label: "Nombre",
  owner: "Usuario",
  assistant: "Asistente",
  message: "Mensaje",
  draft: "Borrador",
  assignment: "Encargo de la rama",
  output: "Resultado",
  status: "Estado",
};
function Value({ value, depth = 0 }: { value: unknown; depth?: number }) {
  useLanguage();
  if (value == null)
    return <span className="text-muted-foreground">{tr("No registrado")}</span>;
  if (typeof value === "boolean")
    return <span>{value ? tr("Sí") : tr("No")}</span>;
  if (typeof value !== "object")
    return (
      <span className="whitespace-pre-wrap break-words">{String(value)}</span>
    );
  if (depth > 5)
    return (
      <span className="text-muted-foreground">
        {tr("Consultar el detalle técnico.")}
      </span>
    );
  if (Array.isArray(value))
    return value.length ? (
      <ul className="space-y-2 border-l pl-3">
        {value.map((item, i) => (
          <li key={i}>
            <Value value={item} depth={depth + 1} />
          </li>
        ))}
      </ul>
    ) : (
      <span className="text-muted-foreground">{tr("Ninguna")}</span>
    );
  return (
    <dl className="space-y-3">
      {Object.entries(value).map(([key, item]) => (
        <div key={key}>
          <dt className="mb-1 text-xs font-medium text-muted-foreground">
            {tr(names[key] || key.replaceAll("_", " "))}
          </dt>
          <dd>
            <Value value={item} depth={depth + 1} />
          </dd>
        </div>
      ))}
    </dl>
  );
}
function Section({
  title,
  value,
  open = false,
}: {
  title: string;
  value: unknown;
  open?: boolean;
}) {
  if (value == null) return null;
  return (
    <details className="rounded-lg border p-3" open={open || undefined}>
      <summary className="cursor-pointer font-medium">{title}</summary>
      <div className="mt-3 text-sm">
        <Value value={value} />
      </div>
    </details>
  );
}
function time(value: unknown) {
  if (typeof value !== "string") return tr("No registrado");
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? value
    : date.toLocaleTimeString(locale());
}
export function InvestigationDetail({ content }: { content: unknown }) {
  useLanguage();
  const [raw, setRaw] = useState(false);
  const data = record(content),
    task = record(data.task),
    event = record(data.selected_event);
  const payload = record(event.payload),
    call = record(data.call),
    inputs = record(call.inputs);
  const exchange = record(data.exchange),
    direction = record(exchange.direction || payload.direction);
  const output = call.output || payload.action;
  const execution = record(data.execution),
    result = record(execution.result);
  const research = record(data.research),
    source = record(data.source);
  const status = String(event.status || task.status || "");
  const statusLabels: Record<string, string> = {
    completed: tr("Terminado"),
    running: tr("En curso"),
    queued: tr("En cola"),
    failed: tr("Necesita atención"),
    interrupted: tr("Interrumpido"),
    superseded: tr("Contexto anterior"),
    waiting_owner: tr("Esperando respuesta"),
  };
  const analyst = exchange.analyst_message || inputs.analyst_message;
  const planner = Object.keys(direction).length
    ? direction
    : call.phase === "business_planner"
      ? record(output)
      : null;
  return (
    <div className="min-w-0 space-y-3">
      <div className="rounded-lg bg-muted/50 p-3">
        <p className="font-medium">
          {String(
            record(event.payload).activity_text ||
              task.text ||
              tr("Actividad seleccionada"),
          )}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          {event.sequence != null
            ? tr("Evento {0} · ", { "0": event.sequence })
            : ""}
          {statusLabels[status] || status}
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          {tr("Inicio de la tarea: ")}
          {time(task.started_at)}
          {tr(" · Fin: ")}
          {time(task.finished_at)}
        </p>
        {event.reconstructed === true && (
          <p className="mt-1 text-xs text-muted-foreground">
            {tr("Evento reconstruido a partir de los registros guardados.")}
          </p>
        )}
      </div>
      {data.exchange != null && analyst == null && (
        <p className="text-sm text-muted-foreground">
          {tr(
            "Consulta automática del planificador; no hay un mensaje explícito del analista guardado para este paso.",
          )}
        </p>
      )}
      <Section title={tr("Analista → Planificador")} value={analyst} open />
      {planner && (
        <div className="rounded-lg border p-3 text-sm">
          <h4 className="font-medium">{tr("Decisión del planificador")}</h4>
          {planner.rationale != null && (
            <p className="mt-2 whitespace-pre-wrap">
              {String(planner.rationale)}
            </p>
          )}
          <div className="mt-3">
            <Value value={planner.instructions || planner.action} />
          </div>
          <Section title={tr("Encargo y alcance")} value={planner.brief} />
          <Section
            title={tr("Pregunta al cliente")}
            value={planner.question}
            open
          />
        </div>
      )}
      <Section title={tr("Pregunta del usuario")} value={inputs.message} open />
      <Section
        title={tr("Encargo de la investigación")}
        value={source.question || research.assignment || inputs.assignment}
        open
      />
      <Section
        title={tr("Contexto de esta llamada")}
        value={inputs.plan || inputs.findings || inputs.conversation}
      />
      <Section title={tr("Borrador revisado")} value={inputs.draft} />
      {!planner && (
        <Section
          title={
            source.kind === "chat_review"
              ? tr("Resultado de la revisión")
              : tr("Resultado y decisión")
          }
          value={output}
          open
        />
      )}
      <Section
        title={tr("Medidas calculadas")}
        value={result.metrics || data.metrics}
        open
      />
      <Section
        title={tr("Observaciones del cálculo")}
        value={result.notes}
        open
      />
      <Section title={tr("Evidencia del cálculo")} value={result.evidence} />
      <Section title={tr("Series calculadas")} value={result.series} />
      <Section
        title={tr("Relaciones entre tablas")}
        value={record(data.discovery).output}
      />
      <Section title={tr("Motivo del cambio")} value={payload.reason} open />
      {typeof data.code === "string" && (
        <details className="rounded-lg border p-3">
          <summary className="cursor-pointer font-medium">
            {tr("Código ejecutado")}
          </summary>
          <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words text-xs">
            {data.code}
          </pre>
        </details>
      )}
      <Section title={tr("Uso de esta llamada")} value={call.usage} />
      <button
        type="button"
        className="text-xs text-muted-foreground underline"
        aria-expanded={raw}
        onClick={() => setRaw(!raw)}
      >
        {raw ? tr("Ocultar JSON técnico") : tr("Ver JSON técnico")}
      </button>
      {raw && (
        <pre className="max-h-[55vh] overflow-auto whitespace-pre-wrap break-words rounded-lg bg-muted p-3 text-xs">
          {JSON.stringify(content, null, 2)}
        </pre>
      )}
    </div>
  );
}
