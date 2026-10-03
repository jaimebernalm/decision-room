import { translate as tr, useLanguage } from "@/lib/i18n";
import { useEffect, useRef } from "react";
import { BotMessageSquare, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useWorkspace } from "@/lib/workspace";
import { useAction, useDraft } from "@/lib/hooks";
import { contextKey, homeDraftKey, launchChat } from "@/lib/api";
import type { QuestionContext } from "@/lib/types";
import { useAssistant, contextualRoute } from "@/lib/assistant";
import { ContextAttachments, SelectionTool } from "./context-selection";
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
export function NewChatComposer({ autoFocus = true }: { autoFocus?: boolean }) {
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
      {(context.analysis_id || context.finding_reference) && (
        <div className="flex items-center gap-2 px-5 pt-2 text-xs text-muted-foreground">
          <span className="min-w-0 flex-1 truncate" title={context.label}>
            {context.label || tr("Contexto seleccionado")}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="size-8 shrink-0 rounded-full"
            aria-label={tr("Quitar contexto")}
            onClick={() => setContext({})}
          >
            <X className="size-3" />
          </Button>
        </div>
      )}
      <Composer
        compact
        tools={<SelectionTool />}
        attachments={
          assistant?.selected.length ? (
            <ContextAttachments
              items={assistant.selected}
              onRemove={assistant.remove}
            />
          ) : undefined
        }
        text={text}
        onChange={setText}
        onSend={send}
        busy={action.busy}
        error={action.error || assistant?.error}
        placeholder={tr("Pregunta o añade contexto…")}
      />
    </div>
  );
}
