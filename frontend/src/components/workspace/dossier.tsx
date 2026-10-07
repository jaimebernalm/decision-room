import { translate as tr, useLanguage } from "@/lib/i18n";
import { useEffect, useRef, useState } from "react";
import {
  Plus,
  Pencil,
  Check,
  Archive,
  RefreshCw,
  MoreHorizontal,
  Info,
  X,
  Settings2,
  FolderInput,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { DossierExplorer, DossierExplorerPanel } from "./dossier-explorer";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuSubContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "@/components/ui/tooltip";
import { useResource, useAction } from "@/lib/hooks";
import { api, date } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import type {
  Dossier as DossierData,
  Fact,
  FactContent,
  Dataset,
  DossierLayout,
} from "@/lib/types";
import {
  Heading,
  Notice,
  Loading,
  Field,
  ChoiceSelect,
  Disclosure,
  Busy,
  Empty,
} from "./shared";
import { Selectable } from "./context-selection";
import { useAssistant } from "@/lib/assistant";
import { UploadForm } from "./business";
import { DossierDataGroups } from "./dossier-data";
import { DragScroll } from "./drag-scroll";
import { GroupEditor } from "./dossier-groups";
import { defaultDossierLayout } from "@/lib/dossier-layout";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
const factKinds: Record<string, string> = {
  context: "Contexto",
  priority: "Prioridad",
  definition: "Definición",
  availability: "Disponibilidad",
  open_question: "Pregunta abierta",
  result_reference: "Resultado",
};
const factStatus: Record<string, string> = {
  declared: "Confirmado por ti",
  inferred: "Por confirmar",
  proposed: "Por confirmar",
  uncertain: "Por revisar",
  conflicted: "En conflicto",
  withdrawn: "Retirado",
  confirmed: "Confirmado",
  superseded: "Sustituido",
};
function needsReview(fact: Fact) {
  return (
    ["proposed", "inferred", "uncertain", "conflicted"].includes(fact.status) ||
    fact.content.temporal_scope === "unresolved" ||
    fact.content.kind === "open_question"
  );
}
function canConfirm(fact: Fact) {
  return (
    ![
      "declared",
      "confirmed",
      "conflicted",
      "withdrawn",
      "superseded",
    ].includes(fact.status) &&
    fact.content.temporal_scope !== "unresolved" &&
    fact.content.kind !== "open_question"
  );
}
function factGroup(fact: Fact, layout: DossierLayout) {
  if (needsReview(fact)) return "review";
  const ids = new Set(layout.groups.map((group) => group.id));
  const assigned = layout.assignments[fact.fact_id];
  if (assigned === "ungrouped") return "ungrouped";
  if (assigned && ids.has(assigned)) return assigned;
  const automatic = automaticGroup(fact);
  return ids.has(automatic) ? automatic : "ungrouped";
}
function automaticGroup(fact: Fact) {
  const { kind, scope, topic = "" } = fact.content;
  if (
    kind === "priority" ||
    /preferenc|objetiv|goal|prioridad|priority/.test(topic.toLowerCase())
  )
    return "goals";
  if (
    scope !== "business" ||
    ["definition", "availability"].includes(kind) ||
    /horario|schedule|opening|operativ|operation|proveedor|supplier|inventario|inventory/.test(
      topic.toLowerCase(),
    )
  )
    return "operations";
  return "business";
}
export function Dossier({ files = false }: { files?: boolean }) {
  useLanguage();
  const { workspace, refresh } = useWorkspace(),
    b = workspace.business!,
    resource = useResource<DossierData>("/api/business/dossier"),
    action = useAction();
  const [edit, setEdit] = useState<Fact | null | undefined>(undefined),
    [detail, setDetail] = useState<Fact | null>(null),
    [detailEditing, setDetailEditing] = useState(false),
    [upload, setUpload] = useState(false);
  const [customize, setCustomize] = useState(false),
    [selectedGroup, setSelectedGroup] = useState("");
  const assistant = useAssistant();
  const [tab, setTab] = useState(files ? "data" : "info");
  const contextBlock = assistant?.dock?.block;
  const [returnedBlock, setReturnedBlock] = useState<string | undefined>();
  if (contextBlock !== returnedBlock) {
    setReturnedBlock(contextBlock);
    if (contextBlock?.includes("-data_model-")) setTab("data");
  }
  const [newGroup, setNewGroup] = useState<{
    id: string;
    title: string;
  } | null>(null);
  const actionFocus = useRef<HTMLButtonElement | null>(null),
    customizeGroups = useRef<HTMLButtonElement | null>(null);
  const factButtons = useRef(new Map<string, HTMLButtonElement>());
  const pendingDetailFocus = useRef<{
    id: string;
    data: DossierData | null;
  } | null>(null);
  useEffect(() => {
    const pending = pendingDetailFocus.current;
    if (!pending || detail || !resource.data || resource.data === pending.data)
      return;
    const saved = resource.data.facts.find(
      (f) =>
        f.fact_id === pending.id &&
        !["withdrawn", "superseded"].includes(f.status),
    );
    if (saved) {
      const group = factGroup(
        saved,
        resource.data.layout || defaultDossierLayout,
      );
      if (selectedGroup !== group) {
        setSelectedGroup(group);
        return;
      }
    }
    const target =
      (saved && factButtons.current.get(saved.fact_id)) ||
      customizeGroups.current;
    if (target) {
      actionFocus.current = target;
      target.focus();
    }
    pendingDetailFocus.current = null;
  }, [detail, resource.data, selectedGroup]);
  const restoreDialogFocus = (event: Event) => {
    const target = actionFocus.current?.isConnected
      ? actionFocus.current
      : customizeGroups.current;
    if (target) {
      event.preventDefault();
      target.focus();
    }
  };
  const done = () => {
    if (detail)
      pendingDetailFocus.current = { id: detail.fact_id, data: resource.data };
    resource.refresh();
    refresh();
    setEdit(undefined);
    setDetail(null);
    setDetailEditing(false);
    setUpload(false);
  };
  const openDetail = (fact: Fact) => {
    pendingDetailFocus.current = null;
    action.setError("");
    setDetailEditing(false);
    setDetail(fact);
  };
  const mutation = (fact: Fact, kind: string) =>
    action.run(async () => {
      await api("/api/business/memory", {
        business_id: b.id,
        action: kind,
        fact_id: fact.fact_id,
        expected_revision: fact.revision,
        request_key: crypto.randomUUID(),
      });
      done();
    });
  if (!resource.data)
    return (
      <>
        <Notice error>{resource.error}</Notice>
        {!resource.error && <Loading />}
      </>
    );
  const data = resource.data,
    facts = data.facts.filter(
      (f) => !["withdrawn", "superseded"].includes(f.status),
    );
  const layout = data.layout || defaultDossierLayout;
  const factGroups = [
    { key: "review", title: tr("Por revisar") },
    ...layout.groups.map((group) => ({
      key: group.id,
      title: data.layout ? group.name : tr(group.name),
    })),
    { key: "ungrouped", title: tr("Otros") },
  ];
  const explorerGroups = factGroups.map((group) => ({
    id: group.key,
    title: group.title,
    count: facts.filter((fact) => factGroup(fact, layout) === group.key).length,
    attention: group.key === "review",
    description:
      group.key === "review"
        ? tr("Propuestas y conflictos pendientes de revisar.")
        : group.key === "ungrouped"
          ? tr("Información que no encaja en los demás grupos.")
          : layout.groups.find((g) => g.id === group.key)?.description,
  }));
  return (
    <>
      <Heading title={b.name} />
      <Notice error>{resource.error || action.error}</Notice>
      {Boolean(
        data.memory.pending || data.memory.failed || data.memory.needs_review,
      ) && (
        <Notice>
          {tr("Hay información pendiente de procesar o revisar.")}{" "}
          {Boolean(data.memory.failed) && (
            <Button
              variant="link"
              disabled={action.busy}
              onClick={() =>
                action.run(async () => {
                  await api("/api/memory/retry", { business_id: b.id });
                  done();
                })
              }
            >
              {tr("Reintentar procesamiento")}
            </Button>
          )}
        </Notice>
      )}
      <Tabs value={tab} onValueChange={setTab} className="min-w-0 w-full">
        <div className="mt-4 mb-6 flex flex-wrap items-center gap-2">
          <TabsList className="rounded-lg group-data-horizontal/tabs:h-10 p-1">
            <TabsTrigger
              value="info"
              className="rounded-md px-3 text-sm font-medium"
            >
              {tr("Información")}
            </TabsTrigger>
            <TabsTrigger
              value="data"
              className="rounded-md px-3 text-sm font-medium"
            >
              {tr("Datos")}
            </TabsTrigger>
            <TabsTrigger
              value="history"
              className="rounded-md px-3 text-sm font-medium"
            >
              {tr("Historial")}
            </TabsTrigger>
          </TabsList>
          <Button variant="ghost" size="sm" onClick={resource.refresh}>
            <RefreshCw />
            {tr("Actualizar")}
          </Button>
        </div>
        <TabsContent value="info" className="min-w-0 space-y-5">
          {!facts.length && data.business.description && (
            <section aria-label={tr("Presentación del negocio")}>
              <h2 className="mb-2 text-sm font-medium">
                {tr("Sobre el negocio")}
              </h2>
              <p className="line-clamp-3 whitespace-pre-wrap break-words text-sm leading-6 text-muted-foreground">
                {data.business.description}
              </p>
            </section>
          )}
          <DossierExplorer
            label={tr("Información")}
            value={selectedGroup}
            onValueChange={setSelectedGroup}
            navigation={
              customize ? (
                <GroupEditor
                  business={b.id}
                  layout={layout}
                  groups={explorerGroups}
                  active={
                    selectedGroup ||
                    explorerGroups.find((group) => group.count > 0)?.id ||
                    layout.groups[0]?.id ||
                    "review"
                  }
                  onSelect={setSelectedGroup}
                  onCancel={() => {
                    setCustomize(false);
                    customizeGroups.current?.focus();
                  }}
                  onDone={() => {
                    resource.refresh();
                    setCustomize(false);
                    customizeGroups.current?.focus();
                  }}
                />
              ) : undefined
            }
            navigationFooter={
              <Button
                variant="ghost"
                size="sm"
                className="h-auto min-h-11 w-full justify-start whitespace-normal text-left text-muted-foreground"
                ref={customizeGroups}
                aria-expanded={customize}
                onClick={(event) => {
                  actionFocus.current = event.currentTarget;
                  setCustomize(!customize);
                }}
              >
                <Settings2 className="shrink-0" />
                {tr("Personalizar grupos")}
              </Button>
            }
            groups={explorerGroups}
          >
            {factGroups.map((group) => {
              const items = facts.filter(
                (fact) => factGroup(fact, layout) === group.key,
              );
              return (
                <DossierExplorerPanel key={group.key} id={group.key}>
                  <div className="mb-3 flex min-w-0 items-center justify-between gap-3 border-b border-border pb-3">
                    <h2 className="min-w-0 text-base font-medium [overflow-wrap:anywhere]">
                      {group.title}
                    </h2>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            size="icon"
                            className="size-9 shrink-0 rounded-full shadow-none [@media(pointer:coarse)]:size-11"
                            aria-label={tr("Añadir información a {0}", {
                              0: group.title,
                            })}
                            onClick={(event) => {
                              actionFocus.current = event.currentTarget;
                              setNewGroup({
                                id: group.key,
                                title: group.title,
                              });
                              setEdit(null);
                            }}
                          >
                            <Plus className="size-5" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          {tr("Añadir información")}
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                  <div className="min-w-0 [&_p:not(:last-child)]:mb-0">
                    {layout.groups.find((g) => g.id === group.key)
                      ?.description && (
                      <p className="px-3 py-2 text-sm text-muted-foreground whitespace-pre-wrap break-words">
                        {
                          layout.groups.find((g) => g.id === group.key)
                            ?.description
                        }
                      </p>
                    )}
                    {!items.length && (
                      <p className="px-3 py-4 text-sm text-muted-foreground">
                        {tr(
                          "Añade información desde el botón + de este grupo.",
                        )}
                      </p>
                    )}
                    <ul className="divide-y divide-border/70">
                      {items.map((f) => (
                        <li key={f.fact_id}>
                          <Selectable
                            item={{
                              kind: "memory",
                              source_id: f.fact_id,
                              source_version: String(f.revision),
                              element_key: "fact",
                              title: f.content.statement.slice(0, 100),
                              href: "#my-business",
                              report_title: tr("Mi negocio"),
                              content: {
                                key: "fact",
                                title: tr(
                                  factKinds[f.content.kind] || "Información",
                                ),
                                statement: f.content.statement,
                              },
                            }}
                          >
                            <div className="group/fact flex items-start gap-3 rounded-lg px-2 py-2 text-sm transition-[background-color,box-shadow] hover:bg-sidebar-accent hover:shadow-sm focus-within:bg-sidebar-accent focus-within:shadow-sm motion-reduce:transition-none sm:px-3">
                              <div className="min-w-0 flex-1 py-2">
                                <button
                                  type="button"
                                  ref={(node) => {
                                    if (node)
                                      factButtons.current.set(f.fact_id, node);
                                    else factButtons.current.delete(f.fact_id);
                                  }}
                                  className="block w-full min-w-0 rounded-sm text-left leading-6 outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                  aria-label={tr("Ver información: {0}", {
                                    0: f.content.statement,
                                  })}
                                  aria-haspopup="dialog"
                                  onClick={(event) => {
                                    actionFocus.current = event.currentTarget;
                                    openDetail(f);
                                  }}
                                >
                                  <span className="block truncate">
                                    {f.content.statement}
                                  </span>
                                </button>
                                {needsReview(f) && (
                                  <div className="mt-1 flex flex-wrap items-center gap-2">
                                    <Badge
                                      variant={
                                        f.status === "conflicted"
                                          ? "destructive"
                                          : "secondary"
                                      }
                                    >
                                      {tr(
                                        f.status === "conflicted"
                                          ? factStatus[f.status]
                                          : f.content.temporal_scope ===
                                              "unresolved"
                                            ? "Fechas por aclarar"
                                            : f.content.kind === "open_question"
                                              ? "Pregunta abierta"
                                              : factStatus[f.status] ||
                                                "Por revisar",
                                      )}
                                    </Badge>
                                    {canConfirm(f) && (
                                      <TooltipProvider>
                                        <span className="inline-flex gap-1 transition-opacity group-hover/fact:opacity-100 group-focus-within/fact:opacity-100 motion-reduce:transition-none sm:[@media(hover:hover)]:opacity-0">
                                          <Tooltip>
                                            <TooltipTrigger asChild>
                                              <Button
                                                variant="outline"
                                                size="icon"
                                                className="size-9"
                                                aria-label={tr(
                                                  "Confirmar: {0}",
                                                  { 0: f.content.statement },
                                                )}
                                                disabled={action.busy}
                                                onClick={() =>
                                                  void mutation(f, "confirm")
                                                }
                                              >
                                                <Check />
                                              </Button>
                                            </TooltipTrigger>
                                            <TooltipContent>
                                              {tr("Confirmar información")}
                                            </TooltipContent>
                                          </Tooltip>
                                          <Tooltip>
                                            <TooltipTrigger asChild>
                                              <Button
                                                variant="destructive"
                                                size="icon"
                                                className="size-9"
                                                aria-label={tr(
                                                  "Descartar: {0}",
                                                  { 0: f.content.statement },
                                                )}
                                                disabled={action.busy}
                                                onClick={() =>
                                                  void mutation(f, "withdraw")
                                                }
                                              >
                                                <X />
                                              </Button>
                                            </TooltipTrigger>
                                            <TooltipContent>
                                              {tr(
                                                "Descartar y conservar en el historial",
                                              )}
                                            </TooltipContent>
                                          </Tooltip>
                                        </span>
                                      </TooltipProvider>
                                    )}
                                    {f.status === "conflicted" && (
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        className="min-h-9 whitespace-normal text-left"
                                        disabled={action.busy}
                                        onClick={(event) => {
                                          actionFocus.current =
                                            event.currentTarget;
                                          setEdit(f);
                                        }}
                                      >
                                        <Pencil />
                                        {tr("Resolver conflicto")}
                                      </Button>
                                    )}
                                  </div>
                                )}
                                {(f.content.scope !== "business" ||
                                  f.content.valid_from ||
                                  f.content.valid_until) && (
                                  <p className="mt-1 break-words text-xs text-muted-foreground">
                                    {scopeLabel(f.content, data.datasets)}
                                  </p>
                                )}
                              </div>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="size-10 shrink-0 transition-opacity group-hover/fact:opacity-100 group-focus-within/fact:opacity-100 data-[state=open]:opacity-100 motion-reduce:transition-none [@media(hover:hover)_and_(pointer:fine)]:opacity-0"
                                    aria-label={tr("Acciones: {0}", {
                                      0: f.content.statement,
                                    })}
                                    onFocus={(event) => {
                                      actionFocus.current = event.currentTarget;
                                    }}
                                    onPointerDown={(event) => {
                                      actionFocus.current = event.currentTarget;
                                    }}
                                  >
                                    <MoreHorizontal />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent
                                  align="end"
                                  className="min-w-44"
                                >
                                  <DropdownMenuItem
                                    disabled={action.busy}
                                    onSelect={() => setEdit(f)}
                                  >
                                    <Pencil />
                                    {tr("Editar")}
                                  </DropdownMenuItem>
                                  <DropdownMenuItem
                                    onSelect={() => openDetail(f)}
                                  >
                                    <Info />
                                    {tr("Ver detalles")}
                                  </DropdownMenuItem>
                                  {canConfirm(f) && (
                                    <DropdownMenuItem
                                      disabled={action.busy}
                                      onSelect={() => {
                                        void mutation(f, "confirm");
                                      }}
                                    >
                                      <Check />
                                      {tr("Confirmar")}
                                    </DropdownMenuItem>
                                  )}
                                  <DropdownMenuSeparator />
                                  <DropdownMenuSub>
                                    <DropdownMenuSubTrigger>
                                      <FolderInput />
                                      {tr("Mover a grupo")}
                                    </DropdownMenuSubTrigger>
                                    <DropdownMenuSubContent className="max-w-64">
                                      <DropdownMenuRadioGroup
                                        value={
                                          layout.assignments[f.fact_id] ||
                                          "auto"
                                        }
                                        onValueChange={(group) => {
                                          void action.run(async () => {
                                            const assignments = {
                                              ...layout.assignments,
                                            };
                                            if (group === "auto")
                                              delete assignments[f.fact_id];
                                            else assignments[f.fact_id] = group;
                                            await api(
                                              "/api/business/dossier-layout",
                                              {
                                                business_id: b.id,
                                                ...layout,
                                                assignments,
                                              },
                                            );
                                            pendingDetailFocus.current = {
                                              id: f.fact_id,
                                              data: resource.data,
                                            };
                                            resource.refresh();
                                          });
                                        }}
                                      >
                                        <DropdownMenuRadioItem
                                          value="auto"
                                          disabled={action.busy}
                                        >
                                          {tr("Clasificación automática")}
                                        </DropdownMenuRadioItem>
                                        <DropdownMenuRadioItem
                                          value="ungrouped"
                                          disabled={action.busy}
                                        >
                                          {tr("Otros")}
                                        </DropdownMenuRadioItem>
                                        {layout.groups.map((group) => (
                                          <DropdownMenuRadioItem
                                            key={group.id}
                                            value={group.id}
                                            disabled={action.busy}
                                            className="whitespace-normal break-words"
                                          >
                                            {group.name}
                                          </DropdownMenuRadioItem>
                                        ))}
                                      </DropdownMenuRadioGroup>
                                    </DropdownMenuSubContent>
                                  </DropdownMenuSub>
                                  <DropdownMenuSeparator />
                                  <DropdownMenuItem
                                    variant="destructive"
                                    disabled={action.busy}
                                    onSelect={() => {
                                      void mutation(f, "withdraw");
                                    }}
                                  >
                                    <Archive />
                                    {tr("Retirar")}
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </div>
                          </Selectable>
                        </li>
                      ))}
                    </ul>
                  </div>
                </DossierExplorerPanel>
              );
            })}
            {!facts.length && !layout.groups.length && (
              <Empty
                title={tr("Un contexto que crece contigo")}
                description={tr(
                  "Personaliza los grupos para empezar a añadir información que el asistente debería recordar.",
                )}
              />
            )}
          </DossierExplorer>
          <Disclosure subtle title={tr("Ver presentación original")}>
            <Selectable
              item={{
                kind: "business",
                source_id: b.id,
                source_version: String(data.business.profile_revision),
                element_key: "profile",
                title: `Presentación de ${data.business.name}`,
                href: "#my-business",
                report_title: tr("Mi negocio"),
                content: {
                  key: "profile",
                  title: data.business.name,
                  statement: data.business.description,
                },
              }}
            >
              <p className="whitespace-pre-wrap break-words leading-6 text-muted-foreground">
                {data.business.description}
              </p>
            </Selectable>
            <Button asChild variant="ghost" size="sm">
              <a href="#business">
                <Pencil />
                {tr("Editar presentación")}
              </a>
            </Button>
          </Disclosure>
        </TabsContent>
        <TabsContent value="data" className="min-w-0">
          <DossierDataGroups
            business={b.id}
            datasets={data.datasets}
            onUpload={() => setUpload(true)}
          />
        </TabsContent>
        <TabsContent value="history" className="space-y-3">
          {data.history.length ? (
            <DragScroll>
              <ol
                aria-label={tr("Historial")}
                className="ml-2 border-l border-border"
              >
                {data.history.map((f, i) => (
                  <li
                    key={`${f.fact_id}-${f.revision}-${i}`}
                    className="relative space-y-3 pb-8 pl-6 last:pb-0"
                  >
                    <span
                      aria-hidden="true"
                      className="absolute -left-[5px] top-1.5 size-[9px] rounded-full bg-primary ring-4 ring-background"
                    />
                    <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                      <span>
                        {date(f.created_at)}
                        {tr(" · revisión ")}
                        {f.revision}
                      </span>
                      <Badge variant="outline">
                        {tr(factStatus[f.status] || f.status)}
                      </Badge>
                    </div>
                    <p className="whitespace-pre-wrap break-words text-sm leading-6">
                      {f.content.statement}
                    </p>
                    <div className="[@media(pointer:coarse)]:[&_button]:min-h-11">
                      <FactOrigin fact={f} subtle />
                    </div>
                  </li>
                ))}
              </ol>
            </DragScroll>
          ) : (
            <p className="py-10 text-center text-sm text-muted-foreground">
              {tr("El historial aparecerá cuando guardes información.")}
            </p>
          )}
        </TabsContent>
      </Tabs>
      <Dialog
        open={detail !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDetail(null);
            setDetailEditing(false);
          }
        }}
      >
        <DialogContent
          className="flex max-h-[90svh] flex-col overflow-hidden sm:max-w-2xl"
          onCloseAutoFocus={restoreDialogFocus}
        >
          <DialogHeader className="shrink-0 pr-8">
            <DialogTitle>
              {detailEditing
                ? tr(
                    detail?.status === "conflicted"
                      ? "Resolver conflicto"
                      : "Corregir información",
                  )
                : tr("Detalles de la información")}
            </DialogTitle>
            <DialogDescription>
              {detailEditing
                ? tr(
                    detail?.status === "conflicted"
                      ? "Marca la versión correcta o escribe otra solución. Revisa el contenido y guarda tu elección."
                      : "Se guardará en la memoria de este negocio.",
                  )
                : tr("Origen, ámbito y vigencia de este dato.")}
            </DialogDescription>
          </DialogHeader>
          {detail && detailEditing ? (
            <FactEditor
              key={`${detail.fact_id}-${detail.revision}`}
              fact={detail}
              autoFocus
              group={null}
              datasets={data.datasets}
              onDone={done}
            />
          ) : (
            detail && (
              <>
                <div className="min-h-0 min-w-0 space-y-4 overflow-y-auto break-words text-sm">
                  <p className="whitespace-pre-wrap text-base leading-7">
                    {detail.content.statement}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="outline">
                      {tr(
                        factKinds[detail.content.kind] || detail.content.kind,
                      )}
                    </Badge>
                    <Badge
                      variant={
                        detail.status === "conflicted"
                          ? "destructive"
                          : "secondary"
                      }
                    >
                      {tr(factStatus[detail.status] || detail.status)}
                    </Badge>
                  </div>
                  <p className="text-muted-foreground">
                    {scopeLabel(detail.content, data.datasets)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {date(detail.created_at)}{" "}
                    {tr("· revisión {0}", { 0: detail.revision })}
                  </p>
                  <FactOrigin fact={detail} expanded />
                </div>
                <div className="shrink-0 space-y-3 border-t pt-3">
                  <Notice error>{action.error}</Notice>
                  <div className="flex flex-wrap gap-2">
                    {canConfirm(detail) && (
                      <Button
                        disabled={action.busy}
                        onClick={() => void mutation(detail, "confirm")}
                      >
                        {action.busy ? <Busy /> : <Check />}
                        {tr("Confirmar")}
                      </Button>
                    )}
                    <Button
                      variant={
                        detail.status === "conflicted" ? "default" : "outline"
                      }
                      disabled={action.busy}
                      onClick={() => setDetailEditing(true)}
                    >
                      <Pencil />
                      {tr(
                        detail.status === "conflicted"
                          ? "Resolver conflicto"
                          : "Corregir información",
                      )}
                    </Button>
                    {needsReview(detail) && (
                      <Button
                        variant="outline"
                        disabled={action.busy}
                        onClick={() => void mutation(detail, "withdraw")}
                      >
                        <X />
                        {tr("Descartar")}
                      </Button>
                    )}
                  </div>
                </div>
              </>
            )
          )}
        </DialogContent>
      </Dialog>
      <Dialog
        open={edit !== undefined}
        onOpenChange={(open) => {
          if (!open) setEdit(undefined);
        }}
      >
        <DialogContent
          className="flex max-h-[90svh] flex-col overflow-hidden sm:max-w-xl"
          onCloseAutoFocus={restoreDialogFocus}
        >
          <DialogHeader>
            <DialogTitle>
              {edit?.status === "conflicted"
                ? tr("Resolver conflicto")
                : edit
                  ? tr("Corregir información")
                  : tr("Añadir información a {0}", {
                      0: newGroup?.title || tr("este grupo"),
                    })}
            </DialogTitle>
            <DialogDescription>
              {edit?.status === "conflicted"
                ? tr(
                    "Marca la versión correcta o escribe otra solución. Revisa el contenido y guarda tu elección.",
                  )
                : edit
                  ? tr("Se guardará en la memoria de este negocio.")
                  : tr("Grupo: {0}. {1}", {
                      0: newGroup?.title,
                      1:
                        newGroup?.id === "review"
                          ? tr(
                              "Se añadirá como propuesta pendiente de confirmar.",
                            )
                          : tr("La información se guardará en este grupo."),
                    })}
            </DialogDescription>
          </DialogHeader>
          {edit !== undefined && (
            <FactEditor
              key={
                edit
                  ? `${edit.fact_id}-${edit.revision}`
                  : `new-${newGroup?.id}`
              }
              fact={edit}
              group={edit ? null : newGroup}
              datasets={data.datasets}
              onDone={done}
            />
          )}
        </DialogContent>
      </Dialog>
      <Dialog open={upload} onOpenChange={setUpload}>
        <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{tr("Añadir datos al negocio")}</DialogTitle>
            <DialogDescription>
              {tr("Conserva el periodo y la relación entre versiones.")}
            </DialogDescription>
          </DialogHeader>
          {upload && <UploadForm datasets={data.datasets} onDone={done} />}
        </DialogContent>
      </Dialog>
    </>
  );
}
function scopeLabel(content: FactContent, datasets: Dataset[]) {
  const target =
    content.scope === "business"
      ? tr("Todo el negocio")
      : content.scope === "analysis"
        ? datasets.find((d) => d.id === content.scope_id)?.title ||
          tr("Conjunto de datos")
        : datasets
            .flatMap((d) => d.files || [])
            .find((f) => f.id === content.scope_id)?.name || tr("Archivo");
  return `${target}${content.valid_from || content.valid_until ? ` · ${content.valid_from || "…"} — ${content.valid_until || "…"}` : ""}${content.temporal_scope === "unresolved" ? tr(" · fechas por aclarar") : ""}`;
}
function FactOrigin({
  fact,
  expanded = false,
  subtle = false,
}: {
  fact: Fact;
  expanded?: boolean;
  subtle?: boolean;
}) {
  const content = (
    <div className="space-y-3 whitespace-pre-wrap break-words">
      <p>
        {fact.content.valid_from || tr("Sin fecha inicial")} {tr("—")}{" "}
        {fact.content.valid_until || tr("Sin fecha final")}
      </p>
      {(fact.original_text || fact.quote) && (
        <blockquote className="border-l-2 pl-3 text-muted-foreground">
          {fact.original_text || fact.quote}
        </blockquote>
      )}
      {fact.question && <p>{fact.question}</p>}
      {fact.conversation_id && (
        <Button asChild variant="link" size="sm">
          <a href={`#chat/${fact.conversation_id}`}>
            {tr("Ver chat de origen")}
          </a>
        </Button>
      )}
      {fact.alternatives?.map((a, i) => (
        <p key={i}>
          {tr("Alternativa: ")}
          {a.content?.statement || a.statement || a.quote}
        </p>
      ))}
    </div>
  );
  return expanded ? (
    content
  ) : (
    <Disclosure title={tr("Origen y vigencia")} subtle={subtle}>
      {content}
    </Disclosure>
  );
}
function FactEditor({
  fact,
  autoFocus = false,
  group,
  datasets,
  onDone,
}: {
  fact: Fact | null;
  autoFocus?: boolean;
  group: { id: string; title: string } | null;
  datasets: Dataset[];
  onDone: () => void;
}) {
  useLanguage();
  const { workspace } = useWorkspace(),
    action = useAction();
  const [content, setContent] = useState<FactContent>(
    fact?.content || {
      kind: group?.id === "goals" ? "priority" : "context",
      statement: "",
      topic: "owner_" + crypto.randomUUID().replaceAll("-", ""),
      scope: "business",
      scope_id: null,
      valid_from: null,
      valid_until: null,
      temporal_scope: "unspecified",
      result_id: null,
    },
  );
  const [change, setChange] = useState("historical"),
    [resolutionChoice, setResolutionChoice] = useState(""),
    pending = useRef({ signature: "", key: "" });
  const update = (field: string, value: unknown) => {
    if (fact?.status === "conflicted") setResolutionChoice("custom");
    setContent({ ...content, [field]: value });
  };
  const options = [
    { value: "business", label: tr("Todo el negocio") },
    ...datasets.flatMap((d) => [
      {
        value: `analysis:${d.id}`,
        label: tr("Datos: {0} · v{1}", { "0": d.title, "1": d.version }),
      },
      ...(d.files || []).map((f) => ({
        value: `source:${f.id}`,
        label: tr("Archivo: {0}", { "0": f.name }),
      })),
    ]),
  ];
  const contentKey = (value: FactContent) =>
    JSON.stringify([
      value.kind,
      value.statement,
      value.topic,
      value.scope,
      value.scope_id,
      value.valid_from,
      value.valid_until,
      value.temporal_scope,
      value.result_id,
    ]);
  const conflictVersions =
    fact?.status === "conflicted"
      ? [
          {
            id: "current",
            label: tr("Información actual"),
            content: fact.content,
            quote:
              fact.alternatives?.find(
                (a) =>
                  a.content &&
                  contentKey(a.content) === contentKey(fact.content),
              )?.quote || fact.quote,
          },
          ...(fact.alternatives || []).flatMap((alternative, index) => {
            const statement =
              alternative.content?.statement || alternative.statement;
            return statement
              ? [
                  {
                    id: `alternative-${index}`,
                    label: tr("Alternativa {0}", { 0: index + 1 }),
                    content: alternative.content || {
                      ...fact.content,
                      statement,
                    },
                    quote: alternative.quote,
                  },
                ]
              : [];
          }),
        ].filter(
          (version, index, versions) =>
            versions.findIndex(
              (v) => contentKey(v.content) === contentKey(version.content),
            ) === index,
        )
      : [];
  return (
    <form
      className="flex min-h-0 flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (fact?.status === "conflicted" && !resolutionChoice) return;
        void action.run(async () => {
          const value = {
            ...content,
            topic:
              content.topic ||
              "owner_" + crypto.randomUUID().replaceAll("-", ""),
            temporal_scope:
              content.valid_from || content.valid_until
                ? "dated"
                : content.temporal_scope === "unresolved"
                  ? "unresolved"
                  : "unspecified",
            result_id:
              content.kind === "result_reference" ? content.result_id : null,
          };
          const body = {
            business_id: workspace.business!.id,
            action: fact
              ? "correct"
              : group?.id === "review"
                ? "propose"
                : "declare",
            content: value,
            ...(!fact && group && group.id !== "review"
              ? { group_id: group.id }
              : {}),
            ...(fact
              ? { fact_id: fact.fact_id, expected_revision: fact.revision }
              : {}),
            change_kind: change,
            original_text: content.statement,
          };
          const signature = JSON.stringify(body);
          if (pending.current.signature !== signature)
            pending.current = { signature, key: crypto.randomUUID() };
          await api("/api/business/memory", {
            ...body,
            request_key: pending.current.key,
          });
          toast.success(tr("Información guardada"));
          onDone();
        });
      }}
    >
      <div className="min-h-0 space-y-4 overflow-y-auto px-1">
        {conflictVersions.length > 0 && (
          <section
            aria-label={tr("Versiones en conflicto")}
            className="space-y-3"
          >
            <RadioGroup
              aria-label={tr("Elige la versión correcta")}
              value={resolutionChoice}
              onValueChange={(choice) => {
                setResolutionChoice(choice);
                const version = conflictVersions.find((v) => v.id === choice);
                if (version) setContent({ ...version.content });
              }}
            >
              {conflictVersions.map((version, index) => (
                <label
                  htmlFor={`conflict-version-${index}`}
                  key={version.id}
                  className={`block cursor-pointer space-y-2 rounded-lg border p-3 text-sm ${resolutionChoice === version.id ? "border-primary bg-primary/5" : "bg-muted/30 hover:bg-sidebar-accent"}`}
                >
                  <div className="flex items-center gap-3">
                    <RadioGroupItem
                      autoFocus={autoFocus && index === 0}
                      id={`conflict-version-${index}`}
                      value={version.id}
                      aria-label={tr("Usar {0}", {
                        0: version.label.toLowerCase(),
                      })}
                      disabled={action.busy}
                    />
                    <h3 className="font-semibold">{version.label}</h3>
                    {resolutionChoice === version.id && (
                      <Badge variant="secondary" className="ml-auto">
                        {tr("Seleccionada")}
                      </Badge>
                    )}
                  </div>
                  <p className="whitespace-pre-wrap break-words leading-6">
                    {version.content.statement}
                  </p>
                  <p className="break-words text-xs text-muted-foreground">
                    {scopeLabel(version.content, datasets)}
                  </p>
                  {version.quote && (
                    <blockquote className="whitespace-pre-wrap break-words border-l-2 pl-2 text-xs text-muted-foreground">
                      {version.quote}
                    </blockquote>
                  )}
                </label>
              ))}
              <label
                htmlFor="conflict-custom"
                className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 ${resolutionChoice === "custom" ? "border-primary bg-primary/5" : "hover:bg-sidebar-accent"}`}
              >
                <RadioGroupItem
                  id="conflict-custom"
                  value="custom"
                  disabled={action.busy}
                />
                {tr("Escribir otra solución")}
              </label>
            </RadioGroup>
            {fact?.question && (
              <p className="whitespace-pre-wrap break-words text-sm">
                {fact.question}
              </p>
            )}
            {fact?.conversation_id && (
              <Button asChild variant="link" size="sm">
                <a href={`#chat/${fact.conversation_id}`}>
                  {tr("Ver conversación de origen")}
                </a>
              </Button>
            )}
          </section>
        )}
        {fact && (
          <ChoiceSelect
            label={tr("Tipo de información")}
            value={content.kind}
            onChange={(v) => update("kind", v)}
            options={Object.entries(factKinds)
              .filter(
                ([k]) => k !== "result_reference" || fact?.content.kind === k,
              )
              .map(([value, label]) => ({ value, label: tr(label) }))}
          />
        )}
        <Field label={tr("Información")} id="fact-statement">
          <Textarea
            id="fact-statement"
            autoFocus={autoFocus && fact?.status !== "conflicted"}
            required
            maxLength={1600}
            value={content.statement}
            onChange={(e) => update("statement", e.target.value)}
            className="min-h-28"
          />
        </Field>
        <ChoiceSelect
          label={tr("Ámbito")}
          value={
            content.scope === "business"
              ? "business"
              : `${content.scope}:${content.scope_id}`
          }
          onChange={(v) => {
            const [scope, id] = v.split(":");
            if (fact?.status === "conflicted") setResolutionChoice("custom");
            setContent({ ...content, scope, scope_id: id || null });
          }}
          options={options}
        />
        <div className="grid grid-cols-2 gap-3">
          <Field label={tr("Desde (opcional)")} id="valid-from">
            <Input
              id="valid-from"
              type="date"
              value={content.valid_from || ""}
              onChange={(e) => update("valid_from", e.target.value || null)}
            />
          </Field>
          <Field label={tr("Hasta (opcional)")} id="valid-until">
            <Input
              id="valid-until"
              type="date"
              min={content.valid_from || ""}
              value={content.valid_until || ""}
              onChange={(e) => update("valid_until", e.target.value || null)}
            />
          </Field>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={content.temporal_scope === "unresolved"}
            disabled={Boolean(content.valid_from || content.valid_until)}
            onCheckedChange={(v) =>
              update("temporal_scope", v ? "unresolved" : "unspecified")
            }
          />
          {tr("Fechas pendientes de aclarar")}
        </label>
        {fact?.status === "declared" && (
          <ChoiceSelect
            label={tr("Cómo aplicar el cambio")}
            value={change}
            onChange={setChange}
            options={[
              {
                value: "historical",
                label: tr("Corregir también el contexto anterior"),
              },
              { value: "future", label: tr("Aplicar desde ahora") },
            ]}
          />
        )}
        <Notice error>{action.error}</Notice>
      </div>
      <div className="shrink-0 space-y-2 border-t pt-3">
        {fact?.status === "conflicted" && (
          <p role="status" className="text-sm text-muted-foreground">
            {resolutionChoice
              ? tr("Solución elegida: {0}.", {
                  0:
                    resolutionChoice === "custom"
                      ? tr("texto personalizado")
                      : conflictVersions.find(
                          (version) => version.id === resolutionChoice,
                        )?.label,
                })
              : tr("Elige una versión o escribe la solución para continuar.")}
          </p>
        )}
        <Button
          type="submit"
          disabled={
            action.busy || (fact?.status === "conflicted" && !resolutionChoice)
          }
        >
          {action.busy && <Busy />}
          {fact?.status === "conflicted"
            ? tr("Guardar solución")
            : tr("Guardar información")}
        </Button>
      </div>
    </form>
  );
}
