import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { AssistantProvider, useAssistant } from "@/lib/assistant";
import { contextKey, store } from "@/lib/api";
import { WorkspaceState, type WorkspaceContext } from "@/lib/workspace";
import { ContextAttachments, SelectionTool } from "./context-selection";
import { DossierDataGroups } from "./dossier-data";
import { DataModelPanel } from "./data-model";

vi.mock("mermaid", () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn(async (id: string) => ({
      svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300"><g id="${id}-entity-table0-0"><rect width="100" height="40" /></g><g id="${id}-entity-table1-1"><rect width="100" height="40" /></g><path class="relationshipLine" data-edge="true" data-id="id_entity-table0-0_entity-table1-1_0" d="M 0 0 L 100 100" /></svg>`,
    })),
  },
}));
const tables = ["Ventas", "Productos"].map((name, index) => ({
  id: `table-${index}`,
  source_id: `file-${index}`,
  name,
  row_count: 2,
  duplicate_rows: 0,
  description: "",
  grain: "",
  columns: [],
  candidate_keys: [],
  declared_keys: [],
}));
beforeEach(() => window.history.replaceState(null, "", "#my-business"));
const relation = {
  id: "link",
  source: tables[0].id,
  target: tables[1].id,
  source_columns: ["product_id"],
  target_columns: ["id"],
  description: "Propuesta sobre los productos",
  cardinality: "many-to-one",
  semantic_status: "proposed",
  verification: "checked",
  origin: "agent",
  evidence: {
    source: { rows: 2, missing_rows: 0, duplicate_keys: 0, duplicate_rows: 0 },
    target: { rows: 2, missing_rows: 0, duplicate_keys: 0, duplicate_rows: 0 },
    unmatched_rows: 0,
    inner_join_rows: 2,
    left_join_rows: 2,
    extra_rows: 0,
    coverage: 1,
  },
};
const model = {
  analysis_id: "analysis",
  revision: 3,
  body: { tables, relations: [relation], metrics: [] },
};
const workspace: WorkspaceContext = {
  workspace: {
    business: {
      id: "business",
      name: "Negocio",
      description: "",
      profile_revision: 1,
    },
    businesses: [],
    analyses: [],
    configured: true,
    memory: {},
  },
  listing: {
    business_id: "business",
    conversations: [],
    datasets: { items: [], more: false },
  },
  route: "my-business",
  refresh: vi.fn(),
  removeChat: vi.fn(),
};
function Attachments() {
  const assistant = useAssistant()!;
  return (
    <ContextAttachments
      items={assistant.selected}
      onRemove={assistant.remove}
    />
  );
}
function Harness({
  stale = false,
  library = false,
}: {
  stale?: boolean;
  library?: boolean;
}) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        model,
        editable: true,
        needs_refresh: stale,
        history: [],
        affected_reports: [],
      }),
    }),
  );
  return (
    <WorkspaceState.Provider value={workspace}>
      <AssistantProvider>
        <SelectionTool />
        {library ? (
          <DossierDataGroups
            business="business"
            onUpload={vi.fn()}
            datasets={[
              {
                id: "analysis",
                title: "Example",
                status: "ready",
                version: 1,
                files: tables.map((table) => ({
                  id: table.source_id,
                  name: table.name,
                  rows: table.row_count,
                })),
              },
            ]}
          />
        ) : (
          <DataModelPanel business="business" analysis="analysis" inline />
        )}
        <Attachments />
      </AssistantProvider>
    </WorkspaceState.Provider>
  );
}

it("picks connections by pointer or keyboard and the entire saved map, with reversible selections and previews", async () => {
  const user = userEvent.setup();
  const view = render(<Harness />);
  const connection = await screen.findByRole("button", {
    name: "Relación Ventas con Productos",
  });
  await user.click(screen.getByRole("button", { name: "Seleccionar" }));
  await user.click(connection);
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(connection).toHaveAttribute("aria-pressed", "true");
  const pointer = {
    kind: "data_model",
    source_id: "analysis",
    source_version: "3",
    element_key: "relation:link",
  };
  await waitFor(() =>
    expect(
      store.get(contextKey("business"), { context_references: [] })
        .context_references,
    ).toEqual([expect.objectContaining(pointer)]),
  );
  await user.click(
    screen.getByRole("button", { name: "Seleccionar: Mapa de relaciones" }),
  );
  expect(
    screen.getByRole("button", { name: "Quitar: Mapa de relaciones" }),
  ).toHaveAttribute("aria-pressed", "true");
  expect(
    store.get(contextKey("business"), { context_references: [] })
      .context_references,
  ).toHaveLength(2);
  fireEvent.keyDown(connection, { key: "Enter" });
  expect(connection).toHaveAttribute("aria-pressed", "false");
  await user.click(
    screen.getByRole("button", {
      name: "Seleccionar: Relación: Ventas → Productos",
    }),
  );
  await user.click(
    screen.getByRole("button", {
      name: "Ver adjunto: Relación: Ventas → Productos",
    }),
  );
  expect(screen.getByRole("dialog")).toHaveTextContent("product_id");
  expect(screen.getByRole("dialog")).toHaveTextContent(
    "Propuesta sobre los productos",
  );
  expect(screen.getByRole("dialog")).toHaveTextContent("Por confirmar");
  await user.keyboard("{Escape}");
  expect(
    screen.getByRole("button", { name: "Seleccionar" }),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Seleccionar" }));
  await user.click(
    screen.getByRole("button", {
      name: "Ver adjunto: Relación: Ventas → Productos",
    }),
  );
  await user.click(screen.getByRole("button", { name: "Ver en Mi negocio" }));
  fireEvent.keyDown(connection, { key: "Enter" });
  expect(connection).toHaveAttribute("aria-pressed", "false");
  await user.click(
    screen.getByRole("button", {
      name: "Seleccionar: Relación: Ventas → Productos",
    }),
  );
  await user.click(screen.getByRole("button", { name: "Listo" }));
  expect(
    screen.queryByRole("button", { name: "Quitar: Mapa de relaciones" }),
  ).toBeNull();
  await user.click(connection);
  expect(screen.getByRole("dialog")).toHaveTextContent(
    "Conexiones y comprobaciones",
  );
  view.unmount();
  render(<Harness />);
  await screen.findByRole("button", {
    name: "Ver adjunto: Mapa de relaciones",
  });
  await user.click(
    screen.getByRole("button", {
      name: "Ver adjunto: Relación: Ventas → Productos",
    }),
  );
  expect(screen.getByRole("dialog")).toHaveTextContent(
    "Propuesta sobre los productos",
  );
});

it("keeps stale models readable without offering them as fresh selectable context", async () => {
  render(<Harness stale />);
  await screen.findByRole("button", { name: "Relación Ventas con Productos" });
  await userEvent.click(screen.getByRole("button", { name: "Seleccionar" }));
  expect(
    screen.queryByRole("button", { name: "Seleccionar: Mapa de relaciones" }),
  ).toBeNull();
  expect(
    screen.queryByRole("button", { name: /Seleccionar: Relación:/ }),
  ).toBeNull();
  await userEvent.click(
    screen.getByRole("button", { name: "Relación Ventas con Productos" }),
  );
  expect(screen.getByRole("dialog")).toHaveTextContent(
    "Conexiones y comprobaciones",
  );
});

it("selects the exact prepared table from the library and returns to its source without opening a preview", async () => {
  const user = userEvent.setup();
  render(<Harness library />);
  await user.click(screen.getByRole("button", { name: "Tablas 2" }));
  expect(
    screen.getByRole("button", { name: "Ver tabla Ventas" }),
  ).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Seleccionar" }));
  const choice = await screen.findByRole("button", {
    name: "Seleccionar: Tabla: Ventas",
  });
  await user.click(choice);
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(
    store.get(contextKey("business"), { context_references: [] })
      .context_references,
  ).toEqual([
    expect.objectContaining({
      kind: "data_model",
      source_id: "analysis",
      source_version: "3",
      element_key: "table:table-0",
    }),
  ]);
  const remove = screen.getByRole("button", { name: "Quitar: Tabla: Ventas" });
  remove.focus();
  await user.keyboard("{Enter}");
  expect(
    screen.getByRole("button", { name: "Seleccionar: Tabla: Ventas" }),
  ).toHaveAttribute("aria-pressed", "false");
  await user.click(
    screen.getByRole("button", { name: "Seleccionar: Tabla: Ventas" }),
  );
  await user.click(screen.getByRole("button", { name: "Listo" }));
  await user.click(screen.getByRole("button", { name: "Relaciones" }));
  await user.click(
    screen.getByRole("button", { name: "Ver adjunto: Tabla: Ventas" }),
  );
  await user.click(screen.getByRole("button", { name: "Ver en Mi negocio" }));
  expect(screen.getByRole("button", { name: "Tablas 2" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(
    screen.getByRole("button", { name: "Ver tabla Ventas" }),
  ).toBeVisible();
});

it("highlights a prospective connection during selection without choosing it", async () => {
  const user = userEvent.setup();
  const { container } = render(<Harness />);
  const connection = await screen.findByRole("button", {
    name: "Relación Ventas con Productos",
  });
  await user.click(screen.getByRole("button", { name: "Seleccionar" }));
  fireEvent.pointerMove(connection, { clientX: 100, clientY: 100 });
  await waitFor(() =>
    expect(connection).toHaveAttribute("data-hovered", "true"),
  );
  expect(connection).toHaveAttribute("aria-pressed", "false");
  fireEvent.pointerLeave(container.querySelector(".data-map-viewport")!);
  await waitFor(() =>
    expect(connection).toHaveAttribute("data-hovered", "false"),
  );
});

it("keeps stale table previews readable without offering obsolete tables for selection", async () => {
  const user = userEvent.setup();
  render(<Harness library stale />);
  await user.click(screen.getByRole("button", { name: "Tablas 2" }));
  expect(
    screen.getByRole("button", { name: "Ver tabla Ventas" }),
  ).toBeEnabled();
  await user.click(screen.getByRole("button", { name: "Seleccionar" }));
  expect(
    screen.queryByRole("button", { name: "Seleccionar: Tabla: Ventas" }),
  ).toBeNull();
});
