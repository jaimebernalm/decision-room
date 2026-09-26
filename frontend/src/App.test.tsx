import { it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { Answer } from "./components/workspace/chat";
import { WorkspaceState, type WorkspaceContext } from "./lib/workspace";
const business = {
  id: "b",
  name: "Negocio de prueba",
  description: "Contexto",
  profile_revision: 1,
};
const ws = {
  business,
  businesses: [business],
  analyses: [],
  configured: true,
  memory: {},
};
const listing = {
  business_id: "b",
  conversations: [
    {
      id: "chat",
      business_id: "b",
      title: "Chat de prueba",
      created_at: "2026-09-26",
    },
  ],
  datasets: { items: [], more: false },
};
const context = {
  workspace: ws,
  listing,
  route: "home",
  refresh: vi.fn(),
  removeChat: vi.fn(),
} satisfies WorkspaceContext;
it("keeps one page and one assistant while navigating, preserving and clearing drafts", async () => {
  location.hash = "ask";
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () => (url === "/api/workspace" ? ws : listing),
    })),
  );
  render(<App />);
  await screen.findByRole("heading", { name: "¿Qué quieres entender hoy?" });
  const user = userEvent.setup();
  await user.type(screen.getByRole("textbox", { name: "Mensaje" }), "Borrador");
  await user.click(screen.getByRole("link", { name: "Ver conversaciones" }));
  await screen.findByRole("heading", { name: "Conversaciones" });
  expect(document.querySelectorAll("#main-content")).toHaveLength(1);
  expect(
    screen.queryByRole("heading", { name: "¿Qué quieres entender hoy?" }),
  ).toBeNull();
  expect(screen.getByRole("textbox", { name: "Mensaje" })).toHaveValue(
    "Borrador",
  );
  await user.clear(screen.getByRole("textbox", { name: "Mensaje" }));
  await user.click(screen.getAllByRole("link", { name: "Nuevo chat" })[0]);
  await screen.findByRole("heading", { name: "¿Qué quieres entender hoy?" });
  expect(document.querySelectorAll("#main-content")).toHaveLength(1);
  expect(
    screen.getAllByRole("region", { name: "Asistente del negocio" }),
  ).toHaveLength(1);
  expect(screen.getByRole("textbox", { name: "Mensaje" })).toHaveValue("");
});
it("keeps onboarding available with no business and supports form editing", async () => {
  location.hash = "home";
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ ...ws, business: null, businesses: [] }),
    })),
  );
  render(<App />);
  expect(
    await screen.findByRole("heading", { name: "Empecemos por tu negocio" }),
  ).toBeInTheDocument();
  await userEvent.type(
    screen.getByLabelText("Nombre del negocio"),
    "Mi tienda",
  );
  expect(screen.getByLabelText("Nombre del negocio")).toHaveValue("Mi tienda");
  expect(
    screen.queryByRole("heading", { name: "Una mirada clara a tu negocio." }),
  ).not.toBeInTheDocument();
});
it("opens a chat without a title header and returns to the conversation list with the arrow", async () => {
  location.hash = "chat/chat";
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url === "/api/workspace"
          ? ws
          : url === "/api/chats"
            ? listing
            : {
                conversation: listing.conversations[0],
                turns: [],
                reports: [],
                memory_items: [],
                memory: {},
              },
    })),
  );
  render(<App />);
  await screen.findByText("Escribe tu primera pregunta para empezar.");
  expect(screen.queryByRole("heading", { name: "Chat de prueba" })).toBeNull();
  expect(screen.getAllByRole("textbox", { name: "Mensaje" })).toHaveLength(1);
  const back = screen.getByRole("link", { name: "Volver a conversaciones" });
  expect(back).toHaveTextContent("");
  await userEvent.click(back);
  expect(
    await screen.findByRole("heading", { name: "Conversaciones" }),
  ).toBeInTheDocument();
});
it("delete dialog cancel makes no mutation and explicit delete refreshes the list", async () => {
  location.hash = "chats";
  const writes: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, options: RequestInit) => {
      if (options.method === "POST") writes.push(url);
      return {
        ok: true,
        json: async () =>
          url === "/api/workspace"
            ? ws
            : url === "/api/chats"
              ? listing
              : { saved: true },
      };
    }),
  );
  render(<App />);
  await screen.findByRole("heading", { name: "Conversaciones" });
  const user = userEvent.setup();
  await user.click(
    screen.getByRole("button", { name: "Eliminar Chat de prueba" }),
  );
  expect(await screen.findByRole("alertdialog")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Cancelar" }));
  expect(writes).toEqual([]);
  await user.click(
    screen.getByRole("button", { name: "Eliminar Chat de prueba" }),
  );
  await user.click(screen.getByRole("button", { name: "Eliminar chat" }));
  await waitFor(() => expect(writes).toEqual(["/api/chats/chat/delete"]));
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
});
it("shows historical memory greetings without dumping stored facts", () => {
  render(
    <WorkspaceState.Provider value={context}>
      <Answer
        ownerText="¡Hola!"
        response={{
          kind: "memory",
          text: "Memoria",
          items: [
            {
              status: "declared",
              content: {
                kind: "context",
                statement: "Detalle privado",
                scope: "business",
                scope_id: null,
                valid_from: null,
                valid_until: null,
                temporal_scope: "unspecified",
              },
            },
          ],
        }}
      />
    </WorkspaceState.Provider>,
  );
  expect(screen.getByText(/¡Hola!.*Negocio de prueba/)).toBeInTheDocument();
  expect(screen.queryByText("Detalle privado")).toBeNull();
});
it("renders prose safely and never turns model links or HTML into active external content", () => {
  render(
    <WorkspaceState.Provider value={context}>
      <Answer
        response={{
          kind: "grounded_answer",
          text: "**Ventas**\n\n- Un dato\n- <img src=x onerror=alert(1)>\n\n[fuera](https://example.test/private)",
          sources: [{ label: "<script>bad</script>", reference: "" }],
        }}
      />
    </WorkspaceState.Provider>,
  );
  expect(screen.getByText("Ventas")).toBeInTheDocument();
  expect(screen.getAllByRole("listitem").length).toBeGreaterThanOrEqual(2);
  expect(document.querySelector("img")).toBeNull();
  expect(document.querySelector('a[href^="https://"]')).toBeNull();
  expect(document.querySelector("script")).toBeNull();
});
