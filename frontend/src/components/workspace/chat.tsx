import { translate as tr, useLanguage } from "@/lib/i18n";
import { ProgressiveAnswer } from "./progressive-answer";
import { AnalysisActivity } from "./analysis-activity";
import { useRef, useState, type ReactNode } from "react";
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
import { Notice, Loading, Status, ChoiceSelect, Disclosure } from "./shared";
import { ReportView } from "./report";
import { useAssistant } from "@/lib/assistant";
import { ContextAttachments, SelectionTool } from "./context-selection";
import { Composer } from "./composer";
import { PresentationChangeReceipt } from "./presentation-receipt";
export function Answer({
  response,
  ownerText = "",
}: {
  response: Response;
  ownerText?: string;
}) {
  useLanguage();
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
          {tr("¡Hola! ¿Qué te gustaría saber o investigar sobre")}{" "}
          {workspace.business?.name || "tu negocio"}?
        </p>
      );
    const text =
      response.text ===
      tr(
        "El mensaje está guardado. Estos son los recuerdos aplicables y su estado.",
      )
        ? response.items?.length
          ? tr("Esto es lo que tenía guardado en ese momento:")
          : tr(
              "En ese momento todavía no encontraba información del negocio que pudiera utilizar.",
            )
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
                      ? tr("Hay versiones diferentes")
                      : item.status === "proposed"
                        ? tr("Por confirmar")
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
      {response.presentation_receipt && (
        <PresentationChangeReceipt receipt={response.presentation_receipt} />
      )}
      {response.paragraphs?.map((p, i) => (
        <p key={i}>{p}</p>
      ))}
      {response.sources?.length ? (
        <Sources>
          <SourcesTrigger count={response.sources.length}>
            {tr("Fuentes consultadas (")}
            {response.sources.length})
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
        <Disclosure title={tr("Ver evidencia revisada")}>
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
              {tr("Columnas: ")}
              {item.columns.join(", ")}
            </p>
          )}
          {item.conversation_id &&
            listing.conversations.some(
              (c) => c.id === item.conversation_id,
            ) && (
              <Button asChild variant="link" size="sm">
                <a href={`#chat/${item.conversation_id}`}>
                  {tr("Abrir conversación")}
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
  setup = false,
  children,
}: {
  id: string;
  docked?: boolean;
  setup?: boolean;
  children?: (data: ChatDetail) => ReactNode;
}) {
  useLanguage();
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
  const send = (override?: string, disposition?: string) =>
    sendAction.run(async () => {
      const previous = draftRef.current;
      const snapshot = override
        ? previous.text === override && previous.disposition === disposition
          ? previous
          : ({ text: override, disposition } as MessageDraft)
        : previous;
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
        disposition: disposition || snapshot.disposition || "answered",
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
        disposition: sent.disposition,
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
  const data = resource.data;
  const [initialTurns, setInitialTurns] = useState<Set<string> | null>(null);
  if (data && !initialTurns)
    setInitialTurns(new Set(data.turns.map((t) => t.id)));
  // Answers to owner questions can create several turns for the same process.
  // Keep its durable activity at the latest turn instead of repeating the panel.
  const activityOwners = new Map<string, string>();
  data?.turns.forEach((turn) =>
    activityOwners.set(
      turn.activity_trace_id || turn.job_id || turn.id,
      turn.id,
    ),
  );
  const latest = data?.turns.at(-1);
  const setupQuestion =
    latest?.status === "completed"
      ? latest.response?.onboarding?.question
      : null;
  const pending = data?.turns.some((t) =>
    ["queued", "routing", "processing", "failed", "blocked"].includes(t.status),
  );
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <h1 className="sr-only">{tr("Conversación con IA")}</h1>
      {!data ? (
        <div className="flex-1 p-6">
          <Notice error>{resource.error}</Notice>
          {!resource.error && <Loading />}
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col">
          <Conversation>
            <ConversationContent
              className={`mx-auto w-full max-w-4xl px-4 py-8 ${docked ? "" : "sm:px-8"}`}
            >
              {data.dataset && (
                <p className="mt-1 text-xs text-muted-foreground">
                  {data.dataset.title} · v{data.dataset.version}
                  {data.dataset.corrected
                    ? tr(" · datos corregidos")
                    : data.dataset.superseded_by
                      ? tr(" · versión anterior")
                      : ""}
                </p>
              )}

              <Notice error>{resource.error || action.error}</Notice>
              {!data.turns.length && (
                <p className="py-16 text-center text-muted-foreground">
                  {tr("Escribe tu primera pregunta para empezar.")}
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
                          {tr("Respuesta con contexto anterior")}
                        </Badge>
                      )}
                      <ProgressiveAnswer
                        id={turn.id}
                        response={turn.response}
                        animate={
                          !turn.historical && !initialTurns?.has(turn.id)
                        }
                      >
                        {(visibleResponse, revealing) => (
                          <>
                            {visibleResponse && (
                              <div aria-hidden={revealing || undefined}>
                                <Answer
                                  response={visibleResponse}
                                  ownerText={turn.payload.text}
                                />
                              </div>
                            )}
                            <Notice error>
                              {turn.historical ? "" : turn.issue}
                            </Notice>
                            {activityOwners.get(
                              turn.activity_trace_id || turn.job_id || turn.id,
                            ) === turn.id && (
                              <AnalysisActivity
                                endpoint={
                                  turn.job_id
                                    ? `/api/jobs/${turn.job_id}/activity`
                                    : `/api/chats/${id}/turns/${turn.id}/activity`
                                }
                                traceId={turn.activity_trace_id}
                                revealing={revealing}
                                responseReady={
                                  Boolean(visibleResponse) &&
                                  !turn.job_id &&
                                  turn.status === "completed"
                                }
                                onQuestion={(questionId) => {
                                  setQuestion(questionId);
                                  requestAnimationFrame(() => {
                                    const input =
                                      document.querySelector<HTMLTextAreaElement>(
                                        'textarea[placeholder="Escribe tu aclaración…"]',
                                      );
                                    input?.scrollIntoView({ block: "center" });
                                    input?.focus();
                                  });
                                }}
                                fallback={
                                  queuePosition(data.turns, index)
                                    ? tr("En cola · posición {0}", {
                                        "0": queuePosition(data.turns, index),
                                      })
                                    : tr("Preparando respuesta…")
                                }
                              />
                            )}
                          </>
                        )}
                      </ProgressiveAnswer>
                      {turn.status === "waiting" && (
                        <Notice>
                          {tr(
                            "El análisis necesita una aclaración. Responde a la pregunta que aparece debajo.",
                          )}
                        </Notice>
                      )}
                      <div className="mt-3 flex flex-wrap gap-2">
                        {((["failed", "blocked"].includes(turn.status) &&
                          turn.can_retry !== false) ||
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
                                ? tr("Recalcular")
                                : tr("Reintentar")}
                            </Button>
                          )}
                        {turn.response?.report_id &&
                          !turn.response.first_report &&
                          !turn.report_outdated &&
                          (turn.report_requested ? (
                            <Button asChild variant="outline" size="sm">
                              <a href={`#chat-report/${id}/${turn.id}`}>
                                <FileText />
                                {tr("Abrir informe")}
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
                              {tr("Crear informe")}
                            </Button>
                          ))}
                        {turn.report_outdated && <Status status="outdated" />}
                        {turn.job_id && !setup && (
                          <Button asChild variant="ghost" size="sm">
                            <a href={`#analysis/${turn.job_id}`}>
                              {tr("Ver informe")}
                              <ArrowUpRight />
                            </a>
                          </Button>
                        )}
                      </div>
                    </MessageContent>
                  </Message>
                </div>
              ))}
              {setupQuestion?.references?.length ? (
                <DataPreview
                  key={latest!.id}
                  endpoint="/api/onboarding/data"
                  questions={[{ ...setupQuestion, id: latest!.id }]}
                />
              ) : null}
              {children?.(data)}
              {data.context_changed_after && <ContextChange />}
              {data.memory_items
                .filter((f) => f.status === "conflicted")
                .map((f) => (
                  <Disclosure
                    key={f.fact_id || f.id}
                    title={tr(
                      "Hay información del negocio que necesita confirmación",
                    )}
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
                        {tr("Usar:")}{" "}
                        {alt.content?.statement || alt.statement || alt.quote}
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
            <ConversationScrollButton aria-label={tr("Ir al último mensaje")} />
          </Conversation>
        </div>
      )}
      <div
        className={`shrink-0 px-4 pb-4 pt-2 ${docked ? "bg-sidebar" : "bg-background sm:px-8"}`}
      >
        <div className="relative z-10 mx-auto max-w-2xl">
          {selected && (
            <div className="mb-3 space-y-2">
              <ChoiceSelect
                label={tr("Aclaración pendiente")}
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
          {setupQuestion && (
            <div className="mb-3 space-y-2">
              <p className="text-xs text-muted-foreground">
                {setupQuestion.reason}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={sendAction.busy}
                  onClick={() => void send(tr("No lo sé"), "unknown")}
                >
                  {tr("No lo sé")}
                </Button>
                {setupQuestion.optional && (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={sendAction.busy}
                    onClick={() =>
                      void send(tr("Prefiero omitir esta pregunta"), "declined")
                    }
                  >
                    {tr("Omitir por ahora")}
                  </Button>
                )}
              </div>
            </div>
          )}
          {selected && (
            <Button
              size="sm"
              variant="outline"
              className="mb-2"
              disabled={sendAction.busy}
              onClick={() => void send(tr("No lo sé"), "unknown")}
            >
              {tr("No lo sé")}
            </Button>
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
            onSend={() => send()}
            busy={
              sendAction.busy ||
              !data ||
              (setup &&
                data.turns.some((t) =>
                  ["queued", "routing", "processing"].includes(t.status),
                ))
            }
            disabled={setup && Boolean(pending)}
            error={sendAction.error}
            placeholder={
              selected
                ? tr("Escribe tu aclaración…")
                : tr("Pregunta o añade contexto…")
            }
          />
        </div>
      </div>
    </div>
  );
}
function ContextChange() {
  useLanguage();
  return (
    <div className="flex items-center gap-3 py-2 text-xs text-muted-foreground">
      <div className="h-px flex-1 bg-border" />
      {tr("Contexto del negocio actualizado")}
      <div className="h-px flex-1 bg-border" />
    </div>
  );
}
