import { it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Home } from "./home";
import { WorkspaceState, type WorkspaceContext } from "@/lib/workspace";
import type { HomeDashboard } from "@/lib/types";
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
