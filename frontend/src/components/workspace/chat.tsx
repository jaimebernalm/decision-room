import { useRef, useState } from "react";
import { FileText, RotateCcw, ArrowUpRight } from "lucide-react";
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import {
  Message,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import {
  Sources,
  SourcesTrigger,
  SourcesContent,
} from "@/components/ai-elements/sources";
import { Button } from "@/components/ui/button";
import { DataPreview } from "./data-preview";
import { Badge } from "@/components/ui/badge";
import { useResource, useDraft, useAction } from "@/lib/hooks";
import { useWorkspace } from "@/lib/workspace";
import {
  api,
  messageKey,
  store,
  queuePosition,
  type MessageDraft,
  referenceWire,
  contextKey,
} from "@/lib/api";
import type { ChatDetail, Response, Report } from "@/lib/types";
import {
  Notice,
  Loading,
  Status,
  ChoiceSelect,
  Disclosure,
  Busy,
} from "./shared";
import { ReportView } from "./report";
import { useAssistant } from "@/lib/assistant";
import { ContextAttachments, SelectionTool } from "./context-selection";
import { Composer } from "./composer";
export function Answer({
  response,
  ownerText = "",
}: {
  response: Response;
  ownerText?: string;
}) {
  const { listing, workspace } = useWorkspace();
  if (response.kind === "memory") {
    const greeting = ownerText
      .toLocaleLowerCase("es")
      .replace(/[¡!¿?.,\s]+/g, " ")
      .trim();
    if (
      [
        "hola",
        "holi",
        "buenas",
        "buen día",
        "buenos días",
        "buenas tardes",
        "buenas noches",
        "qué tal",
        "que tal",
        "hey",
        "hello",
        "hi",
      ].includes(greeting)
    )
      return (
        <p>
          ¡Hola! ¿Qué te gustaría saber o investigar sobre{" "}
          {workspace.business?.name || "tu negocio"}?
        </p>
      );
    const text =
      response.text ===
      "El mensaje está guardado. Estos son los recuerdos aplicables y su estado."
        ? response.items?.length
          ? "Esto es lo que tenía guardado en ese momento:"
          : "En ese momento todavía no encontraba información del negocio que pudiera utilizar."
        : response.text;
    return (
      <div className="space-y-3">
        <p>{text}</p>
        {response.items?.length ? (
          <ul className="list-disc space-y-2 pl-5">
            {response.items.map((item, i) => (
              <li key={i}>
                {item.status !== "declared" && (
                  <span className="font-medium">
                    {item.status === "conflicted"
                      ? "Hay versiones diferentes"
                      : item.status === "proposed"
                        ? "Por confirmar"
                        : item.status}
                    :{" "}
                  </span>
                )}
                {item.content?.statement}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    );
  }
  if (response.kind === "evidence" && response.scope && response.claims)
    return (
      <ReportView
        compact
        report={
          {
            ...response,
            highlights: response.highlights || [],
            charts: response.charts || [],
            limitations: response.limitations || [],
          } as Report
        }
      />
    );
  return (
    <div className="space-y-4">
      {response.text && (
        <MessageResponse
          plugins={{}}
          skipHtml
          components={{
            a: ({ children }) => <span>{children}</span>,
            img: () => null,
          }}
        >
          {response.text}
        </MessageResponse>
      )}
      {response.paragraphs?.map((p, i) => (
        <p key={i}>{p}</p>
      ))}
      {response.sources?.length ? (
        <Sources>
          <SourcesTrigger count={response.sources.length}>
            Fuentes consultadas ({response.sources.length})
          </SourcesTrigger>
          <SourcesContent>
            <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
              {response.sources.map((s, i) => (
                <li key={i}>
                  {s.label}
                  {s.reference ? ` · ${s.reference}` : ""}
                </li>
              ))}
            </ul>
          </SourcesContent>
        </Sources>
      ) : null}
      {response.evidence && (
        <Disclosure title="Ver evidencia revisada">
          <Answer response={response.evidence} />
        </Disclosure>
      )}
      {response.questions?.map((q) => (
        <div key={q.id} className="rounded-lg border p-4">
          <p className="font-medium">{q.text}</p>
          <p className="mt-1 text-sm text-muted-foreground">{q.reason}</p>
        </div>
      ))}
      {response.items?.map((item, i) => (
        <div key={i} className="rounded-lg border p-4 text-sm">
          <p className="font-medium">
            {item.description ||
              item.content?.statement ||
              item.preceding_question}
          </p>
          {item.text && <p className="mt-2 whitespace-pre-wrap">{item.text}</p>}
          {item.names && (
            <p className="text-muted-foreground">{item.names.join(", ")}</p>
          )}
          {item.columns && (
            <p className="mt-2 text-xs text-muted-foreground">
              Columnas: {item.columns.join(", ")}
            </p>
          )}
          {item.conversation_id &&
            listing.conversations.some(
              (c) => c.id === item.conversation_id,
            ) && (
              <Button asChild variant="link" size="sm">
                <a href={`#chat/${item.conversation_id}`}>
                  Abrir conversación
                  <ArrowUpRight />
                </a>
              </Button>
            )}
        </div>
      ))}
    </div>
  );
}
export function ChatPage({
  id,
  docked = false,
}: {
  id: string;
  docked?: boolean;
}) {
  const assistant = useAssistant();
  const { workspace, refresh } = useWorkspace(),
    business = workspace.business!.id;
  const resource = useResource<ChatDetail>(`/api/chats/${id}`, 3000);
  const [draft, persistDraft] = useDraft<MessageDraft>(messageKey(id), {
      text: "",
    }),
    draftRef = useRef(draft);
  const setDraft = (next: MessageDraft) => {
    draftRef.current = next;
    persistDraft(next);
  };
  const [question, setQuestion] = useState(""),
    action = useAction(),
    sendAction = useAction();
  const waiting = resource.data?.turns.find((t) => t.status === "waiting"),
    questions = waiting?.questions || [],
    selected = questions.find((q) => q.id === question) || questions[0];
  const send = () =>
    sendAction.run(async () => {
      const snapshot = draftRef.current;
      if (!snapshot.text.trim()) return;
      const references = assistant
        ? assistant.selected.map(referenceWire)
        : snapshot.context_references;
      const unchanged =
        JSON.stringify(references || []) ===
        JSON.stringify(snapshot.context_references || []);
      const key = (unchanged && snapshot.key) || crypto.randomUUID();
      const sent = {
        ...snapshot,
        context_references: references,
        key,
        question_id:
          unchanged && snapshot.key ? snapshot.question_id : selected?.id,
      };
      setDraft(sent);
      await api(`/api/chats/${id}/messages`, {
        business_id: business,
        request_key: key,
        text: sent.text,
        ...(sent.context_references?.length
          ? { context_references: sent.context_references }
          : {}),
        ...(sent.finding_reference
          ? { finding_reference: sent.finding_reference }
          : {}),
        ...(sent.question_id ? { question_id: sent.question_id } : {}),
      });
      if (
        JSON.stringify(store.get(messageKey(id), {})) === JSON.stringify(sent)
      ) {
        store.remove(messageKey(id));
        const currentContext = store.get<{
          context_references?: import("@/lib/types").ContextReference[];
        }>(contextKey(business), {});
        if (
          JSON.stringify(
            currentContext.context_references?.map(referenceWire) || [],
          ) === JSON.stringify(sent.context_references || [])
        )
          assistant?.clear();
      }
      if (sendAction.isMounted()) {
        resource.refresh();
        refresh();
      }
    });
  const operation = (kind: string, turnId: string, extra = {}) =>
    action.run(async () => {
      await api(`/api/chats/${id}/${kind}`, {
        business_id: business,
        turn_id: turnId,
        request_key: crypto.randomUUID(),
        ...extra,
      });
      if (action.isMounted()) {
        resource.refresh();
        refresh();
      }
    });
  if (!resource.data)
    return (
      <div className="p-6">
        <Notice error>{resource.error}</Notice>
        {!resource.error && <Loading />}
      </div>
    );
  const data = resource.data;
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <h1 className="sr-only">Conversación con IA</h1>
      <Conversation>
        <ConversationContent
          className={`mx-auto w-full max-w-4xl px-4 py-8 ${docked ? "" : "sm:px-8"}`}
        >
          {data.dataset && (
            <p className="mt-1 text-xs text-muted-foreground">
              {data.dataset.title} · v{data.dataset.version}
              {data.dataset.corrected
                ? " · datos corregidos"
                : data.dataset.superseded_by
                  ? " · versión anterior"
                  : ""}
            </p>
          )}

          <Notice error>{resource.error || action.error}</Notice>
          {!data.turns.length && (
            <p className="py-16 text-center text-muted-foreground">
              Escribe tu primera pregunta para empezar.
            </p>
          )}
          {data.turns.map((turn, index) => (
            <div key={turn.id} className="space-y-5">
              {turn.context_changed_before && <ContextChange />}
              <Message from="user" className="ml-auto">
                <div className="ml-auto max-w-full">
                  <ContextAttachments
                    items={turn.attachments || []}
                    chatId={id}
                  />
                </div>
                <MessageContent className="whitespace-pre-wrap break-words">
                  {turn.payload.text}
                </MessageContent>
              </Message>
              <Message from="assistant" className="w-full max-w-full">
                <MessageContent className="w-full overflow-visible">
                  {turn.historical && (
                    <Badge variant="outline" className="mb-3">
                      Respuesta con contexto anterior
                    </Badge>
                  )}
                  {turn.response && (
                    <Answer
                      response={turn.response}
                      ownerText={turn.payload.text}
                    />
                  )}
                  <Notice error>{turn.historical ? "" : turn.issue}</Notice>
                  {["queued", "routing", "processing"].includes(
                    turn.status,
                  ) && (
                    <div
                      role="status"
                      className="flex items-center gap-2 text-sm text-muted-foreground"
                    >
                      <Busy />
                      {queuePosition(data.turns, index)
                        ? `En cola · posición ${queuePosition(data.turns, index)}`
                        : turn.status === "queued"
                          ? "Preparando tu pregunta…"
                          : turn.status === "routing"
                            ? "Preparando respuesta…"
                            : "Analizando los datos…"}
                    </div>
                  )}
                  {turn.status === "waiting" && (
                    <Notice>
                      El análisis necesita una aclaración. Responde a la
                      pregunta que aparece debajo.
                    </Notice>
                  )}
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(["failed", "blocked"].includes(turn.status) ||
                      (turn.status === "stale" &&
                        (!turn.response || turn.job_id))) &&
                      data.turns
                        .slice(index + 1)
                        .every((t) => t.status === "queued") && (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={action.busy}
                          onClick={() => operation("retry", turn.id)}
                        >
                          <RotateCcw />
                          {turn.status === "stale"
                            ? "Recalcular"
                            : "Reintentar"}
                        </Button>
                      )}
                    {turn.response?.report_id &&
                      !turn.report_outdated &&
                      (turn.report_requested ? (
                        <Button asChild variant="outline" size="sm">
                          <a href={`#chat-report/${id}/${turn.id}`}>
                            <FileText />
                            Abrir informe
                          </a>
                        </Button>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={action.busy}
                          onClick={() => operation("report", turn.id)}
                        >
                          <FileText />
                          Crear informe
                        </Button>
                      ))}
                    {turn.report_outdated && <Status status="outdated" />}
                    {turn.job_id && (
                      <Button asChild variant="ghost" size="sm">
                        <a href={`#analysis/${turn.job_id}`}>
                          Ver informe
                          <ArrowUpRight />
                        </a>
                      </Button>
                    )}
                  </div>
                </MessageContent>
              </Message>
            </div>
          ))}
          {data.context_changed_after && <ContextChange />}
          {data.memory_items
            .filter((f) => f.status === "conflicted")
            .map((f) => (
              <Disclosure
                key={f.fact_id || f.id}
                title="Hay información del negocio que necesita confirmación"
                defaultOpen
              >
                <p>{f.content.statement}</p>
                {f.alternatives?.map((alt, i) => (
                  <Button
                    key={i}
                    variant="outline"
                    className="h-auto whitespace-normal text-left"
                    disabled={action.busy}
                    onClick={() =>
                      operation("resolve", "", {
                        fact_id: f.fact_id || f.id,
                        revision: f.revision,
                        alternative: i,
                      })
                    }
                  >
                    Usar: {alt.content?.statement || alt.statement || alt.quote}
                  </Button>
                ))}
              </Disclosure>
            ))}
          {selected && waiting?.job_id && (
            <DataPreview
              key={`${waiting.job_id}:${selected.id}`}
              jobId={waiting.job_id}
              questions={[selected]}
            />
          )}
        </ConversationContent>
        <ConversationScrollButton aria-label="Ir al último mensaje" />
      </Conversation>
      <div
        className={`shrink-0 bg-background px-4 pb-4 pt-2 ${docked ? "" : "sm:px-8"}`}
      >
        <div className="mx-auto max-w-2xl">
          {selected && (
            <div className="mb-3 space-y-2">
              <ChoiceSelect
                label="Aclaración pendiente"
                value={selected.id}
                onChange={setQuestion}
                options={questions.map((q) => ({ value: q.id, label: q.text }))}
              />
              <p className="text-xs text-muted-foreground">{selected.reason}</p>
              {selected.options?.map((option) => (
                <Button
                  key={option}
                  variant="outline"
                  size="sm"
                  className="mr-2"
                  onClick={() => setDraft({ text: option })}
                >
                  {option}
                </Button>
              ))}
            </div>
          )}
          <Composer
            compact
            tools={docked ? <SelectionTool /> : undefined}
            attachments={
              assistant?.selected.length ? (
                <ContextAttachments
                  items={assistant.selected}
                  onRemove={assistant.remove}
                />
              ) : undefined
            }
            text={draft.text}
            onChange={(text) =>
              setDraft({
                text,
                finding_reference: draft.finding_reference,
                context_references: draft.context_references,
              })
            }
            onSend={send}
            busy={sendAction.busy}
            error={sendAction.error}
            placeholder={
              selected ? "Escribe tu aclaración…" : "Pregunta o añade contexto…"
            }
          />
        </div>
      </div>
    </div>
  );
}
function ContextChange() {
  return (
    <div className="flex items-center gap-3 py-2 text-xs text-muted-foreground">
      <div className="h-px flex-1 bg-border" />
      Contexto del negocio actualizado
      <div className="h-px flex-1 bg-border" />
    </div>
  );
}
