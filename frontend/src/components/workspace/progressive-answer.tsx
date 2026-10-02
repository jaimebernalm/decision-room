import { translate as tr, useLanguage } from "@/lib/i18n";
import { useEffect, useState, type ReactNode } from "react";
import type { Response } from "@/lib/types";

// In-memory only: navigating between the chat and its dock must not replay text.
const delivered = new Map<string, string>();
export function ProgressiveAnswer({
  id,
  response,
  animate,
  children,
}: {
  id: string;
  response?: Response | null;
  animate: boolean;
  children: (response: Response | null, revealing: boolean) => ReactNode;
}) {
  useLanguage();
  const text = response?.text || "";
  const [eligible] = useState(animate || !response);
  const [shown, setShown] = useState(() =>
    !eligible || delivered.get(id) === text ? text : "",
  );
  const [skipped, setSkipped] = useState(false);
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const active = Boolean(
    text &&
    !(response?.kind === "evidence" && response.scope) &&
    eligible &&
    shown !== text &&
    !skipped &&
    !reduced,
  );
  const revealing = active && shown !== text;
  useEffect(() => {
    if (!text) return;
    const finish = () => {
      delivered.set(id, text);
      if (delivered.size > 256)
        delivered.delete(delivered.keys().next().value!);
      setShown(text);
    };
    if (!active) {
      finish();
      return;
    }
    const start = performance.now();
    const duration = Math.min(4500, Math.max(450, (text.length / 180) * 1000));
    const timer = window.setInterval(() => {
      if (document.hidden) {
        finish();
        window.clearInterval(timer);
        return;
      }
      const progress = Math.min(1, (performance.now() - start) / duration);
      if (progress === 1) {
        finish();
        window.clearInterval(timer);
        return;
      }
      // Whole word boundaries keep accented characters and emoji sequences intact.
      const target = Math.floor(text.length * progress);
      const end = text.indexOf(" ", target);
      setShown(text.slice(0, end < 0 ? text.length : end));
    }, 32);
    return () => {
      window.clearInterval(timer);
      delivered.set(id, text);
    };
  }, [id, text, active]);
  const visible = response
    ? revealing
      ? {
          ...response,
          text: shown,
          sources: [],
          evidence: undefined,
          questions: [],
          items: [],
        }
      : response
    : null;
  return (
    <>
      {children(visible, revealing)}
      {revealing && (
        <>
          <p className="sr-only" role="status">
            {tr("Respuesta revisada disponible.")}
          </p>
          <p className="sr-only">{text}</p>
          <button
            type="button"
            onClick={() => setSkipped(true)}
            className="mt-1 text-xs text-muted-foreground underline underline-offset-4"
          >
            {tr("Mostrar respuesta completa")}
          </button>
        </>
      )}
    </>
  );
}
