import { translate as tr, useLanguage } from "@/lib/i18n";
import { useState } from "react";
import {
  Check,
  ChevronDown,
  Circle,
  CircleAlert,
  LoaderCircle,
  Pause,
  Database,
} from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  useActivity,
  compactChatActivity,
  type ActivityTask,
} from "@/lib/activity";
import { DataPreview } from "./data-preview";
const openStates = new Map<string, boolean>();
const waiting = new Set(["waiting_owner", "waiting_dependency", "retry_wait"]);
function Icon({ status }: { status: string }) {
  if (status === "completed") return <Check className="size-3.5" aria-hidden />;
  if (["failed", "interrupted", "superseded"].includes(status))
    return <CircleAlert className="size-3.5" aria-hidden />;
  if (waiting.has(status)) return <Pause className="size-3.5" aria-hidden />;
  if (status === "running")
    return (
      <LoaderCircle className="size-3.5 motion-safe:animate-spin" aria-hidden />
    );
  return <Circle className="size-3.5" aria-hidden />;
}
const labels: Record<string, string> = {
  completed: "Completado",
  running: "En curso",
  queued: "En cola",
  waiting_owner: "Esperando tu respuesta",
  waiting_dependency: "Esperando resultados",
  retry_wait: "Esperando al proveedor",
  failed: "Necesita atención",
  interrupted: "Interrumpido",
  superseded: "Contexto anterior",
};
export function AnalysisActivity({
  endpoint,
  traceId,
  fallback = tr("Preparando el análisis…"),
  revealing = false,
  responseReady = false,
  onQuestion,
}: {
  endpoint: string;
  traceId?: string | null;
  fallback?: string;
  revealing?: boolean;
  responseReady?: boolean;
  onQuestion?: (id: string) => void;
}) {
  useLanguage();
  const activity = useActivity(endpoint, traceId);
  const key = traceId || endpoint;
  const [open, setOpen] = useState(() => openStates.get(key) || false);
  const [selected, setSelected] = useState<ActivityTask | null>(null);
  const data = activity.data;
  const headline = revealing
    ? tr("Mostrando respuesta…")
    : responseReady
      ? tr("Respuesta lista · Ver proceso")
      : tr(data?.headline || fallback);
  const tasks = activity.tasks.filter(
    (t) =>
      !["job", "turn", "call", "research_step", "transport"].includes(t.kind),
  );
  const byId = new Map(activity.tasks.map((t) => [t.id, t]));
  function previousVersion(task: ActivityTask) {
    const seen = new Set<string>();
    let current: ActivityTask | undefined = task;
    while (current && !seen.has(current.id)) {
      if (current.status === "superseded") return true;
      seen.add(current.id);
      current = current.parent_id ? byId.get(current.parent_id) : undefined;
    }
    return false;
  }
  const currentTasks = compactChatActivity(
    tasks.filter((t) => !previousVersion(t)),
  );
  const previousTasks = tasks.filter(previousVersion);
  const taskRow = (task: ActivityTask) => (
    <li key={task.id} className="flex items-start gap-2">
      <span className="mt-0.5 text-muted-foreground">
        <Icon status={task.status} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="break-words">{tr(task.text)}</p>
        {task.purpose && (
          <p className="mt-0.5 text-xs text-muted-foreground">{task.purpose}</p>
        )}
        {task.status !== "completed" && (
          <span className="text-xs text-muted-foreground">
            {tr(labels[task.status] || task.status)}
          </span>
        )}
        {task.question_id && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="ml-2 h-6 text-xs"
            onClick={() => {
              if (onQuestion) onQuestion(task.question_id!);
              else {
                const input = document.getElementById(
                  `answer-${task.question_id}`,
                );
                input?.scrollIntoView({ block: "center" });
                input?.focus();
              }
            }}
          >
            {tr("Responder pregunta")}
          </Button>
        )}
        {task.references.length > 0 && task.data_endpoint && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="ml-2 h-6 text-xs"
            onClick={() => setSelected(task)}
          >
            <Database className="size-3" />
            {tr("Ver datos")}
          </Button>
        )}
      </div>
    </li>
  );
  return (
    <div
      id={data?.trace_id ? `activity-${data.trace_id}` : undefined}
      className="my-3 min-w-0 text-sm"
    >
      <Collapsible
        open={open}
        onOpenChange={(value) => {
          setOpen(value);
          openStates.set(key, value);
          if (value) void activity.refresh();
        }}
      >
        <CollapsibleTrigger className="flex max-w-full items-center gap-2 rounded-md py-1.5 text-left text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring">
          <Icon
            status={
              revealing
                ? "running"
                : responseReady
                  ? "completed"
                  : data?.terminal
                    ? data.status === "completed"
                      ? "completed"
                      : "failed"
                    : data?.status === "waiting"
                      ? "waiting_owner"
                      : "running"
            }
          />
          <span aria-live="polite" aria-atomic>
            {headline}
          </span>
          <ChevronDown
            className={`size-3.5 shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
            aria-hidden
          />
        </CollapsibleTrigger>
        {data?.context_notice && (
          <div className="mt-2 max-w-2xl rounded-lg border p-3 text-sm">
            <p>{data.context_notice}</p>
            {data.recovery_href && (
              <Button asChild variant="outline" size="sm" className="mt-3">
                <a href={data.recovery_href}>{tr("Actualizar el informe")}</a>
              </Button>
            )}
          </div>
        )}
        <CollapsibleContent className="mt-2 space-y-2 border-l pl-4">
          {activity.error && (
            <p className="text-xs text-muted-foreground">
              {tr("Reconectando con el progreso… ")}
              <button
                className="underline"
                onClick={() => void activity.refresh()}
              >
                {tr("Actualizar")}
              </button>
            </p>
          )}
          {data?.worker_health === "unconfirmed" && !data.terminal && (
            <p className="text-xs text-muted-foreground">
              {tr(
                "Sin actualización del proceso. Estamos comprobando su estado.",
              )}
            </p>
          )}
          {data && !data.history_complete && (
            <p className="text-xs text-muted-foreground">
              {tr("Parte del historial detallado no está disponible.")}
            </p>
          )}
          {data?.previous_cursor && (
            <Button
              size="sm"
              variant="ghost"
              disabled={activity.loadingOlder}
              onClick={() => void activity.loadOlder()}
            >
              {tr("Ver actividad anterior")}
            </Button>
          )}
          <ol className="space-y-3" aria-label={tr("Historial del análisis")}>
            {currentTasks.map(taskRow)}
          </ol>
          {previousTasks.length > 0 && (
            <details className="mt-4 text-muted-foreground">
              <summary className="cursor-pointer text-xs">
                {tr("Actividad de versiones anteriores (")}
                {previousTasks.length})
              </summary>
              <p className="my-3 text-xs">
                {tr(
                  "Este trabajo se conserva como historial; el informe actual utiliza la versión más reciente del contexto.",
                )}
              </p>
              <ol
                className="space-y-3"
                aria-label={tr("Historial de versiones anteriores")}
              >
                {previousTasks.map(taskRow)}
              </ol>
            </details>
          )}
          {!tasks.length && (
            <p className="text-xs text-muted-foreground">
              {data?.status === "historical"
                ? tr(
                    "Este análisis se creó antes de disponer del historial detallado.",
                  )
                : data?.terminal
                  ? tr(
                      "Este proceso ha terminado y no tiene más actividades para mostrar.",
                    )
                  : tr(
                      "Las comprobaciones aparecerán aquí cuando se registren.",
                    )}
            </p>
          )}
        </CollapsibleContent>
      </Collapsible>
      <Sheet
        open={Boolean(selected)}
        onOpenChange={(value) => {
          if (!value) setSelected(null);
        }}
      >
        <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
          <SheetHeader>
            <SheetTitle>{tr("Datos de esta comprobación")}</SheetTitle>
          </SheetHeader>
          {selected?.data_endpoint && (
            <div className="p-4">
              <DataPreview
                key={selected.id}
                endpoint={selected.data_endpoint}
                activity
                references={selected.references}
              />
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
