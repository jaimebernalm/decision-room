import { translate as tr, useLanguage } from "@/lib/i18n";
import { useId, useRef, useState, type ReactNode } from "react";
import { Pencil, History, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { api, date } from "@/lib/api";
import { presentationNumber } from "@/lib/presentation";
import { useAction } from "@/lib/hooks";
import { useWorkspace } from "@/lib/workspace";
import type { Presentation, Report } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Notice } from "./shared";

export type EditTarget = {
  kind: "report" | "metric" | "chart" | "insight";
  key: string;
  title: string;
};
type Change = {
  kind: string;
  key: string;
  field: string;
  value: string | number;
};
export function PresentationEditor({
  presentation,
  target,
  renderTrigger,
}: {
  presentation?: Presentation;
  target: EditTarget;
  renderTrigger?: (openEditor: () => void, open: boolean) => ReactNode;
}) {
  useLanguage();
  const { workspace } = useWorkspace();
  const action = useAction();
  const request = useRef<{ body: string; key: string } | null>(null);
  const [open, setOpen] = useState(false);
  const [base, setBase] = useState<Report | null>(null);
  const [tab, setTab] = useState("element");
  const [title, setTitle] = useState("");
  const [unit, setUnit] = useState("");
  const [decimals, setDecimals] = useState(0);
  const [names, setNames] = useState<Record<string, string>>({});
  const [historical, setHistorical] = useState<Report | null>(null);
  const unitListId = useId();
  if (!presentation) return renderTrigger?.(() => {}, false) ?? null;
  const endpoint = `/api/presentation/${presentation.report_id}`;
  const element =
    base &&
    (target.kind === "report"
      ? base
      : target.kind === "metric"
        ? base.highlights.find((x) => x.key === target.key)
        : target.kind === "chart"
          ? base.charts.find((x) => x.key === target.key)
          : base.claims.find((x) => x.key === target.key));
  const originalTitle = element
    ? "label" in element
      ? element.label
      : element.title
    : "";
  const numeric = element && "unit" in element ? element : null;
  const changes: Change[] = [];
  if (title !== originalTitle)
    changes.push({ ...target, field: "title", value: title });
  if (numeric && unit !== numeric.unit)
    changes.push({ ...target, field: "unit", value: unit });
  if (numeric && decimals !== (numeric.decimals ?? 0))
    changes.push({ ...target, field: "decimals", value: decimals });
  for (const label of base?.presentation?.labels ?? []) {
    if (names[label.id] !== label.name)
      changes.push({
        kind: "entity",
        key: label.id,
        field: "name",
        value: names[label.id],
      });
  }
  // Send only the explicit edit contract, never UI labels or inferred values.
  const cleanChanges = changes.map(({ kind, key, field, value }) => ({
    kind,
    key,
    field,
    value,
  }));
  const load = () =>
    action.run(async () => {
      const report = await api<Report>(endpoint);
      setBase(report);
      const selected =
        target.kind === "report"
          ? report
          : target.kind === "metric"
            ? report.highlights.find((x) => x.key === target.key)
            : target.kind === "chart"
              ? report.charts.find((x) => x.key === target.key)
              : report.claims.find((x) => x.key === target.key);
      if (!selected)
        throw new Error(tr("Este elemento ya no está disponible."));
      setTitle("label" in selected ? selected.label : selected.title);
      setUnit("unit" in selected ? selected.unit : "");
      setDecimals("decimals" in selected ? (selected.decimals ?? 0) : 0);
      setNames(
        Object.fromEntries(
          (report.presentation?.labels ?? []).map((x) => [x.id, x.name]),
        ),
      );
    });
  const save = (restore_revision?: number) =>
    action.run(async () => {
      if (!base?.presentation || !workspace.business) return;
      const body = {
        business_id: workspace.business.id,
        base_version: base.presentation.base_version,
        revision: base.presentation.revision,
        ...(restore_revision === undefined
          ? { changes: cleanChanges }
          : { restore_revision }),
      };
      const signature = JSON.stringify(body);
      if (request.current?.body !== signature)
        request.current = { body: signature, key: crypto.randomUUID() };
      await api(endpoint, { ...body, request_key: request.current.key });
      dispatchEvent(new Event("dr-presentation"));
      toast.success(
        restore_revision === undefined
          ? tr("Cambios guardados en Inicio, informe y PDF")
          : tr("Versión restaurada en Inicio, informe y PDF"),
      );
      setOpen(false);
    });
  const previewNumber =
    numeric && "raw_value" in numeric ? numeric.raw_value : undefined;
  const openEditor = () => {
    setOpen(true);
    setBase(null);
    setHistorical(null);
    setTab("element");
    action.setError("");
    void load();
  };
  return (
    <>
      {renderTrigger ? (
        renderTrigger(openEditor, open)
      ) : (
        <Button
          variant="ghost"
          size="icon"
          className="size-8 shrink-0 text-muted-foreground"
          aria-label={tr("Editar {0}", { "0": target.title })}
          title={tr("Editar presentación")}
          onClick={openEditor}
        >
          <Pencil className="size-4" />
        </Button>
      )}
      <Dialog
        open={open}
        onOpenChange={(value) => {
          if (!action.busy) setOpen(value);
        }}
      >
        <DialogContent className="sm:max-w-xl max-h-[90dvh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{tr("Editar presentación")}</DialogTitle>
            <DialogDescription>
              {tr(
                "Los cambios se verán en Inicio, en este informe y en su PDF. Las cifras y las fuentes se conservan.",
              )}
            </DialogDescription>
          </DialogHeader>
          <div
            className="flex flex-wrap gap-2"
            role="tablist"
            aria-label={tr("Opciones de edición")}
          >
            {[
              ["element", tr("Este elemento")],
              ["names", tr("Nombres del catálogo")],
              ["history", tr("Historial")],
            ].map(([key, text]) => (
              <Button
                key={key}
                role="tab"
                aria-selected={tab === key}
                variant={tab === key ? "secondary" : "ghost"}
                size="sm"
                onClick={() => {
                  setTab(key);
                  setHistorical(null);
                }}
              >
                {key === "history" && <History className="size-4" />}
                {text}
              </Button>
            ))}
          </div>
          <Notice error>{action.error}</Notice>
          {!base && !action.error && (
            <p role="status">{tr("Cargando presentación…")}</p>
          )}
          {base && tab === "element" && (
            <div className="space-y-4">
              <label className="block space-y-2">
                <span className="font-medium">{tr("Título visible")}</span>
                <Input
                  value={title}
                  maxLength={250}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </label>
              {numeric && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="space-y-2">
                    <span className="block font-medium">
                      {tr("Unidad visible")}
                    </span>
                    {numeric.unit_customizable ? (
                      <>
                        <Input
                          aria-label={tr("Unidad visible")}
                          list={unitListId}
                          value={unit}
                          maxLength={180}
                          onChange={(e) => setUnit(e.target.value)}
                        />
                        <datalist id={unitListId}>
                          {numeric.unit_choices?.map((u) => (
                            <option key={u} value={u} />
                          ))}
                        </datalist>
                        <span className="block text-xs text-muted-foreground">
                          {tr(
                            "Puedes aclarar la unidad con tus palabras. Las cantidades no se convierten.",
                          )}
                          {numeric.original_unit &&
                            tr(" Unidad del análisis: {0}.", {
                              "0": numeric.original_unit,
                            })}
                        </span>
                      </>
                    ) : (
                      <select
                        className="w-full rounded-md border bg-background p-2"
                        value={unit}
                        onChange={(e) => setUnit(e.target.value)}
                      >
                        {(numeric.unit_choices ?? [numeric.unit]).map((u) => (
                          <option key={u} value={u}>
                            {u}
                          </option>
                        ))}
                      </select>
                    )}
                  </label>
                  <label className="space-y-2">
                    <span className="block font-medium">{tr("Decimales")}</span>
                    <select
                      className="w-full rounded-md border bg-background p-2"
                      value={decimals}
                      onChange={(e) => setDecimals(Number(e.target.value))}
                    >
                      {Array.from({ length: 7 }, (_, i) => (
                        <option key={i} value={i}>
                          {i}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              )}
              <div
                className="rounded-lg border bg-muted/40 p-4 space-y-2"
                aria-label={tr("Vista previa")}
              >
                <p className="text-xs text-muted-foreground">
                  {tr("Vista previa")}
                </p>
                <p className="font-medium break-words">{title}</p>
                {previewNumber !== undefined && (
                  <p className="text-2xl font-semibold tabular-nums">
                    {presentationNumber(previewNumber, decimals)}{" "}
                    <span className="text-sm font-normal">{unit}</span>
                  </p>
                )}
                {target.kind === "chart" && (
                  <p className="text-sm">
                    {unit}
                    {tr(
                      " · El formato se aplicará a los valores del gráfico y su tabla.",
                    )}
                  </p>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                {tr(
                  "Para cambiar cifras, cálculos o el significado de una unidad, pide una corrección del análisis en el chat.",
                )}
              </p>
            </div>
          )}
          {base && tab === "names" && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {tr(
                  "Cada nombre cambia en todas las apariciones de su código dentro de este informe.",
                )}
              </p>
              {!base.presentation?.labels.length && (
                <p>
                  {tr(
                    "No hay correspondencias de catálogo comprobadas para este informe.",
                  )}
                </p>
              )}
              {base.presentation?.labels.map((label) => (
                <label key={label.id} className="block space-y-1">
                  <span className="font-medium">{label.code}</span>
                  <Input
                    aria-label={tr("Nombre de {0}", { "0": label.code })}
                    maxLength={180}
                    value={names[label.id] ?? label.name}
                    onChange={(e) =>
                      setNames({ ...names, [label.id]: e.target.value })
                    }
                  />
                  <span className="block text-xs text-muted-foreground">
                    {tr("Catálogo: ")}
                    {label.catalog_name}
                  </span>
                </label>
              ))}
            </div>
          )}
          {base && tab === "history" && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                {tr(
                  "Restaurar crea una nueva versión. Los cambios anteriores y el análisis original se conservan.",
                )}
              </p>
              {base.presentation?.history.map((version) => (
                <div
                  key={version.revision}
                  className="flex items-center justify-between gap-3 rounded-lg border p-3"
                >
                  <div>
                    <p className="font-medium">
                      {tr("Versión ")}
                      {version.revision}
                      {version.revision === base.presentation?.revision
                        ? tr(" · Actual")
                        : ""}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {version.description}
                      {version.created_at
                        ? ` · ${date(version.created_at)}`
                        : ""}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={action.busy}
                    onClick={() =>
                      void action.run(async () =>
                        setHistorical(
                          await api<Report>(
                            `${endpoint}?revision=${version.revision}`,
                          ),
                        ),
                      )
                    }
                  >
                    {tr("Ver")}
                  </Button>
                </div>
              ))}
              {historical && (
                <div className="space-y-3 rounded-lg bg-muted p-4">
                  <p className="text-xs">
                    {tr("Vista previa · Versión ")}
                    {historical.presentation?.revision}
                  </p>
                  <p className="font-medium">{historical.title}</p>
                  <ul className="space-y-1 text-sm">
                    {historical.highlights.map((h) => (
                      <li key={h.key}>
                        {h.label}: {h.value} {h.unit}
                      </li>
                    ))}
                  </ul>
                  <ul className="text-sm">
                    {historical.charts.map((c) => (
                      <li key={c.key}>{c.title}</li>
                    ))}
                  </ul>
                  <ul className="space-y-1 text-sm">
                    {historical.claims.map((c) => (
                      <li key={c.key}>{c.title}</li>
                    ))}
                  </ul>
                  <details>
                    <summary className="cursor-pointer text-sm">
                      {tr("Nombres de esta versión")}
                    </summary>
                    <ul className="mt-2 space-y-1 text-sm">
                      {historical.presentation?.labels.map((label) => (
                        <li key={label.id}>
                          {label.code}: {label.name}
                        </li>
                      ))}
                    </ul>
                  </details>
                  {historical.presentation?.revision !==
                    base.presentation?.revision && (
                    <Button
                      disabled={action.busy}
                      variant="outline"
                      onClick={() =>
                        void save(historical.presentation!.revision)
                      }
                    >
                      <RotateCcw />
                      {tr("Restaurar esta versión")}
                    </Button>
                  )}
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              disabled={action.busy}
              onClick={() => setOpen(false)}
            >
              {tr("Cancelar")}
            </Button>
            {tab !== "history" && (
              <Button
                disabled={
                  action.busy ||
                  !base ||
                  !element ||
                  !title.trim() ||
                  (numeric && !unit.trim()) ||
                  !cleanChanges.length
                }
                onClick={() => void save()}
              >
                {action.busy ? tr("Guardando…") : tr("Guardar cambios")}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
