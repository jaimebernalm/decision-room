import { it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "@/App";
import { store } from "@/lib/api";
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
  expect(
    screen.queryByRole("link", { name: "Bienvenida" }),
  ).toBeNull();
  expect(fetch.mock.calls.some(([url]) => url === "/api/business")).toBe(false);
});

it("creates a business, keeps the CSV when going back, and retries a lost upload with the same request key", async () => {
  location.hash = "onboarding";
  let ws = empty;
  const finished = new Set<string>();
  const uploads: Record<string, unknown>[] = [];
  const profiles: Record<string, unknown>[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, options: RequestInit) => {
      if (url === "/api/workspace") return response(ws);
      if (url === "/api/chats") return response(listing(ws));
      if (url === "/api/business") {
        profiles.push(JSON.parse(options.body as string));
        ws = saved;
        return response({ business });
      }
      if (url === "/api/datasets/bundles") {
        const body = JSON.parse(options.body as string);
        return response(
          finished.has(body.request_key)
            ? { files: [], result: { analysis_id: "source", status: "ready" } }
            : {
                files: body.files.map(
                  (file: { path: string; size: number }) => ({
                    ...file,
                    uploaded: 0,
                  }),
                ),
              },
        );
      }
      if (url.includes("/files/0")) return response({ uploaded: 26 });
      if (url.endsWith("/finish")) {
        finished.add(url.split("/")[4]);
        return response({ analysis_id: "source", status: "ready" });
      }
      if (url === "/api/jobs/from-dataset") {
        uploads.push(JSON.parse(options.body as string));
        if (uploads.length === 1) throw new Error("Lost response");
        return response({ id: "first-job" });
      }
      if (url === "/api/jobs/first-job")
        return response({
          id: "first-job",
          business_id: business.id,
          title: "Primer informe",
          filename: "ventas.csv",
          status: "waiting",
          publishable: false,
          questions: [
            {
              id: "q",
              text: "¿Los importes incluyen impuestos?",
              reason: "Para interpretar las ventas.",
            },
          ],
          files: [],
          answers: [],
          interpretations: [],
        });
      throw new Error(`Unexpected request ${url}`);
    }),
  );
  render(<App />);
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
    screen.getByRole("button", { name: "Continuar con mis datos" }),
  );
  await screen.findByRole("heading", { name: "Ahora, comparte tus datos" });
  expect(profiles).toHaveLength(1);
  expect(profiles[0].expected_active_id).toBeNull();
  expect(uploads).toHaveLength(0);
  history.back();
  await screen.findByRole("heading", { name: "Cuéntanos sobre tu negocio" });
  expect(screen.getByLabelText("Nombre del negocio")).toHaveValue(
    business.name,
  );
  await user.click(
    screen.getByRole("button", { name: "Continuar con mis datos" }),
  );
  await screen.findByRole("heading", { name: "Ahora, comparte tus datos" });
  const file = new File(["date,amount\n2026-01-01,10\n"], "ventas.csv", {
    type: "text/csv",
  });
  await user.upload(screen.getByLabelText("Archivos CSV o Excel"), file);
  await user.type(
    screen.getByLabelText("¿Qué te gustaría entender? (opcional)"),
    "Entender mis ventas",
  );
  await user.click(screen.getByRole("link", { name: "Tu negocio" }));
  await screen.findByRole("heading", { name: "Cuéntanos sobre tu negocio" });
  expect(screen.getByLabelText("Cuéntanos qué haces")).toHaveValue(
    business.description,
  );
  await user.click(
    screen.getByRole("button", { name: "Continuar con mis datos" }),
  );
  await screen.findByRole("heading", { name: "Ahora, comparte tus datos" });
  expect(screen.getByText(/1 archivo ·/)).toBeInTheDocument();
  expect(
    screen.getByLabelText("¿Qué te gustaría entender? (opcional)"),
  ).toHaveValue("Entender mis ventas");
  await user.click(screen.getByRole("button", { name: "Continuar" }));
  await screen.findByRole("heading", {
    name: "Vamos a crear tu primer informe",
  });
  expect(uploads).toHaveLength(0);
  await user.click(
    screen.getByRole("button", { name: "Crear mi primer informe" }),
  );
  await screen.findByText(
    "No hay conexión con el servidor local. Tu progreso guardado se conserva.",
  );
  await user.click(
    screen.getByRole("button", { name: "Crear mi primer informe" }),
  );
  await screen.findByRole("heading", {
    name: "Una aclaración antes de continuar",
  });
  expect(uploads).toHaveLength(2);
  expect(uploads[1]).toEqual(uploads[0]);
  expect(uploads[0].business_id).toBe(business.id);
  expect(profiles[1].business_id).toBe(business.id);
  expect(screen.queryByRole("link", { name: "Nuevo chat" })).toBeNull();
  expect(
    screen.getByText("¿Los importes incluyen impuestos?"),
  ).toBeInTheDocument();
});

it("resumes saved context after reload and explicitly asks to reselect an unsent file", async () => {
  location.hash = "home";
  store.set(`dr-onboarding-upload-${business.id}`, {
    title: "Mi informe",
    goal: "Ventas",
    filename: "pendiente.csv",
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      response(url === "/api/workspace" ? saved : listing(saved)),
    ),
  );
  render(<App />);
  await screen.findByRole("heading", { name: "Ahora, comparte tus datos" });
  expect(
    screen.getByText(/Vuelve a seleccionar tus archivos/),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Continuar" })).toBeDisabled();
  expect(
    screen.getByLabelText("¿Qué te gustaría entender? (opcional)"),
  ).toHaveValue("Ventas");
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
  expect(screen.getByRole("button", { name: "Nuevo chat" })).toBeInTheDocument();
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
    screen.getByRole("button", { name: "Continuar con mis datos" }),
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
    screen.getByRole("button", { name: "Continuar con mis datos" }),
  );
  await screen.findByRole("heading", { name: "Ahora, comparte tus datos" });
  expect(writes).toHaveLength(2);
  expect(writes[1]).toEqual(writes[0]);
  expect(writes[1].expected_active_id).toBeNull();
});

it("accepts a mixed folder, identifies omitted and failed files, and continues with a partial dataset", async () => {
  location.hash = `onboarding/${business.id}`;
  const manifests: { files: { path: string; size: number }[] }[] = [];
  const jobs: Record<string, unknown>[] = [];
  let finished = false;
  const result = { analysis_id: "partial-source", status: "partial" };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, options: RequestInit) => {
      if (url === "/api/workspace") return response(saved);
      if (url === "/api/chats") return response(listing(saved));
      if (url === "/api/datasets/bundles") {
        const body = JSON.parse(options.body as string);
        manifests.push(body);
        return response(
          finished
            ? { files: [], result }
            : {
                files: body.files.map(
                  (file: { path: string; size: number }) => ({
                    ...file,
                    uploaded: 0,
                  }),
                ),
              },
        );
      }
      if (url.includes("/files/")) return response({});
      if (url.endsWith("/finish")) {
        finished = true;
        return response(result);
      }
      if (url === "/api/business/dossier")
        return response({
          business_id: business.id,
          datasets: [
            {
              id: "partial-source",
              status: "partial",
              files: [
                { id: "good", name: "carpeta/ventas.csv", status: "ready" },
                { id: "bad", name: "carpeta/roto.xlsx", status: "failed" },
              ],
            },
          ],
        });
      if (url === "/api/jobs/from-dataset") {
        jobs.push(JSON.parse(options.body as string));
        return response({ id: "partial-job" });
      }
      if (url === "/api/jobs/partial-job")
        return response({
          id: "partial-job",
          business_id: business.id,
          status: "waiting",
          publishable: false,
          title: "Primer informe",
          filename: "ventas.csv",
          files: [],
          answers: [],
          interpretations: [],
          questions: [],
        });
      throw new Error(`Unexpected request ${url}`);
    }),
  );
  render(<App />);
  await screen.findByRole("heading", { name: "Ahora, comparte tus datos" });
  const user = userEvent.setup({ applyAccept: false });
  const files = [
    new File(["date,amount\n2026-01-01,10"], "ventas.csv"),
    new File(["broken"], "roto.xlsx"),
    new File(["notes"], "notas.txt"),
  ];
  files.forEach((file) =>
    Object.defineProperty(file, "webkitRelativePath", {
      value: `carpeta/${file.name}`,
    }),
  );
  await user.upload(screen.getByLabelText("Carpeta de datos"), files);
  expect(screen.getByText(/1 archivo omitido/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Continuar" }));
  await user.click(
    await screen.findByRole("button", { name: "Crear mi primer informe" }),
  );
  await screen.findByText("Algunos archivos no se pudieron preparar");
  expect(
    screen.getByText("carpeta/roto.xlsx · No se incluirá"),
  ).toBeInTheDocument();
  expect(
    screen.getByText("carpeta/ventas.csv · Disponible"),
  ).toBeInTheDocument();
  expect(manifests[0].files.map((file) => file.path)).toEqual([
    "carpeta/ventas.csv",
    "carpeta/roto.xlsx",
  ]);
  expect(jobs).toHaveLength(0);
  await user.click(
    screen.getByRole("button", {
      name: "Continuar con las tablas disponibles",
    }),
  );
  await screen.findByRole("heading", {
    name: "Una aclaración antes de continuar",
  });
  expect(jobs).toHaveLength(1);
  expect(jobs[0].analysis_id).toBe("partial-source");
});
