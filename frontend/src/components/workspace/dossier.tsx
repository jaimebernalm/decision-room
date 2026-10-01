import { useRef, useState } from "react";
import {
  Plus,
  Upload,
  Download,
  MessageSquare,
  Pencil,
  Check,
  Archive,
  RefreshCw,
  MoreHorizontal,
  Info,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
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
import { api, contextKey, store, date } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import type {
  Dossier as DossierData,
  Fact,
  FactContent,
  Dataset,
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
import { UploadForm } from "./business";
import { DataModelPanel } from "./data-model";
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
const factGroups = [
  { key: "review", title: "Por revisar" },
  { key: "business", title: "Sobre el negocio" },
  { key: "operations", title: "Operativa" },
  { key: "goals", title: "Objetivos y preferencias" },
] as const;
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
function factGroup(fact: Fact) {
  if (needsReview(fact)) return "review";
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
  const { workspace, refresh } = useWorkspace(),
    b = workspace.business!,
    resource = useResource<DossierData>("/api/business/dossier"),
    action = useAction();
  const [edit, setEdit] = useState<Fact | null | undefined>(undefined),
    [detail, setDetail] = useState<Fact | null>(null),
    [upload, setUpload] = useState(false);
  const actionFocus = useRef<HTMLButtonElement | null>(null),
    addInformation = useRef<HTMLButtonElement | null>(null);
  const restoreDialogFocus = (event: Event) => {
    const target = actionFocus.current?.isConnected
      ? actionFocus.current
      : addInformation.current;
    if (target) {
      event.preventDefault();
      target.focus();
    }
  };
  const done = () => {
    resource.refresh();
    refresh();
    setEdit(undefined);
    setUpload(false);
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
  return (
    <>
      <Heading title={b.name} />
      <Notice error>{resource.error || action.error}</Notice>
      {Boolean(
        data.memory.pending || data.memory.failed || data.memory.needs_review,
      ) && (
        <Notice>
          Hay información pendiente de procesar o revisar.{" "}
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
              Reintentar procesamiento
            </Button>
          )}
        </Notice>
      )}
      <Tabs defaultValue={files ? "data" : "info"} className="min-w-0 w-full">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <TabsList>
            <TabsTrigger value="info">Información</TabsTrigger>
            <TabsTrigger value="data">Datos</TabsTrigger>
            <TabsTrigger value="history">Historial</TabsTrigger>
          </TabsList>
          <Button variant="ghost" size="sm" onClick={resource.refresh}>
            <RefreshCw />
            Actualizar
          </Button>
        </div>
        <TabsContent value="info" className="max-w-4xl space-y-5">
          <div className="flex justify-end">
            <Button
              size="sm"
              ref={addInformation}
              onClick={(event) => {
                actionFocus.current = event.currentTarget;
                setEdit(null);
              }}
            >
              <Plus />
              Añadir información
            </Button>
          </div>
          {!facts.length && data.business.description && (
            <section aria-label="Presentación del negocio">
              <h2 className="mb-2 text-sm font-medium">Sobre el negocio</h2>
              <p className="line-clamp-3 whitespace-pre-wrap break-words text-sm leading-6 text-muted-foreground">
                {data.business.description}
              </p>
            </section>
          )}
          {facts.length ? (
            <Accordion
              type="multiple"
              defaultValue={factGroups.map((group) => group.key)}
              className="gap-4"
            >
              {factGroups.map((group) => {
                const items = facts.filter(
                  (fact) => factGroup(fact) === group.key,
                );
                if (!items.length) return null;
                return (
                  <AccordionItem
                    key={group.key}
                    value={group.key}
                    className="rounded-xl border border-border bg-card shadow-sm"
                  >
                    <AccordionTrigger className="items-center gap-3 rounded-xl bg-muted/50 px-4 py-3 text-base font-semibold text-foreground hover:bg-sidebar-accent hover:no-underline motion-reduce:transition-none data-open:rounded-b-none">
                      <span className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
                        {group.title}{" "}
                        <span className="inline-flex min-w-6 items-center justify-center rounded-full border border-border bg-background px-1.5 py-0.5 text-xs font-medium text-muted-foreground">
                          {items.length}
                        </span>
                      </span>
                    </AccordionTrigger>
                    <AccordionContent className="h-auto px-2 pt-1 pb-2 [&_p:not(:last-child)]:mb-0">
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
                                report_title: "Mi negocio",
                                content: {
                                  key: "fact",
                                  title:
                                    factKinds[f.content.kind] || "Información",
                                  statement: f.content.statement,
                                },
                              }}
                            >
                              <div className="group/fact flex items-start gap-3 rounded-lg px-2 py-2 text-sm transition-[background-color,box-shadow] hover:bg-sidebar-accent hover:shadow-sm focus-within:bg-sidebar-accent focus-within:shadow-sm motion-reduce:transition-none sm:px-3">
                                <div className="min-w-0 flex-1 py-2">
                                  <p className="whitespace-pre-wrap break-words leading-6">
                                    {f.content.statement}
                                  </p>
                                  {needsReview(f) && (
                                    <div className="mt-1 flex flex-wrap items-center gap-2">
                                      <Badge
                                        variant={
                                          f.status === "conflicted"
                                            ? "destructive"
                                            : "secondary"
                                        }
                                      >
                                        {f.status === "conflicted"
                                          ? factStatus[f.status]
                                          : f.content.temporal_scope ===
                                              "unresolved"
                                            ? "Fechas por aclarar"
                                            : f.content.kind === "open_question"
                                              ? "Pregunta abierta"
                                              : factStatus[f.status] ||
                                                "Por revisar"}
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
                                                  aria-label={`Confirmar: ${f.content.statement}`}
                                                  disabled={action.busy}
                                                  onClick={() =>
                                                    void mutation(f, "confirm")
                                                  }
                                                >
                                                  <Check />
                                                </Button>
                                              </TooltipTrigger>
                                              <TooltipContent>
                                                Confirmar información
                                              </TooltipContent>
                                            </Tooltip>
                                            <Tooltip>
                                              <TooltipTrigger asChild>
                                                <Button
                                                  variant="destructive"
                                                  size="icon"
                                                  className="size-9"
                                                  aria-label={`Descartar: ${f.content.statement}`}
                                                  disabled={action.busy}
                                                  onClick={() =>
                                                    void mutation(f, "withdraw")
                                                  }
                                                >
                                                  <X />
                                                </Button>
                                              </TooltipTrigger>
                                              <TooltipContent>
                                                Descartar y conservar en el
                                                historial
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
                                          Resolver conflicto
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
                                      className="size-10 shrink-0"
                                      aria-label={`Acciones: ${f.content.statement}`}
                                      onFocus={(event) => {
                                        actionFocus.current =
                                          event.currentTarget;
                                      }}
                                      onPointerDown={(event) => {
                                        actionFocus.current =
                                          event.currentTarget;
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
                                      Editar
                                    </DropdownMenuItem>
                                    <DropdownMenuItem
                                      onSelect={() => setDetail(f)}
                                    >
                                      <Info />
                                      Ver detalles
                                    </DropdownMenuItem>
                                    {canConfirm(f) && (
                                      <DropdownMenuItem
                                        disabled={action.busy}
                                        onSelect={() => {
                                          void mutation(f, "confirm");
                                        }}
                                      >
                                        <Check />
                                        Confirmar
                                      </DropdownMenuItem>
                                    )}
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem
                                      variant="destructive"
                                      disabled={action.busy}
                                      onSelect={() => {
                                        void mutation(f, "withdraw");
                                      }}
                                    >
                                      <Archive />
                                      Retirar
                                    </DropdownMenuItem>
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              </div>
                            </Selectable>
                          </li>
                        ))}
                      </ul>
                    </AccordionContent>
                  </AccordionItem>
                );
              })}
            </Accordion>
          ) : (
            <Empty
              title="Un contexto que crece contigo"
              description="Añade prioridades, definiciones o detalles que el asistente debería recordar."
            />
          )}
          <Disclosure title="Ver presentación original">
            <Selectable
              item={{
                kind: "business",
                source_id: b.id,
                source_version: String(data.business.profile_revision),
                element_key: "profile",
                title: `Presentación de ${data.business.name}`,
                href: "#my-business",
                report_title: "Mi negocio",
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
                Editar presentación
              </a>
            </Button>
          </Disclosure>
        </TabsContent>
        <TabsContent value="data" className="space-y-5">
          <div className="flex justify-end">
            <Button size="sm" onClick={() => setUpload(true)}>
              <Upload />
              Subir datos
            </Button>
          </div>
          {data.datasets.length ? (
            data.datasets.map((d) => (
              <Card key={d.id} className="shadow-none">
                <CardHeader>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <CardTitle>{d.title}</CardTitle>
                    <Badge variant={d.corrected ? "destructive" : "secondary"}>
                      v{d.version}
                      {d.corrected
                        ? " · corregida"
                        : d.superseded_by
                          ? " · anterior"
                          : ""}
                      {d.status === "partial" ? " · algunos archivos fallaron" : ""}
                      {d.status === "failed" ? " · sin tablas disponibles" : ""}
                    </Badge>
                  </div>
                  <CardDescription>
                    {d.period_from || "Inicio no indicado"} —{" "}
                    {d.period_until || "Fin no indicado"}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {(d.status === "ready" || d.status === "partial") && <DataModelPanel business={b.id} analysis={d.id} />}
                  {!!d.original_files?.length && <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground">Archivos originales de la entrega</p>
                    {d.original_files.map((file) => <div key={file.path} className="flex items-center gap-2 text-sm">
                      <span className="min-w-0 flex-1 break-all">{file.path} · {(file.size / 1_000_000).toFixed(1)} MB</span>
                      <Button asChild size="icon" variant="ghost"><a href={`/api/datasets/original/${d.id}?path=${encodeURIComponent(file.path)}`} download aria-label={`Descargar ${file.path}`}><Download /></a></Button>
                    </div>)}
                  </div>}
                  {!!d.original_files?.length && <p className="text-xs font-medium text-muted-foreground">Tablas disponibles para analizar</p>}
                  {d.files?.map((f) => (
                    <div key={f.id} className="flex items-center gap-3 text-sm">
                      <span className="min-w-0 flex-1 break-all">
                        {f.name}
                        <span className="ml-2 text-xs text-muted-foreground">
                          {f.status === "failed" ? "No se pudo preparar" : `${f.rows ?? "—"} filas`}
                        </span>
                      </span>
                      {f.status !== "failed" && <Button asChild size="icon" variant="ghost">
                        <a href={`/api/datasets/file/${f.id}`} download aria-label={`Descargar ${f.name}`}>
                          <Download />
                        </a>
                      </Button>}
                    </div>
                  ))}
                  {(d.status === "ready" || d.status === "partial") && !d.corrected && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        store.set(contextKey(b.id), {
                          analysis_id: d.id,
                          label: `${d.title} · v${d.version}`,
                        });
                        location.hash = "ask";
                      }}
                    >
                      <MessageSquare />
                      Preguntar con esta versión
                    </Button>
                  )}
                </CardContent>
              </Card>
            ))
          ) : (
            <Empty
              title="Tus datos empiezan aquí"
              description="Guarda archivos CSV o Excel, juntos o como carpeta, para reutilizarlos en las conversaciones. Cada actualización conserva su versión."
            />
          )}
        </TabsContent>
        <TabsContent value="history" className="space-y-3">
          {data.history.length ? (
            data.history.map((f, i) => (
              <Card
                key={`${f.fact_id}-${f.revision}-${i}`}
                className="shadow-none"
              >
                <CardContent className="space-y-3">
                  <div className="flex flex-wrap justify-between gap-2 text-xs text-muted-foreground">
                    <span>
                      {date(f.created_at)} · revisión {f.revision}
                    </span>
                    <Badge variant="outline">
                      {factStatus[f.status] || f.status}
                    </Badge>
                  </div>
                  <p className="text-sm">{f.content.statement}</p>
                  <FactOrigin fact={f} />
                </CardContent>
              </Card>
            ))
          ) : (
            <p className="py-10 text-center text-sm text-muted-foreground">
              El historial aparecerá cuando guardes información.
            </p>
          )}
        </TabsContent>
      </Tabs>
      <Dialog
        open={detail !== null}
        onOpenChange={(open) => {
          if (!open) setDetail(null);
        }}
      >
        <DialogContent
          className="max-h-[90svh] overflow-y-auto sm:max-w-xl"
          onCloseAutoFocus={restoreDialogFocus}
        >
          <DialogHeader>
            <DialogTitle>Detalles de la información</DialogTitle>
            <DialogDescription>
              Origen, ámbito y vigencia de este dato.
            </DialogDescription>
          </DialogHeader>
          {detail && (
            <div className="min-w-0 space-y-4 break-words text-sm">
              <p className="whitespace-pre-wrap leading-6">
                {detail.content.statement}
              </p>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">
                  {factKinds[detail.content.kind] || detail.content.kind}
                </Badge>
                <Badge
                  variant={
                    detail.status === "conflicted" ? "destructive" : "secondary"
                  }
                >
                  {factStatus[detail.status] || detail.status}
                </Badge>
              </div>
              <p className="text-muted-foreground">
                {scopeLabel(detail.content, data.datasets)}
              </p>
              <p className="text-xs text-muted-foreground">
                {date(detail.created_at)} · revisión {detail.revision}
              </p>
              <FactOrigin fact={detail} expanded />
            </div>
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
          className="max-h-[90svh] overflow-y-auto sm:max-w-xl"
          onCloseAutoFocus={restoreDialogFocus}
        >
          <DialogHeader>
            <DialogTitle>
              {edit?.status === "conflicted"
                ? "Resolver conflicto"
                : edit
                  ? "Corregir información"
                  : "Añadir información"}
            </DialogTitle>
            <DialogDescription>
              {edit?.status === "conflicted"
                ? "Elige una versión como punto de partida o escribe la correcta. Revisa su ámbito y fechas antes de guardar."
                : "Se guardará en la memoria de este negocio."}
            </DialogDescription>
          </DialogHeader>
          {edit !== undefined && (
            <FactEditor
              key={edit ? `${edit.fact_id}-${edit.revision}` : "new"}
              fact={edit}
              datasets={data.datasets}
              onDone={done}
            />
          )}
        </DialogContent>
      </Dialog>
      <Dialog open={upload} onOpenChange={setUpload}>
        <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>Añadir datos al negocio</DialogTitle>
            <DialogDescription>
              Conserva el periodo y la relación entre versiones.
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
      ? "Todo el negocio"
      : content.scope === "analysis"
        ? datasets.find((d) => d.id === content.scope_id)?.title ||
          "Conjunto de datos"
        : datasets
            .flatMap((d) => d.files || [])
            .find((f) => f.id === content.scope_id)?.name || "Archivo";
  return `${target}${content.valid_from || content.valid_until ? ` · ${content.valid_from || "…"} — ${content.valid_until || "…"}` : ""}${content.temporal_scope === "unresolved" ? " · fechas por aclarar" : ""}`;
}
function FactOrigin({
  fact,
  expanded = false,
}: {
  fact: Fact;
  expanded?: boolean;
}) {
  const content = (
    <div className="space-y-3 whitespace-pre-wrap break-words">
      <p>
        {fact.content.valid_from || "Sin fecha inicial"} —{" "}
        {fact.content.valid_until || "Sin fecha final"}
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
            Ver conversación de origen
          </a>
        </Button>
      )}
      {fact.alternatives?.map((a, i) => (
        <p key={i}>
          Alternativa: {a.content?.statement || a.statement || a.quote}
        </p>
      ))}
    </div>
  );
  return expanded ? (
    content
  ) : (
    <Disclosure title="Origen y vigencia">{content}</Disclosure>
  );
}
function FactEditor({
  fact,
  datasets,
  onDone,
}: {
  fact: Fact | null;
  datasets: Dataset[];
  onDone: () => void;
}) {
  const { workspace } = useWorkspace(),
    action = useAction();
  const [content, setContent] = useState<FactContent>(
    fact?.content || {
      kind: "context",
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
    pending = useRef({ signature: "", key: "" });
  const update = (field: string, value: unknown) =>
    setContent({ ...content, [field]: value });
  const options = [
    { value: "business", label: "Todo el negocio" },
    ...datasets.flatMap((d) => [
      { value: `analysis:${d.id}`, label: `Datos: ${d.title} · v${d.version}` },
      ...(d.files || []).map((f) => ({
        value: `source:${f.id}`,
        label: `Archivo: ${f.name}`,
      })),
    ]),
  ];
  const conflictVersions =
    fact?.status === "conflicted"
      ? [
          {
            label: "Información actual",
            content: fact.content,
            quote: fact.quote,
          },
          ...(fact.alternatives || []).flatMap((alternative, index) => {
            const statement =
              alternative.content?.statement || alternative.statement;
            return statement
              ? [
                  {
                    label: `Alternativa ${index + 1}`,
                    content: alternative.content || {
                      ...fact.content,
                      statement,
                    },
                    quote: alternative.quote,
                  },
                ]
              : [];
          }),
        ]
      : [];
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
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
            action: fact ? "correct" : "declare",
            content: value,
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
          toast.success("Información guardada");
          onDone();
        });
      }}
    >
      {conflictVersions.length > 0 && (
        <section aria-label="Versiones en conflicto" className="space-y-3">
          {conflictVersions.map((version) => (
            <div
              key={version.label}
              className="space-y-2 rounded-lg border bg-muted/30 p-3 text-sm"
            >
              <h3 className="font-semibold">{version.label}</h3>
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
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={action.busy}
                aria-label={`Usar ${version.label.toLowerCase()}`}
                onClick={() => setContent({ ...version.content })}
              >
                Usar esta versión
              </Button>
            </div>
          ))}
          {fact?.question && (
            <p className="whitespace-pre-wrap break-words text-sm">
              {fact.question}
            </p>
          )}
          {fact?.conversation_id && (
            <Button asChild variant="link" size="sm">
              <a href={`#chat/${fact.conversation_id}`}>
                Ver conversación de origen
              </a>
            </Button>
          )}
        </section>
      )}
      <ChoiceSelect
        label="Tipo de información"
        value={content.kind}
        onChange={(v) => update("kind", v)}
        options={Object.entries(factKinds)
          .filter(([k]) => k !== "result_reference" || fact?.content.kind === k)
          .map(([value, label]) => ({ value, label }))}
      />
      <Field label="Información" id="fact-statement">
        <Textarea
          id="fact-statement"
          required
          maxLength={1600}
          value={content.statement}
          onChange={(e) => update("statement", e.target.value)}
          className="min-h-28"
        />
      </Field>
      <ChoiceSelect
        label="Ámbito"
        value={
          content.scope === "business"
            ? "business"
            : `${content.scope}:${content.scope_id}`
        }
        onChange={(v) => {
          const [scope, id] = v.split(":");
          setContent({ ...content, scope, scope_id: id || null });
        }}
        options={options}
      />
      <div className="grid grid-cols-2 gap-3">
        <Field label="Desde (opcional)" id="valid-from">
          <Input
            id="valid-from"
            type="date"
            value={content.valid_from || ""}
            onChange={(e) => update("valid_from", e.target.value || null)}
          />
        </Field>
        <Field label="Hasta (opcional)" id="valid-until">
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
        Fechas pendientes de aclarar
      </label>
      {fact?.status === "declared" && (
        <ChoiceSelect
          label="Cómo aplicar el cambio"
          value={change}
          onChange={setChange}
          options={[
            {
              value: "historical",
              label: "Corregir también el contexto anterior",
            },
            { value: "future", label: "Aplicar desde ahora" },
          ]}
        />
      )}
      <Notice error>{action.error}</Notice>
      <Button type="submit" disabled={action.busy}>
        {action.busy && <Busy />}
        {fact?.status === "conflicted"
          ? "Guardar solución"
          : "Guardar información"}
      </Button>
    </form>
  );
}
