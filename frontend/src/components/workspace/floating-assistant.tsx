import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { MessageCircle, ChevronDown, X, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useWorkspace } from "@/lib/workspace";
import { useAction, useDraft } from "@/lib/hooks";
import { contextKey, homeDraftKey, launchChat, store } from "@/lib/api";
import type { QuestionContext } from "@/lib/types";
import { Composer } from "./composer";

// The owner keys this component by business and route: drafts survive navigation,
// while late sends cannot redirect a different page or business.
export function FloatingAssistant({ inline = false }: { inline?: boolean }) {
  const reducedMotion = useReducedMotion();
  const { workspace, route, refresh } = useWorkspace();
  const business = workspace.business!;
  const [text, setText] = useDraft(homeDraftKey(business.id), "");
  const [context, setContext] = useDraft<QuestionContext>(
    contextKey(business.id),
    {},
  );
  const [open, setOpen] = useState<boolean>(
    () =>
      route === "ask" || !store.get<boolean>("dr-assistant-collapsed", false),
  );
  const container = useRef<HTMLDivElement>(null);
  const focusOnChange = useRef(route === "ask");
  const action = useAction();
  useEffect(() => {
    if (focusOnChange.current) {
      container.current
        ?.querySelector<HTMLElement>(open ? "textarea" : "button")
        ?.focus();
      focusOnChange.current = false;
    }
  }, [open]);
  const changeOpen = (value: boolean) => {
    focusOnChange.current = true;
    store.set("dr-assistant-collapsed", !value);
    setOpen(value);
  };
  const send = () =>
    action.run(async () => {
      if (!text.trim()) return;
      const chat = await launchChat(business.id, text, context);
      if (action.isMounted()) {
        refresh();
        location.hash = `chat/${chat.id}`;
      }
    });
  return (
    <div
      ref={container}
      role="region"
      aria-label="Asistente del negocio"
      className={
        inline
          ? "w-full"
          : "pointer-events-none absolute inset-x-0 bottom-0 z-20 flex justify-end px-3 pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-6 sm:pb-6"
      }
    >
      <Collapsible
        open={inline || open}
        onOpenChange={changeOpen}
        className={
          inline || open
            ? "pointer-events-auto mx-auto w-full max-w-2xl"
            : "pointer-events-auto"
        }
      >
        {!inline && !open && (
          <CollapsibleTrigger asChild>
            <Button
              className="h-12 rounded-full px-5 shadow-lg"
              aria-label="Abrir asistente: pregunta algo"
            >
              {action.busy ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <MessageCircle className="size-4" />
              )}
              {action.busy
                ? "Enviando…"
                : action.error
                  ? "Reintentar pregunta"
                  : "Pregunta algo"}
            </Button>
          </CollapsibleTrigger>
        )}
        <CollapsibleContent asChild>
          <motion.div
            layoutId={`assistant-bar-${business.id}`}
            initial={false}
            transition={{
              layout: { duration: reducedMotion ? 0 : 0.32, ease: "easeInOut" },
            }}
            className="relative rounded-[2rem] bg-background shadow-[0_8px_40px_-8px_rgba(0,0,0,0.25)] dark:shadow-[0_8px_40px_-8px_rgba(0,0,0,0.6)]"
          >
            {!inline && (
              <CollapsibleTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute -top-9 right-3 size-7 rounded-full bg-background text-muted-foreground shadow-sm hover:bg-muted aria-expanded:bg-background"
                  aria-label="Minimizar asistente"
                  title="Minimizar asistente"
                >
                  <ChevronDown className="size-3.5" />
                </Button>
              </CollapsibleTrigger>
            )}
            {(context.analysis_id || context.finding_reference) && (
              <div className="flex items-center gap-2 px-5 pt-2 text-xs text-muted-foreground">
                <span className="min-w-0 flex-1 truncate" title={context.label}>
                  {context.label || "Contexto seleccionado"}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-8 shrink-0 rounded-full"
                  aria-label="Quitar contexto"
                  onClick={() => setContext({})}
                >
                  <X className="size-3" />
                </Button>
              </div>
            )}
            <Composer
              compact
              text={text}
              onChange={setText}
              onSend={send}
              busy={action.busy}
              error={action.error}
              placeholder="Pregunta algo…"
            />
          </motion.div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}
