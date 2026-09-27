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
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
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
  uncertain: "Por revisar",
  conflicted: "En conflicto",
  withdrawn: "Retirado",
  confirmed: "Confirmado",
  superseded: "Sustituido",
};
export function Dossier({ files = false }: { files?: boolean }) {
  const { workspace, refresh } = useWorkspace(),
    b = workspace.business!,
    resource = useResource<DossierData>("/api/business/dossier"),
    action = useAction();
  const [edit, setEdit] = useState<Fact | null | undefined>(undefined),
    [upload, setUpload] = useState(false);
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
      <Heading
        title={b.name}
        description="La información y los datos que dan contexto a cada respuesta."
      >
        <Button asChild variant="outline">
          <a href="#business">
            <Pencil />
            Editar presentación
          </a>
        </Button>
      </Heading>
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
        <Card className="mb-6 shadow-none">
          <CardContent className="whitespace-pre-wrap text-sm leading-7 text-muted-foreground">
            {data.business.description}
          </CardContent>
        </Card>
      </Selectable>
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
            <TabsTrigger value="data">Datos y versiones</TabsTrigger>
            <TabsTrigger value="history">Historial</TabsTrigger>
          </TabsList>
          <Button variant="ghost" size="sm" onClick={resource.refresh}>
            <RefreshCw />
            Actualizar
          </Button>
        </div>
        <TabsContent value="info" className="space-y-5">
          <div className="flex justify-end">
            <Button size="sm" onClick={() => setEdit(null)}>
              <Plus />
              Añadir información
            </Button>
          </div>
          {facts.length ? (
            <div className="grid gap-4 md:grid-cols-2">
              {facts.map((f) => (
                <Selectable
                  key={f.fact_id}
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
                      title: factKinds[f.content.kind] || "Información",
                      statement: f.content.statement,
                    },
                  }}
                >
                  <Card className="shadow-none">
                    <CardHeader>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="outline">
                          {factKinds[f.content.kind] || f.content.kind}
                        </Badge>
                        <Badge
                          variant={
                            f.status === "conflicted"
                              ? "destructive"
                              : "secondary"
                          }
                        >
                          {factStatus[f.status] || f.status}
                        </Badge>
                      </div>
                      <CardTitle className="text-base leading-7">
                        {f.content.statement}
                      </CardTitle>
                      <CardDescription>
                        {scopeLabel(f.content, data.datasets)}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <FactOrigin fact={f} />
                      <div className="flex flex-wrap gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setEdit(f)}
                        >
                          <Pencil />
                          Corregir
                        </Button>
                        {f.status !== "declared" && (
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={action.busy}
                            onClick={() => mutation(f, "confirm")}
                          >
                            <Check />
                            Confirmar
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={action.busy}
                          onClick={() => mutation(f, "withdraw")}
                        >
                          <Archive />
                          Retirar
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </Selectable>
              ))}
            </div>
          ) : (
            <Empty
              title="Un contexto que crece contigo"
              description="Añade prioridades, definiciones o detalles que el asistente debería recordar."
            />
          )}
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
        open={edit !== undefined}
        onOpenChange={(open) => {
          if (!open) setEdit(undefined);
        }}
      >
        <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>
              {edit ? "Corregir información" : "Añadir información"}
            </DialogTitle>
            <DialogDescription>
              Se guardará en la memoria de este negocio.
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
function FactOrigin({ fact }: { fact: Fact }) {
  return (
    <Disclosure title="Origen y vigencia">
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
    </Disclosure>
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
        {action.busy && <Busy />}Guardar información
      </Button>
    </form>
  );
}
