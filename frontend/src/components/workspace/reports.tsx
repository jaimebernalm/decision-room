import { translate as tr, useLanguage } from "@/lib/i18n";
import { useState } from "react";
import {
  Plus,
  ArrowUpRight,
  Trash2,
  Undo2,
  Check,
  MousePointer2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from "@/components/ui/table";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
} from "@/components/ui/alert-dialog";
import { api, date, reportState, analysisHref } from "@/lib/api";
import { useAction, useResource } from "@/lib/hooks";
import { useWorkspace } from "@/lib/workspace";
import { blockId, useAssistant } from "@/lib/assistant";
import type { Analysis } from "@/lib/types";
import { Heading, Notice, Loading, Busy } from "./shared";
import { useBlockSelection } from "./context-selection";

export function Reports() {
  const [trash, setTrash] = useState(false);
  const assistant = useAssistant();
  return (
    <ReportsList
      key={String(trash)}
      trash={trash}
      onToggle={() => {
        assistant?.setSelecting(false);
        setTrash(!trash);
      }}
    />
  );
}
function ReportsList({
  trash,
  onToggle,
}: {
  trash: boolean;
  onToggle: () => void;
}) {
  useLanguage();
  const { workspace, refresh } = useWorkspace();
  const [search, setSearch] = useState("");
  const [deleting, setDeleting] = useState<Analysis | null>(null);
  const action = useAction();
  const selecting = useAssistant()?.selecting;
  return (
    <>
      <Heading
        title={trash ? tr("Informes eliminados") : tr("Informes")}
        description={
          trash
            ? tr(
                "Puedes restaurarlos para que vuelvan a aparecer en el listado.",
              )
            : tr("Resultados, contexto y evidencia en un mismo lugar.")
        }
      >
        <div
          className={`flex flex-wrap gap-2 ${selecting ? "invisible" : ""}`}
          inert={selecting || undefined}
        >
          <Button variant="outline" onClick={onToggle}>
            {trash ? <Undo2 /> : <Trash2 />}
            {trash ? tr("Volver a informes") : tr("Papelera")}
          </Button>
          {!trash && (
            <Button asChild>
              <a href="#new">
                <Plus />
                {tr("Crear informe")}
              </a>
            </Button>
          )}
        </div>
      </Heading>
      <Input
        aria-label={tr("Buscar informes")}
        placeholder={tr("Buscar por título o archivo…")}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-6 max-w-sm"
      />
      {trash ? (
        <DeletedReports search={search} />
      ) : (
        <ReportTable
          items={workspace.analyses}
          search={search}
          onDelete={setDeleting}
        />
      )}
      <AlertDialog
        open={Boolean(deleting)}
        onOpenChange={(open) => {
          if (!open && !action.busy) setDeleting(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{tr("Eliminar informe")}</AlertDialogTitle>
            <AlertDialogDescription>
              «{deleting?.title}
              {tr(
                "» se moverá a la papelera. Podrás restaurarlo; sus datos y las referencias de las conversaciones se conservan.",
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <Notice error>{action.error}</Notice>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={action.busy}>
              {tr("Cancelar")}
            </AlertDialogCancel>
            <Button
              variant="destructive"
              disabled={action.busy}
              onClick={() =>
                action.run(async () => {
                  await api(`/api/jobs/${deleting!.id}/delete`, {
                    business_id: workspace.business!.id,
                  });
                  setDeleting(null);
                  refresh();
                })
              }
            >
              {action.busy && <Busy />}
              {tr("Mover a la papelera")}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
function DeletedReports({ search }: { search: string }) {
  const { workspace, refresh } = useWorkspace();
  const resource = useResource<{ items: Analysis[] }>("/api/reports/deleted");
  const action = useAction();
  return (
    <>
      <Notice error>{resource.error || action.error}</Notice>
      {!resource.data ? (
        !resource.error && <Loading />
      ) : (
        <ReportTable
          items={resource.data.items}
          search={search}
          trash
          busy={action.busy}
          onRestore={(item) =>
            action.run(async () => {
              await api(`/api/jobs/${item.id}/restore`, {
                business_id: workspace.business!.id,
              });
              resource.refresh();
              refresh();
            })
          }
        />
      )}
    </>
  );
}
type TableProps = {
  items: Analysis[];
  search: string;
  trash?: boolean;
  busy?: boolean;
  onDelete?: (item: Analysis) => void;
  onRestore?: (item: Analysis) => void;
};
function ReportTable({ items, search, ...actions }: TableProps) {
  useLanguage();
  const filtered = items.filter((a) =>
    `${a.title} ${a.filename}`
      .toLocaleLowerCase()
      .includes(search.toLocaleLowerCase()),
  );
  return filtered.length ? (
    <Card className="gap-0 overflow-hidden py-0 shadow-none">
      <Table className="[&_th]:px-4 [&_td]:px-4">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>{tr("Informe")}</TableHead>
            <TableHead>{tr("Estado")}</TableHead>
            <TableHead className="hidden sm:table-cell">
              {tr("Creado")}
            </TableHead>
            <TableHead>
              <span className="sr-only">{tr("Acciones")}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.map((a) => (
            <ReportRow key={a.id} item={a} {...actions} />
          ))}
        </TableBody>
      </Table>
    </Card>
  ) : (
    <p className="py-10 text-center text-sm text-muted-foreground">
      {search
        ? tr("No hay informes que coincidan con tu búsqueda.")
        : actions.trash
          ? tr("La papelera está vacía.")
          : tr("Todavía no hay informes. Crea uno para empezar.")}
    </p>
  );
}
function ReportRow({
  item: a,
  trash,
  busy,
  onDelete,
  onRestore,
}: Omit<TableProps, "items" | "search"> & { item: Analysis }) {
  useLanguage();
  const reference = trash ? undefined : a.context_reference;
  const { assistant, active, selected } = useBlockSelection(reference);
  const selecting = Boolean(assistant?.selecting && !trash);
  const status = reportState(a);
  const label =
    (
      {
        completed: tr("Disponible"),
        historical: tr("Versión anterior"),
        outdated: tr("Contexto cambiado"),
        withdrawn: tr("Retirado"),
        queued: tr("En preparación"),
        waiting: tr("Necesita tu respuesta"),
        running: tr("En preparación"),
        failed: tr("Interrumpido"),
        blocked: tr("Necesita atención"),
      } as Record<string, string>
    )[status] || status;
  const color =
    status === "withdrawn"
      ? "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200"
      : status === "completed"
        ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200"
        : "";
  return (
    <TableRow
      id={reference ? blockId(reference) : undefined}
      className={`report-pick-row ${selecting && !active ? "report-unselectable" : "cursor-pointer"} ${selected ? "context-picked" : ""}`}
      onClick={(event) => {
        if (!selecting && !(event.target as HTMLElement).closest("a, button"))
          location.hash = analysisHref(a);
      }}
    >
      <TableCell className="whitespace-normal">
        <div inert={selecting || undefined}>
          <a
            className="break-words font-medium hover:underline"
            href={analysisHref(a)}
          >
            {a.title}
          </a>
          <p className="mt-1 break-all text-xs text-muted-foreground">
            {a.filename}
          </p>
        </div>
      </TableCell>
      <TableCell>
        <Badge variant="secondary" className={color}>
          {label}
        </Badge>
        {selecting && !active && (
          <p className="mt-1 text-xs text-muted-foreground">
            {tr("No se puede seleccionar")}
          </p>
        )}
      </TableCell>
      <TableCell className="hidden text-muted-foreground sm:table-cell">
        {date(a.created_at)}
      </TableCell>
      <TableCell className="w-14 sm:w-24">
        <div
          inert={selecting || undefined}
          className={selecting ? "invisible flex" : "flex justify-end"}
        >
          <Button
            asChild
            variant="ghost"
            size="icon"
            className="hidden sm:inline-flex"
          >
            <a
              href={analysisHref(a)}
              aria-label={tr("Abrir {0}", { "0": a.title })}
            >
              <ArrowUpRight />
            </a>
          </Button>
          {trash ? (
            <Button
              variant="ghost"
              size="icon"
              disabled={busy}
              aria-label={tr("Restaurar {0}", { "0": a.title })}
              title={tr("Restaurar informe")}
              onClick={() => onRestore?.(a)}
            >
              <Undo2 />
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="icon"
              disabled={["queued", "running", "waiting"].includes(a.status)}
              aria-label={tr("Eliminar {0}", { "0": a.title })}
              title={tr("Eliminar informe")}
              onClick={() => onDelete?.(a)}
            >
              <Trash2 />
            </Button>
          )}
        </div>
        {active && reference && (
          <button
            type="button"
            className="context-hit report-selection-hit"
            aria-label={`${selected ? tr("Quitar") : tr("Seleccionar")}: ${reference.title}`}
            aria-pressed={Boolean(selected)}
            onClick={() => assistant!.toggle(reference)}
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
      </TableCell>
    </TableRow>
  );
}
