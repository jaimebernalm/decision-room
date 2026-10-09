import { expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { contextKey, homeDraftKey, messageKey, store } from "./lib/api";
import { reportStarter } from "./lib/chat-start";
import { ChatLoading } from "./components/workspace/chat-start";
import { ChatPage } from "./components/workspace/chat";
import { WorkspaceState, type WorkspaceContext } from "./lib/workspace";

const reduced = vi.hoisted(() => ({ value: false }));
vi.mock("motion/react", async (importOriginal) => ({
  ...(await importOriginal<typeof import("motion/react")>()),
  useReducedMotion: () => reduced.value,
}));

const business = {
  id: "starter",
  name: "Tienda",
  description: "Prueba",
  profile_revision: 1,
};
function server(failFirst = false) {
  const writes: { url: string; body: Record<string, unknown> }[] = [];
  let text = "";
  let sends = 0;
  let reportRequested = false;
  const conversation = {
    id: "saved",
    business_id: business.id,
    title: "Mi pregunta",
    created_at: "2026-10-08",
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        writes.push({ url, body });
        if (url.endsWith("/messages")) {
          if (failFirst && ++sends === 1)
            return {
              ok: false,
              status: 503,
              json: async () => ({ error: "Vuelve a intentarlo" }),
            };
          text = body.text;
        }
        if (url.endsWith("/report")) reportRequested = true;
        return {
          ok: true,
          json: async () =>
            url === "/api/chats" ? conversation : { id: "turn", saved: true },
        };
      }
      return {
        ok: true,
        json: async () =>
          url === "/api/workspace"
            ? {
                business,
                businesses: [business],
                analyses: [],
                configured: true,
                memory: {},
              }
            : url === "/api/chats"
              ? {
                  business_id: business.id,
                  conversations: text ? [conversation] : [],
                  datasets: { items: [], more: false },
                }
              : {
                  conversation,
                  turns: text
                    ? [
                        {
                          id: "turn",
                          payload: { text },
                          status: "completed",
                          response: {
                            kind: "answer",
                            text: "Resultado disponible.",
                            report_id: "review",
                          },
                          report_requested: reportRequested,
                        },
                      ]
                    : [],
                  memory: {},
                  memory_items: [],
                },
      };
    }),
  );
  return writes;
}

it("offers editable suggestions without requests and preserves a custom draft", async () => {
  location.hash = "ask";
  const writes = server();
  render(<App />);
  const user = userEvent.setup();
  const input = await screen.findByRole("textbox", { name: "Mensaje" });
  expect(input).toHaveFocus();
  expect(screen.getAllByRole("textbox", { name: "Mensaje" })).toHaveLength(1);
  await user.click(screen.getByRole("button", { name: "Analizar mis datos" }));
  expect(input).toHaveValue("Quiero analizar los datos de mi negocio. ");
  await user.click(
    screen.getByRole("button", { name: "Resolver una pregunta" }),
  );
  expect(input).toHaveValue("");
  await user.type(input, "¿Qué productos funcionan mejor?");
  await user.click(screen.getByRole("button", { name: "Ayúdame a empezar" }));
  expect(input).toHaveValue("¿Qué productos funcionan mejor?");
  expect(input).toHaveFocus();
  expect(writes).toEqual([]);
  expect(
    screen.queryByText(/predicciones|machine learning|investigar online/i),
  ).toBeNull();
  await user.click(screen.getByRole("link", { name: "Nuevo chat" }));
  expect(input).not.toBeInTheDocument();
  await waitFor(() =>
    expect(
      screen.getByRole("heading", { name: "¿En qué te ayudo con tu negocio?" }),
    ).toBeVisible(),
  );
  expect(screen.getByRole("textbox", { name: "Mensaje" })).toHaveValue("");
});

it("starts the first report in the same editable conversation without requiring an upload", async () => {
  location.hash = "reports";
  const writes = server();
  render(<App />);
  await userEvent.click(
    await screen.findByRole("link", { name: "Crear mi primer informe" }),
  );
  await waitFor(() =>
    expect(
      screen.getByRole("heading", {
        name: "¿Qué quieres que incluya el informe?",
      }),
    ).toBeVisible(),
  );
  expect(location.hash).toBe("#ask/report");
  expect(screen.getByRole("textbox", { name: "Mensaje" })).toHaveValue(
    reportStarter,
  );
  expect(screen.getAllByRole("textbox", { name: "Mensaje" })).toHaveLength(1);
  expect(screen.getByRole("link", { name: "Añadir datos" })).toHaveAttribute(
    "href",
    "#files",
  );
  expect(document.querySelector('input[type="file"]')).not.toBeRequired();
  expect(writes).toEqual([]);
});

it.each(["new", "ask/report"])(
  "preserves a draft and a single focused composer on the %s report entry",
  async (route) => {
    location.hash = route;
    store.set(
      homeDraftKey(business.id),
      "Comparar las ventas de agosto y septiembre",
    );
    const writes = server();
    render(<App />);
    const input = await screen.findByRole("textbox", { name: "Mensaje" });
    await waitFor(() =>
      expect(
        screen.getByRole("heading", {
          name: "¿Qué quieres que incluya el informe?",
        }),
      ).toBeVisible(),
    );
    expect(input).toHaveValue("Comparar las ventas de agosto y septiembre");
    expect(input).toHaveFocus();
    expect(screen.getAllByRole("textbox", { name: "Mensaje" })).toHaveLength(1);
    expect(
      screen.queryByRole("complementary", { name: "Chat lateral" }),
    ).toBeNull();
    expect(writes).toEqual([]);
  },
);

it("retries a failed starter send in the same saved chat and retains the report action", async () => {
  location.hash = "ask";
  store.set(contextKey(business.id), { analysis_id: "sales", label: "Ventas" });
  const writes = server(true);
  const user = userEvent.setup();
  render(<App />);
  const input = await screen.findByRole("textbox", { name: "Mensaje" });
  await user.type(input, "¿Qué ha cambiado?");
  await user.click(screen.getByRole("button", { name: "Enviar mensaje" }));
  await screen.findByText("Vuelve a intentarlo");
  expect(input).toHaveValue("¿Qué ha cambiado?");
  expect(location.hash).toBe("#ask");
  await user.click(screen.getByRole("button", { name: "Enviar mensaje" }));
  await screen.findByText("Resultado disponible.");
  expect(location.hash).toBe("#chat/saved");
  expect(screen.getAllByRole("textbox", { name: "Mensaje" })).toHaveLength(1);
  expect(screen.getByRole("textbox", { name: "Mensaje" })).toHaveValue("");
  expect(writes.filter((write) => write.url === "/api/chats")).toHaveLength(1);
  expect(writes[0].body).toMatchObject({
    business_id: business.id,
    analysis_id: "sales",
  });
  const messages = writes.filter((write) => write.url.endsWith("/messages"));
  expect(messages).toHaveLength(2);
  expect(messages[0].body).toEqual(messages[1].body);
  expect(messages[1].body).toMatchObject({
    business_id: business.id,
    text: "¿Qué ha cambiado?",
  });
  expect(store.get(homeDraftKey(business.id), "")).toBe("");
  await user.click(screen.getByRole("button", { name: "Crear informe" }));
  await waitFor(() =>
    expect(screen.getByRole("link", { name: "Abrir informe" })).toHaveAttribute(
      "href",
      "#chat-report/saved/turn",
    ),
  );
  expect(writes.at(-1)).toMatchObject({
    url: "/api/chats/saved/report",
    body: { business_id: business.id, turn_id: "turn" },
  });
});

it("makes the starter immediately visible when reduced motion is preferred", async () => {
  reduced.value = true;
  try {
    location.hash = "ask";
    server();
    render(<App />);
    const input = await screen.findByRole("textbox", { name: "Mensaje" });
    expect(input).toHaveFocus();
    expect(
      screen.getByRole("heading", { name: "¿En qué te ayudo con tu negocio?" }),
    ).toBeVisible();
    expect(
      screen.getByRole("group", { name: "Ideas para empezar" }),
    ).toBeVisible();
    expect(screen.getAllByRole("textbox", { name: "Mensaje" })).toHaveLength(1);
  } finally {
    reduced.value = false;
  }
});

it("preserves typing while the conversation module loads", async () => {
  const writes = server();
  const context: WorkspaceContext = {
    workspace: {
      business,
      businesses: [business],
      analyses: [],
      configured: true,
      memory: {},
    },
    listing: {
      business_id: business.id,
      conversations: [],
      datasets: { items: [], more: false },
    },
    route: "chat/saved",
    refresh: vi.fn(),
    removeChat: vi.fn(),
  };
  const view = render(
    <WorkspaceState.Provider value={context}>
      <ChatLoading />
    </WorkspaceState.Provider>,
  );
  await userEvent.type(
    screen.getByRole("textbox", { name: "Mensaje" }),
    "Mi siguiente pregunta",
  );
  expect(screen.getByRole("button", { name: "Enviar mensaje" })).toBeDisabled();
  expect(store.get(messageKey("saved"), { text: "" }).text).toBe(
    "Mi siguiente pregunta",
  );
  view.rerender(
    <WorkspaceState.Provider value={context}>
      <ChatPage id="saved" />
    </WorkspaceState.Provider>,
  );
  await screen.findByText("Escribe tu primera pregunta para empezar.");
  expect(screen.getAllByRole("textbox", { name: "Mensaje" })).toHaveLength(1);
  expect(screen.getByRole("textbox", { name: "Mensaje" })).toHaveValue(
    "Mi siguiente pregunta",
  );
  expect(writes).toEqual([]);
});
