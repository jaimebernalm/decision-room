import { useState } from "react";
import { Check, ChevronDown, Circle, CircleAlert, LoaderCircle, Pause, Database } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useActivity, type ActivityTask } from "@/lib/activity";
import { DataPreview } from "./data-preview";
const openStates = new Map<string,boolean>();
const waiting = new Set(["waiting_owner","waiting_dependency","retry_wait"]);
function Icon({ status }: { status: string }) {
  if (status === "completed") return <Check className="size-3.5" aria-hidden />;
  if (["failed","interrupted","superseded"].includes(status)) return <CircleAlert className="size-3.5" aria-hidden />;
  if (waiting.has(status)) return <Pause className="size-3.5" aria-hidden />;
  if (status === "running") return <LoaderCircle className="size-3.5 motion-safe:animate-spin" aria-hidden />;
  return <Circle className="size-3.5" aria-hidden />;
}
const labels: Record<string,string> = { completed: "Completado", running: "En curso", queued: "En cola", waiting_owner: "Esperando tu respuesta", waiting_dependency: "Esperando resultados", retry_wait: "Esperando al proveedor", failed: "Necesita atención", interrupted: "Interrumpido", superseded: "Contexto anterior" };
export function AnalysisActivity({ endpoint, traceId, fallback = "Preparando el análisis…", onQuestion }: { endpoint: string; traceId?: string | null; fallback?: string; onQuestion?:(id:string)=>void }) {
  const activity = useActivity(endpoint,traceId);
  const key = traceId || endpoint;
  const [open,setOpen] = useState(() => openStates.get(key) || false);
  const [selected,setSelected] = useState<ActivityTask | null>(null);
  const data = activity.data;
  const headline = data?.headline || fallback;
  const tasks = activity.tasks.filter((t) => !["job","turn","call","chat_call","chat_review","research_step","transport"].includes(t.kind));
  return <div id={data?.trace_id ? `activity-${data.trace_id}` : undefined} className="my-3 min-w-0 text-sm">
    <Collapsible open={open} onOpenChange={(value) => { setOpen(value); openStates.set(key,value); if (value) void activity.refresh(); }}>
      <CollapsibleTrigger className="flex max-w-full items-center gap-2 rounded-md py-1.5 text-left text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring">
        <Icon status={data?.terminal ? data.status === "completed" ? "completed" : "failed" : data?.status === "waiting" ? "waiting_owner" : "running"} />
        <span aria-live="polite" aria-atomic>{headline}</span>
        <ChevronDown className={`size-3.5 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2 space-y-2 border-l pl-4">
        {activity.error && <p className="text-xs text-muted-foreground">Reconectando con el progreso… <button className="underline" onClick={() => void activity.refresh()}>Actualizar</button></p>}
        {data?.worker_health === "unconfirmed" && !data.terminal && <p className="text-xs text-muted-foreground">Sin actualización del proceso. Estamos comprobando su estado.</p>}
        {data && !data.history_complete && <p className="text-xs text-muted-foreground">Parte del historial detallado no está disponible.</p>}
        {data?.previous_cursor && <Button size="sm" variant="ghost" disabled={activity.loadingOlder} onClick={() => void activity.loadOlder()}>Ver actividad anterior</Button>}
        <ol className="space-y-3" aria-label="Historial del análisis">
          {tasks.map((task) => <li key={task.id} className="flex items-start gap-2">
            <span className="mt-0.5 text-muted-foreground"><Icon status={task.status} /></span>
            <div className="min-w-0 flex-1">
              <p className="break-words">{task.text}</p>
              {task.purpose && <p className="mt-0.5 text-xs text-muted-foreground">{task.purpose}</p>}
              <span className="text-xs text-muted-foreground">{labels[task.status] || task.status}</span>
              {task.question_id && <Button type="button" variant="ghost" size="sm" className="ml-2 h-6 text-xs" onClick={() => {
                if (onQuestion) onQuestion(task.question_id!);
                else { const input=document.getElementById(`answer-${task.question_id}`);input?.scrollIntoView({block:'center'});input?.focus(); }
              }}>Responder pregunta</Button>}
              {task.references.length > 0 && task.data_endpoint && <Button type="button" variant="ghost" size="sm" className="ml-2 h-6 text-xs" onClick={() => setSelected(task)}><Database className="size-3" />Ver datos</Button>}
            </div>
          </li>)}
        </ol>
        {!tasks.length && <p className="text-xs text-muted-foreground">{data?.status === "historical" ? "Este análisis se creó antes de disponer del historial detallado." : "Las comprobaciones aparecerán aquí cuando se registren."}</p>}
      </CollapsibleContent>
    </Collapsible>
    <Sheet open={Boolean(selected)} onOpenChange={(value) => { if (!value) setSelected(null); }}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
        <SheetHeader><SheetTitle>Datos de esta comprobación</SheetTitle></SheetHeader>
        {selected?.data_endpoint && <div className="p-4"><DataPreview key={selected.id} endpoint={selected.data_endpoint} activity references={selected.references} /></div>}
      </SheetContent>
    </Sheet>
  </div>;
}
