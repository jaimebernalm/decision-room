import { translate as tr, useLanguage } from "@/lib/i18n";
import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  FileSpreadsheet,
  FileText,
  Upload,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { BusinessForm } from "@/components/workspace/business";
import { JobPage } from "@/components/workspace/job";
import { Busy, Field, Notice } from "@/components/workspace/shared";
import { useWorkspace } from "@/lib/workspace";
import { useAction, useDraft } from "@/lib/hooks";
import {
  api,
  store,
  selectedDataFiles,
  uploadFolder,
  FOLDER_LIMIT,
} from "@/lib/api";
import type { Business, Dataset, Dossier } from "@/lib/types";
import { GuidedOnboarding } from "./guided-onboarding";
import { EntryFrame } from "./welcome";

const steps = ["Tu negocio", "Tus datos", "Primer informe"];

export function Onboarding({
  route,
  onSaved,
}: {
  route: string;
  onSaved: (business: Business) => void;
}) {
  useLanguage();
  const { workspace } = useWorkspace();
  const [, businessId, page, jobId] = route.split("/");
  const review = page === "review";
  const visibleSteps = !businessId
    ? [
        tr("Tu negocio"),
        tr("Tu objetivo"),
        tr("Tus datos"),
        tr("El alcance"),
        tr("Tu informe"),
      ]
    : steps;
  const [files, setFiles] = useState<File[]>([]);
  const [ignored, setIgnored] = useState(0);
  const stage =
    !businessId || page === "business"
      ? 0
      : page === "report" || review
        ? 2
        : 1;
  const heading = useRef<HTMLDivElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, [route, stage]);
  const mismatch = businessId && workspace.business?.id !== businessId;
  const hasExistingBusiness =
    workspace.businesses.some((business) => business.id !== businessId) ||
    (!businessId && Boolean(workspace.business));
  if (
    businessId &&
    !mismatch &&
    !["business", "report", "review"].includes(page)
  )
    return <GuidedOnboarding business={workspace.business!} />;
  return (
    <EntryFrame
      action={
        !hasExistingBusiness && (
          <Button asChild variant="ghost" size="sm" className="rounded-full">
            <a href="#welcome">
              <ArrowLeft className="size-4" />
              {tr("Bienvenida")}
            </a>
          </Button>
        )
      }
    >
      <div className="mx-auto w-full max-w-2xl px-5 pb-12 pt-7 sm:px-8 sm:pt-12">
        <nav aria-label={tr("Pasos de inicio")} className="mb-10 sm:mb-14">
          <ol className="flex items-start">
            {visibleSteps.map((label, index) => (
              <li
                key={tr(label)}
                aria-current={stage === index ? "step" : undefined}
                className="relative flex flex-1 flex-col items-center gap-2 text-center text-xs"
              >
                {index < visibleSteps.length - 1 && (
                  <span
                    aria-hidden="true"
                    className={`absolute left-[calc(50%+1.25rem)] right-[calc(-50%+1.25rem)] top-4 h-px ${stage > index ? "bg-primary/50" : "bg-border"}`}
                  />
                )}
                <span
                  className={`relative flex size-8 items-center justify-center rounded-full text-xs font-medium ${stage >= index ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}
                >
                  {stage > index ? (
                    <Check className="size-4" aria-label={tr("Completado")} />
                  ) : (
                    index + 1
                  )}
                </span>
                <span
                  className={
                    stage === index ? "font-medium" : "text-muted-foreground"
                  }
                >
                  {tr(label)}
                </span>
              </li>
            ))}
          </ol>
        </nav>
        <div ref={heading} tabIndex={-1} className="outline-none">
          {mismatch ? (
            <>
              <Notice>
                {tr(
                  "El negocio activo ha cambiado. Vuelve a tu espacio para continuar con el negocio correcto.",
                )}
              </Notice>
              <Button asChild>
                <a href="#home">{tr("Ir a mi espacio")}</a>
              </Button>
            </>
          ) : !businessId || page === "business" ? (
            <BusinessForm
              key={businessId || "new"}
              create={!businessId}
              onboarding
              onSaved={onSaved}
            />
          ) : page === "report" && jobId ? (
            <>
              <p className="mb-5 text-sm text-muted-foreground">
                {tr(
                  "Ya tenemos tu contexto y tus archivos. Aquí podrás seguir el análisis y responder si necesitamos alguna aclaración.",
                )}
              </p>
              <JobPage id={jobId} onboarding />
            </>
          ) : (
            <FirstReport
              key={businessId}
              business={workspace.business!}
              review={review}
              onReview={(value) => {
                location.hash = `onboarding/${businessId}${value ? "/review" : ""}`;
              }}
              files={files}
              setFiles={setFiles}
              ignored={ignored}
              setIgnored={setIgnored}
            />
          )}
        </div>
      </div>
    </EntryFrame>
  );
}

function FirstReport({
  business,
  review,
  onReview,
  files,
  setFiles,
  ignored,
  setIgnored,
}: {
  business: Business;
  review: boolean;
  onReview: (value: boolean) => void;
  files: File[];
  setFiles: (files: File[]) => void;
  ignored: number;
  setIgnored: (count: number) => void;
}) {
  useLanguage();
  const key = `dr-onboarding-upload-${business.id}`;
  const { refresh } = useWorkspace();
  const [draft, setDraft] = useDraft(key, {
    title: tr("Primer informe de {0}", { "0": business.name }).slice(0, 160),
    goal: "",
    filename: "",
  });
  const action = useAction();
  const input = useRef<HTMLInputElement>(null);
  const [uploaded, setUploaded] = useState(0);
  const [partial, setPartial] = useState<Dataset | null>(null);
  const total = files.reduce((sum, file) => sum + file.size, 0);
  const size =
    total < 1024
      ? `${total} B`
      : total < 1024 ** 2
        ? `${(total / 1024).toFixed(1)} KB`
        : `${(total / 1024 ** 2).toFixed(1)} MB`;
  const fileCount =
    files.length === 1
      ? "1 archivo"
      : tr("{0} archivos", { "0": files.length });
  const choose = (selection: FileList | File[]) => {
    action.setError("");
    const picked = selectedDataFiles(Array.from(selection));
    setFiles(picked.supported);
    setIgnored(picked.ignored.length);
    setPartial(null);
    setUploaded(0);
    setDraft({
      ...draft,
      filename: picked.supported.map((file) => file.name).join(", "),
    });
  };
  const submit = () =>
    action.run(async () => {
      if (!files.length)
        throw new Error(
          tr("Vuelve a seleccionar tus archivos para continuar."),
        );
      const bundle = await uploadFolder(
        `${key}-pending`,
        {
          business_id: business.id,
          title: draft.title,
          mode: "separate",
        },
        files,
        (done) => setUploaded(done),
      );
      if (bundle.status !== "ready" && bundle.status !== "partial")
        throw new Error(
          bundle.message ||
            tr("Revisa los archivos que no se pudieron preparar."),
        );
      if (bundle.status === "partial" && partial?.id !== bundle.analysis_id) {
        const dossier = await api<Dossier>("/api/business/dossier");
        const dataset = dossier.datasets.find(
          (item) => item.id === bundle.analysis_id,
        );
        if (dossier.business_id !== business.id || !dataset)
          throw new Error(
            tr(
              "No se ha podido comprobar qué archivos están disponibles. Vuelve a intentarlo.",
            ),
          );
        setPartial(dataset);
        return;
      }
      const result = await api<{ id: string }>("/api/jobs/from-dataset", {
        business_id: business.id,
        profile_revision: business.profile_revision,
        title: draft.title,
        goal: draft.goal,
        analysis_id: bundle.analysis_id,
        request_key: bundle.upload_id,
      });
      store.remove(key);
      store.remove(`${key}-pending`);
      if (action.isMounted())
        location.hash = `onboarding/${business.id}/report/${result.id}`;
      refresh();
    });
  return (
    <form
      className="space-y-7"
      onSubmit={(event) => {
        event.preventDefault();
        if (review) void submit();
        else if (files.length && total <= FOLDER_LIMIT) onReview(true);
      }}
    >
      <div>
        <p className="mb-3 text-xs font-medium text-primary">{business.name}</p>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          {review
            ? tr("Vamos a crear tu primer informe")
            : tr("Ahora, comparte tus datos")}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          {review
            ? tr(
                "Revisaremos tus archivos, te preguntaremos lo necesario y prepararemos un informe con resultados que puedas comprobar.",
              )
            : tr(
                "Comparte los CSV o Excel que ya tienes, juntos o dentro de una carpeta. No necesitas preparar una plantilla especial.",
              )}
        </p>
      </div>
      {review ? (
        <>
          <div className="space-y-5 rounded-2xl bg-muted/60 p-5 sm:p-6">
            <div>
              <p className="text-xs text-muted-foreground">
                {tr("Tu negocio")}
              </p>
              <p className="mt-1 font-medium">{business.name}</p>
              <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-relaxed text-muted-foreground">
                {business.description}
              </p>
            </div>
            <div className="flex items-center gap-3 border-t pt-4">
              <FileSpreadsheet className="size-5 shrink-0 text-primary" />
              <div className="min-w-0">
                <p className="break-all text-sm font-medium">{fileCount}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {size}
                  {tr(" en total")}
                </p>
              </div>
            </div>
            {files.length > 0 && (
              <ul
                className="space-y-1 text-xs text-muted-foreground"
                aria-label={tr("Archivos seleccionados")}
              >
                {files.slice(0, 5).map((file, index) => (
                  <li className="break-all" key={index}>
                    {file.webkitRelativePath || file.name}
                  </li>
                ))}
                {files.length > 5 && (
                  <li>
                    {tr("Y ")}
                    {files.length - 5}
                    {tr(" archivos más.")}
                  </li>
                )}
              </ul>
            )}
            {draft.goal && (
              <div className="border-t pt-4">
                <p className="text-xs text-muted-foreground">
                  {tr("Qué te gustaría entender")}
                </p>
                <p className="mt-1 whitespace-pre-wrap break-words text-sm">
                  {draft.goal}
                </p>
              </div>
            )}
          </div>
          <Field label={tr("Nombre del informe")} id="first-report-title">
            <Input
              id="first-report-title"
              required
              maxLength={160}
              value={draft.title}
              disabled={action.busy}
              onChange={(event) =>
                setDraft({ ...draft, title: event.target.value })
              }
            />
          </Field>
          <p className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
            <FileText className="mt-0.5 size-4 shrink-0" />
            {tr(
              "Si falta información, guardaremos tu avance y te ayudaremos a aclararla antes de mostrar resultados.",
            )}
          </p>
        </>
      ) : (
        <>
          <div
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              choose(event.dataTransfer.files);
            }}
            className="rounded-2xl border border-dashed border-primary/35 bg-primary/5 p-7 text-center sm:p-10"
          >
            <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-2xl bg-background text-primary">
              <Upload className="size-6" />
            </div>
            <p className="text-sm font-medium">
              {files.length
                ? tr("Datos seleccionados")
                : tr("Arrastra archivos aquí")}
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              {tr("CSV o Excel · Hasta 2 GB en total")}
            </p>
            <Input
              ref={input}
              id="onboarding-files"
              type="file"
              multiple
              accept=".csv,.xlsx"
              className="hidden"
              aria-label={tr("Archivos CSV o Excel")}
              onChange={(event) => choose(event.target.files || [])}
            />
            <Input
              id="onboarding-folder"
              type="file"
              multiple
              accept=".csv,.xlsx"
              className="hidden"
              aria-label={tr("Carpeta de datos")}
              ref={(node) => node?.setAttribute("webkitdirectory", "")}
              onChange={(event) => choose(event.target.files || [])}
            />
            <Button
              type="button"
              variant="outline"
              className="mt-5 rounded-full bg-background"
              onClick={() => input.current?.click()}
            >
              {tr("Seleccionar archivos")}
            </Button>
            <Button
              type="button"
              variant="outline"
              className="mt-5 ml-2 rounded-full bg-background"
              onClick={() =>
                document.getElementById("onboarding-folder")?.click()
              }
            >
              {tr("Seleccionar carpeta")}
            </Button>
            {files.length > 0 && (
              <div className="mt-5 flex items-center justify-center gap-2 text-sm">
                <Check className="size-4 shrink-0 text-primary" />
                <span>
                  {fileCount} · {size}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={tr("Quitar archivo")}
                  onClick={() => {
                    choose([]);
                    if (input.current) input.current.value = "";
                  }}
                >
                  <X className="size-4" />
                </Button>
              </div>
            )}
            {total > FOLDER_LIMIT && (
              <Notice error>{tr("La carpeta supera los 2 GB.")}</Notice>
            )}
            {action.busy && total > 0 && (
              <p role="status" className="mt-2 text-xs">
                {uploaded < total
                  ? tr("Subiendo {0} %", {
                      "0": Math.round((uploaded / total) * 100),
                    })
                  : tr("Preparando las tablas…")}
              </p>
            )}
          </div>
          {draft.filename && !files.length && (
            <Notice>
              {tr(
                "Tu contexto está guardado. Vuelve a seleccionar tus archivos; el navegador no conserva los que todavía no se han enviado.",
              )}
            </Notice>
          )}
          <Field
            label={tr("¿Qué te gustaría entender? (opcional)")}
            id="first-report-goal"
            hint={tr(
              "Si no tienes una pregunta concreta, empezaremos con una exploración general.",
            )}
          >
            <Textarea
              id="first-report-goal"
              maxLength={2000}
              className="min-h-24"
              placeholder={tr(
                "Por ejemplo: quiero entender cómo han cambiado mis ventas.",
              )}
              value={draft.goal}
              onChange={(event) =>
                setDraft({ ...draft, goal: event.target.value })
              }
            />
          </Field>
          <p className="text-xs text-muted-foreground">
            {tr("¿Quieres conocer el formato?")}{" "}
            <a
              className="font-medium text-primary underline underline-offset-4"
              href="/api/sample"
              download
            >
              {tr("Descargar un CSV de ejemplo")}
            </a>
            .
          </p>
        </>
      )}
      {review && !files.length && (
        <Notice>
          {tr(
            "Vuelve a «Tus datos» para seleccionar los archivos y continuar. El contexto y el nombre del informe siguen guardados.",
          )}
        </Notice>
      )}
      {ignored > 0 && (
        <Notice>
          {ignored} {ignored === 1 ? "archivo omitido" : "archivos omitidos"}
          {tr(": solo se incluyen CSV y Excel (.xlsx).")}
        </Notice>
      )}
      {review && partial && (
        <Notice>
          <p className="font-medium">
            {tr("Algunos archivos no se pudieron preparar")}
          </p>
          <p className="mt-2">
            {tr(
              "El informe usará únicamente las tablas disponibles. Puedes continuar o volver a tus datos para corregir la entrega.",
            )}
          </p>
          <ul
            className="mt-3 space-y-1"
            aria-label={tr("Resultado de la preparación")}
          >
            {partial.files?.map((file) => (
              <li key={file.id} className="break-all">
                {file.name} ·{" "}
                {file.status === "ready"
                  ? tr("Disponible")
                  : tr("No se incluirá")}
              </li>
            ))}
          </ul>
        </Notice>
      )}
      {review && action.busy && (
        <p role="status" className="text-sm text-muted-foreground">
          {uploaded < total
            ? tr("Subiendo tus datos… {0} %", {
                "0": Math.round((uploaded / total) * 100),
              })
            : tr("Preparando tus datos y el primer informe…")}
        </p>
      )}
      <Notice error>{action.error}</Notice>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-6">
        {review ? (
          <Button
            type="button"
            variant="ghost"
            disabled={action.busy}
            onClick={() => onReview(false)}
          >
            <ArrowLeft />
            {tr("Tus datos")}
          </Button>
        ) : (
          <Button asChild variant="ghost">
            <a href={`#onboarding/${business.id}/business`}>
              <ArrowLeft />
              {tr("Tu negocio")}
            </a>
          </Button>
        )}
        <Button
          type="submit"
          disabled={!files.length || total > FOLDER_LIMIT || action.busy}
          className="rounded-full px-6"
        >
          {action.busy ? <Busy /> : review ? <FileText /> : null}
          {review
            ? partial
              ? tr("Continuar con las tablas disponibles")
              : tr("Crear mi primer informe")
            : tr("Continuar")}
          {!review && <ArrowRight />}
        </Button>
      </div>
    </form>
  );
}
