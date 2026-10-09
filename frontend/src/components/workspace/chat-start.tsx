import { translate as tr, useLanguage } from "@/lib/i18n";
import { useWorkspace } from "@/lib/workspace";
import { useDraft } from "@/lib/hooks";
import { messageKey, type MessageDraft } from "@/lib/api";
import { useAssistant } from "@/lib/assistant";
import { isChatStart } from "@/lib/chat-start";
import { NewChatComposer } from "./floating-assistant";
import { Composer } from "./composer";
import { ComposerSurface } from "./composer-surface";
import { Loading } from "./shared";
import "./chat-start.css";

export function StartChat() {
  useLanguage();
  const { route } = useWorkspace();
  const assistant = useAssistant();
  return (
    <section className="chat-start" aria-label={tr("Nuevo chat")}>
      <div className="chat-start-content">
        <NewChatComposer
          key={assistant?.startRevision}
          start
          intent={isChatStart(route) && route !== "ask" ? "report" : undefined}
        />
      </div>
    </section>
  );
}

// Keep the shared surface at the conversation's final position while its
// heavier answer/report module loads. There is still only one active form.
export function ChatLoading() {
  useLanguage();
  const { route } = useWorkspace();
  const [draft, setDraft] = useDraft<MessageDraft>(
    messageKey(route.split("/")[1]),
    { text: "" },
  );
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex-1 p-6">
        <Loading />
      </div>
      <div className="shrink-0 px-4 pb-4 pt-2 sm:px-8">
        <div className="mx-auto max-w-2xl">
          <ComposerSurface>
            <Composer
              compact
              busy
              text={draft.text}
              onChange={(text) => setDraft({ ...draft, text })}
              onSend={async () => {}}
              placeholder={tr("Pregunta o añade contexto…")}
            />
          </ComposerSurface>
        </div>
      </div>
    </div>
  );
}
