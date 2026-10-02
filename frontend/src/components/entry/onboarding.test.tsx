import { it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "@/App";
import type { Business, Workspace } from "@/lib/types";

const business: Business = {
  id: "new-business",
  name: "Papelería de prueba",
  description: "Vendemos material escolar.",
  profile_revision: 1,
  onboarding_status: "context_saved",
};
const empty: Workspace = {
  business: null,
  businesses: [],
  analyses: [],
  configured: true,
  memory: {},
};
const saved: Workspace = { ...empty, business, businesses: [business] };
const listing = (ws: Workspace) => ({
  business_id: ws.business?.id || null,
  conversations: [],
  datasets: { items: [], more: false },
});
const response = (data: unknown, status = 200) => ({
  ok: status === 200,
  status,
  json: async () => data,
});

it("shows the welcome page without authentication and preserves start intent through login", async () => {
  location.hash = "home";
  let authenticated = false;
  const fetch = vi.fn(async (url: string, options: RequestInit) => {
    if (url === "/api/login" && options.method === "POST") {
      authenticated = true;
      return response({ ok: true });
    }
    return authenticated
      ? response(empty)
      : response({ error: "Acceso requerido" }, 401);
  });
  vi.stubGlobal("fetch", fetch);
  render(<App />);
  await screen.findByRole("heading", {
    name: "Tus datos tienen mucho que contarte.",
  });
  expect(screen.queryByRole("link", { name: "Nuevo chat" })).toBeNull();
  const user = userEvent.setup();
  await user.click(screen.getByRole("link", { name: "Empezar" }));
  await user.type(
    await screen.findByLabelText("Clave de acceso"),
    "synthetic-test-key",
  );
  await user.click(screen.getByRole("button", { name: "Abrir mi espacio" }));
  await screen.findByRole("heading", { name: "Cuéntanos sobre tu negocio" });
  expect(
    fetch.mock.calls
      .filter(([, options]) => options.method === "POST")
      .map(([url]) => url),
  ).toEqual(["/api/login"]);
});

it("lets an existing owner view the new experience without changing the active business", async () => {
  location.hash = "welcome";
  const fetch = vi.fn(async (url: string) =>
    response(url === "/api/workspace" ? saved : listing(saved)),
  );
  vi.stubGlobal("fetch", fetch);
  render(<App />);
  await screen.findByRole("link", { name: "Mi espacio" });
  await userEvent.click(screen.getByRole("link", { name: "Empezar" }));
  await screen.findByRole("heading", { name: "Cuéntanos sobre tu negocio" });
  expect(screen.getByLabelText("Nombre del negocio")).toHaveValue("");
  expect(screen.queryByRole("link", { name: "Nuevo chat" })).toBeNull();
  expect(screen.queryByText("Cambiar de negocio")).toBeNull();
  expect(screen.queryByRole("link", { name: "Bienvenida" })).toBeNull();
  expect(fetch.mock.calls.some(([url]) => url === "/api/business")).toBe(false);
});

it("blocks a stale onboarding URL belonging to another business", async () => {
  location.hash = "onboarding/another-business";
  const fetch = vi.fn(async (url: string) =>
    response(url === "/api/workspace" ? saved : listing(saved)),
  );
  vi.stubGlobal("fetch", fetch);
  render(<App />);
  await screen.findByText(/El negocio activo ha cambiado/);
  expect(screen.queryByLabelText("Archivos CSV o Excel")).toBeNull();
  expect(screen.queryByRole("link", { name: "Nuevo chat" })).toBeNull();
});

it("opens a published first report in the workspace", async () => {
  location.hash = `onboarding/${business.id}/report/ready`;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      response(
        url === "/api/workspace"
          ? saved
          : url === "/api/chats"
            ? listing(saved)
            : url === "/api/jobs/ready"
              ? {
                  id: "ready",
                  title: "Primer informe",
                  publishable: true,
                  status: "completed",
                  files: [],
                  answers: [],
                  interpretations: [],
                }
              : {
                  title: "Mi primer resultado",
                  scope: {
                    period: "Septiembre",
                    coverage: "Ventas disponibles",
                  },
                  highlights: [],
                  charts: [],
                  claims: [],
                  limitations: [],
                },
      ),
    ),
  );
  render(<App />);
  await screen.findByRole("heading", { name: "Mi primer resultado" });
  await waitFor(() => expect(location.hash).toBe("#report/ready"));
  expect(screen.getByRole("link", { name: "Nuevo chat" })).toBeInTheDocument();
});

it("recovers a lost business creation response after reload without creating a second business", async () => {
  location.hash = "onboarding";
  let ws = empty;
  const writes: Record<string, unknown>[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, options: RequestInit) => {
      if (url === "/api/workspace") return response(ws);
      if (url === "/api/chats") return response(listing(ws));
      if (url === "/api/onboarding/start" || url === "/api/onboarding/session")
        return response({
          business_id: business.id,
          conversation_id: "setup-chat",
          revision: 1,
          stage: "goal",
          goal: {},
        });
      if (url === "/api/chats/setup-chat")
        return response({
          conversation: { id: "setup-chat" },
          turns: [],
          memory_items: [],
        });
      if (url === "/api/business") {
        writes.push(JSON.parse(options.body as string));
        ws = saved;
        if (writes.length === 1) throw new Error("Lost response after commit");
        return response({ business });
      }
      throw new Error(`Unexpected request ${url}`);
    }),
  );
  const first = render(<App />);
  const user = userEvent.setup();
  await user.type(
    await screen.findByLabelText("Nombre del negocio"),
    business.name,
  );
  await user.type(
    screen.getByLabelText("Cuéntanos qué haces"),
    business.description,
  );
  await user.click(
    screen.getByRole("button", { name: "Nuevo chat" }),
  );
  await screen.findByText(
    "No hay conexión con el servidor local. Tu progreso guardado se conserva.",
  );
  first.unmount();
  render(<App />);
  expect(await screen.findByLabelText("Nombre del negocio")).toHaveValue(
    business.name,
  );
  await user.click(
    screen.getByRole("button", { name: "Nuevo chat" }),
  );
  await screen.findByRole("heading", { name: /Qué te gustaría conseguir/ });
  expect(writes).toHaveLength(2);
  expect(writes[1]).toEqual(writes[0]);
  expect(writes[1].expected_active_id).toBeNull();
});
