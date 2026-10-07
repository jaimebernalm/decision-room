import { useRef, useState, type ReactNode } from "react";
import { Download, MessageSquare, Plus } from "lucide-react";
import { translate as tr } from "@/lib/i18n";
import { contextKey, store } from "@/lib/api";
import { useAssistant } from "@/lib/assistant";
import { useWorkspace } from "@/lib/workspace";
import type { Dataset } from "@/lib/types";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";
import { tableName } from "@/lib/table-name";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "@/components/ui/tooltip";
import { DataModelPanel } from "./data-model";
import { DataPreview } from "./data-preview";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

function DataGroup({
  id,
  title,
  count,
  onUpload,
  children,
}: {
  id: string;
  title: string;
  count?: number;
  onUpload?: () => void;
  children: ReactNode;
}) {
  return (
    <AccordionItem
      value={id}
      className="rounded-xl border border-border bg-card shadow-sm"
    >
      <div className="relative rounded-xl bg-muted/50 transition-colors hover:bg-sidebar-accent focus-within:bg-sidebar-accent motion-reduce:transition-none">
        <AccordionTrigger className="items-center gap-3 rounded-xl px-4 py-4 text-base font-semibold text-foreground hover:no-underline">
          <span
            className={`flex min-w-0 items-center gap-3 ${onUpload ? "pr-14" : ""}`}
          >
            {title}{" "}
            {count !== undefined && (
              <span className="inline-flex min-w-6 items-center justify-center rounded-full border border-border bg-background px-1.5 py-0.5 text-xs font-medium text-muted-foreground">
                {count}
              </span>
            )}
          </span>
        </AccordionTrigger>
        {onUpload && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="icon"
                  className="absolute top-1/2 right-10 size-9 -translate-y-1/2 rounded-full shadow-none [@media(pointer:coarse)]:size-11"
                  aria-label={tr("Subir datos")}
                  onClick={onUpload}
                >
                  <Plus className="size-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>{tr("Subir datos")}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </div>
      <AccordionContent className="h-auto px-4 pt-1 pb-2 [&_p:not(:last-child)]:mb-0">
        {children}
      </AccordionContent>
    </AccordionItem>
  );
}

export function DossierDataGroups({
  business,
  datasets,
  onUpload,
}: {
  business: string;
  datasets: Dataset[];
  onUpload: () => void;
}) {
  const tableTrigger = useRef<HTMLButtonElement | null>(null);
  const [table, setTable] = useState<{ id: string; name: string } | null>(null);
  const current = datasets.filter(
    (d) => !d.library_hidden && !d.corrected && !d.superseded_by,
  );
  const assistant = useAssistant();
  const { route } = useWorkspace();
  const prepared = current.filter(
    (d) =>
      (d.status === "ready" || d.status === "partial") &&
      !d.corrected &&
      (d.files?.filter((f) => f.status !== "failed").length || 0) > 1,
  );
  return (
    <>
      <Accordion
        type="multiple"
        defaultValue={["files", "tables", "relations"]}
        className="gap-4 min-w-0"
      >
        <DataGroup
          id="files"
          title={tr("Archivos")}
          count={current.reduce(
            (n, d) => n + (d.original_files?.length || 0),
            0,
          )}
          onUpload={onUpload}
        >
          {current.length ? (
            <ul className="space-y-2">
              {current.map((d) => (
                <li key={d.id} className="space-y-3 py-3">
                  {d.original_files?.length ? (
                    d.original_files.map((file) => (
                      <div
                        key={file.path}
                        className="flex items-center gap-2 text-sm"
                      >
                        <span className="min-w-0 flex-1 break-all">
                          {file.path} · {(file.size / 1_000_000).toFixed(1)} MB
                        </span>
                        <Button asChild size="icon" variant="ghost">
                          <a
                            href={`/api/datasets/original/${d.id}?path=${encodeURIComponent(file.path)}`}
                            download
                            aria-label={tr("Descargar {0}", { 0: file.path })}
                          >
                            <Download />
                          </a>
                        </Button>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      {tr("No hay archivos originales disponibles.")}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <div className="space-y-2 py-4">
              <p className="text-sm font-medium">
                {tr("Tus datos empiezan aquí")}
              </p>
              <p className="text-sm text-muted-foreground">
                {tr("Sube un CSV o Excel con el botón +.")}
              </p>
            </div>
          )}
        </DataGroup>
        <DataGroup
          id="tables"
          title={tr("Tablas")}
          count={current.reduce((n, d) => n + (d.files?.length || 0), 0)}
        >
          {current.length ? (
            <ul className="space-y-2">
              {current.map((d) => (
                <li key={d.id} className="space-y-3 py-3">
                  {d.files?.length ? (
                    d.files.map((file) => (
                      <div
                        key={file.id}
                        className="flex items-center gap-3 text-sm"
                      >
                        <button
                          type="button"
                          className="flex min-w-0 flex-1 items-center justify-between gap-3 rounded-xl bg-muted/40 p-3 text-left transition-colors hover:bg-foreground/10 focus-visible:bg-foreground/10 disabled:cursor-default disabled:opacity-60"
                          title={file.name}
                          aria-label={tr("Ver tabla {0}", {
                            0: tableName(file.name),
                          })}
                          disabled={
                            file.status === "failed" ||
                            !["ready", "partial"].includes(d.status)
                          }
                          onClick={(event) => {
                            tableTrigger.current = event.currentTarget;
                            setTable({
                              id: file.id,
                              name: tableName(file.name),
                            });
                          }}
                        >
                          <span className="min-w-0 break-words font-medium">
                            {tableName(file.name)}
                          </span>
                          <span className="shrink-0 text-xs text-muted-foreground">
                            {file.status === "failed"
                              ? tr("No se pudo preparar")
                              : tr("{0} filas", { 0: file.rows ?? "—" })}
                          </span>
                        </button>
                        {file.status !== "failed" && (
                          <Button asChild size="icon" variant="ghost">
                            <a
                              href={`/api/datasets/file/${file.id}`}
                              download
                              aria-label={tr("Descargar {0}", {
                                0: tableName(file.name),
                              })}
                            >
                              <Download />
                            </a>
                          </Button>
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      {tr("No hay tablas disponibles para analizar.")}
                    </p>
                  )}
                  {(d.status === "ready" || d.status === "partial") &&
                    !d.corrected &&
                    d.files?.some((file) => file.status !== "failed") && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-auto max-w-full whitespace-normal text-left"
                        onClick={() => {
                          store.set(contextKey(business), {
                            analysis_id: d.id,
                            label: (d.files || [])
                              .map((file) => tableName(file.name))
                              .join(", "),
                          });
                          if (assistant)
                            assistant.setDock({ open: true, origin: route });
                          else location.hash = "ask";
                        }}
                      >
                        <MessageSquare />
                        {tr("Preguntar sobre estas tablas")}
                      </Button>
                    )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-4 text-sm text-muted-foreground">
              {tr("No hay tablas disponibles para analizar.")}
            </p>
          )}
        </DataGroup>
        <DataGroup id="relations" title={tr("Relaciones")}>
          {prepared.length ? (
            <ul className="space-y-2">
              {prepared.map((d) => (
                <li key={d.id} className="space-y-3 py-3">
                  <DataModelPanel business={business} analysis={d.id} inline />
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-4 text-sm text-muted-foreground">
              {tr("No hay conexiones entre tablas todavía.")}
            </p>
          )}
        </DataGroup>
      </Accordion>
      <Dialog
        open={!!table}
        onOpenChange={(open) => {
          if (!open) setTable(null);
        }}
      >
        {table && (
          <DialogContent
            className="flex max-h-[85dvh] flex-col sm:max-w-4xl"
            aria-describedby={undefined}
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              tableTrigger.current?.focus();
            }}
          >
            <DialogHeader className="shrink-0 pr-8">
              <DialogTitle>{table.name}</DialogTitle>
            </DialogHeader>
            <DataPreview
              key={`${business}/${table.id}`}
              endpoint={`/api/datasets/table/${table.id}`}
              compact
            />
          </DialogContent>
        )}
      </Dialog>
    </>
  );
}
