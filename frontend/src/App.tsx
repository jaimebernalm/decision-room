import { useEffect, useState, lazy, Suspense } from "react";
import { ThemeProvider } from "next-themes";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
} from "@/components/ui/alert-dialog";
import { api, ApiError } from "@/lib/api";
import type { Workspace, ChatListing, Chat } from "@/lib/types";
import { WorkspaceState } from "@/lib/workspace";
import { useAction } from "@/lib/hooks";
import { FloatingAssistant } from "@/components/workspace/floating-assistant";
import { Layout } from "@/components/workspace/layout";
import {
  Heading,
  Notice,
  Loading,
  Field,
  Busy,
} from "@/components/workspace/shared";
const Home = lazy(() =>
  import("@/components/workspace/overview").then((m) => ({ default: m.Home })),
);
const StartChat = lazy(() =>
  import("@/components/workspace/overview").then((m) => ({
    default: m.StartChat,
  })),
);
const Chats = lazy(() =>
  import("@/components/workspace/overview").then((m) => ({ default: m.Chats })),
);
const AnalysisList = lazy(() =>
  import("@/components/workspace/overview").then((m) => ({
    default: m.AnalysisList,
  })),
);
const Presentation = lazy(() =>
  import("@/components/workspace/overview").then((m) => ({
    default: m.Presentation,
  })),
);
const How = lazy(() =>
  import("@/components/workspace/overview").then((m) => ({ default: m.How })),
);
const ChatPage = lazy(() =>
  import("@/components/workspace/chat").then((m) => ({ default: m.ChatPage })),
);
const BusinessForm = lazy(() =>
  import("@/components/workspace/business").then((m) => ({
    default: m.BusinessForm,
  })),
);
const BusinessPicker = lazy(() =>
  import("@/components/workspace/business").then((m) => ({
    default: m.BusinessPicker,
  })),
);
const NewAnalysis = lazy(() =>
  import("@/components/workspace/business").then((m) => ({
    default: m.NewAnalysis,
  })),
);
const Dossier = lazy(() =>
  import("@/components/workspace/dossier").then((m) => ({
    default: m.Dossier,
  })),
);
const JobPage = lazy(() =>
  import("@/components/workspace/job").then((m) => ({ default: m.JobPage })),
);
const routeNow = () => location.hash.slice(1) || "home";
let loginPromise: Promise<unknown> | undefined;
function exchangeAccess() {
  if (location.hash.startsWith("#access=")) {
    const token = decodeURIComponent(location.hash.slice(8));
    history.replaceState(null, "", location.pathname + "#home");
    loginPromise = api("/api/login", { token });
  }
  return loginPromise || Promise.resolve();
}
function App() {
  const [route, setRoute] = useState(() =>
      routeNow().startsWith("access=") ? "home" : routeNow(),
    ),
    [workspace, setWorkspace] = useState<Workspace | null>(null),
    [listing, setListing] = useState<ChatListing>({
      business_id: null,
      conversations: [],
      datasets: { items: [], more: false },
    }),
    [error, setError] = useState(""),
    [login, setLogin] = useState(false),
    [revision, setRevision] = useState(0),
    [deleting, setDeleting] = useState<Chat | null>(null);
  const deletion = useAction(),
    refresh = () => setRevision((v) => v + 1);
  useEffect(() => {
    const change = () => setRoute(routeNow());
    addEventListener("hashchange", change);
    return () => removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function read() {
      try {
        await exchangeAccess();
        const ws = await api<Workspace>(
          "/api/workspace",
          undefined,
          controller.signal,
        );
        const chats = ws.business
          ? await api<ChatListing>("/api/chats", undefined, controller.signal)
          : {
              business_id: null,
              conversations: [],
              datasets: { items: [], more: false },
            };
        if (controller.signal.aborted) return;
        if (chats.business_id !== (ws.business?.id || null))
          throw new Error(
            "El negocio activo ha cambiado. Actualizando el espacio…",
          );
        setWorkspace(ws);
        setListing(chats);
        setError("");
        setLogin(false);
      } catch (e) {
        if (!controller.signal.aborted) {
          setError((e as Error).message);
          if (e instanceof ApiError && e.status === 401) {
            setLogin(true);
            setWorkspace(null);
            loginPromise = undefined;
          }
        }
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(read, 5000);
      }
    }
    void read();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [revision]);
  let body;
  if (login)
    body = (
      <Login
        onDone={() => {
          loginPromise = undefined;
          refresh();
        }}
      />
    );
  else if (!workspace)
    body = (
      <div className="mx-auto max-w-3xl p-8">
        <Notice error>{error}</Notice>
        {!error ? <Loading /> : <Button onClick={refresh}>Reintentar</Button>}
      </div>
    );
  else {
    const activeRoute =
      !workspace.business &&
      !["business-new", "businesses", "how"].includes(route)
        ? workspace.businesses.length
          ? "businesses"
          : "business-new"
        : route;
    const showAssistant =
      Boolean(workspace.business) &&
      !activeRoute.startsWith("chat/") &&
      !["business-new", "businesses", "ask"].includes(activeRoute);
    body = (
      <WorkspaceState.Provider
        value={{
          workspace,
          listing,
          route: activeRoute,
          refresh,
          removeChat: setDeleting,
        }}
      >
        <a
          href="#main-content"
          className="skip-link"
          onClick={(e) => {
            e.preventDefault();
            document.getElementById("main-content")?.focus();
          }}
        >
          Saltar al contenido
        </a>
        <Layout>
          <div
            key={`${workspace.business?.id || "empty"}:${activeRoute}`}
            id="main-content"
            tabIndex={-1}
            className={
              activeRoute.startsWith("chat/")
                ? "flex min-h-0 flex-1 flex-col outline-none"
                : "min-h-0 flex-1 overflow-y-auto outline-none"
            }
          >
            <Notice error>{error}</Notice>
            <Suspense
              fallback={
                <div className="p-6">
                  <Loading />
                </div>
              }
            >
              {activeRoute.startsWith("chat/") ? (
                <ChatPage id={activeRoute.split("/")[1]} />
              ) : (
                <div
                  className={`mx-auto w-full max-w-7xl px-5 py-8 sm:px-8 lg:px-10 ${showAssistant ? "pb-64" : ""} ${activeRoute === "ask" ? "flex min-h-full flex-col" : ""}`}
                >
                  <Route route={activeRoute} />
                </div>
              )}
            </Suspense>
          </div>
          {showAssistant && (
            <FloatingAssistant
              key={`assistant:${workspace.business!.id}:${activeRoute}`}
            />
          )}
        </Layout>
        <AlertDialog
          open={Boolean(deleting)}
          onOpenChange={(v) => {
            if (!v && !deletion.busy) setDeleting(null);
          }}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Eliminar conversación</AlertDialogTitle>
              <AlertDialogDescription>
                Se ocultará «{deleting?.title}» y no podrás continuar este chat.
                La información del negocio y sus datos se conservan.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <Notice error>{deletion.error}</Notice>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={deletion.busy}>
                Cancelar
              </AlertDialogCancel>
              <Button
                variant="destructive"
                disabled={deletion.busy}
                onClick={() =>
                  deletion.run(async () => {
                    const chat = deleting!;
                    await api(`/api/chats/${chat.id}/delete`, {
                      business_id: chat.business_id,
                    });
                    setDeleting(null);
                    if (route === `chat/${chat.id}`) location.hash = "chats";
                    refresh();
                  })
                }
              >
                {deletion.busy && <Busy />}Eliminar chat
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </WorkspaceState.Provider>
    );
  }
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      enableSystem
      scriptProps={{ type: "application/json" }}
    >
      <TooltipProvider>
        {body}
        <Toaster />
      </TooltipProvider>
    </ThemeProvider>
  );
}
function Route({ route }: { route: string }) {
  const [page, id, turn] = route.split("/");
  switch (page) {
    case "home":
      return <Home />;
    case "ask":
      return <StartChat />;
    case "chats":
      return <Chats />;
    case "reports":
      return <AnalysisList reports />;
    case "analyses":
      return <AnalysisList />;
    case "new":
      return <NewAnalysis />;
    case "business-new":
      return <BusinessForm create />;
    case "business":
      return <BusinessForm />;
    case "businesses":
      return <BusinessPicker />;
    case "my-business":
      return <Dossier />;
    case "files":
      return <Dossier files />;
    case "analysis":
      return <JobPage id={id} />;
    case "report":
      return (
        <Presentation
          path={`/api/jobs/${id}/presentation`}
          exportUrl={`/api/jobs/${id}/report`}
        />
      );
    case "chat-report":
      return (
        <Presentation
          path={`/api/chats/${id}/presentation/${turn}`}
          exportUrl={`/api/chats/${id}/report/${turn}`}
        />
      );
    case "how":
      return <How />;
    default:
      return (
        <>
          <Heading title="Esta página no existe" />
          <Button asChild>
            <a href="#home">Volver al inicio</a>
          </Button>
        </>
      );
  }
}
function Login({ onDone }: { onDone: () => void }) {
  const [token, setToken] = useState(""),
    action = useAction();
  return (
    <div className="flex min-h-svh items-center justify-center p-5">
      <Card className="w-full max-w-md shadow-none">
        <CardContent>
          <Heading
            title="Decision Room"
            description="Abre tu espacio local con la clave de acceso del servidor."
          />
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              void action.run(async () => {
                await api("/api/login", { token });
                setToken("");
                onDone();
              });
            }}
          >
            <Field label="Clave de acceso" id="access-key">
              <Input
                id="access-key"
                type="password"
                autoComplete="current-password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                required
              />
            </Field>
            <Notice error>{action.error}</Notice>
            <Button className="w-full" disabled={action.busy} type="submit">
              {action.busy && <Busy />}Abrir mi espacio
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
export default App;
