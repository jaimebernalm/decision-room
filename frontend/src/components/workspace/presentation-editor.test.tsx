import { expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PresentationEditor } from "./presentation-editor";
import { WorkspaceState, type WorkspaceContext } from "@/lib/workspace";
import type { Report } from "@/lib/types";
const report: Report = {
  report_id: "r",
  report_version: "approved",
  title: "Mi informe",
  scope: { period: "Julio", coverage: "Ventas" },
  claims: [],
  charts: [],
  limitations: [],
  highlights: [
    {
      key: "m",
      label: "Kit",
      value: "410",
      raw_value: "410",
      unit: "unidades",
      unit_choices: ["unidades", "uds."],
      original_unit: "unidades",
      unit_customizable: true,
      unit_origin: "analysis",
      decimals: 0,
      claim_key: "c",
    },
  ],
  presentation: {
    report_id: "r",
    base_version: "approved",
    revision: 1,
    labels: [
      {
        id: "catalog:P06",
        code: "P06",
        name: "Kit",
        catalog_name: "Kit original",
        key_column: "producto_id",
      },
    ],
    history: [
      {
        revision: 1,
        origin: "editor",
        description: "Título",
        created_at: null,
      },
      {
        revision: 0,
        origin: "catalog",
        description: "Nombres del catálogo",
        created_at: null,
      },
    ],
  },
};
function setup(fail = false) {
  const calls: Record<string, unknown>[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.body) {
        calls.push(JSON.parse(String(init.body)));
        return {
          ok: !fail,
          status: fail ? 409 : 200,
          json: async () =>
            fail
              ? { error: "Alguien ha cambiado esta presentación" }
              : { saved: true },
        };
      }
      return {
        ok: true,
        json: async () =>
          url.includes("revision=0")
            ? {
                ...report,
                title: "Título anterior",
                presentation: { ...report.presentation, revision: 0 },
              }
            : report,
      };
    }),
  );
  const context = {
    workspace: {
      business: { id: "b", name: "Café", description: "", profile_revision: 1 },
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
  render(
    <WorkspaceState.Provider value={context}>
      <PresentationEditor
        presentation={report.presentation}
        target={{ kind: "metric", key: "m", title: "Kit" }}
      />
    </WorkspaceState.Provider>,
  );
  return calls;
}
it("saves explicit title and catalogue edits against the loaded revision, then refreshes shared views", async () => {
  const calls = setup(),
    user = userEvent.setup(),
    changed = vi.fn();
  addEventListener("dr-presentation", changed);
  try {
    await user.click(screen.getByRole("button", { name: "Editar Kit" }));
    await user.clear(await screen.findByLabelText("Título visible"));
    await user.type(screen.getByLabelText("Título visible"), "Mis kits");
    await user.selectOptions(screen.getByLabelText("Decimales"), "2");
    expect(screen.getByLabelText("Vista previa")).toHaveTextContent("410,00");
    await user.click(screen.getByRole("tab", { name: "Nombres del catálogo" }));
    await user.clear(screen.getByLabelText("Nombre de P06"));
    await user.type(screen.getByLabelText("Nombre de P06"), "Kit Bruma");
    await user.click(screen.getByRole("button", { name: "Guardar cambios" }));
    await waitFor(() => expect(changed).toHaveBeenCalledOnce());
    expect(calls[0]).toMatchObject({
      business_id: "b",
      revision: 1,
      base_version: "approved",
      changes: [
        { kind: "metric", key: "m", field: "title", value: "Mis kits" },
        { kind: "metric", key: "m", field: "decimals", value: 2 },
        {
          kind: "entity",
          key: "catalog:P06",
          field: "name",
          value: "Kit Bruma",
        },
      ],
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  } finally {
    removeEventListener("dr-presentation", changed);
  }
});
it("previews a historical version and restores it as a new revision", async () => {
  const calls = setup(),
    user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Editar Kit" }));
  await screen.findByLabelText("Título visible");
  await user.click(screen.getByRole("tab", { name: "Historial" }));
  await user.click(screen.getAllByRole("button", { name: "Ver" })[1]);
  expect(await screen.findByText("Título anterior")).toBeVisible();
  await user.click(
    screen.getByRole("button", { name: "Restaurar esta versión" }),
  );
  await waitFor(() =>
    expect(calls[0]).toMatchObject({ revision: 1, restore_revision: 0 }),
  );
  expect(calls[0]).not.toHaveProperty("changes");
});
it("keeps edits visible when a concurrent save is rejected", async () => {
  setup(true);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Editar Kit" }));
  await user.type(await screen.findByLabelText("Título visible"), " nuevo");
  await user.click(screen.getByRole("button", { name: "Guardar cambios" }));
  expect(
    await screen.findByText("Alguien ha cambiado esta presentación"),
  ).toBeVisible();
  expect(screen.getByLabelText("Título visible")).toHaveValue("Kit nuevo");
  expect(screen.getByRole("dialog")).toBeVisible();
});
it("accepts an owner unit clarification outside suggestions and sends only a visible label change", async () => {
  const calls = setup(),
    user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Editar Kit" }));
  const unit = await screen.findByRole("combobox", { name: "Unidad visible" });
  await user.clear(unit);
  expect(
    screen.getByRole("button", { name: "Guardar cambios" }),
  ).toBeDisabled();
  await user.type(unit, "unidades registradas (paquete)");
  expect(screen.getByLabelText("Vista previa")).toHaveTextContent(
    "410 unidades registradas (paquete)",
  );
  await user.click(screen.getByRole("button", { name: "Guardar cambios" }));
  await waitFor(() =>
    expect(calls[0]).toMatchObject({
      revision: 1,
      base_version: "approved",
      changes: [
        {
          kind: "metric",
          key: "m",
          field: "unit",
          value: "unidades registradas (paquete)",
        },
      ],
    }),
  );
  expect(calls[0]).not.toHaveProperty("raw_value");
});
