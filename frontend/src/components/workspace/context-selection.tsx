import { useState, useEffect, type ReactNode } from "react";
import { MousePointer2, Check, FileText, MessagesSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Attachments,
  Attachment,
  AttachmentRemove,
} from "@/components/ai-elements/attachments";
import {
  useAssistant,
  referenceId,
  blockId,
  selectableRoute,
} from "@/lib/assistant";
import { useWorkspace } from "@/lib/workspace";
import type {
  ContextAttachment,
  ContextReference,
  ChartData,
} from "@/lib/types";
import { EvidenceChart } from "./report";

export function useBlockSelection(item?: ContextAttachment) {
  const assistant = useAssistant();
  const register = assistant?.register;
  const serialized = item ? JSON.stringify(item) : "";
  useEffect(() => {
    if (register && serialized) return register(JSON.parse(serialized));
  }, [register, serialized]);
  const active = Boolean(assistant?.selecting && item);
  const selected =
    item &&
    assistant?.selected.some((r) => referenceId(r) === referenceId(item));
  return { assistant, active, selected };
}
export function Selectable({
  item,
  children,
}: {
  item?: ContextAttachment;
  children: ReactNode;
}) {
  const { assistant, active, selected } = useBlockSelection(item);
  return (
    <div
      id={item ? blockId(item) : undefined}
      className={`context-block min-w-0 ${active ? "context-pickable" : ""} ${selected ? "context-picked" : ""}`}
    >
      <div inert={active || undefined}>{children}</div>
      {active && item && (
        <button
          type="button"
          className="context-hit"
          aria-label={`${selected ? "Quitar" : "Seleccionar"}: ${item.title}`}
          aria-pressed={Boolean(selected)}
          onClick={() => assistant!.toggle(item)}
        >
          <span className="context-check">
            {selected ? (
              <Check className="size-4" />
            ) : (
              <MousePointer2 className="size-4" />
            )}
          </span>
        </button>
      )}
    </div>
  );
}
export function SelectionTool() {
  const a = useAssistant();
  const { route } = useWorkspace();
  if (!a || !selectableRoute(route)) return null;
  return (
    <Button
      type="button"
      variant={a.selecting ? "secondary" : "ghost"}
      size="sm"
      aria-pressed={a.selecting}
      onClick={() => a.setSelecting(!a.selecting)}
      className="rounded-full text-xs"
    >
      {a.selecting ? (
        <Check className="size-3.5" />
      ) : (
        <MousePointer2 className="size-3.5" />
      )}
      {a.selecting ? "Listo" : "Seleccionar"}
    </Button>
  );
}
function MiniChart({ chart }: { chart: ChartData }) {
  if (chart.kind === "table")
    return <FileText className="size-5 text-muted-foreground" />;
  const values = chart.points.map((p) => Number(p.value));
  const min = Math.min(0, ...values),
    max = Math.max(0, ...values),
    span = max - min || 1;
  const y = (v: number) => 44 - ((v - min) / span) * 38;
  const x = (v: number) => 4 + ((v - min) / span) * 112;
  const dates = chart.points.map((p) => Date.parse(p.label));
  const temporal = dates.every(Number.isFinite) && dates.at(-1)! > dates[0];
  const pointX = (i: number) =>
    temporal
      ? 4 + ((dates[i] - dates[0]) / (dates.at(-1)! - dates[0])) * 112
      : 4 + (i / Math.max(1, values.length - 1)) * 112;
  return (
    <svg
      viewBox="0 0 120 50"
      className="h-12 w-full text-primary"
      aria-hidden="true"
    >
      {chart.kind === "line" ? (
        <>
          {values.map((v, i) => (
            <g key={i}>
              <circle cx={pointX(i)} cy={y(v)} r="1.5" fill="currentColor" />
              {i > 0 && (!temporal || dates[i] - dates[i - 1] <= 86400000) && (
                <line
                  x1={pointX(i - 1)}
                  x2={pointX(i)}
                  y1={y(values[i - 1])}
                  y2={y(v)}
                  stroke="currentColor"
                  strokeWidth="2"
                />
              )}
            </g>
          ))}
        </>
      ) : (
        <>
          <line
            x1={x(0)}
            x2={x(0)}
            y1="3"
            y2="47"
            stroke="currentColor"
            opacity=".2"
          />
          {values.map((v, i) => (
            <rect
              key={i}
              x={Math.min(x(v), x(0))}
              y={4 + (i * 42) / values.length}
              width={Math.max(1, Math.abs(x(v) - x(0)))}
              height={Math.max(1, 34 / values.length)}
              rx="1"
              fill="currentColor"
              opacity=".7"
            />
          ))}
        </>
      )}
    </svg>
  );
}
export function ContextAttachments({
  items,
  onRemove,
  chatId,
}: {
  items: ContextAttachment[];
  onRemove?: (r: ContextReference) => void;
  chatId?: string;
}) {
  const [opened, setOpened] = useState<string | null>(null);
  const assistant = useAssistant();
  const chosen = items.find((r) => referenceId(r) === opened);
  if (!items.length) return null;
  return (
    <>
      <Attachments
        variant="grid"
        className="!ml-0 !w-full gap-2"
        aria-label="Contexto adjunto"
      >
        {items.map((r) => (
          <Attachment
            key={referenceId(r)}
            data={{
              type: "source-document",
              id: referenceId(r),
              sourceId: referenceId(r),
              mediaType: "application/json",
              title: r.title || "Elemento seleccionado",
            }}
            onRemove={onRemove ? () => onRemove(r) : undefined}
            className="!h-auto !w-36 !rounded-xl bg-muted/40"
          >
            <button
              type="button"
              className="w-full rounded-xl p-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={() => setOpened(referenceId(r))}
              aria-label={`Ver adjunto: ${r.title || "Elemento seleccionado"}`}
            >
              <div className="mb-1 flex items-center gap-1 text-[10px] text-muted-foreground">
                {r.kind === "report" && <FileText className="size-3" />}
                {r.kind === "conversation" && (
                  <MessagesSquare className="size-3" />
                )}
                {r.kind === "conversation"
                  ? "Conversación"
                  : r.kind === "report"
                    ? "Informe"
                    : r.kind === "business" || r.kind === "memory"
                      ? "Mi negocio"
                      : "Fragmento de informe"}
              </div>
              <div className="mb-1 flex h-12 items-center overflow-hidden">
                {r.status === "withdrawn" ? (
                  <span className="text-xs text-muted-foreground">
                    Ya no disponible
                  </span>
                ) : r.content && "points" in r.content ? (
                  <MiniChart chart={r.content} />
                ) : r.content && "value" in r.content ? (
                  <span className="truncate text-xl font-semibold">
                    {r.content.value}{" "}
                    <small className="text-xs font-normal">
                      {r.content.unit}
                    </small>
                  </span>
                ) : r.content && "statement" in r.content ? (
                  <span className="line-clamp-3 text-[10px] text-muted-foreground">
                    {r.content.statement}
                  </span>
                ) : (
                  <FileText className="size-5 text-muted-foreground" />
                )}
              </div>
              <span className="block truncate text-xs font-medium">
                {r.title || "Elemento seleccionado"}
              </span>
            </button>
            {onRemove && (
              <AttachmentRemove
                label={`Quitar ${r.title || "elemento"}`}
                className="!opacity-100"
              />
            )}
          </Attachment>
        ))}
      </Attachments>
      <Dialog
        open={Boolean(chosen)}
        onOpenChange={(v) => {
          if (!v) setOpened(null);
        }}
      >
        <DialogContent className="max-h-[85svh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>
              {chosen?.title || "Contexto seleccionado"}
            </DialogTitle>
            <DialogDescription>
              {chosen?.report_title || "Contexto seleccionado"}
              {chosen?.period ? ` · ${chosen.period}` : ""}
            </DialogDescription>
          </DialogHeader>
          {chosen?.status === "withdrawn" ? (
            <p>
              Este contenido ha cambiado o se ha retirado. Vuelve al origen para
              seleccionar su versión actual.
            </p>
          ) : chosen?.content && "points" in chosen.content ? (
            <EvidenceChart chart={chosen.content} />
          ) : chosen?.content && "value" in chosen.content ? (
            <p className="text-3xl font-semibold">
              {chosen.content.value} {chosen.content.unit}
            </p>
          ) : chosen?.content && "statement" in chosen.content ? (
            <p className="whitespace-pre-wrap leading-7">
              {chosen.content.statement}
            </p>
          ) : (
            <p>
              Abre el origen para consultar este elemento antes de enviarlo.
            </p>
          )}
          {chosen?.href && chosen.status !== "withdrawn" && (
            <Button
              variant="outline"
              onClick={() => {
                assistant?.returnToSource(chosen, chatId);
                if (!assistant) location.hash = chosen.href!;
                setOpened(null);
              }}
            >
              {chosen.kind === "conversation"
                ? "Ver conversación original"
                : chosen.href === "#my-business"
                  ? "Ver en Mi negocio"
                  : "Ver en el informe"}
            </Button>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
