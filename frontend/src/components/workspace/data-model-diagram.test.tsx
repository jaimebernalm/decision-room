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
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 300"><g id="${id}-entity-table0-0"><rect width="100" height="40" /><g class="attribute-type"><text>dato</text></g><g class="attribute-name"><text>id</text></g><g class="divider" /></g><g id="${id}-entity-table1-1"><rect width="100" height="40" /></g><path class="relationshipLine" data-edge="true" data-id="id_entity-table0-0_entity-table1-1_0" d="M 0 0 L 100 100" marker-end="url(#arrow)" /><g class="edgeLabel"><g data-id="id_entity-table0-0_entity-table1-1_0"><text>id</text></g></g></svg>`;
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
  expect(table.querySelector(".attribute-type")).toBeNull();
  expect(table.querySelector(".divider")).toBeNull();
  expect(table.querySelector(".attribute-name")).toHaveTextContent("id");
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

it("pans at fit size, suppresses selection after dragging, and recenters without rendering Mermaid again", async () => {
  class Pointer extends MouseEvent {
    pointerId: number;
    constructor(
      type: string,
      init: MouseEventInit & { pointerId?: number } = {},
    ) {
      super(type, init);
      this.pointerId = init.pointerId ?? 1;
    }
  }
  vi.stubGlobal("PointerEvent", Pointer);
  const chooseTable = vi.fn();
  render(
    <ERDiagram
      tables={tables}
      relations={relations}
      selected=""
      edge=""
      chooseTable={chooseTable}
      chooseEdge={vi.fn()}
    />,
  );
  const table = await screen.findByRole("button", { name: "Tabla a.csv" });
  const viewport = screen.getByRole("group", {
    name: "Diagrama ER de esta revisión del modelo",
  });
  const drawing = table.closest(".data-map-drawing")! as HTMLElement;
  const initial = drawing.style.transform;
  const count = renderDiagram.mock.calls.length;
  fireEvent.pointerDown(table, { button: 0, clientX: 100, clientY: 100 });
  fireEvent.pointerMove(viewport, { clientX: 160, clientY: 130 });
  expect(drawing.style.transform).toContain("translate(60px, 30px)");
  expect(viewport).toHaveAttribute("data-dragging", "true");
  fireEvent.pointerUp(viewport);
  fireEvent.click(table);
  expect(chooseTable).not.toHaveBeenCalled();
  expect(viewport).toHaveAttribute("data-dragging", "false");
  await userEvent.click(table);
  expect(chooseTable).toHaveBeenCalledWith("a");
  fireEvent.keyDown(viewport, { key: "ArrowRight" });
  expect(drawing.style.transform).toContain("translate(12px, 30px)");
  await userEvent.click(screen.getByRole("button", { name: "Acercar mapa" }));
  expect(drawing.style.transform).not.toBe(initial);
  await userEvent.click(screen.getByRole("button", { name: "Ajustar mapa" }));
  expect(drawing.style.transform).toBe(initial);
  expect(renderDiagram.mock.calls).toHaveLength(count);
  fireEvent.pointerDown(viewport, { button: 0, clientX: 10, clientY: 10 });
  fireEvent.pointerMove(viewport, { clientX: 30, clientY: 20 });
  fireEvent.pointerCancel(viewport);
  expect(viewport).toHaveAttribute("data-dragging", "false");
});

it("explains a connection on hover or focus, preserves uncertainty, and allows clicking its label", async () => {
  const chooseEdge = vi.fn();
  render(
    <ERDiagram
      tables={tables}
      relations={relations}
      selected=""
      edge=""
      chooseTable={vi.fn()}
      chooseEdge={chooseEdge}
    />,
  );
  const connection = await screen.findByRole("button", {
    name: "Relación a.csv con b.csv",
  });
  expect(connection).toHaveAccessibleDescription(
    /Varias filas de «a.csv».*«b.csv»/,
  );
  fireEvent.pointerMove(connection.querySelector(".data-map-hit")!, {
    clientX: 20,
    clientY: 30,
  });
  const tooltip = screen.getByRole("tooltip");
  expect(tooltip).toHaveTextContent("Se conectan comparando «id» con «id».");
  expect(tooltip).toHaveTextContent("su significado aún está por confirmar");
  fireEvent.pointerLeave(connection.closest(".data-map-viewport")!);
  expect(screen.queryByRole("tooltip")).toBeNull();
  fireEvent.focus(connection);
  expect(screen.getByRole("tooltip")).toBeVisible();
  fireEvent.keyDown(connection, { key: "Escape" });
  expect(screen.queryByRole("tooltip")).toBeNull();
  const label = connection
    .closest(".data-map-drawing")!
    .querySelector(".edgeLabel text")!;
  fireEvent.click(label);
  expect(chooseEdge).toHaveBeenCalledWith("link");
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

it("offers optional map help and explains cardinality even when the connection has its own description", async () => {
  const user = userEvent.setup();
  render(
    <ERDiagram
      tables={tables}
      relations={[
        {
          ...relations[0],
          description: "Cada línea del pedido describe un artículo.",
        },
      ]}
      selected=""
      edge=""
      chooseTable={vi.fn()}
      chooseEdge={vi.fn()}
    />,
  );
  const connection = await screen.findByRole("button", {
    name: "Relación a.csv con b.csv",
  });
  expect(screen.queryByText("Una raya: una fila.")).toBeNull();
  const help = screen.getByRole("button", { name: "Cómo leer este mapa" });
  await user.click(help);
  expect(help).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByText("Tres puntas: varias filas.")).toBeVisible();
  expect(
    screen.getByText(/no establece qué relaciones son obligatorias/),
  ).toBeVisible();
  await user.keyboard("{Enter}");
  expect(help).toHaveAttribute("aria-expanded", "false");
  fireEvent.focus(connection);
  expect(screen.getByRole("tooltip")).toHaveTextContent(
    "Varias filas de «a.csv» pueden corresponder a una misma fila de «b.csv».",
  );
  expect(screen.getByRole("tooltip")).toHaveTextContent(
    "Cada línea del pedido describe un artículo.",
  );
  expect(connection).toHaveAccessibleDescription(
    /Varias filas.*Cada línea del pedido/,
  );
});
