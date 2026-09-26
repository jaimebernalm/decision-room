import { useState } from "react";
import { Plus, ArrowUpRight, FileText, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useWorkspace } from "@/lib/workspace";
import { useResource, useDraft, useAction } from "@/lib/hooks";
import {
  contextKey,
  homeDraftKey,
  store,
  launchChat,
  date,
  reportState,
} from "@/lib/api";
import type { Dashboard, QuestionContext, Claim, Report } from "@/lib/types";
import { Heading, Notice, Empty, Loading, ChoiceSelect } from "./shared";
import { Composer } from "./composer";
import { ReportView } from "./report";
export function StartChat({ home = false }: { home?: boolean }) {
  const { workspace, listing, refresh } = useWorkspace(),
    business = workspace.business!;
  const [text, setText] = useDraft(homeDraftKey(business.id), "");
  const [context, setContext] = useDraft<QuestionContext>(
    contextKey(business.id),
    {},
  );
  const datasetOptions = [
    ...new Map(
      listing.datasets.items.map((d) => [
        d.analysis_id,
        {
          value: d.analysis_id,
          label: `${d.description} · v${d.dataset_version}`,
        },
      ]),
    ).values(),
  ];
  if (
    context.analysis_id &&
    !datasetOptions.some((d) => d.value === context.analysis_id)
  )
    datasetOptions.push({
      value: context.analysis_id,
      label: context.label || "Versión seleccionada",
    });
  const action = useAction();
  const send = () =>
    action.run(async () => {
      const chat = await launchChat(business.id, text, context);
      if (action.isMounted()) {
        refresh();
        location.hash = `chat/${chat.id}`;
      }
    });
  return (
    <div
      className={
        home
          ? "mb-10"
          : "mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center py-12"
      }
    >
      <div className="mb-7">
        <p className="mb-3 text-xs font-medium text-muted-foreground">
          {business.name}
        </p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          {home
            ? "Una mirada clara a tu negocio."
            : "¿Qué quieres entender hoy?"}
        </h1>
        <p className="mt-3 text-sm text-muted-foreground">
          {home
            ? "Tus datos, tus conversaciones y las decisiones que vienen."
            : "Pregunta, añade contexto o explora tus datos con la IA."}
        </p>
      </div>
      {(listing.datasets?.items.length > 0 || context.label) && (
        <div className="mb-4 max-w-md">
          <ChoiceSelect
            label="Datos para esta conversación"
            value={context.analysis_id || "auto"}
            onChange={(value) =>
              setContext(
                value === "auto"
                  ? {}
                  : {
                      analysis_id: value,
                      label: datasetOptions.find((d) => d.value === value)
                        ?.label,
                    },
              )
            }
            options={[
              { value: "auto", label: "Elegir según la pregunta" },
              ...datasetOptions,
            ]}
          />
          {context.finding_reference && (
            <div className="mt-2 flex items-center gap-2">
              <Badge variant="secondary">
                {context.label || "Hallazgo seleccionado"}
              </Badge>
              <Button size="sm" variant="ghost" onClick={() => setContext({})}>
                Quitar contexto
              </Button>
            </div>
          )}
        </div>
      )}
      <Composer
        text={text}
        onChange={setText}
        onSend={send}
        busy={action.busy}
        error={action.error}
        suggestions={!home}
      />
    </div>
  );
}
export function Home() {
  const { workspace } = useWorkspace();
  const [selected, setSelected] = useState("latest");
  const resource = useResource<Dashboard>(
    `/api/dashboard${selected === "latest" ? "" : `?report=${encodeURIComponent(selected)}`}`,
    5000,
  );
  const ask = (claim: Claim) => {
    const data = resource.data!;
    store.set(contextKey(workspace.business!.id), {
      analysis_id: data.analysis_id,
      finding_reference: {
        report_id: data.report_id,
        report_version: data.report_version,
        claim_key: claim.key,
        title: claim.title,
        period: data.report!.scope.period,
      },
      label: claim.title,
    });
    location.hash = "ask";
  };
  return (
    <>
      <StartChat home />
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium text-muted-foreground">
            PERSPECTIVA DEL NEGOCIO
          </p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight">
            Tu último informe
          </h2>
        </div>
        <Button asChild variant="outline" size="sm">
          <a href="#new">
            <Plus />
            Nuevo análisis
          </a>
        </Button>
      </div>
      <Notice error>{resource.error}</Notice>
      {!resource.data && !resource.error ? (
        <Loading />
      ) : resource.data?.report ? (
        <>
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div className="w-full max-w-sm">
              <ChoiceSelect
                label="Informe"
                value={selected}
                onChange={setSelected}
                options={[
                  { value: "latest", label: "Último disponible" },
                  ...resource.data.reports.map((r) => ({
                    value: r.id,
                    label: `${r.title} · ${date(r.created_at)}`,
                  })),
                ]}
              />
            </div>
            <Button asChild variant="ghost">
              <a href={`#report/${resource.data.selected_id}`}>
                Abrir informe completo
                <ArrowUpRight />
              </a>
            </Button>
          </div>
          <ReportView report={resource.data.report} onAsk={ask} />
        </>
      ) : (
        <Empty
          title="El primer hallazgo empieza con tus datos"
          description="Sube un CSV y prepara un análisis. Aquí aparecerán los resultados que hayan superado la revisión."
          href="#new"
          label="Preparar un análisis"
        />
      )}
      {resource.data?.activity.length ? (
        <section className="mt-10">
          <h2 className="mb-4 text-base font-semibold">Necesita tu atención</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {resource.data.activity.map((a, i) => (
              <a
                key={i}
                href={a.href}
                className="flex items-center justify-between gap-3 rounded-xl border p-4 hover:bg-muted/50"
              >
                <span className="text-sm">{a.title}</span>
                <ArrowUpRight className="size-4 shrink-0" />
              </a>
            ))}
          </div>
        </section>
      ) : null}
    </>
  );
}
export function AnalysisList({ reports = false }: { reports?: boolean }) {
  const { workspace } = useWorkspace();
  const [search, setSearch] = useState("");
  const items = workspace.analyses.filter(
    (a) =>
      (!reports ||
        ["completed", "historical", "outdated", "withdrawn"].includes(
          reportState(a),
        )) &&
      `${a.title} ${a.filename}`
        .toLocaleLowerCase()
        .includes(search.toLocaleLowerCase()),
  );
  return (
    <>
      <Heading
        title={reports ? "Informes" : "Todos los análisis"}
        description="Resultados, contexto y evidencia en un mismo lugar."
      >
        <Button asChild>
          <a href="#new">
            <Plus />
            Nuevo análisis
          </a>
        </Button>
      </Heading>
      <Input
        aria-label="Buscar análisis"
        placeholder="Buscar por título o archivo…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-6 max-w-sm"
      />
      {items.length ? (
        <Card className="shadow-none">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Análisis</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead className="hidden sm:table-cell">Creado</TableHead>
                <TableHead>
                  <span className="sr-only">Abrir</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((a) => (
                <TableRow key={a.id}>
                  <TableCell>
                    <a
                      className="font-medium hover:underline"
                      href={`#analysis/${a.id}`}
                    >
                      {a.title}
                    </a>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {a.filename}
                    </p>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">
                      {(
                        {
                          completed: "Disponible",
                          historical: "Versión anterior",
                          outdated: "Contexto cambiado",
                          withdrawn: "Retirado",
                          queued: "En cola",
                          waiting: "Necesita respuesta",
                          running: "En curso",
                          failed: "Interrumpido",
                          blocked: "Necesita atención",
                        } as Record<string, string>
                      )[reportState(a)] || reportState(a)}
                    </Badge>
                  </TableCell>
                  <TableCell className="hidden text-muted-foreground sm:table-cell">
                    {date(a.created_at)}
                  </TableCell>
                  <TableCell>
                    <Button asChild variant="ghost" size="icon">
                      <a
                        href={`#analysis/${a.id}`}
                        aria-label={`Abrir ${a.title}`}
                      >
                        <ArrowUpRight />
                      </a>
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      ) : (
        <Empty
          title="Todavía no hay resultados"
          description="Empieza con una pregunta o prepara un análisis de tus datos."
          href="#new"
          label="Nuevo análisis"
        />
      )}
    </>
  );
}
export function Chats() {
  const { listing, removeChat } = useWorkspace();
  const [search, setSearch] = useState("");
  const chats = listing.conversations.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <Heading
        title="Conversaciones"
        description="Retoma una pregunta o empieza a explorar algo nuevo."
      >
        <Button asChild>
          <a href="#ask">
            <Plus />
            Nuevo chat
          </a>
        </Button>
      </Heading>
      <Input
        aria-label="Buscar conversación"
        placeholder="Buscar conversación…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-6 max-w-sm"
      />
      {chats.length ? (
        <div className="grid gap-3">
          {chats.map((c) => (
            <Card key={c.id} className="shadow-none">
              <CardContent className="flex items-center gap-4 py-4">
                <FileText className="size-4 text-muted-foreground" />
                <a className="min-w-0 flex-1" href={`#chat/${c.id}`}>
                  <p className="truncate text-sm font-medium">{c.title}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {date(c.last_message_at || c.created_at)}
                  </p>
                </a>
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label={`Eliminar ${c.title}`}
                  onClick={() => removeChat(c)}
                >
                  <Trash2 />
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Empty
          title="Un espacio para pensar con tus datos"
          description="Tus conversaciones se guardan dentro de cada negocio."
          href="#ask"
        />
      )}
    </>
  );
}
export function Presentation({
  path,
  back,
  exportUrl,
}: {
  path: string;
  back: string;
  exportUrl: string;
}) {
  const { data, error } = useResource<Report>(path, 5000);
  return (
    <>
      <Heading title="Informe del negocio">
        <div className="flex gap-2">
          <Button asChild variant="ghost">
            <a href={back}>Volver</a>
          </Button>
          <Button asChild variant="outline">
            <a href={exportUrl} target="_blank" rel="noreferrer">
              Vista para imprimir
              <ArrowUpRight />
            </a>
          </Button>
        </div>
      </Heading>
      <Notice error>{error}</Notice>
      {error ? null : data ? <ReportView report={data} /> : <Loading />}
    </>
  );
}
export function How() {
  return (
    <>
      <Heading
        title="De tus datos a una decisión"
        description="Un espacio privado para entender tu negocio, con resultados que puedes comprobar."
      />
      <div className="grid gap-4 md:grid-cols-3">
        {[
          [
            "01",
            "Presenta tu negocio",
            "Cuenta qué haces, cuáles son tus prioridades y qué debería tener en cuenta el análisis.",
          ],
          [
            "02",
            "Añade tus datos",
            "Sube un CSV UTF-8 de hasta 20 MB. Puedes mantener versiones y corregir archivos anteriores.",
          ],
          [
            "03",
            "Pregunta y revisa",
            "El asistente pide aclaraciones cuando las necesita. Los informes se publican después de comprobar su evidencia.",
          ],
        ].map(([n, t, d]) => (
          <Card key={n} className="shadow-none">
            <CardHeader>
              <p className="mb-4 text-xs text-muted-foreground">{n}</p>
              <CardTitle>{t}</CardTitle>
              <CardDescription className="leading-6">{d}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
      <Notice>
        Los datos permanecen en este espacio local. Las respuestas pueden
        contener errores: revisa el alcance, las fuentes y las limitaciones
        antes de tomar decisiones.
      </Notice>
      <Button asChild className="mt-4">
        <a href="#ask">
          Empezar una conversación
          <ArrowUpRight />
        </a>
      </Button>
    </>
  );
}
