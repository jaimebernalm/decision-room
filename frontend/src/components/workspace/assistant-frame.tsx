import {
  useEffect,
  useState,
  useRef,
  lazy,
  Suspense,
  type ReactNode,
  type CSSProperties,
} from "react";
import { Maximize2, PanelRightClose, Plus } from "lucide-react";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip";
import { FloatingAssistant } from "./floating-assistant";
import { Button } from "@/components/ui/button";
import { useAssistant, contextualRoute } from "@/lib/assistant";
import { useWorkspace } from "@/lib/workspace";
import { store } from "@/lib/api";
import {
  AnimatePresence,
  motion,
  useReducedMotion,
  useIsPresent,
} from "motion/react";
import { SidebarInset, useSidebar } from "@/components/ui/sidebar";
const ChatPage = lazy(() =>
  import("./chat").then((m) => ({ default: m.ChatPage })),
);
import { SelectionTool } from "./context-selection";
import { Loading } from "./shared";
import "./contextual-chat.css";
export function AssistantFrame({
  children,
  header,
}: {
  children: ReactNode;
  header?: ReactNode;
}) {
  const a = useAssistant()!;
  const { route } = useWorkspace();
  const { open, openMobile, isMobile, setOpen, setOpenMobile } = useSidebar();
  const navigationOpen = isMobile ? openMobile : open;
  const previous = useRef({ panel: false, navigationOpen });
  const [width, setWidth] = useState(() =>
    Number(store.get("dr-chat-panel-width", 420)),
  );
  const panel = a.dock.open && contextualRoute(route);
  useEffect(() => {
    const was = previous.current;
    previous.current = { panel, navigationOpen };
    if (panel && !was.panel) {
      setOpen(false);
      setOpenMobile(false);
    } else if (panel && navigationOpen && !was.navigationOpen) {
      a.setSelecting(false);
      a.setDock({ ...a.dock, open: false });
    }
  }, [panel, navigationOpen, setOpen, setOpenMobile, a]);
  useEffect(() => {
    if (route !== a.dock.origin) return;
    // Lazy report loading may finish after navigation. Observe until the target arrives.
    const restore = () => {
      const target = a.dock.block && document.getElementById(a.dock.block);
      if (target) {
        target.scrollIntoView({ block: "center" });
        target.classList.add("context-returned");
        return true;
      }
      const main = document.getElementById("main-content");
      if (!a.dock.block && main && a.dock.scroll !== undefined) {
        main.scrollTop = a.dock.scroll;
        return true;
      }
      return false;
    };
    if (restore()) return;
    const observer = new MutationObserver(() => {
      if (restore()) observer.disconnect();
    });
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [route, a.dock.origin, a.dock.block, a.dock.scroll]);
  const resize = (value: number) => {
    const next = Math.max(340, Math.min(value, 640, innerWidth * 0.55));
    setWidth(next);
    store.set("dr-chat-panel-width", next);
  };
  return (
    <div
      className={`assistant-frame ${panel ? "assistant-docked" : ""} ${a.selecting ? "assistant-selecting" : ""}`}
      style={{ "--chat-panel-width": `${width}px` } as CSSProperties}
    >
      <SidebarInset className="assistant-page">
        {header}
        <div className="assistant-content">
          {children}
          {a.selecting && (
            <div className="selection-banner" role="status">
              <span>Selecciona elementos · {a.selected.length}/8</span>
              <SelectionTool />
              {a.error && <span>{a.error}</span>}
            </div>
          )}
        </div>
      </SidebarInset>
      <AnimatePresence initial={false}>
        {panel && (
          <PanelPresence key="chat-panel" mobile={isMobile} width={width}>
            <aside
              className="assistant-panel"
              aria-label="Conversación lateral"
            >
              <div
                role="separator"
                tabIndex={0}
                aria-label="Anchura del chat"
                aria-orientation="vertical"
                aria-valuemin={340}
                aria-valuemax={640}
                aria-valuenow={Math.round(width)}
                className="assistant-resize"
                onPointerDown={(e) => {
                  e.currentTarget.setPointerCapture(e.pointerId);
                  e.preventDefault();
                }}
                onPointerMove={(e) => {
                  if (e.currentTarget.hasPointerCapture(e.pointerId))
                    resize(innerWidth - e.clientX);
                }}
                onKeyDown={(e) => {
                  if (
                    ["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)
                  ) {
                    e.preventDefault();
                    resize(
                      e.key === "Home"
                        ? 340
                        : e.key === "End"
                          ? 640
                          : width + (e.key === "ArrowLeft" ? 24 : -24),
                    );
                  }
                }}
              />
              <header className="flex h-16 shrink-0 items-center gap-1 px-4">
                <span className="mr-auto text-sm font-medium">
                  Conversación
                </span>
                <PanelAction label="Nueva conversación">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Nueva conversación"
                    disabled={!a.dock.chatId}
                    onClick={() => {
                      a.clear();
                      a.setDock({ open: true, origin: route });
                    }}
                  >
                    <Plus />
                  </Button>
                </PanelAction>
                <PanelAction label="Ampliar">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Abrir conversación completa"
                    disabled={!a.dock.chatId}
                    onClick={() => {
                      a.setSelecting(false);
                      a.setDock({
                        ...a.dock,
                        origin: route,
                        scroll:
                          document.getElementById("main-content")?.scrollTop,
                      });
                      location.hash = `chat/${a.dock.chatId}`;
                    }}
                  >
                    <Maximize2 />
                  </Button>
                </PanelAction>
                <PanelAction label="Cerrar">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Plegar conversación"
                    onClick={() => a.setDock({ ...a.dock, open: false })}
                  >
                    <PanelRightClose />
                  </Button>
                </PanelAction>
              </header>
              {a.dock.chatId ? (
                <Suspense fallback={<Loading />}>
                  <ChatPage key={a.dock.chatId} id={a.dock.chatId} docked />
                </Suspense>
              ) : a.launching ? (
                <div className="p-5">
                  <Loading />
                  <p className="mt-3 text-sm">Preparando tu conversación…</p>
                </div>
              ) : (
                <div className="flex min-h-0 flex-1 flex-col">
                  <div className="flex flex-1 items-center justify-center p-6 text-center text-sm text-muted-foreground">
                    Pregunta sobre tu negocio o selecciona algo del dashboard o
                    informe.
                  </div>
                  <div className="p-3">
                    <FloatingAssistant inline />
                  </div>
                </div>
              )}
            </aside>
          </PanelPresence>
        )}
      </AnimatePresence>
    </div>
  );
}

function PanelAction({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent side="bottom" sideOffset={6}>
        {label}
      </TooltipContent>
    </Tooltip>
  );
}

function PanelPresence({
  children,
  mobile,
  width,
}: {
  children: ReactNode;
  mobile: boolean;
  width: number;
}) {
  const reduced = useReducedMotion();
  const present = useIsPresent();
  return (
    <motion.div
      className="assistant-panel-shell"
      initial={{ width: 0, opacity: 0 }}
      animate={{
        width: mobile ? "100%" : width,
        opacity: 1,
      }}
      exit={{ width: 0, opacity: 0 }}
      transition={{ duration: reduced ? 0 : 0.28, ease: [0.22, 1, 0.36, 1] }}
      aria-hidden={!present}
      inert={!present}
    >
      {children}
    </motion.div>
  );
}
