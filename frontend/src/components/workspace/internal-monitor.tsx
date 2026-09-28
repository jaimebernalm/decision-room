import { InvestigationDetail } from "./investigation-detail";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, LogOut, RefreshCw, ChevronRight } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAction, useResource } from "@/lib/hooks";
import { useActivity, clearActivityCache } from "@/lib/activity";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loading, Notice } from "./shared";

type Process = { id:string; business:string; business_id:string; title:string; goal:string; status:string; created_at:string };
const roles: Record<string,string> = { chat:"Conversacional",planning:"Planificación",data_discovery:"Analista de relaciones",business_planner:"Planificador de negocio",research:"Analista principal",subanalyst:"Subanalista",analyst_review:"Redacción del informe",reviewer:"Revisor",chat_reviewer:"Revisor del chat" };
const activeStates = new Set(["running","queued","retry_wait","waiting_owner","waiting_dependency"]);
const statuses: Record<string,string> = { queued:"En cola",running:"Trabajando",completed:"Terminado",waiting:"Esperando al cliente",waiting_owner:"Esperando al cliente",waiting_dependency:"Esperando resultados",retry_wait:"Esperando al proveedor",failed:"Necesita atención",blocked:"Bloqueado",interrupted:"Interrumpido",superseded:"Contexto anterior",stale:"Contexto anterior" };
export function InternalMonitor({ route }: { route:string }) {
  const session = useResource<{ authorized:boolean }>("/api/internal/session");
  const [key,setKey] = useState("");
  const [loginError,setLoginError] = useState("");
  const action = useAction();
  const trace = route.split("/")[2];
  return <main className="min-h-screen bg-background p-4 text-foreground md:p-8">
    <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div><p className="text-xs uppercase tracking-widest text-muted-foreground">Decision Room · Uso interno</p><h1 className="mt-1 text-2xl font-semibold">Monitor de investigación</h1></div>
      <div className="flex gap-2"><Button variant="ghost" asChild><a href="#home">Abrir plataforma</a></Button>{session.data && <Button variant="outline" onClick={() => void action.run(async () => { await api('/api/internal/logout',{});clearActivityCache();session.refresh(); })}><LogOut />Cerrar sesión interna</Button>}</div>
    </header>
    {!session.data ? <div className="mx-auto max-w-md">
      {!session.error ? <Loading /> : <Card><CardHeader><CardTitle>Acceso interno</CardTitle></CardHeader><CardContent>
        <p className="mb-4 text-sm text-muted-foreground">Introduce la clave interna del monitor. El servidor debe estar iniciado con el monitor habilitado.</p>
        <form onSubmit={(e) => { e.preventDefault();void action.run(async () => { try { await api('/api/internal/login',{token:key});setKey('');setLoginError('');session.refresh(); } catch(error) {setLoginError((error as Error).message);} }); }}>
          <label className="mb-2 block text-sm" htmlFor="internal-key">Clave interna</label><Input id="internal-key" type="password" value={key} onChange={(e) => setKey(e.target.value)} autoComplete="off" />
          <Notice error>{loginError || action.error}</Notice><Button className="mt-4" disabled={!key || action.busy}>Entrar al monitor</Button>
        </form>
      </CardContent></Card>}
    </div> : trace ? <Investigation key={trace} trace={trace} onUnauthorized={session.refresh} /> : <Processes onUnauthorized={session.refresh} />}
  </main>;
}
function Processes({ onUnauthorized }: { onUnauthorized:()=>void }) {
  const [business,setBusiness] = useState("");const [status,setStatus] = useState("");const [offset,setOffset] = useState(0);const [previous,setPrevious] = useState<number[]>([]);
  const params = new URLSearchParams({offset:String(offset)});if (business) params.set('business_id',business);if (status) params.set('status',status);
  const data = useResource<{items:Process[];has_more:boolean;next_offset:number;businesses?:{id:string;name:string}[]}>(`/api/internal/investigations?${params}`,5000);
  useEffect(() => { if ([401,403].includes(data.errorStatus || 0)) { clearActivityCache();onUnauthorized(); } },[data.errorStatus,onUnauthorized]);
  const [choices,setChoices] = useState<Map<string,string>>(new Map());
  const combined = new Map(choices);data.data?.items.forEach((p) => combined.set(p.business_id,p.business));
  data.data?.businesses?.forEach((b) => combined.set(b.id,b.name));
  return <>
    <div className="mb-5 flex flex-wrap items-end gap-3">
      <label className="text-sm">Negocio<select className="ml-2 rounded-md border bg-background p-2" aria-label="Filtrar negocio" value={business} onChange={(e) => {setChoices(combined);setBusiness(e.target.value);setOffset(0);setPrevious([]);}}><option value="">Todos</option>{[...combined].map(([id,name]) => <option key={id} value={id}>{name}</option>)}</select></label>
      <label className="text-sm">Estado<select className="ml-2 rounded-md border bg-background p-2" aria-label="Filtrar estado" value={status} onChange={(e) => {setStatus(e.target.value);setOffset(0);setPrevious([]);}}><option value="">Todos</option>{Object.entries(statuses).map(([id,name]) => <option key={id} value={id}>{name}</option>)}</select></label>
      <Button size="sm" variant="outline" onClick={data.refresh}><RefreshCw />Actualizar</Button>
    </div>
    <Notice error>{data.error}</Notice>{!data.data && !data.error && <Loading />}
    <div className="grid gap-3">{data.data?.items.map((p) => <a className="rounded-xl border p-4 transition-colors hover:bg-muted" key={p.id} href={`#internal/investigations/${p.id}`}>
      <div className="flex flex-wrap justify-between gap-2"><p className="font-medium">{p.title}</p><Badge variant="outline">{statuses[p.status] || p.status}</Badge></div>
      <p className="mt-1 text-sm text-muted-foreground">{p.business} · {new Date(p.created_at).toLocaleString()}</p>{p.goal && <p className="mt-2 line-clamp-2 text-sm">{p.goal}</p>}
    </a>)}</div>
    {data.data && !data.data.items.length && <p className="text-muted-foreground">No hay procesos en esta página con los filtros elegidos.</p>}
    <div className="mt-4 flex gap-2"><Button variant="ghost" disabled={!previous.length} onClick={() => {setOffset(previous.at(-1) || 0);setPrevious(previous.slice(0,-1));}}>Anterior</Button><Button variant="ghost" disabled={!data.data?.has_more} onClick={() => {setPrevious([...previous,offset]);setOffset(data.data?.next_offset || 0);}}>Siguiente</Button></div>
  </>;
}
function Investigation({ trace,onUnauthorized }: { trace:string;onUnauthorized:()=>void }) {
  const base = `/api/internal/investigations/${trace}`;
  const activity = useActivity(base,trace,true);const data = activity.data;
  useEffect(() => { if ([401,403].includes(activity.errorStatus || 0)) { clearActivityCache();onUnauthorized(); } },[activity.errorStatus,onUnauthorized]);
  const [actor,setActor] = useState("");const [phase,setPhase] = useState("");const [errorsOnly,setErrorsOnly] = useState(false);const [selected,setSelected] = useState<string | null>(null);
  const [detail,setDetail] = useState<{content:unknown;truncated:boolean} | null>(null);const [detailError,setDetailError] = useState("");
  const action = useAction();
  const detailPanel=useRef<HTMLElement>(null);
  const [selectedEvent,setSelectedEvent] = useState<string | null>(null);
  const actors = new Map<string,{role:string;status:string;assignmentLabel?:string;taskIds:Set<string>;parents:Set<string>}>();
  const taskActor = new Map(data?.actors?.map((a) => [a.task_id,a.id]));
  data?.actors?.forEach((a) => {
    const old=actors.get(a.id);const parent=a.parent_id ? taskActor.get(a.parent_id) : null;
    if (!old) actors.set(a.id,{role:a.role,status:a.status,assignmentLabel:a.assignment_label || undefined,taskIds:new Set([a.task_id]),parents:new Set(parent && parent!==a.id ? [parent] : [])});
    else {if (a.assignment_label) old.assignmentLabel=a.assignment_label;old.taskIds.add(a.task_id);if (parent && parent!==a.id) old.parents.add(parent);if (activeStates.has(a.status) || !activeStates.has(old.status)) old.status=a.status;}
  });
  const subanalysts = [...actors].filter(([,a]) => a.role==='subanalyst').map(([id]) => id);
  const tasks = new Map(activity.tasks.map((t) => [t.id,t]));
  const labels:Record<string,string>={branch:'Investigaciones delegadas',call:'Llamadas de agentes',execution:'Cálculos',planner_consult:'Consultas al planificador',planning:'Planificación',plan:'Alcance',research:'Investigación',research_step:'Pasos de investigación',review:'Revisión',review_step:'Pasos de revisión',transport:'Peticiones al proveedor',job:'Informe',turn:'Turno',chat_call:'Preparación de respuesta',chat_review:'Revisión de respuesta',context:'Cambios de contexto',discovery:'Relaciones de datos',inspection:'Archivos',data_model:'Modelo de datos',question:'Preguntas al cliente'};
  const phases = [...new Set(activity.tasks.map((t) => t.kind))].sort();
  const events = activity.events.filter((e) => (!actor || actors.get(actor)?.taskIds.has(e.task_id)) && (!phase || tasks.get(e.task_id)?.kind===phase) && (!errorsOnly || ['failed','interrupted','retry_wait'].includes(e.status)));
  async function select(taskId:string,eventId:string) {
    if (action.busy) return;
    setSelected(taskId);setSelectedEvent(eventId);setDetail(null);setDetailError('');
    await action.run(async () => {try {const result=await api<{content:unknown;truncated:boolean}>(`${base}/tasks/${taskId}?event_id=${encodeURIComponent(eventId)}`);setDetail(result);if (window.matchMedia('(max-width: 1023px)').matches) detailPanel.current?.scrollIntoView({behavior:'smooth',block:'start'});} catch(error) {if (error instanceof ApiError && error.status===401) onUnauthorized();setDetailError((error as Error).message);}});
  }
  return <>
    <Button asChild variant="ghost" className="mb-4"><a href="#internal/investigations"><ArrowLeft />Todos los procesos</a></Button>
    <Notice error>{activity.error}</Notice>{!data && !activity.error && <Loading />}
    {data && <>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-medium">{data.title || data.business}</h2><p className="mt-1 text-sm text-muted-foreground">{data.title ? data.business : null}</p>{data.goal && <p className="mt-2 max-w-3xl text-sm">{data.goal}</p>}<p className="mt-1 text-sm text-muted-foreground" aria-live="polite">{data.headline}</p></div><Button size="sm" variant="outline" onClick={() => void activity.refresh()}><RefreshCw />Actualizar</Button></div>
      {data.context_notice && <Notice>{data.context_notice}</Notice>}
      {!data.history_complete && <Notice>El historial contiene una interrupción de captura; los eventos reconstruidos están identificados.</Notice>}
      {data.worker_health==='unconfirmed' && !data.terminal && <Notice>Worker sin actualización: interrupción por confirmar.</Notice>}
      {data.resources && <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        {[["Tiempo transcurrido",`${data.resources.wall_seconds.toFixed(1)} s`],["Llamadas / intentos HTTP",`${data.resources.logical_calls} / ${data.resources.http_attempts}`],["Cálculos / reutilizaciones",`${data.resources.executions} / ${data.resources.cache_hits}`],["Tokens conocidos",`${data.resources.input_tokens ?? '—'} entrada · ${data.resources.output_tokens ?? '—'} salida`]].map(([label,value]) => <div key={label} className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 break-words text-sm font-medium">{value}</p></div>)}
        <p className="col-span-full text-xs text-muted-foreground">Incluye pausas y reintentos. Espera del cliente: {data.resources.owner_wait_seconds.toFixed(1)} s · Espera del proveedor: {data.resources.provider_wait_seconds.toFixed(1)} s · Uso desconocido en {data.resources.unknown_usage_calls} llamadas · Intentos HTTP sin registro en {data.resources.unknown_http_calls || 0} llamadas · Coste monetario no calculado</p>
      </div>}
      <section aria-label="Mapa de agentes" className="mb-6 rounded-xl border p-4">
        <h3 className="mb-3 font-medium">Agentes participantes</h3><div className="flex flex-wrap gap-3">
          {[...actors].map(([id,a]) => <button key={id} className={`min-w-40 rounded-lg border p-3 text-left text-sm ${actor===id ? 'border-primary bg-primary/5' : 'hover:bg-muted'}`} onClick={() => setActor(actor===id ? '' : id)}>
            <p className="font-medium">{roles[a.role] || a.role}{a.role==='subanalyst' ? ` · ${subanalysts.indexOf(id)+1}` : ''}</p><p className="mt-1 text-xs text-muted-foreground">{statuses[a.status] || a.status}</p>
            {a.role==='subanalyst' && <p className="mt-2 max-w-64 text-xs">{a.assignmentLabel || [...a.taskIds].map((id)=>tasks.get(id)).find((t)=>t?.kind==='branch')?.text}</p>}
            {[...a.parents].map((parent) => <p key={parent} className="mt-2 flex items-center gap-1 text-xs text-muted-foreground"><ChevronRight className="size-3" />Encargo de {roles[actors.get(parent)?.role || ''] || 'otro agente'}</p>)}
          </button>)}
        </div>
      </section>
      <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section className="min-w-0 rounded-xl border p-4" aria-label="Cronología de investigación">
          <div className="mb-4 flex flex-wrap justify-between gap-3"><h3 className="font-medium">Cronología</h3><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={errorsOnly} onChange={(e) => setErrorsOnly(e.target.checked)} />Errores y esperas</label></div>
          <label className="mb-3 block text-sm">Tipo de actividad<select aria-label="Filtrar tipo de actividad" className="ml-2 rounded-md border bg-background p-1" value={phase} onChange={(e) => setPhase(e.target.value)}><option value="">Todos</option>{phases.map((kind) => <option key={kind} value={kind}>{labels[kind] || kind}</option>)}</select></label>
          {actor && <Button variant="ghost" size="sm" onClick={() => setActor('')}>Ver todos los agentes</Button>}
          {data.previous_cursor && <Button variant="outline" size="sm" disabled={activity.loadingOlder} onClick={() => void activity.loadOlder()}>Cargar eventos anteriores</Button>}
          <ol className="mt-3 max-h-[65vh] space-y-1 overflow-auto" aria-label="Eventos registrados">
            {events.map((e) => <li key={e.id}><button onClick={() => void select(e.task_id,e.id)} className={`w-full rounded-md px-3 py-2 text-left text-sm ${selectedEvent===e.id ? 'bg-primary/10' : 'hover:bg-muted'}`}>
              <span className="mr-2 text-xs text-muted-foreground">#{e.sequence} · {new Date(e.recorded_at).toLocaleTimeString()}</span><span>{e.text || tasks.get(e.task_id)?.text || e.type}</span>
              <span className="mt-1 block text-xs text-muted-foreground">{statuses[e.status] || e.status} · {e.type}{e.reconstructed ? ' · Reconstruido desde el registro' : ''}</span>
            </button></li>)}
          </ol>
        </section>
        <section ref={detailPanel} className="min-w-0 rounded-xl border p-4 lg:max-h-[85vh] lg:overflow-auto" aria-label="Detalle de actividad"><h3 className="mb-3 font-medium">Encargo, intercambio y evidencia</h3>
          {!selected && <p className="text-sm text-muted-foreground">Selecciona un evento para abrir sus entradas, resultados y referencias.</p>}
          <Notice error>{detailError || action.error}</Notice>{selected && !detail && !detailError && <Loading />}
          {detail?.truncated && <p className="mb-3 text-xs text-muted-foreground">Vista acotada: contenido truncado.</p>}
          {detail && <InvestigationDetail key={selectedEvent} content={detail.content}/>}
        </section>
      </div>
    </>}
  </>;
}
