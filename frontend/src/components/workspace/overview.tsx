import { useState } from "react";
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
import { Input } from "@/components/ui/input";
import { useWorkspace } from "@/lib/workspace";
import { useResource } from "@/lib/hooks";
import { date } from "@/lib/api";
import type { Report } from "@/lib/types";
import { Heading, Notice, Empty, Loading } from "./shared";
import { ReportView } from "./report";
import { ChatActions } from "./chat-actions";
import { FloatingAssistant } from "./floating-assistant";
import { Selectable } from "./context-selection";
import { useAssistant } from "@/lib/assistant";
export function StartChat() {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <h1 className="sr-only">Nueva conversación</h1>
      <div className="flex-1" />
      <div className="shrink-0 px-4 pb-4 pt-2 sm:px-8">
        <div className="mx-auto max-w-2xl">
          <FloatingAssistant inline />
        </div>
      </div>
    </div>
  );
}
export { Reports } from "./reports";
export function Chats() {
  const { listing } = useWorkspace();
  const assistant = useAssistant();
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
          <a href="#ask" onClick={() => assistant?.newConversation("page")}>
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
            <Selectable key={c.id} item={c.context_reference}>
              <Card className="conversation-tile gap-0 border-0 py-0 shadow-none ring-0">
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
            </Selectable>
          ))}
        </div>
      ) : (
        <Empty
          title="Un espacio para pensar con tus datos"
          description="Tus conversaciones se guardan dentro de cada negocio."
          href="#ask"
          onAction={() => assistant?.newConversation("page")}
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
