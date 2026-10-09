import { translate as tr, useLanguage } from "@/lib/i18n";
import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { BotMessageSquare, X, Paperclip } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useWorkspace } from "@/lib/workspace";
import { useAction, useDraft } from "@/lib/hooks";
import { contextKey, homeDraftKey, launchChat, store } from "@/lib/api";
import type { QuestionContext } from "@/lib/types";
import { useAssistant, contextualRoute } from "@/lib/assistant";
import { ContextAttachments, SelectionTool } from "./context-selection";
import { starterOptions, reportStarter } from "@/lib/chat-start";
import { ComposerSurface } from "./composer-surface";
import { Composer } from "./composer";

export function AssistantToggle() {
  useLanguage();
  const assistant = useAssistant();
  const { workspace, route } = useWorkspace();
  const [draft] = useDraft(homeDraftKey(workspace.business?.id || "empty"), "");
  if (
    !assistant ||
    !workspace.business ||
    !contextualRoute(route) ||
    assistant.dock.open
  )
    return null;
  const continuing = Boolean(
    assistant.dock.chatId || draft.trim() || assistant.selected.length,
  );
  return (
    <span>
      <Button
        variant="default"
        size="icon-lg"
        className="rounded-full"
        aria-label={continuing ? tr("Continuar chat") : tr("Preguntar algo")}
        title={continuing ? tr("Continuar chat") : tr("Preguntar algo")}
        onClick={() =>
          assistant.setDock({ ...assistant.dock, open: true, origin: route })
        }
      >
        <BotMessageSquare aria-hidden="true" className="size-6" />
      </Button>
    </span>
  );
}

// Used both in the empty side panel and the standalone new conversation.
// The page owns the component lifetime, so late sends cannot redirect another page.
export function NewChatComposer({
  autoFocus = true,
  start = false,
  intent,
}: {
  autoFocus?: boolean;
  start?: boolean;
  intent?: "report";
}) {
  useLanguage();
  const assistant = useAssistant();
  const { workspace, route, refresh } = useWorkspace();
  const business = workspace.business!;
  const [text, setText] = useDraft(homeDraftKey(business.id), "");
  const [context, setContext] = useDraft<QuestionContext>(
    contextKey(business.id),
    {},
  );
  const container = useRef<HTMLDivElement>(null);
  const action = useAction();
  const reduced = useReducedMotion();
  const reveal = { delay: reduced ? 0 : 0.24, duration: reduced ? 0 : 0.12 };
  const [choice, setChoice] = useState<string | null>(intent || null);
  const starter = starterOptions.find((item) => item.id === choice);
  useEffect(() => {
    if (intent === "report" && !store.get(homeDraftKey(business.id), "").trim())
      setText(tr(reportStarter));
  }, [intent, business.id, setText]);
  const choose = (id: string, prompt: string) => {
    setChoice(id);
    const current = store.get(homeDraftKey(business.id), "").trim();
    const canned = [
      ...starterOptions.map((item) => tr(item.prompt).trim()),
      tr(reportStarter).trim(),
    ];
    if (!current || canned.includes(current)) setText(tr(prompt));
    container.current
      ?.querySelector("textarea")
      ?.focus({ preventScroll: true });
  };
  useEffect(() => {
    if (!autoFocus) return;
    container.current
      ?.querySelector("textarea")
      ?.focus({ preventScroll: true });
  }, [autoFocus]);
  const send = () =>
    action.run(async () => {
      if (!text.trim()) return;
      if (assistant && contextualRoute(route)) {
        await assistant.launch(text, context, route);
        if (action.isMounted()) refresh();
      } else {
        const chat = await launchChat(business.id, text, context);
        if (action.isMounted()) {
          assistant?.setDock({ chatId: chat.id, open: false });
          refresh();
          location.hash = `chat/${chat.id}`;
        }
      }
    });
  return (
    <div
      ref={container}
      role="region"
      aria-label={tr("Asistente del negocio")}
      className="w-full"
    >
      {start && (
        <motion.div
          className="chat-start-heading"
          initial={{ opacity: reduced ? 1 : 0 }}
          animate={{ opacity: 1 }}
          transition={reveal}
        >
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            {choice === "report"
              ? tr("¿Qué quieres que incluya el informe?")
              : starter
                ? tr(starter.question)
                : tr("¿En qué te ayudo con tu negocio?")}
          </h1>
          <p className="mt-3 text-sm text-muted-foreground">
            {tr("Pregunta algo o prepara un informe.")}
          </p>
        </motion.div>
      )}
      <ComposerSurface shared={!assistant?.dock.open || start}>
        <Composer
          compact
          tools={
            start ? (
              <Button
                asChild
                variant="ghost"
                size="icon"
                className="size-8 rounded-full"
              >
                <a
                  href="#files"
                  aria-label={tr("Añadir datos")}
                  title={tr("Añadir datos")}
                >
                  <Paperclip className="size-4" />
                </a>
              </Button>
            ) : (
              <SelectionTool />
            )
          }
          attachments={
            <>
              {(context.analysis_id || context.finding_reference) && (
                <div
                  className="composer-context-bubble flex w-fit max-w-[min(100%,16rem)] items-center gap-1 pl-2.5 pr-1 py-0.5 text-[11px] leading-4"
                  role="group"
                  aria-label={tr("Tablas seleccionadas")}
                >
                  <span className="min-w-0 truncate" title={context.label}>
                    {context.label || tr("Contexto seleccionado")}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-6 shrink-0 rounded-full"
                    aria-label={tr("Quitar contexto")}
                    onClick={() =>
                      setContext({
                        ...context,
                        analysis_id: undefined,
                        finding_reference: undefined,
                        label: undefined,
                      })
                    }
                  >
                    <X className="size-3" />
                  </Button>
                </div>
              )}
              {!!assistant?.selected.length && (
                <ContextAttachments
                  compact
                  items={assistant.selected}
                  onRemove={assistant.remove}
                />
              )}
            </>
          }
          text={text}
          onChange={setText}
          onSend={send}
          busy={action.busy}
          error={action.error || assistant?.error}
          placeholder={
            start
              ? tr("Escribe lo que quieres conseguir…")
              : tr("Pregunta o añade contexto…")
          }
        />
      </ComposerSurface>
      {start && (
        <motion.div
          initial={{ opacity: reduced ? 1 : 0 }}
          animate={{ opacity: 1 }}
          transition={reveal}
          className="chat-start-options"
          role="group"
          aria-label={tr("Ideas para empezar")}
        >
          {starterOptions.map((item) => (
            <Button
              key={item.id}
              variant="outline"
              size="sm"
              type="button"
              aria-pressed={choice === item.id}
              disabled={action.busy}
              onClick={() => choose(item.id, item.prompt)}
            >
              {tr(item.label)}
            </Button>
          ))}
        </motion.div>
      )}
    </div>
  );
}
