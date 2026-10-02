import { it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Home } from "./home";
import { WorkspaceState, type WorkspaceContext } from "@/lib/workspace";
import type { HomeDashboard } from "@/lib/types";
import type { Report } from "@/lib/types";
const context = {
  workspace: {
    business: {
      id: "b",
      name: "Tienda",
      description: "Ventas",
      profile_revision: 1,
    },
    businesses: [],
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
const data: HomeDashboard = {
  business_id: "b",
  revision: 2,
  fingerprint: "v1",
  selected: ["m"],
  pinned: [],
  hidden: [],
  unavailable: 0,
  reasons: {},
  selection_origin: "initial",
  proposal: null,
  can_suggest: true,
  activity: [],
  limited: false,
  sources: [],
  items: [
    {
      id: "m",
      kind: "metric",
      title: "Ventas",
      content: {
        label: "Ventas",
        value: "80",
        unit: "EUR",
        claim_key: "sales",
      },
      source: {
        job_id: "j",
        report_id: "r",
        version: "v",
        title: "Informe",
        period: "Abril de 2025",
        coverage: "Solo ventas registradas",
        filename: "ventas.csv",
        created_at: "2025-05-01",
        analysis_id: "a",
        limitations: ["Sin costes"],
        href: "#report/j",
      },
    },
  ],
};
function mount() {
  return render(
    <WorkspaceState.Provider value={context}>
      <Home />
    </WorkspaceState.Provider>,
  );
}
it("opens card actions with the keyboard and preserves pinning behavior", async () => {
  let current = data;
  const writes: object[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_path: string, init?: RequestInit) => {
      if (init?.body) {
        const body = JSON.parse(String(init.body));
        writes.push(body);
        current = { ...current, pinned: body.pinned };
      }
      return { ok: true, json: async () => current };
    }),
  );
  mount();
  const user = userEvent.setup();
  const options = await screen.findByRole("button", {
    name: "Opciones de Ventas",
  });
  options.focus();
  await user.keyboard("{Enter}");
  expect(
    await screen.findByRole("menuitem", { name: "Editar presentación" }),
  ).toHaveAttribute("data-disabled");
  expect(
    screen.getByRole("menuitem", { name: "Ocultar tarjeta" }),
  ).toBeVisible();
  await user.click(screen.getByRole("menuitem", { name: "Fijar tarjeta" }));
  await waitFor(() =>
    expect(writes[0]).toMatchObject({
      revision: 2,
      pinned: ["m"],
      selected: ["m"],
    }),
  );
  await user.click(options);
  expect(
    await screen.findByRole("menuitem", { name: "Desfijar tarjeta" }),
  ).toBeVisible();
  expect(
    screen.queryByRole("menuitem", { name: "Ocultar tarjeta" }),
  ).toBeNull();
});
it("opens the shared editor from a card menu without losing the dialog on menu close", async () => {
  const presentation = {
    report_id: "r",
    base_version: "v",
    revision: 0,
    labels: [],
    history: [],
  };
  const item = data.items[0];
  const displayed = {
    ...data,
    items: [
      {
        ...item,
        content: { ...item.content, key: "m" },
        source: { ...item.source, presentation },
      },
    ],
  };
  const report: Report = {
    title: "Informe",
    scope: { period: "Abril", coverage: "Ventas" },
    highlights: [
      {
        key: "m",
        label: "Ventas",
        value: "80",
        unit: "EUR",
        claim_key: "sales",
      },
    ],
    charts: [],
    claims: [],
    limitations: [],
    presentation,
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => ({
      ok: true,
      json: async () => (path === "/api/home" ? displayed : report),
    })),
  );
  mount();
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("button", { name: "Opciones de Ventas" }),
  );
  await user.click(
    screen.getByRole("menuitem", { name: "Editar presentación" }),
  );
  expect(await screen.findByRole("dialog")).toBeVisible();
  expect(await screen.findByLabelText("Título visible")).toHaveValue("Ventas");
  expect(screen.queryByRole("menu")).toBeNull();
});
it("shows scoped indicators with source and period instead of the latest report", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => data })),
  );
  mount();
  await screen.findByText("80");
  expect(screen.queryByText("Tu último informe")).toBeNull();
  expect(screen.getByText("Abril de 2025")).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", { name: "Periodo y fuente" }),
  );
  expect(screen.getByRole("link", { name: "Ver fuente" })).toHaveAttribute(
    "href",
    "#report/j",
  );
  expect(screen.getByText("Sin costes")).toBeVisible();
});
it("preserves pinned cards in the editor and sends the captured revision", async () => {
  const fetcher = vi.fn(async () => ({
    ok: true,
    json: async () => ({ ...data, pinned: ["m"] }),
  }));
  vi.stubGlobal("fetch", fetcher);
  mount();
  await screen.findByRole("button", { name: "Personalizar" });
  await userEvent.click(screen.getByRole("button", { name: "Personalizar" }));
  expect(screen.getByRole("checkbox")).toBeDisabled();
  await userEvent.click(
    screen.getByRole("button", { name: "Guardar selección" }),
  );
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      "/api/home/preferences",
      expect.objectContaining({
        body: expect.stringContaining('"revision":2'),
      }),
    ),
  );
});
it("previews agent choices without applying them until the owner accepts", async () => {
  const proposed = {
    ...data,
    revision: 3,
    proposal: {
      picks: [{ id: "m", reason: "Relevante para ventas" }],
      fingerprint: "v1",
    },
  };
  const calls: { path: string; body?: string }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: { body?: string }) => {
      calls.push({ path, body: init?.body });
      return {
        ok: true,
        json: async () => (path === "/api/home/suggest" ? proposed : data),
      };
    }),
  );
  mount();
  await screen.findByRole("button", { name: "Proponer selección" });
  await userEvent.click(
    screen.getByRole("button", { name: "Proponer selección" }),
  );
  await screen.findByRole("dialog");
  expect(screen.getByText("Relevante para ventas")).toBeVisible();
  expect(calls.some((call) => call.path === "/api/home/preferences")).toBe(
    false,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Aplicar propuesta" }),
  );
  await waitFor(() =>
    expect(
      calls.find((call) => call.path === "/api/home/preferences")?.body,
    ).toContain('"apply_proposal":true'),
  );
  expect(
    JSON.parse(
      calls.find((call) => call.path === "/api/home/preferences")!.body!,
    ).revision,
  ).toBe(3);
});

it("connects charts only to findings from the same report and review and links to that exact finding", async () => {
  const source = data.items[0].source;
  const chart = {
    id: "chart",
    kind: "chart" as const,
    title: "Evolución",
    source,
    content: {
      key: "chart",
      title: "Evolución",
      kind: "table" as const,
      unit: "EUR",
      caption: "Sin devoluciones",
      claim_key: "sales",
      points: [],
    },
  };
  const insight = {
    id: "insight",
    kind: "insight" as const,
    title: "Hallazgo",
    source,
    content: {
      key: "sales",
      title: "Hallazgo",
      statement: "Conclusión de abril con sus condiciones completas.",
    },
  };
  const old = {
    ...insight,
    id: "old",
    content: { ...insight.content, statement: "Conclusión de otra revisión" },
    source: { ...source, version: "old", period: "Marzo" },
  };
  const dashboard = {
    ...data,
    selected: ["chart", "old", "insight"],
    items: [chart, old, insight],
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => dashboard })),
  );
  mount();
  expect(await screen.findByText(insight.content.statement)).toBeVisible();
  expect(screen.getAllByText(insight.content.statement)).toHaveLength(1);
  const links = screen.getAllByRole("link", {
    name: "Ver hallazgo en el informe",
  });
  expect(links[0]).toHaveAttribute("href", "#report/j/finding/sales/r/v");
  expect(links[1]).toHaveAttribute("href", "#report/j/finding/sales/r/old");
  expect(screen.getAllByText("Abril de 2025")[0]).toBeVisible();
  expect(screen.getByText("Marzo")).toBeVisible();
});
