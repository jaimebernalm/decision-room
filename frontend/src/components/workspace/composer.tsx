import { translate as tr, useLanguage } from "@/lib/i18n";
import { useEffect, useRef, type ReactNode } from "react";
import { useReducedMotion } from "motion/react";
import { Paperclip, ArrowUp, LoaderCircle, Sparkles } from "lucide-react";
import { InputGroupAddon } from "@/components/ui/input-group";
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputFooter,
  PromptInputTools,
  PromptInputButton,
  PromptInputSubmit,
} from "@/components/ai-elements/prompt-input";
import { Suggestion, Suggestions } from "@/components/ai-elements/suggestion";
import { Notice } from "./shared";
import "./composer.css";
export function Composer({
  text,
  onChange,
  onSend,
  busy,
  disabled = false,
  error,
  placeholder = tr("Pregunta sobre tu negocio…"),
  animatePlaceholder = false,
  suggestions = false,
  compact = false,
  attachments,
  tools,
}: {
  text: string;
  onChange: (v: string) => void;
  onSend: () => Promise<unknown>;
  busy: boolean;
  disabled?: boolean;
  error?: string;
  placeholder?: string;
  animatePlaceholder?: boolean;
  suggestions?: boolean;
  compact?: boolean;
  attachments?: ReactNode;
  tools?: ReactNode;
}) {
  useLanguage();
  const reduced = useReducedMotion();
  const field = useRef<HTMLTextAreaElement>(null);
  const lastPlaceholder = useRef(placeholder);
  useEffect(() => {
    const changed = lastPlaceholder.current !== placeholder;
    lastPlaceholder.current = placeholder;
    // Animate the empty field's example, keeping its node, focus and caret intact.
    // Typing or changing the motion preference cancels an in-progress animation.
    if (
      !changed ||
      !animatePlaceholder ||
      text ||
      reduced ||
      !field.current?.animate
    )
      return;
    const animation = field.current.animate(
      [
        { opacity: 0.35, transform: "translateY(2px)" },
        { opacity: 1, transform: "translateY(0)" },
      ],
      { duration: 160, easing: "ease-out" },
    );
    return () => animation.cancel();
  }, [placeholder, animatePlaceholder, text, reduced]);
  return (
    <div className="chat-composer w-full">
      {attachments && <div className="composer-contexts">{attachments}</div>}
      <PromptInput
        onSubmit={async () => {
          if (!busy && !disabled) await onSend();
        }}
        onReset={(e) => e.preventDefault()}
        className={`[&_[data-slot=input-group]]:has-disabled:opacity-100 [&_[data-slot=input-group]]:has-disabled:bg-transparent ${compact ? "[&_[data-slot=input-group]]:rounded-[2rem] [&_[data-slot=input-group]]:p-2" : "rounded-2xl"}`}
        maxFiles={0}
      >
        {compact && (
          <InputGroupAddon align="inline-start" className="pl-2 pr-0">
            {tools || <Sparkles className="size-4" aria-hidden="true" />}
          </InputGroupAddon>
        )}
        <PromptInputTextarea
          ref={field}
          aria-label={tr("Mensaje")}
          value={text}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          maxLength={6000}
          rows={compact ? 1 : undefined}
          className={
            compact
              ? "min-h-10 max-h-32 py-2.5 text-base sm:text-sm"
              : "min-h-24"
          }
        />
        {compact ? (
          <InputGroupAddon
            align="inline-end"
            className="py-0 pr-1 has-[>button]:mr-0"
          >
            <PromptInputSubmit
              aria-label={tr("Enviar mensaje")}
              className="size-9 rounded-full"
              disabled={!text.trim() || busy || disabled}
              status={busy ? "submitted" : "ready"}
            >
              {busy ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <ArrowUp className="size-4" />
              )}
            </PromptInputSubmit>
          </InputGroupAddon>
        ) : (
          <PromptInputFooter>
            <PromptInputTools>
              {tools}
              <PromptInputButton
                aria-label={tr("Gestionar datos y archivos")}
                onClick={() => {
                  location.hash = "files";
                }}
              >
                <Paperclip />
                <span className="text-xs">{tr("Datos del negocio")}</span>
              </PromptInputButton>
            </PromptInputTools>
            <PromptInputSubmit
              aria-label={tr("Enviar mensaje")}
              disabled={!text.trim() || busy || disabled}
              status={busy ? "submitted" : "ready"}
            >
              {busy ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <ArrowUp className="size-4" />
              )}
            </PromptInputSubmit>
          </PromptInputFooter>
        )}
      </PromptInput>
      <Notice error>{error}</Notice>
      {suggestions && (
        <Suggestions className="mt-4">
          {[
            tr("¿Qué sabes de mi negocio?"),
            tr("¿Qué datos tengo disponibles?"),
            tr("¿Qué debería revisar primero?"),
          ].map((s) => (
            <Suggestion key={s} suggestion={s} onClick={() => onChange(s)} />
          ))}
        </Suggestions>
      )}
      {!compact && (
        <p className="mt-3 text-center text-xs text-muted-foreground">
          {tr("Enter para enviar · Mayús + Enter para una nueva línea")}
        </p>
      )}
    </div>
  );
}
