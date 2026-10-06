import { translate as tr, useLanguage } from "@/lib/i18n";
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
import { NewChatComposer } from "./floating-assistant";
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
import { ResizeHandle } from "./resize-handle";
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
  useLanguage();
  const a = useAssistant()!;
  const { route, workspace } = useWorkspace();
  const { open, openMobile, isMobile, setOpen, setOpenMobile } = useSidebar();
  const navigationOpen = isMobile ? openMobile : open;
  const previous = useRef({ panel: false, navigationOpen });
  const [width, setWidth] = useState(() =>
    Number(store.get("dr-chat-panel-width", 420)),
  );
  const panel = a.dock.open && contextualRoute(route);
  const floatingComposer = Boolean(
    workspace.business && contextualRoute(route) && !panel,
  );
  const panelRef = useRef<HTMLElement>(null);
  const pageRef = useRef<HTMLElement>(null);
  const composerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const page = pageRef.current;
    const composer = composerRef.current;
    if (!page || !composer || !floatingComposer) return;
    const measure = () =>
      page.style.setProperty(
        "--workspace-composer-height",
        `${composer.getBoundingClientRect().height}px`,
      );
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(composer);
    return () => {
      observer.disconnect();
      page.style.removeProperty("--workspace-composer-height");
    };
  }, [floatingComposer]);
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
      <SidebarInset
        ref={pageRef}
        className={`assistant-page ${floatingComposer ? "has-workspace-composer" : ""}`}
      >
        {header}
        <div className="assistant-content">
          {children}
          {a.selecting && (
            <div className="selection-banner" role="status">
              <span>
                {tr("Selecciona elementos · ")}
                {a.selected.length}/8
              </span>
              <SelectionTool />
              {a.error && <span>{a.error}</span>}
            </div>
          )}
        </div>
        {floatingComposer && (
          <div
            ref={composerRef}
            className="workspace-composer px-4 pb-4 pt-2 sm:px-8"
          >
            <div className="workspace-composer-island mx-auto w-full max-w-2xl">
              {a.dock.chatId ? (
                <Suspense fallback={<Loading />}>
                  <ChatPage
                    key={a.dock.chatId}
                    id={a.dock.chatId}
                    composerOnly
                  />
                </Suspense>
              ) : (
                <NewChatComposer autoFocus={false} />
              )}
            </div>
          </div>
        )}
      </SidebarInset>
      {panel && !isMobile && (
        <ResizeHandle
          label={tr("Anchura del chat")}
          className="assistant-resize"
          min={340}
          max={640}
          width={width}
          direction={-1}
          step={24}
          getWidth={() =>
            panelRef.current?.getBoundingClientRect().width ?? width
          }
          onResize={resize}
        />
      )}
      <AnimatePresence initial={false}>
        {panel && (
          <PanelPresence key="chat-panel" mobile={isMobile} width={width}>
            <aside
              ref={panelRef}
              className="assistant-panel"
              aria-label={tr("Chat lateral")}
            >
              <header className="flex h-14 shrink-0 items-center gap-1 px-4">
                <span className="mr-auto text-sm font-medium">
                  {tr("Chat")}
                </span>
                <PanelAction label={tr("Nuevo chat")}>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={tr("Nuevo chat")}
                    disabled={!a.dock.chatId}
                    onClick={() => a.newConversation("panel")}
                  >
                    <Plus />
                  </Button>
                </PanelAction>
                <PanelAction label={tr("Ampliar")}>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={tr("Ampliar chat")}
                    disabled={!a.dock.chatId}
                    onClick={() => {
                      a.setSelecting(false);
                      a.setDock({
                        ...a.dock,
                        origin: route,
                        block: undefined,
                        scroll:
                          document.getElementById("main-content")?.scrollTop,
                      });
                      location.hash = `chat/${a.dock.chatId}`;
                    }}
                  >
                    <Maximize2 />
                  </Button>
                </PanelAction>
                <PanelAction label={tr("Cerrar")}>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={tr("Cerrar chat lateral")}
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
                  <p className="mt-3 text-sm">{tr("Preparando tu chat…")}</p>
                </div>
              ) : (
                <div className="flex min-h-0 flex-1 flex-col">
                  <div className="flex flex-1 items-center justify-center p-6 text-center text-sm text-muted-foreground">
                    {tr("Pregunta sobre tu negocio.")}
                  </div>
                  <div className="p-3">
                    <NewChatComposer />
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
      style={{ width: mobile ? "100%" : width }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: reduced ? 0 : 0.28, ease: [0.22, 1, 0.36, 1] }}
      aria-hidden={!present}
      inert={!present}
    >
      {children}
    </motion.div>
  );
}
