import { useEffect, useState } from "react";
import { it, expect, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import { WorkspaceState, type WorkspaceContext } from "@/lib/workspace";
import { store, messageKey } from "@/lib/api";
import type { ContextAttachment } from "@/lib/types";
import { Selectable } from "./context-selection";
import { FloatingAssistant } from "./floating-assistant";
import { ChatPage } from "./chat";
import { Chats, Reports, StartChat } from "./overview";
import { Dossier } from "./dossier";
import { Layout } from "./layout";
const item: ContextAttachment = {
  report_id: "review",
  report_version: "v1",
  kind: "metric",
  element_key: "total",
  title: "Ventas",
  href: "#home",
  content: {
    key: "total",
    label: "Ventas",
    value: "80",
    unit: "EUR",
    claim_key: "sales",
  },
};
const workspace: WorkspaceContext = {
  workspace: {
    business: {
      id: "a",
      name: "Negocio",
      description: "Prueba",
      profile_revision: 1,
    },
    businesses: [],
    analyses: [
      {
        id: "analysis",
        title: "Informe de ventas",
        filename: "ventas.csv",
        created_at: "2026-09-27",
        status: "completed",
        context_reference: {
          ...item,
          kind: "report",
          element_key: "report",
          title: "Informe de ventas",
        },
      },
    ],
    configured: true,
    memory: {},
  },
  listing: {
    business_id: "a",
    conversations: [],
    datasets: { items: [], more: false },
  },
  route: "home",
  refresh: vi.fn(),
  removeChat: vi.fn(),
};
function Harness({
  initialRoute = "home",
  conversations = workspace.listing.conversations,
}: {
  initialRoute?: string;
  conversations?: WorkspaceContext["listing"]["conversations"];
} = {}) {
  const [route, setRoute] = useState(initialRoute);
  useEffect(() => {
    const change = () => setRoute(location.hash.slice(1));
    addEventListener("hashchange", change);
    return () => removeEventListener("hashchange", change);
  }, []);
  return (
    <TooltipProvider>
      <WorkspaceState.Provider
        value={{
          ...workspace,
          route,
          listing: { ...workspace.listing, conversations },
        }}
      >
        <Layout>
          {route.startsWith("chat/") ? (
            <ChatPage id={route.split("/")[1]} />
          ) : route === "ask" ? (
            <StartChat />
          ) : route === "chats" ? (
            <>
              <Chats />
              <FloatingAssistant />
            </>
          ) : (
            <>
              <div id="main-content">
                {route === "my-business" ? (
                  <Dossier />
                ) : route === "reports" ? (
                  <Reports />
                ) : (
                  <Selectable item={item}>
                    <p>Ventas: 80 EUR</p>
                  </Selectable>
                )}
              </div>
              <FloatingAssistant />
            </>
          )}
        </Layout>
      </WorkspaceState.Provider>
    </TooltipProvider>
  );
}
function server(delayed?: Promise<void>, failSend = 0) {
  const calls: { url: string; data: Record<string, unknown> }[] = [];
  let sent = false;
  let sendCount = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const data = JSON.parse(String(init?.body || "{}"));
      calls.push({ url, data });
      let body: unknown;
      if (url === "/api/business/dossier") {
        body = {
          business: workspace.workspace.business,
          business_id: "a",
          memory: {},
          facts: [],
          history: [],
          datasets: [],
        };
      } else if (url === "/api/chats") {
        await delayed;
        body = { id: "chat", business_id: "a" };
      } else if (url.endsWith("/messages")) {
        if (++sendCount === failSend)
          return {
            ok: false,
            status: 503,
            json: async () => ({ error: "Reintenta el mensaje" }),
          };
        sent = true;
        body = { id: "turn" };
      } else
        body = {
          conversation: { id: "chat", business_id: "a" },
          turns: sent
            ? [
                {
                  id: "turn",
                  payload: { text: "Explica esto" },
                  attachments: [item],
                  status: "completed",
                  response: { kind: "answer", text: "Ventas revisadas." },
                },
              ]
            : [],
          memory: {},
          memory_items: [],
        };
      return { ok: true, json: async () => body };
    }),
  );
  return calls;
}
it.each(["home", "my-business", "reports", "chats"])(
  "opens the right panel immediately from the launcher on %s, preserving a folded draft",
  async (route) => {
    location.hash = route;
    store.set("dr-assistant-collapsed", false);
    const calls = server();
    const user = userEvent.setup();
    render(<Harness initialRoute={route} />);
    expect(screen.queryByRole("textbox", { name: "Mensaje" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Preguntar algo" }));
    const panel = await screen.findByRole("complementary", {
      name: "Conversación lateral",
    });
    const composer = within(panel).getByRole("textbox", { name: "Mensaje" });
    expect(composer).toHaveFocus();
    expect(location.hash).toBe(`#${route}`);
    expect(calls.filter((call) => call.url === "/api/chats")).toHaveLength(0);
    await user.type(composer, "Borrador del panel");
    await user.click(
      within(panel).getByRole("button", { name: "Plegar conversación" }),
    );
    await waitFor(() => expect(screen.queryByRole("complementary")).toBeNull());
    expect(screen.queryByRole("textbox", { name: "Mensaje" })).toBeNull();
    await user.click(
      screen.getByRole("button", { name: "Continuar conversación" }),
    );
    expect(await screen.findByRole("textbox", { name: "Mensaje" })).toHaveValue(
      "Borrador del panel",
    );
    expect(screen.getAllByRole("textbox", { name: "Mensaje" })).toHaveLength(1);
  },
);
it("sends the first standalone message without routing through home or opening a side panel", async () => {
  location.hash = "ask";
  const calls = server();
  const user = userEvent.setup();
  render(<Harness initialRoute="ask" />);
  expect(screen.queryByRole("complementary")).toBeNull();
  expect(calls).toHaveLength(0);
  await user.type(
    screen.getByRole("textbox", { name: "Mensaje" }),
    "Mi primera pregunta",
  );
  await user.click(screen.getByRole("button", { name: "Enviar mensaje" }));
  await screen.findByText("Ventas revisadas.");
  expect(location.hash).toBe("#chat/chat");
  expect(screen.queryByRole("complementary")).toBeNull();
  expect(calls.filter((call) => call.url === "/api/chats")).toHaveLength(1);
  expect(calls.filter((call) => call.url.endsWith("/messages"))).toEqual([
    expect.objectContaining({
      data: expect.objectContaining({ text: "Mi primera pregunta" }),
    }),
  ]);
});
it("can fold and resume an existing side conversation from the library", async () => {
  location.hash = "chats";
  store.set("dr-dock-a", { chatId: "existing", open: true });
  store.set(messageKey("existing"), { text: "Continuar aquí" });
  const calls = server();
  const user = userEvent.setup();
  render(<Harness initialRoute="chats" conversations={existingChats} />);
  const panel = await screen.findByRole("complementary", {
    name: "Conversación lateral",
  });
  expect(await within(panel).findByRole("textbox")).toHaveValue(
    "Continuar aquí",
  );
  await user.click(
    within(panel).getByRole("button", { name: "Plegar conversación" }),
  );
  await waitFor(() => expect(screen.queryByRole("complementary")).toBeNull());
  expect(screen.queryByRole("button", { name: "Preguntar algo" })).toBeNull();
  await user.click(
    screen.getByRole("button", { name: "Continuar conversación" }),
  );
  expect(await screen.findByRole("textbox", { name: "Mensaje" })).toHaveValue(
    "Continuar aquí",
  );
  expect(location.hash).toBe("#chats");
  expect(
    calls.some(
      (call) => call.url === "/api/chats" || call.url.endsWith("/messages"),
    ),
  ).toBe(false);
});
it("selects context, opens a dock, expands the same chat and recovers attachments after remount", async () => {
  location.hash = "home";
  const calls = server();
  const user = userEvent.setup();
  const mounted = render(<Harness />);
  await user.click(screen.getByRole("button", { name: "Preguntar algo" }));
  await user.click(screen.getByRole("button", { name: "Seleccionar" }));
  await user.click(screen.getByRole("button", { name: "Seleccionar: Ventas" }));
  expect(
    screen.getByRole("button", { name: "Ver adjunto: Ventas" }),
  ).toBeInTheDocument();
  await user.keyboard("{Escape}");
  expect(
    screen.queryByRole("button", { name: "Quitar: Ventas" }),
  ).not.toBeInTheDocument();
  await user.type(
    screen.getByRole("textbox", { name: "Mensaje" }),
    "Explica esto",
  );
  await user.click(screen.getByRole("button", { name: "Enviar mensaje" }));
  const panel = await screen.findByRole("complementary", {
    name: "Conversación lateral",
  });
  await within(panel).findByText("Ventas revisadas.");
  expect(location.hash).toBe("#home");
  const sent = calls.find((c) => c.url.endsWith("/messages"))!;
  expect(sent.data.context_references).toEqual([
    {
      report_id: "review",
      report_version: "v1",
      kind: "metric",
      element_key: "total",
    },
  ]);
  await user.type(within(panel).getByRole("textbox"), "Mi siguiente pregunta");
  await user.click(
    screen.getByRole("button", { name: "Abrir conversación completa" }),
  );
  await waitFor(() => expect(location.hash).toBe("#chat/chat"));
  await waitFor(() =>
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument(),
  );
  expect(screen.getByRole("textbox")).toHaveValue("Mi siguiente pregunta");
  await user.click(screen.getByRole("button", { name: "Ver adjunto: Ventas" }));
  expect(
    within(screen.getByRole("dialog")).getByText("80 EUR"),
  ).toBeInTheDocument();
  expect(calls.filter((c) => c.url.endsWith("/messages"))).toHaveLength(1);
  mounted.unmount();
  render(
    <TooltipProvider>
      <WorkspaceState.Provider value={workspace}>
        <ChatPage id="chat" />
      </WorkspaceState.Provider>
    </TooltipProvider>,
  );
  expect(
    await screen.findByRole("button", { name: "Ver adjunto: Ventas" }),
  ).toBeInTheDocument();
});
it("does not reopen a panel folded before the first send finishes", async () => {
  location.hash = "home";
  let finish!: () => void;
  server(
    new Promise<void>((resolve) => {
      finish = resolve;
    }),
  );
  const user = userEvent.setup();
  render(<Harness />);
  await user.click(screen.getByRole("button", { name: "Preguntar algo" }));
  await user.type(screen.getByRole("textbox"), "Explica esto");
  await user.click(screen.getByRole("button", { name: "Enviar mensaje" }));
  await user.click(screen.getByRole("button", { name: "Plegar conversación" }));
  finish();
  await screen.findByRole("button", { name: "Continuar conversación" });
  expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
  expect(
    store.get<{ chatId: string }>("dr-dock-a", { chatId: "" }).chatId,
  ).toBe("chat");
});
it("keeps selected references and the question when the first send fails", async () => {
  location.hash = "home";
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: false,
      status: 503,
      json: async () => ({ error: "Servidor ocupado" }),
    })),
  );
  const user = userEvent.setup();
  render(<Harness />);
  await user.click(screen.getByRole("button", { name: "Preguntar algo" }));
  await user.click(screen.getByRole("button", { name: "Seleccionar" }));
  await user.click(screen.getByRole("button", { name: "Seleccionar: Ventas" }));
  await user.keyboard("{Escape}");
  await user.type(screen.getByRole("textbox"), "Explica esto");
  await user.click(screen.getByRole("button", { name: "Enviar mensaje" }));
  await screen.findByText("Servidor ocupado");
  expect(screen.getByRole("textbox")).toHaveValue("Explica esto");
  expect(
    screen.getByRole("button", { name: "Ver adjunto: Ventas" }),
  ).toBeInTheDocument();
});

it("uses the edited attachment selection after a failed follow-up", async () => {
  location.hash = "home";
  store.set("dr-dock-a", { chatId: "chat", open: true });
  const calls = server(undefined, 1);
  const user = userEvent.setup();
  render(<Harness />);
  await screen.findByRole("textbox");
  await user.click(screen.getByRole("button", { name: "Seleccionar" }));
  await user.click(screen.getByRole("button", { name: "Seleccionar: Ventas" }));
  await user.keyboard("{Escape}");
  await user.type(screen.getByRole("textbox"), "Explica esto");
  await user.click(screen.getByRole("button", { name: "Enviar mensaje" }));
  await screen.findByText("Reintenta el mensaje");
  await user.click(screen.getByRole("button", { name: "Quitar Ventas" }));
  await user.click(screen.getByRole("button", { name: "Enviar mensaje" }));
  await screen.findByText("Ventas revisadas.");
  const sends = calls.filter((c) => c.url.endsWith("/messages"));
  expect(sends).toHaveLength(2);
  expect(sends[0].data.context_references).toHaveLength(1);
  expect(sends[1].data.context_references).toBeUndefined();
  expect(sends[0].data.request_key).not.toBe(sends[1].data.request_key);
});

it("opens navigation by folding the chat and can resume it", async () => {
  location.hash = "home";
  store.set("dr-dock-a", { chatId: "chat", open: true });
  server();
  const user = userEvent.setup();
  render(<Harness />);
  await screen.findByRole("textbox");
  await user.click(
    screen.getByRole("button", { name: "Abrir o cerrar navegación" }),
  );
  await waitFor(() =>
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument(),
  );
  expect(document.querySelector('[data-slot="sidebar"]')).toHaveAttribute(
    "data-state",
    "expanded",
  );
  await user.click(
    screen.getByRole("button", { name: "Continuar conversación" }),
  );
  await screen.findByRole("complementary", { name: "Conversación lateral" });
  await waitFor(() =>
    expect(document.querySelector('[data-slot="sidebar"]')).toHaveAttribute(
      "data-state",
      "collapsed",
    ),
  );
  expect(
    store.get<{ chatId: string }>("dr-dock-a", { chatId: "" }).chatId,
  ).toBe("chat");
});

it("starts a new conversation inside the open panel and labels its actions", async () => {
  location.hash = "home";
  store.set("dr-dock-a", { chatId: "previous-chat", open: true });
  const calls = server();
  const user = userEvent.setup();
  render(<Harness />);
  await screen.findByRole("textbox");
  await user.hover(screen.getByRole("button", { name: "Nueva conversación" }));
  expect(await screen.findByRole("tooltip")).toHaveTextContent(
    "Nueva conversación",
  );
  await user.keyboard("{Escape}");
  await user.click(screen.getByRole("button", { name: "Nueva conversación" }));
  const panel = screen.getByRole("complementary", {
    name: "Conversación lateral",
  });
  expect(within(panel).getByRole("textbox")).toHaveValue("");
  expect(calls.filter((c) => c.url === "/api/chats")).toHaveLength(0);
  await user.type(within(panel).getByRole("textbox"), "Una pregunta nueva");
  await user.click(
    within(panel).getByRole("button", { name: "Enviar mensaje" }),
  );
  await within(panel).findByText("Ventas revisadas.");
  expect(calls.filter((c) => c.url === "/api/chats")).toHaveLength(1);
  expect(calls.filter((c) => c.url.endsWith("/messages"))).toEqual([
    expect.objectContaining({
      url: "/api/chats/chat/messages",
      data: expect.objectContaining({ text: "Una pregunta nueva" }),
    }),
  ]);
  expect(location.hash).toBe("#home");
});

const existingChats = [
  { id: "old", business_id: "a", title: "Anterior", created_at: "2026-09-27" },
  {
    id: "existing",
    business_id: "a",
    title: "Ya guardada",
    created_at: "2026-09-27",
  },
];
it("opens an existing conversation from its page on home without duplicate return actions or sending", async () => {
  location.hash = "chat/existing";
  store.set("dr-assistant-origin-a", "report/sales");
  store.set(messageKey("existing"), { text: "Borrador existente" });
  const calls = server();
  const user = userEvent.setup();
  render(<Harness initialRoute="chat/existing" />);
  await screen.findByRole("textbox");
  expect(
    screen.queryByRole("button", {
      name: /Volver al dashboard|Volver al informe/,
    }),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Abrir en panel" }));
  const panel = await screen.findByRole("complementary", {
    name: "Conversación lateral",
  });
  expect(await within(panel).findByRole("textbox")).toHaveValue(
    "Borrador existente",
  );
  expect(location.hash).toBe("#home");
  expect(store.get("dr-dock-a", {})).toMatchObject({
    chatId: "existing",
    open: true,
  });
  expect(
    calls.some((c) => c.url.endsWith("/messages") || c.url === "/api/chats"),
  ).toBe(false);
});
it("opens an existing chat in the panel without leaving the conversation list", async () => {
  location.hash = "chats";
  server();
  const user = userEvent.setup();
  render(<Harness initialRoute="chats" conversations={existingChats} />);
  const buttons = screen.getAllByRole("button", {
    name: "Opciones de Ya guardada",
  });
  await user.click(buttons[buttons.length - 1]);
  await user.click(screen.getByRole("menuitem", { name: "Abrir en panel" }));
  await screen.findByRole("complementary", { name: "Conversación lateral" });
  expect(location.hash).toBe("#chats");
  expect(store.get("dr-dock-a", {})).toMatchObject({ chatId: "existing" });
});
it("switches chats from navigation without leaving the report or losing the previous draft", async () => {
  location.hash = "report/sales";
  store.set("dr-dock-a", { chatId: "old", open: true });
  server();
  const user = userEvent.setup();
  render(<Harness initialRoute="report/sales" conversations={existingChats} />);
  await user.type(await screen.findByRole("textbox"), "Conservar borrador");
  await user.click(
    screen.getByRole("button", { name: "Abrir o cerrar navegación" }),
  );
  await user.click(
    screen.getByRole("button", { name: "Opciones de Ya guardada" }),
  );
  await user.click(screen.getByRole("menuitem", { name: "Abrir en panel" }));
  await screen.findByRole("complementary", { name: "Conversación lateral" });
  expect(location.hash).toBe("#report/sales");
  expect(await screen.findByRole("textbox")).toHaveValue("");
  expect(store.get(messageKey("old"), {})).toMatchObject({
    text: "Conservar borrador",
  });
  expect(store.get("dr-dock-a", {})).toMatchObject({ chatId: "existing" });
});

it("keeps the same dock, draft and attachments across all four sections", async () => {
  location.hash = "home";
  store.set("dr-dock-a", { chatId: "existing", open: true });
  const calls = server();
  const user = userEvent.setup();
  render(<Harness />);
  const panel = await screen.findByRole("complementary", {
    name: "Conversación lateral",
  });
  await user.type(
    await within(panel).findByRole("textbox"),
    "Explica la selección",
  );
  await user.click(screen.getByRole("link", { name: "Mi negocio" }));
  await user.click(screen.getByRole("button", { name: "Seleccionar" }));
  await user.click(
    await screen.findByRole("button", {
      name: "Seleccionar: Presentación de Negocio",
    }),
  );
  await user.keyboard("{Escape}");
  await user.click(screen.getByRole("link", { name: "Informes" }));
  expect(screen.getByRole("complementary")).toBe(panel);
  expect(within(panel).getByRole("textbox")).toHaveValue(
    "Explica la selección",
  );
  await user.click(screen.getByRole("button", { name: "Seleccionar" }));
  await user.click(
    screen.getByRole("button", { name: "Seleccionar: Informe de ventas" }),
  );
  expect(location.hash).toBe("#reports");
  await user.keyboard("{Escape}");
  await user.click(screen.getByRole("link", { name: "Conversaciones" }));
  expect(location.hash).toBe("#chats");
  expect(screen.getByRole("complementary")).toBe(panel);
  expect(within(panel).getByRole("textbox")).toHaveValue(
    "Explica la selección",
  );
  expect(
    within(panel).getByRole("button", { name: "Seleccionar" }),
  ).toBeInTheDocument();
  expect(
    within(panel).getAllByRole("button", { name: /Ver adjunto:/ }),
  ).toHaveLength(2);
  await user.click(screen.getByRole("link", { name: "Inicio" }));
  expect(screen.getByRole("complementary")).toBe(panel);
  await user.click(
    within(panel).getByRole("button", { name: "Enviar mensaje" }),
  );
  await within(panel).findByText("Ventas revisadas.");
  expect(calls.filter((c) => c.url === "/api/chats")).toHaveLength(0);
  expect(calls.filter((c) => c.url.endsWith("/messages"))).toEqual([
    expect.objectContaining({
      url: "/api/chats/existing/messages",
      data: expect.objectContaining({
        text: "Explica la selección",
        context_references: [
          {
            source_id: "a",
            source_version: "1",
            kind: "business",
            element_key: "profile",
          },
          {
            report_id: "review",
            report_version: "v1",
            kind: "report",
            element_key: "report",
          },
        ],
      }),
    }),
  ]);
});

it("attaches a conversation without opening it, keeps it across navigation and sends only the reference", async () => {
  location.hash = "chats";
  const calls = server();
  const user = userEvent.setup();
  const ref: ContextAttachment = {
    kind: "conversation",
    source_id: "previous",
    source_version: "2:version",
    element_key: "conversation",
    title: "Plan anterior",
    href: "#chat/previous",
    content: {
      key: "conversation",
      title: "Plan anterior",
      statement: "2 intercambios · Vista previa",
    },
  };
  render(
    <Harness
      initialRoute="chats"
      conversations={[
        {
          id: "previous",
          business_id: "a",
          title: "Plan anterior",
          created_at: "2026-09-27",
          context_reference: ref,
        },
      ]}
    />,
  );
  await user.click(screen.getByRole("button", { name: "Preguntar algo" }));
  const panel = screen.getByRole("complementary", {
    name: "Conversación lateral",
  });
  await user.click(within(panel).getByRole("button", { name: "Seleccionar" }));
  await user.click(
    screen.getByRole("button", { name: "Seleccionar: Plan anterior" }),
  );
  expect(location.hash).toBe("#chats");
  await user.keyboard("{Escape}");
  expect(
    within(panel).getByRole("button", { name: "Ver adjunto: Plan anterior" }),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "Informes" }));
  expect(screen.getByRole("complementary")).toBe(panel);
  await user.type(within(panel).getByRole("textbox"), "¿Qué decidimos?");
  await user.click(
    within(panel).getByRole("button", { name: "Enviar mensaje" }),
  );
  await within(panel).findByText("Ventas revisadas.");
  expect(
    calls.find((c) => c.url.endsWith("/messages"))?.data.context_references,
  ).toEqual([
    {
      kind: "conversation",
      source_id: "previous",
      source_version: "2:version",
      element_key: "conversation",
    },
  ]);
});
