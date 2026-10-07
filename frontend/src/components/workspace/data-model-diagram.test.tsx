import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ERDiagram } from "./data-model-diagram";
import type { Table, Relation } from "./data-model";

const renderDiagram = vi.hoisted(() => vi.fn());
vi.mock("mermaid", () => ({
  default: { initialize: vi.fn(), render: renderDiagram },
}));
const tables: Table[] = ["a", "b"].map((id) => ({
  id,
  name: `${id}.csv`,
  row_count: 1,
  duplicate_rows: 0,
  description: "",
  grain: "",
  columns: [],
  candidate_keys: [],
  declared_keys: [],
}));
const relations = [
  {
    id: "link",
    source: "a",
    target: "b",
    source_columns: ["id"],
    target_columns: ["id"],
    cardinality: "many-to-one",
    semantic_status: "proposed",
  },
] as Relation[];
const svg = (id: string) =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 300"><g id="${id}-entity-table0-0"><rect width="100" height="40" /></g><g id="${id}-entity-table1-1"><rect width="100" height="40" /></g><path class="relationshipLine" data-edge="true" data-id="id_entity-table0-0_entity-table1-1_0" d="M 0 0 L 100 100" marker-end="url(#arrow)" /></svg>`;
beforeEach(() => {
  renderDiagram
    .mockReset()
    .mockImplementation(async (id) => ({ svg: svg(id) }));
});

it("selects real Mermaid node IDs and activates connections through their widened hit area and keyboard", async () => {
  const chooseTable = vi.fn(),
    chooseEdge = vi.fn();
  const { rerender } = render(
    <ERDiagram
      tables={tables}
      relations={relations}
      selected=""
      edge=""
      chooseTable={chooseTable}
      chooseEdge={chooseEdge}
    />,
  );
  const table = await screen.findByRole("button", { name: "Tabla a.csv" });
  await userEvent.click(table);
  expect(chooseTable).toHaveBeenCalledWith("a");
  const connection = screen.getByRole("button", {
    name: "Relación a.csv con b.csv",
  });
  const hit = connection.querySelector(".data-map-hit")!;
  expect(hit).not.toHaveAttribute("marker-end");
  fireEvent.click(hit);
  fireEvent.keyDown(connection, { key: "Enter" });
  expect(chooseEdge).toHaveBeenCalledTimes(2);
  expect(chooseEdge).toHaveBeenLastCalledWith("link");
  const count = renderDiagram.mock.calls.length;
  rerender(
    <ERDiagram
      tables={tables}
      relations={relations}
      selected="a"
      edge="link"
      chooseTable={chooseTable}
      chooseEdge={chooseEdge}
    />,
  );
  expect(table).toHaveAttribute("aria-pressed", "true");
  expect(connection).toHaveAttribute("aria-pressed", "true");
  expect(renderDiagram.mock.calls).toHaveLength(count);
});

it("ignores a late render from an older dataset instead of replacing the current graph", async () => {
  let resolveOld!: (value: { svg: string }) => void;
  renderDiagram.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        resolveOld = resolve;
      }),
  );
  const props = {
    relations: [],
    selected: "",
    edge: "",
    chooseTable: vi.fn(),
    chooseEdge: vi.fn(),
  };
  const { rerender } = render(<ERDiagram {...props} tables={[tables[0]]} />);
  await waitFor(() => expect(renderDiagram).toHaveBeenCalledTimes(1));
  const oldId = renderDiagram.mock.calls[0][0];
  rerender(
    <ERDiagram {...props} tables={[{ ...tables[0], name: "Nuevo.csv" }]} />,
  );
  expect(
    await screen.findByRole("button", { name: "Tabla Nuevo.csv" }),
  ).toBeVisible();
  await act(async () => resolveOld({ svg: svg(oldId) }));
  expect(screen.getByRole("button", { name: "Tabla Nuevo.csv" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Tabla a.csv" })).toBeNull();
});

it("shows a useful fallback if the renderer fails", async () => {
  renderDiagram.mockRejectedValue(new Error("render failed"));
  render(
    <ERDiagram
      tables={tables}
      relations={relations}
      selected=""
      edge=""
      chooseTable={vi.fn()}
      chooseEdge={vi.fn()}
    />,
  );
  expect(await screen.findByText(/No se pudo dibujar el mapa/)).toBeVisible();
});
