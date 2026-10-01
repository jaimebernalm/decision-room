import { translate as tr, useLanguage } from "@/lib/i18n";
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowRight, Check, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ReportView } from "@/components/workspace/report";
import { ChatPage } from "@/components/workspace/chat";
import { Busy, Field, Notice } from "@/components/workspace/shared";
import { useAction, useDraft, useResource } from "@/lib/hooks";
import { useWorkspace } from "@/lib/workspace";
import {
  api,
  store,
  selectedDataFiles,
  uploadFolder,
  FOLDER_LIMIT,
} from "@/lib/api";
import type {
  Business,
  ChatDetail,
  Dataset,
  Dossier,
  SetupSession,
  Job,
  Report as ReportData,
} from "@/lib/types";
import { EntryFrame } from "./welcome";

const goals = [
  ["discover", "Descubrir oportunidades y problemas"],
  ["organize", "Tener mis cifras organizadas"],
  ["evolution", "Entender cómo evoluciona el negocio"],
  ["question", "Resolver una pregunta concreta"],
  ["help", "Ayúdame a decidir por dónde empezar"],
];
const stages = [
  "Tu negocio",
  "Tu objetivo",
  "Tus datos",
  "El alcance",
  "Tu informe",
];

export function GuidedOnboarding({ business }: { business: Business }) {
  useLanguage();
  const resource = useResource<SetupSession | null>(
    "/api/onboarding/session",
    2000,
  );
  const { refresh } = useWorkspace();
  const refreshSession = resource.refresh;
  const [started, setStarted] = useState(false);
  const [startError, setStartError] = useState("");
  const attempt = useRef(0);
  const boot = useCallback(async () => {
    setStartError("");
    try {
      await api("/api/onboarding/start", { business_id: business.id });
      setStarted(true);
      refreshSession();
      refresh();
    } catch (e) {
      setStartError((e as Error).message);
    }
  }, [business.id, refreshSession, refresh]);
  useEffect(() => {
    if (!attempt.current++) void boot();
  }, [boot]); // start is idempotent on the server
  const state = resource.data;
  const stage = state
    ? { goal: 1, data: 2, scope: 3, report: 4, complete: 4 }[state.stage]
    : 1;
  return (
    <EntryFrame
      action={
        <Button asChild variant="ghost" size="sm">
          <a href="#businesses">{tr("Mis negocios")}</a>
        </Button>
      }
    >
      <div className="mx-auto flex w-full max-w-5xl flex-col px-3 pb-4 sm:px-6">
        <div className="mx-auto w-full max-w-3xl py-4">
          <p className="mb-3 text-sm text-muted-foreground">
            {business.name}
            {tr(" · Vamos a preparar tu primer análisis")}
          </p>
          <nav aria-label={tr("Pasos de inicio")}>
            <ol className="grid grid-cols-5 gap-2">
              {stages.map((label, index) => (
                <li
                  key={tr(label)}
                  aria-current={index === stage ? "step" : undefined}
                  className={`border-t-2 pt-2 text-xs ${index <= stage ? "border-primary text-foreground" : "border-border text-muted-foreground"}`}
                >
                  {index < stage && (
                    <Check
                      className="mr-1 inline size-3"
                      aria-label={tr("Completado")}
                    />
                  )}
                  {tr(label)}
                </li>
              ))}
            </ol>
          </nav>
        </div>
        <Notice error>{startError || resource.error}</Notice>
        {startError && (
          <Button variant="outline" onClick={() => void boot()}>
            {tr("Reintentar inicio")}
          </Button>
        )}
        {!state && !startError && (
          <p role="status" className="p-6">
            <Busy />
            {tr(" Preparando tu chat…")}
          </p>
        )}
        {state && (
          <div className="flex h-[min(780px,75svh)] min-h-[440px] flex-col overflow-hidden rounded-2xl border bg-background">
            <ChatPage
              id={state.conversation_id}
              setup={state.stage !== "complete"}
            >
              {(chat) => (
                <SetupCards
                  key={business.id}
                  business={business}
                  state={state}
                  chat={chat}
                  onChange={() => {
                    resource.refresh();
                    refresh();
                  }}
                />
              )}
            </ChatPage>
          </div>
        )}
        {started && (
          <p className="mx-auto mt-3 text-xs text-muted-foreground">
            {tr("Tu chat se guarda. Puedes volver para continuar.")}
          </p>
        )}
      </div>
    </EntryFrame>
  );
}

function SetupCards({
  business,
  state,
  chat,
  onChange,
}: {
  business: Business;
  state: SetupSession;
  chat: ChatDetail;
  onChange: () => void;
}) {
  useLanguage();
  const action = useAction();
  const [editGoal, setEditGoal] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const folder = useRef<HTMLInputElement>(null);
  const [fileDraft, setFileDraft] = useDraft(`dr-setup-files-${business.id}`, {
    names: [] as string[],
  });
  const choose = (selection: FileList | null) => {
    const selected = selectedDataFiles(Array.from(selection || []));
    setFiles(selected.supported);
    setIgnored(selected.ignored.length);
    setPartial(null);
    setUploaded(0);
    setFileDraft({ names: selected.supported.map((file) => file.name) });
  };
  const [ignored, setIgnored] = useState(0);
  const [uploaded, setUploaded] = useState(0);
  const [partial, setPartial] = useState<Dataset | null>(null);
  const [draft, setDraft] = useDraft(`dr-setup-goal-${business.id}`, {
    text: state.goal.text || "",
    choices: state.goal.choices || [],
  });
  const [scopeEdit, setScopeEdit] = useDraft(`dr-setup-scope-${business.id}`, {
    text: "",
    key: "",
  });
  const busy =
    action.busy ||
    chat.turns.some((t) =>
      ["queued", "routing", "processing", "failed", "blocked"].includes(
        t.status,
      ),
    );
  const pendingKey = `dr-setup-change-${business.id}`;
  const mutate = async (fields: Record<string, unknown>) => {
    const body = {
      business_id: business.id,
      revision: state.revision,
      ...fields,
    };
    const prior = store.get<{ body: unknown; request_key: string } | null>(
      pendingKey,
      null,
    );
    const request_key =
      prior && JSON.stringify(prior.body) === JSON.stringify(body)
        ? prior.request_key
        : crypto.randomUUID();
    store.set(pendingKey, { body, request_key });
    const result = await api<SetupSession>("/api/onboarding/change", {
      ...body,
      request_key,
    });
    store.remove(pendingKey);
    onChange();
    return result;
  };
  const suggestion = [...chat.turns]
    .reverse()
    .find((t) => t.response?.onboarding?.goal_suggestion)?.response
    ?.onboarding?.goal_suggestion;
  const total = files.reduce((sum, f) => sum + f.size, 0);
  const upload = async () => {
    const bundle = await uploadFolder(
      `dr-setup-upload-${business.id}`,
      {
        business_id: business.id,
        title: tr("Datos de {0}", { "0": business.name }),
        mode: "separate",
      },
      files,
      setUploaded,
    );
    if (!["ready", "partial"].includes(bundle.status))
      throw new Error(
        bundle.message || tr("Revisa los archivos y vuelve a intentarlo."),
      );
    if (bundle.status === "partial" && partial?.id !== bundle.analysis_id) {
      const dossier = await api<Dossier>("/api/business/dossier");
      const dataset = dossier.datasets.find((d) => d.id === bundle.analysis_id);
      if (!dataset || dossier.business_id !== business.id)
        throw new Error(tr("No podemos comprobar los archivos preparados."));
      setPartial(dataset);
      return;
    }
    await mutate({ action: "data", analysis_id: bundle.analysis_id });
    store.remove(`dr-setup-upload-${business.id}`);
    setFiles([]);
    setFileDraft({ names: [] });
    setPartial(null);
  };
  const canEdit = !["report", "complete"].includes(state.stage);
  return (
    <section
      className="space-y-4"
      aria-label={tr("Preparar el primer análisis")}
    >
      <Notice error>{action.error}</Notice>
      {action.error && (
        <Button variant="ghost" size="sm" onClick={onChange}>
          {tr("Actualizar estado")}
        </Button>
      )}
      {(state.stage === "goal" || editGoal) && canEdit ? (
        <form
          className="space-y-4 rounded-xl border p-5"
          onSubmit={(e) => {
            e.preventDefault();
            void action.run(async () => {
              await mutate({ action: "goal", ...draft });
              setEditGoal(false);
            });
          }}
        >
          <h2 className="text-lg font-semibold">
            {tr("¿Qué te gustaría conseguir con este primer análisis?")}
          </h2>
          <p className="text-sm text-muted-foreground">
            {tr("Cuéntamelo con tus palabras o combina estas ideas.")}
          </p>
          <div className="flex flex-wrap gap-2">
            {goals.map(([key, label]) => (
              <Button
                key={key}
                type="button"
                size="sm"
                className="h-auto whitespace-normal text-left"
                variant={draft.choices.includes(key) ? "default" : "outline"}
                aria-pressed={draft.choices.includes(key)}
                onClick={() =>
                  setDraft({
                    ...draft,
                    choices: draft.choices.includes(key)
                      ? draft.choices.filter((c) => c !== key)
                      : [...draft.choices, key],
                  })
                }
              >
                {tr(label)}
              </Button>
            ))}
          </div>
          <Field label={tr("Lo que me gustaría conseguir")} id="setup-goal">
            <Textarea
              id="setup-goal"
              maxLength={2000}
              placeholder={tr(
                "Por ejemplo: quiero entender por qué vendo más pero el margen está bajando.",
              )}
              value={draft.text}
              onChange={(e) => setDraft({ ...draft, text: e.target.value })}
            />
          </Field>
          {suggestion && (
            <Button
              type="button"
              variant="ghost"
              className="h-auto whitespace-normal text-left"
              onClick={() => setDraft({ ...draft, text: suggestion })}
            >
              {tr("Usar el objetivo que hemos comentado: ")}
              {suggestion}
            </Button>
          )}
          <Button
            disabled={busy || (!draft.text.trim() && !draft.choices.length)}
          >
            {tr("Guardar objetivo ")}
            <ArrowRight />
          </Button>
        </form>
      ) : (
        state.goal &&
        canEdit && (
          <div className="rounded-xl bg-muted/50 p-4">
            <p className="text-sm font-medium">{tr("Tu objetivo")}</p>
            <p className="mt-1 text-sm">
              {state.goal.text ||
                state.goal.choices
                  ?.map((c) => goals.find(([k]) => k === c)?.[1])
                  .join(" · ")}
            </p>
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() => setEditGoal(true)}
            >
              {tr("Cambiar objetivo")}
            </Button>
          </div>
        )
      )}
      {["data", "scope"].includes(state.stage) && !editGoal && (
        <details
          open={state.stage === "data"}
          className="rounded-xl border p-5"
        >
          <summary className="cursor-pointer font-medium">
            {state.analysis_id
              ? tr("Cambiar los archivos")
              : tr("Comparte tus datos")}
          </summary>
          <p className="my-3 text-sm text-muted-foreground">
            {tr(
              "CSV o Excel, uno o varios archivos. Exploraremos las tablas antes de confirmar el informe.",
            )}
          </p>
          <input
            type="file"
            multiple
            accept=".csv,.xlsx,.xls"
            aria-label={tr("Archivos del negocio")}
            disabled={busy}
            className="block w-full text-sm"
            onChange={(e) => choose(e.target.files)}
          />
          <input
            type="file"
            multiple
            className="hidden"
            aria-label={tr("Carpeta del negocio")}
            ref={(node) => {
              folder.current = node;
              node?.setAttribute("webkitdirectory", "");
            }}
            onChange={(e) => choose(e.target.files)}
          />
          <Button
            className="mt-3"
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => folder.current?.click()}
          >
            {tr("Seleccionar carpeta")}
          </Button>
          {!files.length && fileDraft.names.length > 0 && (
            <Notice>
              {tr(
                "Vuelve a seleccionar tus archivos para continuar la subida:",
              )}{" "}
              {fileDraft.names.join(", ")}.
            </Notice>
          )}

          {ignored > 0 && (
            <Notice>
              {ignored}
              {tr(" archivos no compatibles no se subirán.")}
            </Notice>
          )}
          {files.length > 0 && (
            <p className="my-3 text-xs">
              {files.map((f) => f.name).join(", ")}
            </p>
          )}
          {partial && (
            <div className="my-3 text-sm">
              <p>
                {tr(
                  "Algunos archivos no pudieron prepararse. Revisa cuáles usaríamos:",
                )}
              </p>
              <ul className="list-disc pl-5">
                {partial.files?.map((f) => (
                  <li key={f.id}>
                    {f.name}: {f.status}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {total > FOLDER_LIMIT && (
            <Notice error>
              {tr("Los archivos superan el límite de 2 GiB.")}
            </Notice>
          )}
          <Button
            className="mt-3"
            disabled={busy || !files.length || total > FOLDER_LIMIT}
            onClick={() => void action.run(upload)}
          >
            {action.busy ? <Busy /> : <Upload />}
            {partial
              ? tr("Continuar con los archivos preparados")
              : tr("Compartir archivos")}
          </Button>
          {action.busy && uploaded > 0 && (
            <p role="status" className="mt-2 text-sm">
              {(uploaded / 1024).toFixed(1)}
              {tr(" KB enviados")}
            </p>
          )}
        </details>
      )}
      {state.brief && state.stage === "scope" && !editGoal && (
        <div className="space-y-3 rounded-xl border border-primary/30 p-5">
          <h2 className="text-lg font-semibold">
            {tr("Esto es lo que vamos a analizar")}
          </h2>
          <p className="text-sm text-muted-foreground">
            {state.brief.business_summary}
          </p>
          <p className="font-medium">{state.brief.objective}</p>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {state.brief.questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
          {!!state.brief.limitations.length && (
            <div className="text-sm">
              <p className="font-medium">
                {tr("Qué quedará fuera o necesita cautela")}
              </p>
              <ul className="mt-1 list-disc pl-5">
                {state.brief.limitations.map((v) => (
                  <li key={v}>{v}</li>
                ))}
              </ul>
            </div>
          )}
          <details>
            <summary className="cursor-pointer text-sm">
              {tr("Editar el alcance")}
            </summary>
            <label htmlFor="scope-edit" className="mt-3 block text-sm">
              {tr("¿Qué quieres cambiar?")}
            </label>
            <Textarea
              id="scope-edit"
              value={scopeEdit.text}
              maxLength={3000}
              onChange={(e) => setScopeEdit({ text: e.target.value, key: "" })}
            />
            <Button
              className="mt-2"
              variant="outline"
              disabled={busy || !scopeEdit.text.trim()}
              onClick={() =>
                void action.run(async () => {
                  const key = scopeEdit.key || crypto.randomUUID();
                  setScopeEdit({ ...scopeEdit, key });
                  await api(`/api/chats/${state.conversation_id}/messages`, {
                    business_id: business.id,
                    request_key: key,
                    text: tr("Quiero cambiar el alcance: {0}", {
                      "0": scopeEdit.text,
                    }),
                  });
                  setScopeEdit({ text: "", key: "" });
                  onChange();
                })
              }
            >
              {tr("Actualizar propuesta")}
            </Button>
          </details>
          <Button
            disabled={busy}
            onClick={() => void action.run(() => mutate({ action: "confirm" }))}
          >
            {tr("Crear mi informe ")}
            <ArrowRight />
          </Button>
          <p className="text-xs text-muted-foreground">
            {tr("Puedes confirmar aunque hayas omitido contexto opcional.")}
          </p>
        </div>
      )}
      {state.job_id && (
        <div className="space-y-3 rounded-xl border p-5">
          <p className="font-medium">
            {state.publishable
              ? tr("Tu primer informe está listo")
              : state.context_stale
                ? tr("El contexto ha cambiado")
                : ["failed", "blocked"].includes(state.job_status ?? "")
                  ? tr("Tu informe necesita atención")
                  : tr("Estamos preparando tu informe")}
          </p>
          <p className="text-sm text-muted-foreground">
            {state.publishable
              ? tr(
                  "Puedes abrirlo y seguir profundizando en este mismo chat.",
                )
              : state.context_stale
                ? tr(
                    "Revisa y recalcula el informe con la información actual del negocio. Conservamos el chat y los archivos.",
                  )
                : ["failed", "blocked"].includes(state.job_status ?? "")
                  ? tr(
                      "Tus archivos y respuestas están guardados. Puedes revisar el estado aquí y usar Reintentar en este chat.",
                    )
                  : tr(
                      "Las aclaraciones y los resultados aparecerán en este chat.",
                    )}
          </p>
          <FirstReport
            key={`${state.job_id}:${Boolean(state.publishable)}`}
            id={state.job_id}
            ready={Boolean(state.publishable)}
          />
          {(state.publishable || state.stage === "complete") && (
            <Button
              disabled={busy}
              onClick={() =>
                void action.run(async () => {
                  if (state.stage !== "complete")
                    await mutate({ action: "complete" });
                  location.hash = `chat/${state.conversation_id}`;
                  onChange();
                })
              }
            >
              {tr("Continuar en mi espacio ")}
              <ArrowRight />
            </Button>
          )}
        </div>
      )}
    </section>
  );
}

function FirstReport({ id, ready }: { id: string; ready: boolean }) {
  useLanguage();
  const [open, setOpen] = useState(false);
  return (
    <div>
      <Button
        variant="outline"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {open
          ? tr("Cerrar vista")
          : ready
            ? tr("Abrir informe")
            : tr("Ver progreso")}
      </Button>
      {open && (
        <div
          className="mt-4 space-y-3"
          role="region"
          aria-label={
            ready ? tr("Primer informe revisado") : tr("Progreso del informe")
          }
        >
          {ready ? (
            <FirstReportResult id={id} />
          ) : (
            <FirstReportProgress id={id} />
          )}
        </div>
      )}
    </div>
  );
}
function FirstReportProgress({ id }: { id: string }) {
  useLanguage();
  const { data: job, error } = useResource<Job>(`/api/jobs/${id}`, 3000);
  return (
    <>
      <Notice error>{error}</Notice>
      {!job && !error && <Busy />}
      {job && (
        <>
          <p className="text-sm text-muted-foreground">
            {tr(
              "Puedes seguir las comprobaciones y las aclaraciones en este chat.",
            )}
          </p>
          <p className="text-sm whitespace-pre-wrap">{job.context}</p>
          {job.goal && (
            <p className="text-sm">
              {tr("Objetivo: ")}
              {job.goal}
            </p>
          )}
        </>
      )}
    </>
  );
}
function FirstReportResult({ id }: { id: string }) {
  const { data, error } = useResource<ReportData>(
    `/api/jobs/${id}/presentation`,
  );
  return (
    <>
      <Notice error>{error}</Notice>
      {data ? <ReportView report={data} compact /> : !error && <Busy />}
    </>
  );
}
