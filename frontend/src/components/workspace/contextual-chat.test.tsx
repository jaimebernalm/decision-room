import { useEffect, useState } from "react";
import { it, expect, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import { WorkspaceState, type WorkspaceContext } from "@/lib/workspace";
import { store } from "@/lib/api";
import type { ContextAttachment } from "@/lib/types";
import { Selectable } from "./context-selection";
import { FloatingAssistant } from "./floating-assistant";
import { ChatPage } from "./chat";
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
    analyses: [],
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
function Harness() {
  const [route, setRoute] = useState("home");
  useEffect(() => {
    const change = () => setRoute(location.hash.slice(1));
    addEventListener("hashchange", change);
    return () => removeEventListener("hashchange", change);
  }, []);
  return (
    <TooltipProvider>
      <WorkspaceState.Provider value={{ ...workspace, route }}>
        <Layout>
          {route.startsWith("chat/") ? (
            <ChatPage id={route.split("/")[1]} />
          ) : (
            <>
              <div id="main-content">
                <Selectable item={item}>
                  <p>Ventas: 80 EUR</p>
                </Selectable>
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
      if (url === "/api/chats") {
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
it("selects context, opens a dock, expands the same chat and recovers attachments after remount", async () => {
  location.hash = "home";
  const calls = server();
  const user = userEvent.setup();
  const mounted = render(<Harness />);
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
