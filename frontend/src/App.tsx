import { InternalMonitor } from "@/components/workspace/internal-monitor";
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
import { MainContent } from "@/components/workspace/main-content";
import { EntryFrame, Welcome } from "@/components/entry/welcome";
const Onboarding = lazy(() =>
  import("@/components/entry/onboarding").then((m) => ({
    default: m.Onboarding,
  })),
);
import {
  Heading,
  Notice,
  Loading,
  Field,
  Busy,
} from "@/components/workspace/shared";
const Home = lazy(() =>
  import("@/components/workspace/home").then((m) => ({ default: m.Home })),
);
const StartChat = lazy(() =>
  import("@/components/workspace/overview").then((m) => ({
    default: m.StartChat,
  })),
);
const Chats = lazy(() =>
  import("@/components/workspace/overview").then((m) => ({ default: m.Chats })),
);
const Reports = lazy(() =>
  import("@/components/workspace/overview").then((m) => ({
    default: m.Reports,
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
const NewReport = lazy(() =>
  import("@/components/workspace/business").then((m) => ({
    default: m.NewReport,
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
const routeNow = () => {
  const route = location.hash.slice(1) || "home";
  return route === "analyses" ? "reports" : route;
};
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
  const internal = route.startsWith("internal/");
  const deletion = useAction(),
    refresh = () => setRevision((v) => v + 1);
  useEffect(() => {
    const change = () => setRoute(routeNow());
    addEventListener("hashchange", change);
    return () => removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    if (internal) return;
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
  }, [revision, internal]);
  let body;
  if (internal) body = <InternalMonitor route={route} />;
  else if (route === "welcome" || (login && route === "home"))
    body = <Welcome signedIn={Boolean(workspace)} />;
  else if (login)
    body = (
      <Login
        onDone={() => {
          loginPromise = undefined;
          if (route === "login/start") location.hash = "onboarding";
          else if (route === "login") location.hash = "home";
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
    const requestedRoute =
      route === "login/start" || route === "business-new"
        ? "onboarding"
        : route === "login"
          ? "home"
          : route;
    const activeRoute =
      !workspace.business &&
      !requestedRoute.startsWith("onboarding") &&
      !["businesses", "how"].includes(requestedRoute)
        ? workspace.businesses.length
          ? "businesses"
          : "welcome"
        : !requestedRoute.startsWith("onboarding") &&
            !["businesses", "how", "welcome"].includes(requestedRoute) &&
            workspace.setup &&
            workspace.setup.stage !== "complete"
          ? `onboarding/${workspace.business!.id}`
          : requestedRoute === "home" &&
              workspace.business?.onboarding_status === "context_saved" &&
              !workspace.analyses.length
            ? `onboarding/${workspace.business.id}`
            : requestedRoute;
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
        {activeRoute !== "welcome" && !activeRoute.startsWith("onboarding") && (
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
        )}
        {activeRoute === "welcome" ? (
          <Welcome signedIn />
        ) : activeRoute.startsWith("onboarding") ? (
          <Onboarding
            key={activeRoute.split("/")[1] || "new"}
            route={activeRoute}
            onSaved={(saved) => {
              setWorkspace((current) =>
                current
                  ? {
                      ...current,
                      business: saved,
                      businesses: [
                        saved,
                        ...current.businesses.filter((b) => b.id !== saved.id),
                      ],
                      analyses:
                        current.business?.id === saved.id
                          ? current.analyses
                          : [],
                    }
                  : current,
              );
              if (saved.id !== workspace.business?.id)
                setListing({
                  business_id: saved.id,
                  conversations: [],
                  datasets: { items: [], more: false },
                });
              if (activeRoute === "onboarding")
                history.replaceState(
                  null,
                  "",
                  `${location.pathname}${location.search}#onboarding/${saved.id}/business`,
                );
              location.hash = `onboarding/${saved.id}`;
            }}
          />
        ) : (
          <Layout>
            <MainContent
              key={`${workspace.business?.id || "empty"}:${activeRoute}`}
              scrollable={
                activeRoute !== "ask" && !activeRoute.startsWith("chat/")
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
                ) : activeRoute === "ask" ? (
                  <StartChat />
                ) : (
                  <div
                    className={`mx-auto w-full max-w-7xl px-5 py-8 sm:px-8 lg:px-10 ${showAssistant ? "pb-24" : ""}`}
                  >
                    <Route route={activeRoute} />
                  </div>
                )}
              </Suspense>
            </MainContent>
            {showAssistant && (
              <FloatingAssistant
                key={`assistant:${workspace.business!.id}:${activeRoute}`}
              />
            )}
          </Layout>
        )}
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
        <Suspense
          fallback={
            <div className="mx-auto max-w-2xl p-8">
              <Loading />
            </div>
          }
        >
          {body}
        </Suspense>
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
      return <Reports />;
    case "analyses":
      return <Reports />;
    case "new":
      return <NewReport />;
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
          exportUrl={`/api/jobs/${id}/pdf`}
        />
      );
    case "chat-report":
      return (
        <Presentation
          path={`/api/chats/${id}/presentation/${turn}`}
          exportUrl={`/api/chats/${id}/pdf/${turn}`}
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
    <EntryFrame
      action={
        <Button asChild variant="ghost">
          <a href="#welcome">Volver</a>
        </Button>
      }
    >
      <div className="flex items-center justify-center px-5 py-16 sm:py-24">
        <Card className="w-full max-w-md shadow-none">
          <CardContent>
            <Heading
              title="Entra a tu espacio"
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
    </EntryFrame>
  );
}
export default App;
