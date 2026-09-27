import {
  useEffect,
  useState,
  lazy,
  Suspense,
  type ReactNode,
  type CSSProperties,
} from "react";
import { Maximize2, PanelRightClose, Plus, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAssistant, contextualRoute } from "@/lib/assistant";
import { useWorkspace } from "@/lib/workspace";
import { store } from "@/lib/api";
import { useSidebar } from "@/components/ui/sidebar";
const ChatPage = lazy(() =>
  import("./chat").then((m) => ({ default: m.ChatPage })),
);
import { SelectionTool } from "./context-selection";
import { Loading } from "./shared";
import "./contextual-chat.css";
export function AssistantFrame({ children }: { children: ReactNode }) {
  const a = useAssistant()!;
  const { route } = useWorkspace();
  const { setOpen } = useSidebar();
  const [width, setWidth] = useState(() =>
    Number(store.get("dr-chat-panel-width", 420)),
  );
  const panel = a.dock.open && contextualRoute(route);
  useEffect(() => {
    if (panel) setOpen(false);
  }, [panel, setOpen]);
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
      <div className="assistant-content">
        {route.startsWith("chat/") &&
          a.dock.chatId === route.split("/")[1] &&
          a.dock.origin && (
            <Button
              variant="secondary"
              size="sm"
              className="my-1 mr-4 ml-auto shrink-0"
              onClick={() => {
                a.setDock({
                  ...a.dock,
                  open: !matchMedia("(max-width: 767px)").matches,
                });
                location.hash = a.dock.origin!;
              }}
            >
              <ArrowLeft className="size-3" />
              {a.dock.origin === "home"
                ? "Volver al dashboard"
                : "Volver al informe"}
            </Button>
          )}
        {children}
      </div>
      {a.selecting && (
        <div className="selection-banner" role="status">
          <span>Selecciona elementos · {a.selected.length}/8</span>
          <SelectionTool />
          {a.error && <span>{a.error}</span>}
        </div>
      )}
      {panel && (
        <aside className="assistant-panel" aria-label="Conversación lateral">
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
              if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) {
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
          <header className="flex h-12 shrink-0 items-center gap-1 border-b px-3">
            <span className="mr-auto text-sm font-medium">Conversación</span>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Nueva conversación"
              disabled={!a.dock.chatId}
              onClick={() => {
                a.clear();
                a.setDock({ open: false });
              }}
            >
              <Plus />
            </Button>
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
                  scroll: document.getElementById("main-content")?.scrollTop,
                });
                location.hash = `chat/${a.dock.chatId}`;
              }}
            >
              <Maximize2 />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Plegar conversación"
              onClick={() => a.setDock({ ...a.dock, open: false })}
            >
              <PanelRightClose />
            </Button>
          </header>
          {a.dock.chatId ? (
            <Suspense fallback={<Loading />}>
              <ChatPage key={a.dock.chatId} id={a.dock.chatId} docked />
            </Suspense>
          ) : (
            <div className="p-5">
              <Loading />
              <p className="mt-3 text-sm">Preparando tu conversación…</p>
            </div>
          )}
        </aside>
      )}
    </div>
  );
}
