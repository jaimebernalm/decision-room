import { useState } from "react";
import {
  ArrowRight,
  Plus,
  Upload,
  Download,
  FileSpreadsheet,
  Check,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { useWorkspace } from "@/lib/workspace";
import { useDraft, useAction } from "@/lib/hooks";
import { api, store, uploadPayload } from "@/lib/api";
import type { Dataset } from "@/lib/types";
import { Heading, Field, Notice, ChoiceSelect, Busy } from "./shared";
export function BusinessPicker() {
  const { workspace, refresh } = useWorkspace(),
    action = useAction();
  return (
    <>
      <Heading
        title="Tus negocios"
        description="Cada negocio tiene sus propios datos, memoria y conversaciones."
      >
        <Button asChild>
          <a href="#business-new">
            <Plus />
            Nuevo negocio
          </a>
        </Button>
      </Heading>
      <Notice error>{action.error}</Notice>
      <div className="grid gap-4 md:grid-cols-2">
        {workspace.businesses.map((b) => (
          <Card key={b.id} className="shadow-none">
            <CardHeader>
              <CardTitle>{b.name}</CardTitle>
              <CardDescription className="line-clamp-3">
                {b.description}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                variant="outline"
                disabled={action.busy}
                onClick={() =>
                  action.run(async () => {
                    await api("/api/business/select", { business_id: b.id });
                    refresh();
                    location.hash = "home";
                  })
                }
              >
                {workspace.business?.id === b.id ? (
                  <>
                    <Check />
                    Negocio activo
                  </>
                ) : (
                  <>
                    Abrir negocio
                    <ArrowRight />
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
export function BusinessForm({ create = false }: { create?: boolean }) {
  const { workspace, refresh } = useWorkspace(),
    current = create ? null : workspace.business,
    key = current
      ? `dr-profile-${current.id}`
      : `dr-profile-new-${workspace.business?.id || "empty"}`;
  const [draft, setDraft] = useDraft(key, {
    name: current?.name || "",
    description: current?.description || "",
    profile_revision: current?.profile_revision,
    request_key: crypto.randomUUID(),
  });
  const action = useAction();
  return (
    <div className="mx-auto max-w-2xl">
      <Heading
        title={
          current ? "Presentación del negocio" : "Empecemos por tu negocio"
        }
        description="Este contexto ayuda a interpretar tus datos y responder con más criterio."
      />
      <Card className="shadow-none">
        <CardContent>
          <form
            className="space-y-6"
            onSubmit={(e) => {
              e.preventDefault();
              void action.run(async () => {
                await api("/api/business", {
                  ...draft,
                  business_id: current?.id,
                  expected_active_id: workspace.business?.id || null,
                });
                store.remove(key);
                refresh();
                if (action.isMounted()) {
                  location.hash = "home";
                  toast.success("Presentación guardada");
                }
              });
            }}
          >
            <Field label="Nombre del negocio" id="business-name">
              <Input
                id="business-name"
                autoComplete="organization"
                required
                maxLength={100}
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
            </Field>
            <Field
              label="Cuéntanos qué haces"
              id="business-description"
              hint="Qué vendes, a quién, cómo funciona el negocio y qué te interesa mejorar."
            >
              <Textarea
                id="business-description"
                required
                maxLength={6000}
                className="min-h-48"
                value={draft.description}
                onChange={(e) =>
                  setDraft({ ...draft, description: e.target.value })
                }
              />
            </Field>
            <Notice error>{action.error}</Notice>
            {current && current.profile_revision !== draft.profile_revision && (
              <Notice>
                El perfil ha cambiado.{" "}
                <Button
                  type="button"
                  variant="link"
                  onClick={() => {
                    setDraft({
                      ...draft,
                      name: current.name,
                      description: current.description,
                      profile_revision: current.profile_revision,
                      request_key: crypto.randomUUID(),
                    });
                    action.setError("");
                  }}
                >
                  Descartar borrador y cargar la versión actual
                </Button>
              </Notice>
            )}
            <Button disabled={action.busy} type="submit">
              {action.busy ? <Busy /> : <ArrowRight />}
              {current ? "Guardar presentación" : "Crear negocio"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
export function UploadForm({
  datasets,
  onDone,
}: {
  datasets?: Dataset[];
  onDone?: () => void;
}) {
  const { workspace, refresh } = useWorkspace(),
    b = workspace.business!,
    dataOnly = datasets !== undefined;
  const key = dataOnly ? `dr-dataset-upload-${b.id}` : `dr-draft-${b.id}`;
  const [draft, setDraft] = useDraft(key, {
    title: "",
    mode: dataOnly ? "separate" : "general",
    goal: "",
    previous_id: "",
    period_from: "",
    period_until: "",
  });
  const [file, setFile] = useState<File | null>(null),
    action = useAction();
  const update = (field: string, value: string) =>
    setDraft({ ...draft, [field]: value });
  const submit = () =>
    action.run(async () => {
      if (!file) throw new Error("Selecciona el CSV que quieres subir.");
      const metadata = dataOnly
        ? {
            business_id: b.id,
            title: draft.title,
            mode: draft.mode,
            previous_id: draft.mode === "separate" ? "" : draft.previous_id,
            period_from: draft.period_from,
            period_until: draft.period_until,
          }
        : {
            business_id: b.id,
            profile_revision: b.profile_revision,
            title: draft.title,
            goal: draft.mode === "specific" ? draft.goal : "",
          };
      const body = await uploadPayload(`${key}-pending`, metadata, file);
      const result = await api<{ id: string; message?: string }>(
        dataOnly ? "/api/datasets" : "/api/jobs",
        body,
      );
      store.remove(key);
      store.remove(`${key}-pending`);
      refresh();
      if (action.isMounted()) {
        if (dataOnly) {
          toast.success(result.message || "Datos guardados");
          onDone?.();
        } else location.hash = `analysis/${result.id}`;
      }
    });
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <Field
        label={
          dataOnly ? "Nombre del conjunto de datos" : "Título del análisis"
        }
        id="upload-title"
      >
        <Input
          id="upload-title"
          required
          maxLength={160}
          placeholder="Por ejemplo, ventas del último trimestre"
          value={draft.title}
          onChange={(e) => update("title", e.target.value)}
        />
      </Field>
      <ChoiceSelect
        label={
          dataOnly ? "Cómo se relaciona con tus datos" : "Qué quieres analizar"
        }
        value={draft.mode}
        onChange={(v) => update("mode", v)}
        options={
          dataOnly
            ? [
                { value: "separate", label: "Datos independientes" },
                { value: "update", label: "Nueva versión de un conjunto" },
                { value: "correction", label: "Corregir una versión anterior" },
              ]
            : [
                { value: "general", label: "Exploración general" },
                { value: "specific", label: "Una pregunta concreta" },
              ]
        }
      />
      {!dataOnly && draft.mode === "specific" && (
        <Field label="Tu pregunta" id="goal">
          <Textarea
            id="goal"
            required
            value={draft.goal}
            maxLength={2000}
            onChange={(e) => update("goal", e.target.value)}
          />
        </Field>
      )}
      {dataOnly && draft.mode !== "separate" && (
        <>
          <ChoiceSelect
            label="Conjunto anterior"
            value={draft.previous_id || "none"}
            onChange={(v) => update("previous_id", v === "none" ? "" : v)}
            options={[
              { value: "none", label: "Selecciona una versión" },
              ...datasets
                .filter((d) => !d.superseded_by || d.id === draft.previous_id)
                .map((d) => ({
                  value: d.id,
                  label: `${d.title} · v${d.version}`,
                })),
            ]}
          />
          <Notice>
            {draft.mode === "correction"
              ? "La corrección invalidará las respuestas que dependan de los datos sustituidos."
              : "La versión anterior seguirá disponible como histórico."}
          </Notice>
        </>
      )}
      {dataOnly && (
        <div className="grid grid-cols-2 gap-3">
          <Field label="Desde (opcional)" id="period-from">
            <Input
              type="date"
              id="period-from"
              value={draft.period_from}
              onChange={(e) => update("period_from", e.target.value)}
            />
          </Field>
          <Field label="Hasta (opcional)" id="period-until">
            <Input
              type="date"
              id="period-until"
              value={draft.period_until}
              min={draft.period_from}
              onChange={(e) => update("period_until", e.target.value)}
            />
          </Field>
        </div>
      )}
      <div
        className="rounded-xl border border-dashed bg-muted/30 p-6"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          setFile(e.dataTransfer.files[0] || null);
        }}
      >
        <FileSpreadsheet className="mb-3 size-6 text-muted-foreground" />
        <Field
          label="Archivo CSV"
          id="csv-file"
          hint="Arrastra un archivo o selecciónalo. CSV UTF-8, hasta 20 MB."
        >
          <Input
            id="csv-file"
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </Field>
        {file && (
          <p className="mt-3 break-all text-xs">
            {file.name} · {(file.size / 1024).toFixed(1)} KB
          </p>
        )}
      </div>
      <Notice error>{action.error}</Notice>
      <div className="flex flex-wrap items-center gap-3">
        <Button
          disabled={
            action.busy ||
            !file ||
            (dataOnly && draft.mode !== "separate" && !draft.previous_id)
          }
          type="submit"
        >
          {action.busy ? <Busy /> : <Upload />}
          {dataOnly ? "Guardar datos" : "Preparar análisis"}
        </Button>
        <Button asChild type="button" variant="ghost">
          <a href="/api/sample" download>
            <Download />
            CSV de ejemplo
          </a>
        </Button>
      </div>
    </form>
  );
}
export function NewAnalysis() {
  return (
    <div className="mx-auto max-w-2xl">
      <Heading
        title="Un nuevo análisis"
        description="Sube tus datos. Revisaremos su estructura y pediremos las aclaraciones que hagan falta."
      />
      <Card className="shadow-none">
        <CardContent>
          <UploadForm />
        </CardContent>
      </Card>
    </div>
  );
}
