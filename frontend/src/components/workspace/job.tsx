import { useEffect, useRef } from "react";
import { FileText, Download, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { useResource, useDraft, useAction } from "@/lib/hooks";
import { api, date, store } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { DataPreview } from "./data-preview";
import type { Job, Question } from "@/lib/types";
import {
  Heading,
  Loading,
  Notice,
  Status,
  Field,
  Disclosure,
  Busy,
} from "./shared";
export function JobPage({
  id,
  onboarding = false,
}: {
  id: string;
  onboarding?: boolean;
}) {
  const resource = useResource<Job>(`/api/jobs/${id}`, 3000),
    action = useAction(),
    { refresh } = useWorkspace();
  useEffect(() => {
    if (resource.data?.publishable) location.hash = `report/${id}`;
  }, [resource.data?.publishable, id]);
  if (!resource.data)
    return (
      <>
        <Notice error>{resource.error}</Notice>
        {!resource.error && <Loading />}
      </>
    );
  const job = resource.data;
  const canClarify =
    job.status === "blocked" &&
    job.phase === "planning" &&
    !job.context_stale &&
    !!job.unresolved_questions?.length &&
    !!job.analysis_id &&
    !job.data_version?.corrected;
  return (
    <>
      <Heading
        title={
          onboarding
            ? job.status === "waiting"
              ? "Una aclaración antes de continuar"
              : job.publishable
                ? "Tu primer informe está listo"
                : ["failed", "blocked"].includes(job.status) ||
                    job.context_stale
                  ? "Tu informe necesita atención"
                  : "Tu primer informe, en preparación"
            : job.title
        }
        description={`${date(job.created_at)} · ${job.filename}`}
      >
        <Status
          status={
            job.context_stale
              ? "outdated"
              : job.presentation_status ||
                (["queued", "running"].includes(job.status)
                  ? "preparing"
                  : job.status)
          }
        />
      </Heading>
      <Notice error>{resource.error || action.error || job.issue}</Notice>
      {job.publishable && (
        <Card className="mb-6 shadow-none">
          <CardHeader>
            <CardTitle>Tu informe está listo</CardTitle>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <a href={`#report/${id}`}>
                <FileText />
                Abrir informe revisado
              </a>
            </Button>
          </CardContent>
        </Card>
      )}
      {["queued", "running"].includes(job.status) && (
        <Notice>
          <span role="status" className="flex items-center gap-3">
            <Busy />
            {job.activity ||
              "El análisis está en curso. Puedes seguir usando el espacio."}
          </span>
        </Notice>
      )}
      {job.status === "waiting" && !job.context_stale && (
        <div className="mb-6 space-y-4">
          <DataPreview
            key={job.questions.map((q) => q.id).join(":")}
            jobId={id}
            questions={job.questions}
          />
          {job.questions.map((q) => (
            <QuestionForm
              key={q.id}
              question={q}
              job={job}
              onDone={() => {
                resource.refresh();
                refresh();
              }}
            />
          ))}
        </div>
      )}
      {(job.status === "failed" || job.context_stale) && (
        <Button
          className="mb-6"
          disabled={action.busy}
          onClick={() =>
            action.run(async () => {
              await api(`/api/jobs/${id}/retry`, {});
              resource.refresh();
              refresh();
            })
          }
        >
          <RotateCcw />
          {job.context_stale
            ? "Recalcular con el contexto actual"
            : "Reintentar informe"}
        </Button>
      )}
      {canClarify && (
        <ClarificationRecovery key={id} job={job} onboarding={onboarding} />
      )}
      {job.status === "blocked" && !canClarify && (
        <Button asChild className="mb-6" variant="outline">
          <a href={onboarding ? `#onboarding/${job.business_id}` : "#new"}>
            {onboarding ? "Revisar mis datos" : "Crear otro informe"}
          </a>
        </Button>
      )}
      <div className="grid gap-4">
        <Disclosure title="Contexto y archivos" defaultOpen>
          <p className="font-medium">{job.business}</p>
          <p className="whitespace-pre-wrap text-muted-foreground">
            {job.context}
          </p>
          {job.goal && <p>Objetivo: {job.goal}</p>}
          <div className="flex flex-wrap gap-3">
            {job.origin !== "chat" ? (
              <Button asChild variant="outline" size="sm">
                {job.byte_count > 0 ? (
                  <a href={`/api/jobs/${id}/file`} download>
                    <Download />
                    Descargar CSV original
                  </a>
                ) : (
                  <a href="#files">
                    <FileText />
                    Ver archivos del negocio
                  </a>
                )}
              </Button>
            ) : (
              job.conversation_id && (
                <Button asChild variant="outline" size="sm">
                  <a href={`#chat/${job.conversation_id}`}>
                    Abrir conversación
                  </a>
                </Button>
              )
            )}
            <Button asChild variant="ghost" size="sm">
              <a href="#my-business">Revisar memoria del negocio</a>
            </Button>
          </div>
          {job.files.map((f, i) => (
            <p key={i} className="text-xs text-muted-foreground">
              {f.row_count ?? "—"} filas · {f.column_count ?? "—"} columnas
            </p>
          ))}
        </Disclosure>
        {job.answers.length > 0 && (
          <Disclosure title="Tus aclaraciones">
            {job.answers.map((a, i) => (
              <div key={i}>
                <p className="font-medium">
                  {typeof a.question === "string" ? a.question : ""}
                </p>
                <p className="whitespace-pre-wrap">
                  {a.disposition === "unknown" ? "No disponible" : a.text}
                </p>
              </div>
            ))}
          </Disclosure>
        )}
        {job.interpretations.length > 0 && (
          <Disclosure title="Interpretaciones revisadas">
            {job.interpretations.map((a, i) => (
              <p key={i}>{a.text}</p>
            ))}
          </Disclosure>
        )}
      </div>
    </>
  );
}
function QuestionForm({
  question,
  job,
  onDone,
}: {
  question: Question;
  job: Job;
  onDone: () => void;
}) {
  const key = `dr-answer-${job.id}-${question.id}`;
  const [text, setText] = useDraft(key, "");
  const action = useAction(),
    pending = useRef({ signature: "", key: "" });
  const submit = (disposition: string) =>
    action.run(async () => {
      const signature = JSON.stringify([text, disposition]);
      if (pending.current.signature !== signature)
        pending.current = { signature, key: crypto.randomUUID() };
      await api(`/api/jobs/${job.id}/answers`, {
        business_id: job.business_id,
        request_key: pending.current.key,
        question_id: question.id,
        phase: question.phase || job.phase,
        text: disposition === "answered" ? text : "",
        disposition,
      });
      store.remove(key);
      onDone();
    });
  return (
    <Card className="shadow-none">
      <CardHeader>
        <CardTitle>{question.text}</CardTitle>
        <p className="text-sm text-muted-foreground">{question.reason}</p>
      </CardHeader>
      <CardContent>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            void submit("answered");
          }}
        >
          {question.options?.map((o) => (
            <Button
              key={o}
              type="button"
              variant="outline"
              size="sm"
              className="mr-2 h-auto whitespace-normal text-left"
              disabled={action.busy}
              aria-pressed={text === o}
              onClick={() => setText(o)}
            >
              {o}
            </Button>
          ))}
          <Field label="Tu respuesta" id={`answer-${question.id}`}>
            <Textarea
              id={`answer-${question.id}`}
              required
              maxLength={6000}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </Field>
          <Notice error>{action.error}</Notice>
          {text.trim() && (
            <p className="text-xs text-muted-foreground">
              Pulsa «Guardar respuesta» para confirmar este texto. Para indicar
              que no dispones del dato, borra primero la respuesta.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button disabled={action.busy || !text.trim()} type="submit">
              {action.busy && <Busy />}Guardar respuesta
            </Button>
            <Button
              disabled={action.busy || Boolean(text.trim())}
              type="button"
              variant="ghost"
              onClick={() => submit("unknown")}
            >
              No dispongo de ese dato
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function ClarificationRecovery({
  job,
  onboarding,
}: {
  job: Job;
  onboarding: boolean;
}) {
  const { workspace, refresh } = useWorkspace();
  const key = `dr-clarify-${job.id}`;
  const questions = job.unresolved_questions || [];
  const [answers, setAnswers] = useDraft<Record<string, string>>(
    key,
    Object.fromEntries(questions.map((q) => [q.id, q.previous_text || ""])),
  );
  const action = useAction();
  const goal = [
    job.goal,
    "Aclaraciones confirmadas para este nuevo informe:",
    ...questions.map((q) => `${q.text}\n${answers[q.id] || ""}`),
  ].join("\n\n");
  return (
    <div className="mb-6 space-y-4">
      <DataPreview jobId={job.id} questions={questions} />
      <Card className="shadow-none">
        <CardHeader>
          <CardTitle>Completa la aclaración con los datos a la vista</CardTitle>
          <p className="text-sm text-muted-foreground">
            Revisa y confirma las respuestas. Crearemos un informe con los
            mismos archivos; el intento anterior se conservará como registro.
          </p>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              void action.run(async () => {
                if (workspace.business?.id !== job.business_id)
                  throw new Error(
                    "El negocio activo ha cambiado. Recarga la página.",
                  );
                const payload = {
                  business_id: job.business_id,
                  profile_revision: workspace.business.profile_revision,
                  analysis_id: job.analysis_id,
                  title: job.title,
                  goal,
                };
                const signature = JSON.stringify(payload);
                const previous = store.get<{
                  signature: string;
                  key: string;
                } | null>(`${key}-pending`, null);
                const pending =
                  previous?.signature === signature
                    ? previous
                    : { signature, key: crypto.randomUUID() };
                store.set(`${key}-pending`, pending);
                const result = await api<{ id: string }>(
                  "/api/jobs/from-dataset",
                  { ...payload, request_key: pending.key },
                );
                store.remove(key);
                store.remove(`${key}-pending`);
                if (action.isMounted())
                  location.hash = onboarding
                    ? `onboarding/${job.business_id}/report/${result.id}`
                    : `analysis/${result.id}`;
                refresh();
              });
            }}
          >
            {questions.map((q) => (
              <Field key={q.id} label={q.text} id={`clarify-${q.id}`}>
                <Textarea
                  id={`clarify-${q.id}`}
                  value={answers[q.id] || ""}
                  required
                  disabled={action.busy}
                  maxLength={2000}
                  onChange={(event) =>
                    setAnswers({ ...answers, [q.id]: event.target.value })
                  }
                />
              </Field>
            ))}
            {goal.length > 2000 && (
              <Notice error>
                Acorta las aclaraciones: el objetivo y las respuestas admiten
                hasta 2.000 caracteres en total.
              </Notice>
            )}
            <Notice error>{action.error}</Notice>
            <Button
              type="submit"
              disabled={
                action.busy ||
                goal.length > 2000 ||
                questions.some((q) => !answers[q.id]?.trim())
              }
            >
              {action.busy && <Busy />}Confirmar aclaración y crear informe
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
