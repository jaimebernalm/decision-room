import { useCallback, useEffect, useState } from "react";
import { useReducedMotion } from "motion/react";
import {
  Plus,
  ArrowUpRight,
  MoreHorizontal,
  MessageCircle,
} from "lucide-react";
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
import { useResource } from "@/lib/hooks";
import { date, reportState, shortTitle, analysisHref } from "@/lib/api";
import type { Report } from "@/lib/types";
import { Heading, Notice, Empty, Loading } from "./shared";
import { ReportView } from "./report";
import { ChatActions } from "./chat-actions";
import { FloatingAssistant } from "./floating-assistant";
export function StartChat({ home = false }: { home?: boolean }) {
  const reducedMotion = useReducedMotion();
  const [arrived, setArrived] = useState(false);
  const reveal = useCallback(() => setArrived(true), []);
  const showIntro = home || reducedMotion || arrived;
  useEffect(() => {
    if (showIntro) return;
    // Direct visits have no shared-layout animation to signal arrival.
    const timer = setTimeout(reveal, 320);
    return () => clearTimeout(timer);
  }, [showIntro, reveal]);
  const revealStyle = {
    opacity: showIntro ? 1 : 0,
    visibility: showIntro ? ("visible" as const) : ("hidden" as const),
  };
  const { workspace, listing } = useWorkspace(),
    business = workspace.business!;
  return (
    <div
      className={
        home
          ? "mb-10"
          : "mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center py-8 sm:py-12"
      }
    >
      <div
        style={revealStyle}
        className={
          home ? "mb-7" : "mb-8 text-center transition-opacity duration-150"
        }
      >
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
      {!home && (
        <>
          <FloatingAssistant inline onArrive={reveal} />
          {listing.conversations.length > 0 && (
            <section
              aria-label="Conversaciones recientes"
              style={revealStyle}
              className="mt-10 transition-opacity duration-150"
            >
              <div className="mb-3 flex items-center justify-between gap-3">
                <h2 className="text-xs font-medium text-muted-foreground">
                  Conversaciones recientes
                </h2>
                <Button
                  variant="link"
                  size="sm"
                  className="h-auto p-0 text-xs"
                  asChild
                >
                  <a href="#chats">Ver todas</a>
                </Button>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                {listing.conversations.slice(0, 4).map((chat) => (
                  <a
                    key={chat.id}
                    href={`#chat/${chat.id}`}
                    className="conversation-tile flex min-w-0 items-center gap-3 px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <MessageCircle
                      className="size-4 shrink-0 text-muted-foreground"
                      aria-hidden="true"
                    />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">
                        {shortTitle(chat.title)}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {date(chat.last_message_at || chat.created_at)}
                      </p>
                    </div>
                  </a>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
export function Reports() {
  const { workspace } = useWorkspace();
  const [search, setSearch] = useState("");
  const items = workspace.analyses.filter((a) =>
    `${a.title} ${a.filename}`
      .toLocaleLowerCase()
      .includes(search.toLocaleLowerCase()),
  );
  return (
    <>
      <Heading
        title="Informes"
        description="Resultados, contexto y evidencia en un mismo lugar."
      >
        <Button asChild>
          <a href="#new">
            <Plus />
            Crear informe
          </a>
        </Button>
      </Heading>
      <Input
        aria-label="Buscar informes"
        placeholder="Buscar por título o archivo…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-6 max-w-sm"
      />
      {items.length ? (
        <Card className="gap-0 overflow-hidden py-0 shadow-none">
          <Table className="[&_th]:px-4 [&_td]:px-4">
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Informe</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead className="hidden sm:table-cell">Creado</TableHead>
                <TableHead className="hidden sm:table-cell">
                  <span className="sr-only">Abrir</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((a) => (
                <TableRow
                  key={a.id}
                  className="cursor-pointer hover:bg-muted focus-within:bg-muted"
                  onClick={(event) => {
                    if (!(event.target as HTMLElement).closest("a, button"))
                      location.hash = analysisHref(a);
                  }}
                >
                  <TableCell className="whitespace-normal">
                    <a
                      className="break-words font-medium hover:underline"
                      href={analysisHref(a)}
                    >
                      {a.title}
                    </a>
                    <p className="mt-1 break-all text-xs text-muted-foreground">
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
                          queued: "En preparación",
                          waiting: "Necesita tu respuesta",
                          running: "En preparación",
                          failed: "Interrumpido",
                          blocked: "Necesita atención",
                        } as Record<string, string>
                      )[reportState(a)] || reportState(a)}
                    </Badge>
                  </TableCell>
                  <TableCell className="hidden text-muted-foreground sm:table-cell">
                    {date(a.created_at)}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    <Button
                      asChild
                      variant="ghost"
                      size="icon"
                      className="hover:bg-transparent"
                    >
                      <a href={analysisHref(a)} aria-label={`Abrir ${a.title}`}>
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
          description="Empieza con una pregunta o crea un informe de tus datos."
          href="#new"
          label="Crear informe"
        />
      )}
    </>
  );
}
export function Chats() {
  const { listing } = useWorkspace();
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
        <div className="grid gap-2">
          {chats.map((c) => (
            <Card
              key={c.id}
              className="conversation-tile gap-0 border-0 py-0 shadow-none ring-0"
            >
              <CardContent className="flex items-center gap-3 px-4 py-3">
                <MessageCircle className="size-4 shrink-0 text-muted-foreground" />
                <a
                  className="min-w-0 flex-1 after:absolute after:inset-0 after:rounded-2xl focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-inset focus-visible:after:ring-ring"
                  href={`#chat/${c.id}`}
                >
                  <p className="truncate text-sm font-medium">{c.title}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {date(c.last_message_at || c.created_at)}
                  </p>
                </a>
                <ChatActions chat={c}>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="relative z-10 rounded-full text-muted-foreground hover:bg-transparent hover:text-foreground"
                    aria-label={`Opciones de ${c.title}`}
                  >
                    <MoreHorizontal />
                  </Button>
                </ChatActions>
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
  exportUrl,
}: {
  path: string;
  exportUrl: string;
}) {
  const { data, error } = useResource<Report>(path, 5000);
  return (
    <>
      <Heading title="Informe del negocio">
        <div className="flex gap-2">
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
