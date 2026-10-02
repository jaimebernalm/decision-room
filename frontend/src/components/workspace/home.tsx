import { displayNumber } from "@/lib/presentation";
import { translate as tr, useLanguage } from "@/lib/i18n";
import { useState } from "react";
import {
  ArrowUpRight,
  ChevronDown,
  EyeOff,
  Pin,
  PinOff,
  SlidersHorizontal,
  Sparkles,
  LoaderCircle,
  MoreHorizontal,
  Pencil,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { useWorkspace } from "@/lib/workspace";
import { useResource, useAction } from "@/lib/hooks";
import { api, date } from "@/lib/api";
import type { HomeDashboard, HomeItem } from "@/lib/types";
import { Heading, Notice, Empty, Loading, Disclosure, Status } from "./shared";
import { Selectable } from "./context-selection";
import type { ContextAttachment } from "@/lib/types";
import { EvidenceChart, DecisionGuidance } from "./report";
import { PresentationEditor } from "./presentation-editor";
import { findingHref, relatedFinding } from "@/lib/report-navigation";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";

const selection = (item: HomeItem): ContextAttachment => ({
  report_id: item.source.report_id,
  report_version: item.source.version,
  kind: item.kind,
  element_key: item.content.key || item.id.split(":").at(-1)!,
  title: item.title,
  period: item.source.period,
  report_title: item.source.title,
  href: item.source.href,
  content: item.content,
});
const labels = {
  metric: "Indicadores",
  chart: "Gráficos",
  insight: "Hallazgos",
};
const limits = { metric: 10, chart: 2, insight: 3 };
function Source({ item, reason }: { item: HomeItem; reason?: string }) {
  useLanguage();
  return (
    <div className="mt-5 text-xs text-muted-foreground">
      <p className="mb-2 leading-relaxed">
        <span>{item.source.period}</span> ·{" "}
        {tr("Revisión {0}", { "0": item.source.version })}
      </p>
      <Collapsible>
        <CollapsibleTrigger className="group inline-flex items-center gap-1 rounded-sm py-1 text-xs hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          {tr("Periodo y fuente")}{" "}
          <ChevronDown className="size-3 transition-transform group-data-[state=open]:rotate-180" />
        </CollapsibleTrigger>
        <CollapsibleContent className="space-y-3 pt-3 text-sm leading-relaxed">
          {item.kind !== "insight" && item.content.unit_origin === "owner" && (
            <p>
              {tr("Unidad visible indicada por ti. Unidad del análisis:")}{" "}
              {item.content.original_unit}.
            </p>
          )}
          <p>{item.source.coverage}</p>
          <p>
            {item.source.filename}
            {item.source.data_version
              ? tr(" · Versión {0}", { "0": item.source.data_version.version })
              : ""}
          </p>
          {item.source.limitations.map((text, index) => (
            <p key={index}>{text}</p>
          ))}
          {reason && (
            <p>
              <span className="font-medium">
                {tr("Motivo de la selección: ")}
              </span>
              {reason}
            </p>
          )}
          <a
            className="inline-flex items-center gap-1 font-medium text-primary underline underline-offset-4"
            href={item.source.href}
          >
            {tr("Ver fuente ")}
            <ArrowUpRight className="size-3" />
          </a>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}
export function Home() {
  useLanguage();
  const { workspace } = useWorkspace();
  const resource = useResource<HomeDashboard>("/api/home", 15000);
  const action = useAction();
  const [editor, setEditor] = useState<{
    base: HomeDashboard;
    selected: string[];
  } | null>(null);
  const [preview, setPreview] = useState<HomeDashboard | null>(null);
  const data = resource.data;
  const openEditor = () => {
    if (!data) return;
    action.setError("");
    setEditor({ base: data, selected: [...data.selected] });
  };
  const save = (base: HomeDashboard, changes: object, close?: () => void) =>
    action.run(async () => {
      await api<HomeDashboard>("/api/home/preferences", {
        business_id: base.business_id,
        revision: base.revision,
        fingerprint: base.fingerprint,
        selected: base.selected,
        pinned: base.pinned,
        ...changes,
      });
      if (action.isMounted()) {
        close?.();
        resource.refresh();
      }
    });
  const suggest = () =>
    action.run(async () => {
      const result = await api<HomeDashboard>("/api/home/suggest", {
        business_id: workspace.business!.id,
      });
      if (action.isMounted()) {
        setPreview(result);
        resource.refresh();
      }
    });
  const controls = (item: HomeItem) => {
    const pinned = data!.pinned.includes(item.id);
    return (
      <PresentationEditor
        presentation={item.source.presentation}
        target={{
          kind: item.kind,
          key: item.content.key!,
          title: item.title,
        }}
        renderTrigger={(openEditor, editorOpen) => (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="icon"
                variant="ghost"
                className="size-8 shrink-0 text-muted-foreground"
                aria-label={tr("Opciones de {0}", { "0": item.title })}
                title={tr("Opciones de la tarjeta")}
              >
                <MoreHorizontal />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="min-w-48"
              onCloseAutoFocus={(event) => {
                if (editorOpen) event.preventDefault();
              }}
            >
              <DropdownMenuItem
                disabled={!item.source.presentation}
                onSelect={openEditor}
              >
                <Pencil />
                {tr(" Editar presentación")}
              </DropdownMenuItem>
              <DropdownMenuItem
                disabled={action.busy}
                onSelect={() =>
                  void save(data!, {
                    pinned: pinned
                      ? data!.pinned.filter((id) => id !== item.id)
                      : [...data!.pinned, item.id],
                  })
                }
              >
                {pinned ? <PinOff /> : <Pin />}{" "}
                {pinned ? tr("Desfijar tarjeta") : tr("Fijar tarjeta")}
              </DropdownMenuItem>
              {!pinned && (
                <DropdownMenuItem
                  disabled={action.busy}
                  onSelect={() =>
                    void save(data!, {
                      selected: data!.selected.filter((id) => id !== item.id),
                    })
                  }
                >
                  <EyeOff />
                  {tr(" Ocultar tarjeta")}
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      />
    );
  };
  const selected =
    data?.selected.flatMap((id) =>
      data.items.filter((item) => item.id === id),
    ) ?? [];
  return (
    <>
      <Heading
        eyebrow={workspace.business?.name}
        title={tr("Tu negocio, de un vistazo")}
        description={tr(
          "Indicadores y señales de tus datos revisados. Cada tarjeta muestra el periodo al que pertenece.",
        )}
      >
        {data && data.items.length > 0 && (
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={action.busy}
              onClick={openEditor}
            >
              <SlidersHorizontal />
              {tr("Personalizar")}
            </Button>
            <Button
              size="sm"
              disabled={action.busy || !data.can_suggest}
              onClick={() => {
                action.setError("");
                if (data.proposal) setPreview(data);
                else void suggest();
              }}
            >
              {action.busy ? (
                <LoaderCircle className="animate-spin" />
              ) : (
                <Sparkles />
              )}
              {data.proposal
                ? tr("Revisar propuesta")
                : tr("Proponer selección")}
            </Button>
          </div>
        )}
      </Heading>
      <Notice error>
        {resource.error || (!editor && !preview ? action.error : "")}
      </Notice>
      {action.busy && !editor && !preview && (
        <p role="status" className="mb-4 text-sm text-muted-foreground">
          {tr("Preparando los cambios…")}
        </p>
      )}
      {!data && !resource.error && <Loading />}
      {data && (
        <>
          {data.unavailable > 0 && (
            <Notice>
              {tr("Se han retirado ")}
              {data.unavailable}
              {tr(
                " tarjetas porque su evidencia ya no está disponible o necesita revisión. Puedes elegir otras en Personalizar.",
              )}
            </Notice>
          )}
          {selected.length > 0 ? (
            <>
              <p className="mb-5 text-xs text-muted-foreground">
                {data.selection_origin === "agent"
                  ? tr("Selección propuesta por el agente y aceptada por ti")
                  : data.selection_origin === "owner"
                    ? tr("Tu selección de indicadores y hallazgos")
                    : tr("Selección inicial de resultados revisados")}
              </p>
              <section
                aria-label={tr("Indicadores")}
                className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
              >
                {selected
                  .filter((item) => item.kind === "metric")
                  .map((item) => (
                    <Selectable key={item.id} item={selection(item)}>
                      <Card className="min-w-0 gap-3 rounded-2xl bg-muted/45 shadow-none ring-0">
                        <CardHeader>
                          <div className="flex items-start justify-between gap-2">
                            <CardTitle className="text-sm leading-relaxed text-muted-foreground">
                              {item.title}
                            </CardTitle>
                            {controls(item)}
                          </div>
                        </CardHeader>
                        <CardContent>
                          <p className="break-words text-3xl font-semibold tracking-tight tabular-nums">
                            {displayNumber(item.content.value)}{" "}
                            <span className="mt-1 block text-xs font-normal tracking-normal text-muted-foreground">
                              {item.content.unit}
                            </span>
                          </p>
                          <Source item={item} reason={data.reasons[item.id]} />
                        </CardContent>
                      </Card>
                    </Selectable>
                  ))}
              </section>
              {selected.some((item) => item.kind === "chart") && (
                <section
                  aria-label={tr("Evolución y distribución")}
                  className="mt-8 grid items-start gap-5 xl:grid-cols-2"
                >
                  {selected
                    .filter((item) => item.kind === "chart")
                    .map((item) => (
                      <Selectable key={item.id} item={selection(item)}>
                        <EvidenceChart
                          chart={item.content}
                          sourceHref={item.source.href}
                          actions={controls(item)}
                          lead={(() => {
                            const finding = relatedFinding(data.items, item);
                            return finding ? (
                              <p className="mb-4 text-sm leading-6">
                                {finding.content.statement}
                              </p>
                            ) : null;
                          })()}
                          footer={
                            <>
                              <a
                                href={findingHref(item)}
                                className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary underline underline-offset-4"
                              >
                                {tr("Ver hallazgo en el informe")}
                                <ArrowUpRight className="size-4" />
                              </a>
                              <Source
                                item={item}
                                reason={data.reasons[item.id]}
                              />
                            </>
                          }
                        />
                      </Selectable>
                    ))}
                </section>
              )}
              {selected.some((item) => item.kind === "insight") && (
                <section className="mt-8">
                  <h2 className="mb-4 text-base font-semibold">
                    {tr("Lo que destaca")}
                  </h2>
                  <div className="grid gap-4 lg:grid-cols-2">
                    {selected
                      .filter((item) => item.kind === "insight")
                      .map((item) => (
                        <Selectable key={item.id} item={selection(item)}>
                          <Card className="min-w-0 shadow-none">
                            <CardHeader>
                              <div className="flex items-start justify-between gap-3">
                                <CardTitle className="leading-relaxed">
                                  {item.title}
                                </CardTitle>
                                {controls(item)}
                              </div>
                            </CardHeader>
                            <CardContent>
                              {!selected.some(
                                (chart) =>
                                  chart.kind === "chart" &&
                                  relatedFinding(data.items, chart)?.id ===
                                    item.id,
                              ) && (
                                <p className="text-sm leading-relaxed">
                                  {item.content.statement}
                                </p>
                              )}
                              <div className="mt-3">
                                <DecisionGuidance claim={item.content} />
                              </div>
                              <a
                                href={findingHref(item)}
                                className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary underline underline-offset-4"
                              >
                                {tr("Ver hallazgo en el informe")}
                                <ArrowUpRight className="size-4" />
                              </a>
                              <Source
                                item={item}
                                reason={data.reasons[item.id]}
                              />
                            </CardContent>
                          </Card>
                        </Selectable>
                      ))}
                  </div>
                </section>
              )}
            </>
          ) : (
            <Empty
              title={
                data.items.length
                  ? tr("Elige qué quieres tener a la vista")
                  : tr("Tu dashboard empieza con tus datos")
              }
              description={
                data.items.length
                  ? tr(
                      "Personaliza la selección o pide una propuesta al agente. Los elementos que ocultas no vuelven a aparecer en sus propuestas.",
                    )
                  : tr(
                      "Cuando haya resultados revisados, aquí aparecerán indicadores y gráficos con su periodo y fuente.",
                    )
              }
              {...(!data.items.length
                ? { href: "#new", label: tr("Crear informe") }
                : {
                    iconAction: {
                      label: tr("Añadir tarjetas al dashboard"),
                      onClick: openEditor,
                      disabled: action.busy,
                    },
                  })}
            />
          )}
          {data.activity.length > 0 && (
            <section className="mt-8">
              <h2 className="mb-4 text-base font-semibold">
                {tr("Actividad y pendientes")}
              </h2>
              <div className="grid gap-3 sm:grid-cols-2">
                {data.activity.map((item, index) => (
                  <a
                    key={index}
                    href={item.href}
                    className="conversation-tile flex items-center justify-between gap-3 p-4 text-sm"
                  >
                    <span className="min-w-0 break-words">{item.title}</span>
                    <Status status={item.status} />
                  </a>
                ))}
              </div>
            </section>
          )}
          <section className="mt-8 rounded-2xl bg-muted/40 p-5">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold">
                {tr("Datos disponibles")}
              </h2>
              <Button asChild variant="link" size="sm">
                <a href="#my-business">
                  {tr("Mi negocio ")}
                  <ArrowUpRight />
                </a>
              </Button>
            </div>
            <p className="text-sm text-muted-foreground">
              {data.sources.length
                ? tr(
                    "{0} {1} para este dashboard. Los periodos pueden ser distintos; no se suman entre sí.",
                    {
                      "0": data.sources.length,
                      "1":
                        data.sources.length === 1
                          ? tr("fuente revisada disponible")
                          : tr("fuentes revisadas disponibles"),
                    },
                  )
                : tr("Todavía no hay resultados revisados disponibles.")}
            </p>
            {data.sources.length > 0 && (
              <div className="mt-4">
                <Disclosure title={tr("Ver cobertura y actualizaciones")}>
                  {data.sources.map((source) => (
                    <div key={source.job_id} className="space-y-1 py-2">
                      <a
                        href={source.href}
                        className="font-medium text-primary hover:underline"
                      >
                        {source.filename}
                      </a>
                      <p>
                        {source.period} · {source.coverage}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {tr("Informe creado ")}
                        {date(source.created_at)}
                        {source.data_version
                          ? tr(" · Datos v{0}", {
                              "0": source.data_version.version,
                            })
                          : ""}
                      </p>
                    </div>
                  ))}
                </Disclosure>
              </div>
            )}
            {data.limited && (
              <p className="mt-3 text-xs text-muted-foreground">
                {tr(
                  "Se consideran las 20 fuentes revisadas más recientes y las fuentes de las tarjetas fijadas.",
                )}
              </p>
            )}
            <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
              {tr(
                "Las tarjetas fijadas conservan su fuente. Para incorporar nuevos periodos, revisa la selección. Las cifras nunca se calculan a partir de una propuesta del agente.",
              )}
            </p>
          </section>
        </>
      )}
      <Dialog
        open={!!editor}
        onOpenChange={(open) => {
          if (!open && !action.busy) setEditor(null);
        }}
      >
        <DialogContent className="flex max-h-[85dvh] flex-col sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{tr("Personaliza tu inicio")}</DialogTitle>
            <DialogDescription>
              {tr(
                "Hasta 10 indicadores, 2 gráficos y 3 hallazgos. Desfija una tarjeta antes de ocultarla.",
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 space-y-6 overflow-y-auto pr-2">
            {editor &&
              (Object.keys(labels) as HomeItem["kind"][]).map((kind) => (
                <section key={kind}>
                  <h3 className="mb-3 text-sm font-medium">
                    {tr(labels[kind])} ·{" "}
                    {
                      editor.selected.filter((id) =>
                        editor.base.items.some(
                          (item) => item.id === id && item.kind === kind,
                        ),
                      ).length
                    }
                    /{limits[kind]}
                  </h3>
                  <div className="space-y-2">
                    {editor.base.items
                      .filter((item) => item.kind === kind)
                      .map((item) => (
                        <label
                          key={item.id}
                          className="flex cursor-pointer items-start gap-3 rounded-xl bg-muted/50 p-3 text-sm"
                        >
                          <Checkbox
                            className="mt-0.5"
                            checked={editor.selected.includes(item.id)}
                            disabled={
                              action.busy ||
                              editor.base.pinned.includes(item.id)
                            }
                            onCheckedChange={(checked) =>
                              setEditor({
                                ...editor,
                                selected: checked
                                  ? [...editor.selected, item.id]
                                  : editor.selected.filter(
                                      (id) => id !== item.id,
                                    ),
                              })
                            }
                          />
                          <span className="min-w-0">
                            <span className="font-medium">
                              {item.title}
                              {editor.base.pinned.includes(item.id)
                                ? tr(" · Fijado")
                                : ""}
                            </span>
                            <span className="mt-1 block text-xs text-muted-foreground">
                              {item.source.period} · {item.source.filename}
                            </span>
                          </span>
                        </label>
                      ))}
                  </div>
                </section>
              ))}
          </div>
          <Notice error>{action.error}</Notice>
          <DialogFooter>
            <Button
              variant="outline"
              disabled={action.busy}
              onClick={() => setEditor(null)}
            >
              {tr("Cancelar")}
            </Button>
            <Button
              disabled={action.busy}
              onClick={() =>
                editor &&
                void save(editor.base, { selected: editor.selected }, () =>
                  setEditor(null),
                )
              }
            >
              {tr("Guardar selección")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!preview}
        onOpenChange={(open) => {
          if (!open && !action.busy) setPreview(null);
        }}
      >
        <DialogContent className="flex max-h-[85dvh] flex-col sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{tr("Propuesta para tu dashboard")}</DialogTitle>
            <DialogDescription>
              {tr(
                "El agente selecciona entre resultados revisados según el contexto de tu negocio. Comprueba los periodos antes de aplicarla.",
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 space-y-3 overflow-y-auto pr-2">
            {preview?.proposal?.picks.map((pick) => {
              const item = preview.items.find((item) => item.id === pick.id);
              return item ? (
                <div
                  key={pick.id}
                  className="rounded-xl bg-muted/50 p-4 text-sm"
                >
                  <p className="font-medium">{item.title}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {item.source.period}
                  </p>
                  <p className="mt-2 leading-relaxed">{pick.reason}</p>
                </div>
              ) : null;
            })}
            {preview?.proposal?.picks.length === 0 && (
              <p className="text-sm">
                {tr(
                  "El agente no ha encontrado elementos que recomendar. Aplicar esta propuesta dejará vacía la selección.",
                )}
              </p>
            )}
          </div>
          <Notice error>{action.error}</Notice>
          <DialogFooter>
            <Button
              variant="outline"
              disabled={action.busy}
              onClick={() => setPreview(null)}
            >
              {tr("Ahora no")}
            </Button>
            <Button
              disabled={action.busy}
              onClick={() =>
                preview &&
                void save(preview, { apply_proposal: true }, () =>
                  setPreview(null),
                )
              }
            >
              {tr("Aplicar propuesta")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
