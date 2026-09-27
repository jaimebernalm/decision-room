import { expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "@/App";

const question = {
  id: "q",
  text: "¿Precio unitario o total de fila?",
  reason: "Cambia el cálculo.",
  phase: "planning",
  options: ["Total de fila"],
  references: [{ kind: "column", id: "table", column: "importe" }],
};
const job = {
  id: "job",
  business_id: "business",
  analysis_id: "source",
  title: "Mi informe",
  business: "Mi negocio",
  status: "waiting",
  phase: "planning",
  publishable: false,
  files: [],
  answers: [],
  interpretations: [],
  questions: [question],
  goal: "Comparar ventas",
};
const preview = {
  tables: [{ id: "table", name: "ventas.csv", row_count: 51, column_count: 2 }],
  table_id: "table",
  columns: ["unidades", "importe"],
  rows: [{ number: 1, values: ["2", "10.00"] }],
  offset: 0,
  column_offset: 0,
  page_rows: 50,
  page_columns: 12,
  cell_characters: 500,
};
function mockFetch(current = job) {
  const writes: { url: string; body: Record<string, unknown> }[] = [];
  const fetch = vi.fn(async (url: string, options: RequestInit) => {
    let data: unknown;
    if (options.method === "POST") {
      writes.push({ url, body: JSON.parse(options.body as string) });
      data =
        url === "/api/jobs/from-dataset" ? { id: "new-job" } : { saved: true };
    } else if (url === "/api/workspace")
      data = {
        business: { id: "business", name: "Mi negocio", profile_revision: 1 },
        businesses: [],
        analyses: [],
        memory: {},
        configured: true,
      };
    else if (url === "/api/chats")
      data = {
        business_id: "business",
        conversations: [],
        datasets: { items: [] },
      };
    else if (url === "/api/chats/chat")
      data = {
        conversation: { id: "chat", business_id: "business" },
        turns: [
          {
            id: "turn",
            job_id: "job",
            status: "waiting",
            payload: { text: "Analiza mis ventas" },
            questions: [question],
          },
        ],
        memory: {},
        memory_items: [],
      };
    else if (url.includes("/data?"))
      data = url.includes("offset=50")
        ? {
            ...preview,
            offset: 50,
            rows: [{ number: 51, values: ["3", "20.00"] }],
          }
        : preview;
    else if (url === "/api/jobs/new-job")
      data = { ...job, id: "new-job", status: "queued", questions: [] };
    else data = current;
    return { ok: true, json: async () => data };
  });
  vi.stubGlobal("fetch", fetch);
  return { writes, fetch };
}

it("opens the data with the question, highlights its column and pages without losing the answer", async () => {
  location.hash = "analysis/job";
  const { writes } = mockFetch();
  render(<App />);
  const user = userEvent.setup();
  expect(
    await screen.findByRole("table", { name: "Datos de ventas.csv" }),
  ).toBeVisible();
  expect(
    screen.getByRole("columnheader", {
      name: "importe (mencionada en la pregunta)",
    }),
  ).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Total de fila" }));
  expect(
    screen.getByRole("button", { name: "No dispongo de ese dato" }),
  ).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Filas siguientes" }));
  await screen.findByText("20.00");
  expect(screen.getByLabelText("Tu respuesta")).toHaveValue("Total de fila");
  await user.click(screen.getByRole("button", { name: "Guardar respuesta" }));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0].body).toMatchObject({
    text: "Total de fila",
    disposition: "answered",
  });
});

it("sends an unknown answer only when the answer field is empty", async () => {
  location.hash = "analysis/job";
  const { writes } = mockFetch();
  render(<App />);
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("button", { name: "No dispongo de ese dato" }),
  );
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0].body).toMatchObject({ text: "", disposition: "unknown" });
});

it("recovers a blocked clarification using the same dataset only after the owner confirms it", async () => {
  location.hash = "analysis/job";
  const { writes } = mockFetch({
    ...job,
    status: "blocked",
    questions: [],
    unresolved_questions: [{ ...question, previous_text: "Total de fila" }],
  } as typeof job);
  render(<App />);
  const user = userEvent.setup();
  expect(await screen.findByLabelText(question.text)).toHaveValue(
    "Total de fila",
  );
  expect(
    await screen.findByRole("table", { name: "Datos de ventas.csv" }),
  ).toBeVisible();
  expect(writes).toHaveLength(0);
  await user.click(
    screen.getByRole("button", {
      name: "Confirmar aclaración y crear informe",
    }),
  );
  await waitFor(() => expect(location.hash).toBe("#analysis/new-job"));
  expect(writes).toHaveLength(1);
  expect(writes[0].url).toBe("/api/jobs/from-dataset");
  expect(writes[0].body.analysis_id).toBe("source");
  expect(writes[0].body.goal).toContain(
    "¿Precio unitario o total de fila?\nTotal de fila",
  );
});

it("opens the same data preview for an analytical question in chat", async () => {
  location.hash = "chat/chat";
  mockFetch();
  render(<App />);
  expect(
    await screen.findByRole("table", { name: "Datos de ventas.csv" }),
  ).toBeVisible();
  expect(
    screen.getByRole("combobox", { name: "Aclaración pendiente" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("columnheader", {
      name: "importe (mencionada en la pregunta)",
    }),
  ).toBeVisible();
});
