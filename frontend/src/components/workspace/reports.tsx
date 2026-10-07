import { translate as tr, useLanguage } from "@/lib/i18n";
import { useState } from "react";
import {
  Plus,
  ArrowUpRight,
  Trash2,
  Undo2,
  Check,
  MousePointer2,
  FileText,
  Info,
} from "lucide-react";
import { tableName } from "@/lib/table-name";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
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
            : undefined
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
                "» se moverá a la papelera. Podrás restaurarlo; sus datos y las referencias de los chats se conservan.",
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
  const [details, setDetails] = useState<Analysis | null>(null);
  const filtered = items.filter((a) =>
    `${a.title} ${a.filename}`
      .toLocaleLowerCase()
      .includes(search.toLocaleLowerCase()),
  );
  return (
    <>
      {filtered.length ? (
        <Table className="report-library block border-separate border-spacing-y-2 [&_th]:px-4 [&_td]:px-4 [&_tbody]:block [&_tbody]:space-y-3 sm:table sm:[&_tbody]:table-row-group sm:[&_tbody]:space-y-0">
          <TableHeader className="hidden sm:table-header-group">
            <TableRow className="border-0 hover:bg-transparent">
              <TableHead>{tr("Informe")}</TableHead>
              <TableHead>
                <Badge
                  variant="outline"
                  className="font-normal text-muted-foreground"
                >
                  {tr("Estado")}
                </Badge>
              </TableHead>
              <TableHead className="hidden sm:table-cell">
                <Badge
                  variant="outline"
                  className="font-normal text-muted-foreground"
                >
                  {tr("Creado")}
                </Badge>
              </TableHead>
              <TableHead>
                <span className="sr-only">{tr("Acciones")}</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((a) => (
              <ReportRow
                key={a.id}
                item={a}
                onDetails={setDetails}
                {...actions}
              />
            ))}
          </TableBody>
        </Table>
      ) : (
        <p className="py-10 text-center text-sm text-muted-foreground">
          {search
            ? tr("No hay informes que coincidan con tu búsqueda.")
            : actions.trash
              ? tr("La papelera está vacía.")
              : tr("Todavía no hay informes. Crea uno para empezar.")}
        </p>
      )}
      <Dialog
        open={!!details}
        onOpenChange={(open) => {
          if (!open) setDetails(null);
        }}
      >
        {details && <ReportDetails key={details.id} item={details} />}
      </Dialog>
    </>
  );
}
function ReportDetails({ item }: { item: Analysis }) {
  const resource = useResource<{
    tables: { id: string; name: string }[] | null;
    added_tables: { id: string; name: string }[];
  }>(`/api/jobs/${item.id}/sources`);
  return (
    <DialogContent
      className="max-h-[85dvh] overflow-y-auto sm:max-w-md"
      aria-describedby={undefined}
    >
      <DialogHeader>
        <DialogTitle className="pr-6 break-words">{item.title}</DialogTitle>
      </DialogHeader>
      <p className="text-sm text-muted-foreground">
        {tr("Creado")}: {date(item.created_at)}
      </p>
      <Notice error>{resource.error}</Notice>
      {!resource.data && !resource.error && <Loading />}
      {resource.data && (
        <>
          {resource.data.tables ? (
            <section className="space-y-2">
              <h3 className="text-sm font-medium">
                {tr("Tablas al crearlo")}{" "}
                <span className="text-muted-foreground">
                  ({resource.data.tables.length})
                </span>
              </h3>
              <ul className="flex flex-wrap gap-2">
                {resource.data.tables.map((t) => (
                  <li
                    key={t.id}
                    className="rounded-full bg-muted px-3 py-1 text-sm"
                    title={t.name}
                  >
                    {tableName(t.name)}
                  </li>
                ))}
              </ul>
            </section>
          ) : (
            <p className="text-sm text-muted-foreground">
              {tr("Las tablas aparecerán cuando empiece la preparación.")}
            </p>
          )}
          {!!resource.data.added_tables.length && (
            <section className="space-y-2 border-t pt-4">
              <h3 className="text-sm font-medium">
                {tr("Tablas añadidas después")}{" "}
                <span className="text-muted-foreground">
                  ({resource.data.added_tables.length})
                </span>
              </h3>
              <ul className="flex flex-wrap gap-2">
                {resource.data.added_tables.map((t) => (
                  <li
                    key={t.id}
                    className="rounded-full bg-muted px-3 py-1 text-sm"
                    title={t.name}
                  >
                    {tableName(t.name)}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
      <DialogFooter>
        <Button asChild>
          <a href={analysisHref(item)}>
            <ArrowUpRight />
            {tr("Abrir informe")}
          </a>
        </Button>
      </DialogFooter>
    </DialogContent>
  );
}
function ReportRow({
  item: a,
  trash,
  busy,
  onDelete,
  onRestore,
  onDetails,
}: Omit<TableProps, "items" | "search"> & {
  item: Analysis;
  onDetails: (item: Analysis) => void;
}) {
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
      ? "border-red-600/30 text-red-700 dark:border-red-400/40 dark:text-red-300"
      : status === "completed"
        ? "border-emerald-600/30 text-emerald-700 dark:border-emerald-400/40 dark:text-emerald-300"
        : "";
  return (
    <TableRow
      id={reference ? blockId(reference) : undefined}
      className={`report-pick-row grid grid-cols-[minmax(0,1fr)_auto] rounded-2xl sm:table-row border-0 bg-muted/70 transition-colors hover:bg-foreground/[0.08] focus-within:bg-foreground/[0.08] dark:hover:bg-muted dark:focus-within:bg-muted [&>td:first-child]:rounded-l-2xl [&>td:last-child]:rounded-r-2xl [&>td]:py-3 ${selecting && !active ? "report-unselectable" : "cursor-pointer"} ${selected ? "context-picked" : ""}`}
      onClick={(event) => {
        if (!selecting && !(event.target as HTMLElement).closest("a, button"))
          onDetails(a);
      }}
    >
      <TableCell className="col-start-1 row-start-1 min-w-0 whitespace-normal">
        <div inert={selecting || undefined} className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="flex size-8 shrink-0 items-center justify-center rounded-full border border-foreground/25 text-muted-foreground"
          >
            <FileText className="size-4" />
          </span>
          <div className="min-w-0">
            <a
              className="break-words text-sm font-medium hover:underline"
              href={analysisHref(a)}
            >
              {a.title}
            </a>
            <p className="mt-1 text-xs text-muted-foreground sm:hidden">
              {tr("Creado")}: {date(a.created_at)}
            </p>
          </div>
        </div>
      </TableCell>
      <TableCell className="col-start-1 row-start-2 !pt-0 !pl-16 sm:!px-4 sm:!pt-3">
        <Badge variant="outline" className={`font-normal ${color}`}>
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
      <TableCell className="col-start-2 row-span-2 row-start-1 w-24 self-center sm:w-40">
        <div
          inert={selecting || undefined}
          className={
            selecting
              ? "invisible flex"
              : "flex max-w-24 flex-wrap justify-end gap-1 sm:max-w-none sm:flex-nowrap"
          }
        >
          <Button
            variant="ghost"
            size="icon"
            className="order-2 sm:order-none"
            aria-label={tr("Detalles de {0}", { 0: a.title })}
            onClick={() => onDetails(a)}
          >
            <Info />
          </Button>
          <Button
            asChild
            variant="outline"
            size="sm"
            className="order-1 sm:order-none"
          >
            <a
              href={analysisHref(a)}
              aria-label={tr("Abrir {0}", { "0": a.title })}
            >
              {tr("Abrir")}
              <ArrowUpRight />
            </a>
          </Button>
          {trash ? (
            <Button
              variant="ghost"
              size="icon"
              disabled={busy}
              className="order-3 sm:order-none"
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
              className="order-3 sm:order-none"
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
