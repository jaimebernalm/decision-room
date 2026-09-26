import { Paperclip, ArrowUp, LoaderCircle } from "lucide-react";
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
}: {
  text: string;
  onChange: (v: string) => void;
  onSend: () => Promise<unknown>;
  busy: boolean;
  error?: string;
  placeholder?: string;
  suggestions?: boolean;
}) {
  return (
    <div className="w-full">
      <PromptInput
        onSubmit={async () => {
          await onSend();
        }}
        onReset={(e) => e.preventDefault()}
        className="rounded-2xl [&_[data-slot=input-group]]:has-disabled:opacity-100 [&_[data-slot=input-group]]:has-disabled:bg-transparent"
        maxFiles={0}
      >
        <PromptInputTextarea
          aria-label="Mensaje"
          value={text}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          maxLength={6000}
          className="min-h-24"
        />
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
      <p className="mt-3 text-center text-xs text-muted-foreground">
        Enter para enviar · Mayús + Enter para una nueva línea
      </p>
    </div>
  );
}
