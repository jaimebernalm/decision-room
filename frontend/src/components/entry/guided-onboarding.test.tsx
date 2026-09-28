import { expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "@/App";
import type {
  Business,
  ChatDetail,
  SetupSession,
  Workspace,
} from "@/lib/types";

const business: Business = {
  id: "business",
  name: "Papelería",
  description: "Vendemos material escolar en Sevilla.",
  profile_revision: 1,
  onboarding_status: "context_saved",
};
const brief = {
  objective: "Comparar ventas",
  business_summary: "Papelería en Sevilla",
  questions: ["¿Cómo cambian las ventas?"],
  limitations: ["No incluye gastos generales"],
};
const response = (data: unknown) => ({
  ok: true,
  status: 200,
  json: async () => data,
});
function fixture(stage: SetupSession["stage"] = "goal") {
  const state: SetupSession = {
    business_id: business.id,
    conversation_id: "chat",
    revision: 1,
    stage,
    goal:
      stage === "goal"
        ? {}
        : { text: "Comparar ventas", choices: ["evolution"] },
    ...(stage === "scope" ? { analysis_id: "dataset", brief } : {}),
  };
  const chat: ChatDetail = {
    conversation: {
      id: "chat",
      business_id: business.id,
      title: "Primer análisis",
      created_at: "",
    },
    memory: {},
    memory_items: [],
    turns: [
      {
        id: "intro",
        status: "completed",
        payload: { text: business.description },
        response: {
          kind: "grounded_answer",
          text: "Elige qué te gustaría conseguir.",
        },
      },
    ],
  };
  const ws: Workspace = {
    business,
    businesses: [business],
    configured: true,
    memory: {},
    analyses: [],
    setup: { conversation_id: "chat", stage },
  };
  const writes: { url: string; body: Record<string, unknown> }[] = [];
  let lostMessage = false;
  let lost = false,
    partial = false,
    bundleFinished = false;
  const fetch = vi.fn(async (url: string, options: RequestInit) => {
    const body =
      options.method === "POST" && typeof options.body === "string"
        ? JSON.parse(options.body)
        : {};
    if (options.method === "POST") writes.push({ url, body });
    if (url === "/api/workspace") return response(ws);
    if (url === "/api/chats")
      return response({
        business_id: business.id,
        conversations: [chat.conversation],
        datasets: { items: [], more: false },
      });
    if (url === "/api/onboarding/session" || url === "/api/onboarding/start")
      return response({ ...state });
    if (url === "/api/jobs/job/presentation")
      return response({
        title: "Informe revisado de prueba",
        summary: "Resultados guardados",
        scope: {
          business: "Papelería",
          question: "Comparar ventas",
          period: "Julio",
          coverage: "Datos compartidos",
        },
        highlights: [],
        claims: [],
        charts: [],
        limitations: [],
        no_chart_reason: "Sin gráfico",
      });
    if (url.startsWith("/api/jobs/job/activity")) return response({schema_version:1,trace_id:"job-trace",status:"running",headline:"Contrastando los resultados",terminal:false,history_complete:true,task_updates:[],active_tasks:[],events:[],next_cursor:"job-trace:0",previous_cursor:null,has_more:false,worker_health:"live"});
    if (url === "/api/jobs/job")
      return response({
        id: "job",
        status: "running",
        context: "Papelería en Sevilla",
        goal: "Comparar ventas",
        activity: "Contrastando los resultados",
        publishable: false,
      });
    if (url === "/api/chats/chat") return response(structuredClone(chat));
    if (url === "/api/onboarding/change") {
      if (lost) {
        lost = false;
        throw new Error("Response lost");
      }
      if (body.action === "goal") {
        state.goal = { text: body.text, choices: body.choices };
        state.stage = state.analysis_id ? "scope" : "data";
        state.brief = undefined;
      }
      if (body.action === "data") {
        state.analysis_id = body.analysis_id;
        state.stage = "scope";
        state.brief = brief;
      }
      if (body.action === "confirm") {
        state.stage = "report";
        state.job_id = "job";
      }
      if (body.action === "complete") state.stage = "complete";
      state.revision++;
      ws.setup!.stage = state.stage;
      return response({ ...state });
    }
    if (url === "/api/chats/chat/messages") {
      if (lostMessage) {
        lostMessage = false;
        throw new Error("Response lost");
      }
      return response({ id: "answer" });
    }
    if (url.startsWith("/api/onboarding/data?"))
      return response({
        tables: [
          { id: "table", name: "ventas.csv", row_count: 2, column_count: 1 },
        ],
        table_id: "table",
        columns: ["amount"],
        rows: [{ number: 1, values: ["10"] }],
        offset: 0,
        column_offset: 0,
        page_rows: 50,
        page_columns: 12,
      });
    if (url === "/api/datasets/bundles")
      return response(
        bundleFinished
          ? {
              files: [],
              result: {
                analysis_id: "dataset",
                status: partial ? "partial" : "ready",
              },
            }
          : {
              files: body.files.map((f: { path: string; size: number }) => ({
                ...f,
                uploaded: 0,
              })),
              result: null,
            },
      );
    if (/\/files\/\d+$/.test(url)) return response({ uploaded: 10 });
    if (url.endsWith("/finish")) {
      bundleFinished = true;
      return response({
        analysis_id: "dataset",
        status: partial ? "partial" : "ready",
      });
    }
    if (url === "/api/business/dossier")
      return response({
        business_id: business.id,
        datasets: [
          {
            id: "dataset",
            files: [
              { id: "good", name: "ventas.csv", status: "ready" },
              { id: "bad", name: "roto.csv", status: "failed" },
            ],
          },
        ],
      });
    throw new Error(`Unexpected ${url}`);
  });
  vi.stubGlobal("fetch", fetch);
  location.hash = `onboarding/${business.id}`;
  return {
    state,
    chat,
    writes,
    fetch,
    loseMessage: () => {
      lostMessage = true;
    },
    loseNext: () => {
      lost = true;
    },
    partial: () => {
      partial = true;
    },
  };
}

it("resumes the conversation and combines goal options with free text", async () => {
  const f = fixture();
  render(<App />);
  const user = userEvent.setup();
  await screen.findByRole("heading", { name: /Qué te gustaría conseguir/ });
  expect(screen.getByText(business.description)).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Bienvenida" })).toBeNull();
  await user.click(
    screen.getByRole("button", { name: "Descubrir oportunidades y problemas" }),
  );
  await user.click(
    screen.getByRole("button", { name: "Tener mis cifras organizadas" }),
  );
  await user.type(
    screen.getByLabelText("Lo que me gustaría conseguir"),
    "Priorizar productos con poco margen",
  );
  await user.click(screen.getByRole("button", { name: "Guardar objetivo" }));
  await screen.findByLabelText("Archivos del negocio");
  expect(f.state.goal).toEqual({
    text: "Priorizar productos con poco margen",
    choices: ["discover", "organize"],
  });
});

it("opens the referenced column and sends explicit unknown disposition", async () => {
  const f = fixture("scope");
  f.chat.turns[0].response = {
    kind: "grounded_answer",
    text: "¿El importe es unitario?",
    onboarding: {
      question: {
        text: "¿El importe es unitario?",
        reason: "Cambia el cálculo",
        optional: false,
        references: [{ kind: "column", id: "table", column: "amount" }],
      },
      brief: null,
    },
  };
  render(<App />);
  await screen.findByRole("columnheader", {
    name: "amount (mencionada en la pregunta)",
  });
  expect(screen.queryByRole("button", { name: "Omitir por ahora" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "No lo sé" }));
  await waitFor(() =>
    expect(f.writes.some((w) => w.body.disposition === "unknown")).toBe(true),
  );
  expect(
    f.fetch.mock.calls.some(
      ([url]) => url.includes("table=table") && url.includes("column=amount"),
    ),
  ).toBe(true);
});

it("optional context is skippable and does not disable confirmation", async () => {
  const f = fixture("scope");
  f.chat.turns[0].response!.onboarding = {
    question: {
      text: "¿Hubo una campaña?",
      reason: "Ayuda a interpretar",
      optional: true,
      references: [],
    },
    brief,
  };
  render(<App />);
  expect(
    await screen.findByRole("button", { name: "Crear mi informe" }),
  ).toBeEnabled();
  await userEvent.click(
    screen.getByRole("button", { name: "Omitir por ahora" }),
  );
  await waitFor(() =>
    expect(f.writes.some((w) => w.body.disposition === "declined")).toBe(true),
  );
});

it("retries lost confirmation with the same request key", async () => {
  const f = fixture("scope");
  f.loseNext();
  render(<App />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Crear mi informe" }),
  );
  await screen.findByText(/No hay conexión/);
  await userEvent.click(
    screen.getByRole("button", { name: "Crear mi informe" }),
  );
  await screen.findByText("Estamos preparando tu informe");
  const writes = f.writes.filter((w) => w.body.action === "confirm");
  expect(writes).toHaveLength(2);
  expect(writes[0].body).toEqual(writes[1].body);
});

it("requires explicit acceptance of partial uploads", async () => {
  const f = fixture("data");
  f.partial();
  render(<App />);
  const user = userEvent.setup();
  await user.upload(
    await screen.findByLabelText("Archivos del negocio"),
    new File(["amount\n10\n"], "ventas.csv", { type: "text/csv" }),
  );
  await user.click(screen.getByRole("button", { name: "Compartir archivos" }));
  await screen.findByText("roto.csv: failed");
  expect(f.writes.some((w) => w.body.action === "data")).toBe(false);
  await user.click(
    screen.getByRole("button", {
      name: "Continuar con los archivos preparados",
    }),
  );
  await screen.findByRole("heading", {
    name: "Esto es lo que vamos a analizar",
  });
  expect(f.state.analysis_id).toBe("dataset");
});

it("edits scope through the same conversation before confirming", async () => {
  const f = fixture("scope");
  render(<App />);
  const user = userEvent.setup();
  await user.click(await screen.findByText("Editar el alcance"));
  await user.type(
    screen.getByLabelText("¿Qué quieres cambiar?"),
    "Solo el canal online",
  );
  await user.click(
    screen.getByRole("button", { name: "Actualizar propuesta" }),
  );
  await waitFor(() =>
    expect(
      f.writes.some(
        (w) =>
          w.url === "/api/chats/chat/messages" &&
          w.body.text === "Quiero cambiar el alcance: Solo el canal online",
      ),
    ).toBe(true),
  );
  expect(f.writes.some((w) => w.body.action === "confirm")).toBe(false);
});

it("continues in the same chat after the reviewed report", async () => {
  const f = fixture("report");
  f.state.job_id = "job";
  f.state.publishable = true;
  render(<App />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Abrir informe" }),
  );
  await screen.findByRole("heading", { name: "Informe revisado de prueba" });
  expect(location.hash).toBe("#onboarding/business");
  await userEvent.click(
    screen.getByRole("button", { name: "Continuar en mi espacio" }),
  );
  await waitFor(() => expect(location.hash).toBe("#chat/chat"));
  expect(f.state.stage).toBe("complete");
});

it("distinguishes a stale completed report from ongoing work", async () => {
  const f = fixture("complete");
  f.state.job_id = "job";
  f.state.publishable = false;
  f.state.context_stale = true;
  f.state.job_status = "failed";
  render(<App />);
  await screen.findByText("El contexto ha cambiado");
  expect(screen.queryByText("Estamos preparando tu informe")).toBeNull();
  expect(
    screen.getByRole("button", { name: "Continuar en mi espacio" }),
  ).toBeEnabled();
});

it("preserves unknown disposition and request identity after a lost response", async () => {
  const f = fixture("scope");
  f.chat.turns[0].response!.onboarding = {
    question: {
      text: "¿Hubo una campaña?",
      reason: "Ayuda a interpretar",
      optional: true,
      references: [],
    },
    brief,
  };
  f.loseMessage();
  render(<App />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "No lo sé" }));
  await screen.findByText(/No hay conexión/);
  await user.click(screen.getByRole("button", { name: "No lo sé" }));
  await waitFor(() =>
    expect(
      f.writes.filter((w) => w.url === "/api/chats/chat/messages"),
    ).toHaveLength(2),
  );
  const sends = f.writes.filter((w) => w.url === "/api/chats/chat/messages");
  expect(sends[0].body).toEqual(sends[1].body);
  expect(sends[1].body.disposition).toBe("unknown");
});

it.each(["home", "my-business", "analysis/job", "report/job", "chats"])(
  "keeps unfinished onboarding inside the conversation for %s",
  async (route) => {
    fixture("report");
    location.hash = route;
    render(<App />);
    await screen.findByLabelText("Pasos de inicio");
    expect(screen.queryByRole("link", { name: "Nuevo chat" })).toBeNull();
  },
);
it("shows progress inside onboarding and no report link before approval", async () => {
  const f = fixture("report");
  f.state.job_id = "job";
  f.state.job_status = "running";
  f.chat.turns.push({
    id: "work",
    status: "processing",
    job_id: "job",
    payload: { text: "Crear informe" },
  });
  render(<App />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Ver progreso" }),
  );
  await screen.findByText("Contrastando los resultados");
  expect(location.hash).toBe("#onboarding/business");
  expect(screen.queryByRole("link", { name: "Ver informe" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Abrir informe" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Cerrar vista" }));
  expect(
    screen.queryByRole("region", { name: "Progreso del informe" }),
  ).toBeNull();
});
it("does not show a loading spinner on a blocked turn", async () => {
  const f = fixture("report");
  f.chat.turns.push({
    id: "work",
    status: "blocked",
    job_id: "job",
    can_retry: true,
    payload: { text: "Crear informe" },
  });
  render(<App />);
  await screen.findByRole("button", { name: "Reintentar" });
  const send = screen.getByRole("button", { name: "Enviar mensaje" });
  expect(send).toBeDisabled();
  expect(send.querySelector(".animate-spin")).toBeNull();
});
