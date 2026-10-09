import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  AnimatePresence,
  motion,
  useIsPresent,
  useReducedMotion,
} from "motion/react";
import {
  ChartNoAxesCombined,
  Lightbulb,
  MessageCircle,
  TrendingUp,
} from "lucide-react";
import { translate as tr, useLanguage } from "@/lib/i18n";
import { starterOptions, type StarterChoice } from "@/lib/chat-start";
import { Button } from "@/components/ui/button";

const icons = {
  question: MessageCircle,
  analyze: ChartNoAxesCombined,
  predict: TrendingUp,
  ideas: Lightbulb,
};
const ease = [0.22, 1, 0.36, 1] as const;

function GoalOptions({
  choice,
  disabled,
  onChoose,
  onDismiss,
}: {
  choice: StarterChoice | null;
  disabled: boolean;
  onChoose: (id: StarterChoice) => void;
  onDismiss: () => void;
}) {
  const present = useIsPresent();
  const reduced = useReducedMotion();
  const group = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (choice && present)
      group.current
        ?.querySelector<HTMLButtonElement>('[aria-pressed="true"]')
        ?.focus({ preventScroll: true });
    // Focus on opening, not when the selected card begins its exit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [present]);
  return (
    <motion.div
      className="chat-start-options-surface"
      initial={reduced ? false : { height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: reduced ? 0 : 0.26, ease }}
      inert={!present}
      aria-hidden={!present}
      onKeyDown={(event) => {
        if (choice && event.key === "Escape") {
          event.preventDefault();
          onDismiss();
        }
      }}
    >
      <div
        ref={group}
        className="chat-start-options"
        role="group"
        aria-label={tr("Elige un objetivo")}
      >
        {starterOptions.map((item) => {
          const Icon = icons[item.id];
          return (
            <button
              key={item.id}
              type="button"
              className="chat-start-card"
              aria-label={tr(item.label)}
              aria-pressed={choice === item.id}
              aria-describedby={`goal-${item.id}-badge`}
              disabled={disabled}
              onClick={() => onChoose(item.id)}
            >
              <Icon className="size-5" aria-hidden="true" />
              <span className="chat-start-card-label">{tr(item.label)}</span>
              <span
                className="chat-start-card-badge"
                id={`goal-${item.id}-badge`}
              >
                {tr(item.badge)}
              </span>
            </button>
          );
        })}
      </div>
    </motion.div>
  );
}

export function GoalPicker({
  choice,
  disabled,
  onChoose,
  children,
}: {
  choice: StarterChoice | null;
  disabled: boolean;
  onChoose: (id: StarterChoice) => void;
  children: ReactNode;
}) {
  useLanguage();
  const reduced = useReducedMotion();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const starter = starterOptions.find((item) => item.id === choice);
  const expanded = !starter || open;
  const Icon = starter ? icons[starter.id] : MessageCircle;
  const focusInput = () =>
    root.current?.querySelector("textarea")?.focus({ preventScroll: true });
  const dismiss = () => {
    setOpen(false);
    focusInput();
  };
  const choose = (id: StarterChoice) => {
    setOpen(false);
    onChoose(id);
  };
  return (
    <motion.div
      ref={root}
      layout="position"
      initial={{ opacity: reduced ? 1 : 0 }}
      animate={{ opacity: 1 }}
      transition={{
        opacity: { delay: reduced ? 0 : 0.24, duration: reduced ? 0 : 0.12 },
        layout: { duration: reduced ? 0 : 0.26, ease },
      }}
    >
      <AnimatePresence initial={false}>
        {starter && (
          <motion.div
            className="chat-start-selected-surface"
            initial={reduced ? false : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: reduced ? 0 : 0.2, ease }}
          >
            <div
              className="chat-start-selected"
              role="group"
              aria-label={tr("Objetivo elegido")}
            >
              <motion.span
                key={starter.id}
                className="chat-start-goal"
                role="status"
                initial={{ opacity: reduced ? 1 : 0, y: reduced ? 0 : 3 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: reduced ? 0 : 0.16 }}
              >
                <Icon className="size-4 shrink-0" aria-hidden="true" />
                <span>{tr(starter.label)}</span>
                {starter.upcoming && (
                  <span className="chat-start-goal-badge">
                    {tr("Próximamente")}
                  </span>
                )}
              </motion.span>
              <Button
                variant="ghost"
                size="sm"
                className="chat-start-change"
                type="button"
                aria-label={tr("Cambiar objetivo")}
                aria-expanded={expanded}
                aria-controls="chat-start-goals"
                disabled={disabled}
                onClick={() => {
                  if (open) dismiss();
                  else setOpen(true);
                }}
              >
                {tr("Cambiar")}
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      {children}
      {starter?.upcoming && !expanded && (
        <motion.div
          className="chat-start-continue"
          initial={{ opacity: reduced ? 1 : 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: reduced ? 0 : 0.12 }}
        >
          <Button
            variant="ghost"
            size="sm"
            type="button"
            disabled={disabled}
            onClick={() => choose("question")}
          >
            {tr("Continuar como pregunta")}
          </Button>
        </motion.div>
      )}
      <div id="chat-start-goals">
        <AnimatePresence initial={false}>
          {expanded && (
            <GoalOptions
              key="goals"
              choice={choice}
              disabled={disabled}
              onChoose={choose}
              onDismiss={dismiss}
            />
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
