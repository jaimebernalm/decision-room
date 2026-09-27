import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { useWorkspace } from "./workspace";
import { contextKey, referenceWire, launchChat, store } from "./api";
import { useDraft } from "./hooks";
import type {
  ContextAttachment,
  ContextReference,
  QuestionContext,
} from "./types";
export const referenceId = (r: ContextReference) =>
  [r.report_id, r.report_version, r.kind, r.element_key].join(":");
export const blockId = (r: ContextReference) =>
  `context-${r.report_id}-${r.kind}-${r.element_key}`;
export const contextualRoute = (route: string) =>
  route === "home" ||
  route.startsWith("report/") ||
  route.startsWith("chat-report/");
type Dock = {
  chatId?: string;
  open: boolean;
  origin?: string;
  scroll?: number;
  block?: string;
};
type Assistant = {
  dock: Dock;
  setDock: (d: Dock) => void;
  openConversation: (id: string) => void;
  selecting: boolean;
  setSelecting: (v: boolean) => void;
  selected: ContextAttachment[];
  toggle: (r: ContextAttachment) => void;
  clear: () => void;
  remove: (r: ContextReference) => void;
  register: (r: ContextAttachment) => () => void;
  launch: (
    text: string,
    context: QuestionContext,
    origin: string,
  ) => Promise<void>;
  error: string;
  launching: boolean;
  returnToSource: (r: ContextAttachment, chatId?: string) => void;
};
const AssistantContext = createContext<Assistant | null>(null);
export const useAssistant = () => useContext(AssistantContext);
export function AssistantProvider({ children }: { children: ReactNode }) {
  const { workspace, route } = useWorkspace();
  const business = workspace.business?.id || "empty";
  const mounted = useRef(true);
  const launchVersion = useRef(0);
  useEffect(() => {
    if (contextualRoute(route))
      store.set(`dr-assistant-origin-${business}`, route);
  }, [business, route]);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const [dock, setDock] = useDraft<Dock>(`dr-dock-${business}`, {
    open: false,
  });
  const [context, setContext] = useDraft<QuestionContext>(
    contextKey(business),
    {},
  );
  const [selectionRoute, setSelectionRoute] = useState<string | null>(null);
  const selecting = selectionRoute === route;
  const setSelecting = (value: boolean) =>
    setSelectionRoute(value ? route : null);
  const [error, setError] = useState("");
  const [launching, setLaunching] = useState(false);
  const [previews, setPreviews] = useState<Record<string, ContextAttachment>>(
    {},
  );
  const register = useCallback((item: ContextAttachment) => {
    const key = referenceId(item);
    setPreviews((current) => ({ ...current, [key]: item }));
    return () =>
      setPreviews((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
  }, []);
  const refs = context.context_references || [];
  const selected = refs.map((r) => previews[referenceId(r)] || r);
  const save = (items: ContextAttachment[]) =>
    setContext({
      ...context,
      finding_reference: undefined,
      context_references: items.map((r) => ({
        ...referenceWire(r),
        title: r.title,
        period: r.period,
        href: r.href,
      })),
    });
  useEffect(() => {
    const cancel = () => setSelectionRoute(null);
    const leave = (e: KeyboardEvent) => {
      if (e.key === "Escape") cancel();
    };
    addEventListener("keydown", leave);
    addEventListener("hashchange", cancel);
    return () => {
      removeEventListener("keydown", leave);
      removeEventListener("hashchange", cancel);
    };
  }, []);
  const clear = () => {
    save([]);
    setSelecting(false);
    setError("");
  };
  return (
    <AssistantContext.Provider
      value={{
        dock,
        setDock,
        openConversation: (id) => {
          launchVersion.current += 1;
          setLaunching(false);
          setSelecting(false);
          setError("");
          const remembered = store.get<string>(
            `dr-assistant-origin-${business}`,
            "home",
          );
          const origin = contextualRoute(route)
            ? route
            : contextualRoute(remembered)
              ? remembered
              : "home";
          setDock({ chatId: id, open: true, origin });
          if (route !== origin) location.hash = origin;
        },
        selecting,
        setSelecting,
        selected,
        register,
        error,
        launching,
        clear,
        launch: async (text, selectedContext, origin) => {
          const version = ++launchVersion.current;
          const startedInPanel = dock.open && !dock.chatId;
          setSelecting(false);
          setError("");
          setLaunching(true);
          setDock({ open: true, origin });
          try {
            const chat = await launchChat(business, text, selectedContext);
            if (mounted.current && launchVersion.current === version) {
              const current = store.get<Dock>(`dr-dock-${business}`, {
                open: false,
              });
              setDock({ ...current, chatId: chat.id, origin });
            }
          } catch (error) {
            if (mounted.current && launchVersion.current === version) {
              const current = store.get<Dock>(`dr-dock-${business}`, {
                open: false,
              });
              setDock({ open: startedInPanel && current.open, origin });
              setError((error as Error).message);
            }
            throw error;
          } finally {
            if (mounted.current && launchVersion.current === version)
              setLaunching(false);
          }
        },
        remove: (r) => {
          save(refs.filter((x) => referenceId(x) !== referenceId(r)));
          setError("");
        },
        toggle: (r) => {
          const exists = refs.some((x) => referenceId(x) === referenceId(r));
          if (!exists && refs.length >= 8) {
            setError("Puedes añadir hasta ocho elementos por mensaje.");
            return;
          }
          save(
            exists
              ? refs.filter((x) => referenceId(x) !== referenceId(r))
              : [...refs, r],
          );
          setError("");
        },
        returnToSource: (r, chatId) => {
          if (r.status === "withdrawn") return;
          const origin = (r.href || "#home").slice(1);
          setDock({
            chatId: chatId || dock.chatId,
            open: !matchMedia("(max-width: 767px)").matches,
            origin,
            block: blockId(r),
          });
          location.hash = origin;
        },
      }}
    >
      {children}
    </AssistantContext.Provider>
  );
}
