import { it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { setLanguage } from "@/lib/i18n";
import { WorkspaceState, type WorkspaceContext } from "@/lib/workspace";
import type { IndicatorsOverview, QuickCalculation } from "@/lib/types";
import { IndicatorsPanel } from "./indicators";
import { QuickCalculations } from "./quick-calculation";

const business = {
  id: "b",
  name: "Tienda",
  description: "",
  profile_revision: 1,
};
const context = {
  workspace: {
    business,
    businesses: [business],
    analyses: [],
    configured: true,
    memory: {},
  },
  listing: {
    business_id: "b",
    conversations: [],
    datasets: { items: [], more: false },
  },
  route: "home",
  refresh: vi.fn(),
  removeChat: vi.fn(),
} satisfies WorkspaceContext;

const overview: IndicatorsOverview = {
  label:
    "Indicador guardado · fórmula fija recalculada sin modelo · sin comprobación independiente",
  indicators: [
    {
      id: "i1",
      name: "Unidades vendidas",
      status: "active",
      revision: 1,
      label:
        "Indicador guardado · fórmula fija recalculada sin modelo · sin comprobación independiente",
      version: {
        id: "v1",
        version: 1,
        code: "print('<b>x</b>')",
        metric_keys: ["unidades"],
        applies_from: 1,
      },
      values: [
        {
          id: "x2",
          dataset_version: 2,
          status: "completed",
          metrics: { unidades: 200 },
          display: { unidades: "200" },
          reason: null,
          detail: null,
          meanings:
            "Calculado con la fórmula y los significados guardados de la versión 1; esos significados no están confirmados en esta versión.",
        },
      ],
      proposals: [
        {
          id: "v2",
          version: 2,
          code: "print(2)",
          comparison: {
            state: "mismatch",
            sha256: "s".repeat(64),
            metrics: [
              {
                metric: "unidades",
                before: 180,
                after: 999,
                present: true,
                same: false,
              },
            ],
          },
        },
      ],
    },
    {
      id: "i2",
      name: "Cancelaciones",
      status: "active",
      revision: 1,
      label:
        "Indicador guardado · fórmula fija recalculada sin modelo · sin comprobación independiente",
      version: {
        id: "w1",
        version: 1,
        code: "",
        metric_keys: ["c"],
        applies_from: 1,
      },
      values: [
        {
          id: "y",
          dataset_version: 3,
          status: "unavailable",
          metrics: null,
          display: {},
          reason: "Las columnas de un archivo han cambiado.",
          detail: null,
          meanings: null,
        },
      ],
      proposals: [],
    },
  ],
  follow_ups: {
    items: [
      {
        id: "f1",
        state: "proposed",
        note: null,
        revision: 3,
        headline: "Crece la tienda online",
        report_date: "2026-10-01T10:00:00",
        priority_title: "Revisar la recogida en local",
        content: {
          labels: {
            check: "Qué comprobar",
            if_confirmed: "Si se confirma",
            if_not: "Si no",
          },
          check: ["Contar las recogidas de abril."],
          if_confirmed: null,
          if_not: ["Mantener el horario."],
        },
        link: null,
      },
    ],
    counts: { open: 1, closed: 2, withdrawn: 0 },
  },
};

afterEach(() => vi.unstubAllGlobals());

function serve() {
  const posts: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST")
        posts.push({ url, body: JSON.parse(String(init.body)) });
      return new Response(
        JSON.stringify(init?.method === "POST" ? { ok: true } : overview),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }),
  );
  return posts;
}

it("shows values with their labels, reasons and meanings basis, and confirms only with the receipt", async () => {
  setLanguage("es");
  const posts = serve();
  render(
    <WorkspaceState.Provider value={context}>
      <IndicatorsPanel />
    </WorkspaceState.Provider>,
  );
  expect(await screen.findByText("Unidades vendidas")).toBeInTheDocument();
  expect(
    screen.getAllByText(/sin comprobación independiente/).length,
  ).toBeGreaterThan(0);
  expect(
    screen.getByText(/no están confirmados en esta versión/),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Las columnas de un archivo han cambiado."),
  ).toBeInTheDocument();
  expect(screen.getByText(/Da un resultado distinto/)).toBeInTheDocument();
  expect(document.querySelector("b")).toBeNull();
  await userEvent.click(
    screen.getByRole("button", { name: "Confirmar esta versión" }),
  );
  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0].url).toBe("/api/indicators/i1/versions/v2/confirm");
  expect(posts[0].body).toMatchObject({
    expected_active_version_id: "v1",
    comparison_sha: "s".repeat(64),
    business_id: "b",
  });
});

it("changes a topic's state with its expected revision and reuses the key on a double click", async () => {
  setLanguage("es");
  const posts = serve();
  render(
    <WorkspaceState.Provider value={context}>
      <IndicatorsPanel />
    </WorkspaceState.Provider>,
  );
  expect(
    await screen.findByText("Contar las recogidas de abril."),
  ).toBeInTheDocument();
  expect(screen.getByText("2 tema(s) cerrado(s).")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Cerrar" }));
  await waitFor(() => expect(posts.length).toBeGreaterThanOrEqual(1));
  await userEvent.click(screen.getByRole("button", { name: "Cerrar" }));
  await waitFor(() => expect(posts).toHaveLength(2));
  expect(posts[0].body).toMatchObject({
    state: "closed",
    expected_revision: 3,
  });
  expect(posts[1].body.request_key).toBe(posts[0].body.request_key);
});

it("saves a published calculation as an indicator from its card", async () => {
  setLanguage("es");
  const posts = serve();
  const item: QuickCalculation = {
    calculation_id: "c1",
    execution_id: "e1",
    label: "Cálculo rápido, sin comprobación independiente",
    purpose: "Unidades vendidas en total",
    code: "write_result({'unidades': 180})",
    tables: [{ alias: "ventas", names: ["ventas.csv"] }],
    metrics: { unidades: 180, devoluciones: 3 },
    evidence: [],
    evidence_omitted: 0,
    notes: [],
    notes_omitted: 0,
  };
  render(
    <WorkspaceState.Provider value={context}>
      <QuickCalculations items={[item]} turnId="t1" />
    </WorkspaceState.Provider>,
  );
  await userEvent.click(screen.getByText("Guardar este cálculo"));
  await userEvent.click(
    await screen.findByRole("checkbox", { name: "devoluciones" }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Guardar como indicador" }),
  );
  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0].url).toBe("/api/indicators");
  expect(posts[0].body).toMatchObject({
    turn_id: "t1",
    calculation_id: "c1",
    metric_keys: ["unidades"],
    name: "Unidades vendidas en total",
  });
  expect(
    await screen.findByText("Indicador guardado. Lo verás en Inicio."),
  ).toBeInTheDocument();
});
