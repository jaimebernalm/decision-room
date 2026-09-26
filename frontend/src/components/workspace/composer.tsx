import type { ReactNode } from "react";
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
export function Composer({
  text,
  onChange,
  onSend,
  busy,
  error,
  placeholder = "Pregunta sobre tu negocio…",
  suggestions = false,
  compact = false,
  trailingAction,
}: {
  text: string;
  onChange: (v: string) => void;
  onSend: () => Promise<unknown>;
  busy: boolean;
  error?: string;
  placeholder?: string;
  suggestions?: boolean;
  compact?: boolean;
  trailingAction?: ReactNode;
}) {
  return (
    <div className="w-full">
      <PromptInput
        onSubmit={async () => {
          await onSend();
        }}
        onReset={(e) => e.preventDefault()}
        className={`[&_[data-slot=input-group]]:has-disabled:opacity-100 [&_[data-slot=input-group]]:has-disabled:bg-transparent ${compact ? "[&_[data-slot=input-group]]:rounded-[2rem] [&_[data-slot=input-group]]:p-2" : "rounded-2xl"}`}
        maxFiles={0}
      >
        {compact && (
          <InputGroupAddon align="inline-start" className="pl-2 pr-0">
            <Sparkles className="size-4" aria-hidden="true" />
          </InputGroupAddon>
        )}
        <PromptInputTextarea
          aria-label="Mensaje"
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
          <InputGroupAddon align="inline-end" className="gap-1 pr-0">
            <PromptInputSubmit
              aria-label="Enviar mensaje"
              className="size-10 rounded-full"
              disabled={!text.trim() || busy}
              status={busy ? "submitted" : "ready"}
            >
              {busy ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <ArrowUp className="size-4" />
              )}
            </PromptInputSubmit>
            {trailingAction}
          </InputGroupAddon>
        ) : (
          <PromptInputFooter>
            <PromptInputTools>
              <PromptInputButton
                aria-label="Gestionar datos y archivos"
                onClick={() => {
                  location.hash = "files";
                }}
              >
                <Paperclip />
                <span className="text-xs">Datos del negocio</span>
              </PromptInputButton>
            </PromptInputTools>
            <PromptInputSubmit
              aria-label="Enviar mensaje"
              disabled={!text.trim() || busy}
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
            "¿Qué sabes de mi negocio?",
            "¿Qué datos tengo disponibles?",
            "¿Qué debería revisar primero?",
          ].map((s) => (
            <Suggestion key={s} suggestion={s} onClick={() => onChange(s)} />
          ))}
        </Suggestions>
      )}
      {!compact && (
        <p className="mt-3 text-center text-xs text-muted-foreground">
          Enter para enviar · Mayús + Enter para una nueva línea
        </p>
      )}
    </div>
  );
}
