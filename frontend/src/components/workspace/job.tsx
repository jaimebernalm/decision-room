import { useEffect, useRef } from "react";
import { FileText, Download, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { useResource, useDraft, useAction } from "@/lib/hooks";
import { api, date, store } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
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
export function JobPage({ id }: { id: string }) {
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
  return (
    <>
      <Heading
        title={job.title}
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
      {job.status === "blocked" && (
        <Button asChild className="mb-6" variant="outline">
          <a href="#new">Crear otro informe</a>
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
                <a href={`/api/jobs/${id}/file`} download>
                  <Download />
                  Descargar CSV original
                </a>
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
        text,
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
              className="mr-2"
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
          <div className="flex flex-wrap gap-2">
            <Button disabled={action.busy || !text.trim()} type="submit">
              {action.busy && <Busy />}Guardar respuesta
            </Button>
            <Button
              disabled={action.busy}
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
