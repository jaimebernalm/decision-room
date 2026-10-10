import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DataModelPanel } from "./data-model";
vi.mock("mermaid", () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn(async (_id: string, source: string) => ({
      svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300">${[...source.matchAll(/table(\d+)\["/g)].map((match) => `<g id="entity-table${match[1]}-${match[1]}"><rect width="100" height="40" /></g>`).join("")}</svg>`,
    })),
  },
}));
const columns = [
  {
    name: "id",
    logical_type: "identifier",
    missing: 0,
    distinct: 2,
    duplicate_nonempty: 0,
    period: null,
    key_candidate: true,
    meaning: "",
    unit: "",
    conversion: "",
  },
];
const tables = Array.from({ length: 15 }, (_, i) => ({
  id: `table-${i}`,
  name: `Table ${i}`,
  row_count: 2,
  duplicate_rows: 0,
  description: "",
  grain: "",
  columns,
  candidate_keys: [["id"]],
  declared_keys: [],
}));
const response = {
  model: {
    analysis_id: "analysis",
    revision: 3,
    body: {
      tables,
      relations: [
        {
          id: "r",
          source: "table-0",
          target: "table-1",
          source_columns: ["id"],
          target_columns: ["id"],
          description: "",
          cardinality: "many-to-many",
          semantic_status: "proposed",
          verification: "attention",
          origin: "agent",
          evidence: {
            source: { missing_rows: 0, duplicate_keys: 1 },
            target: { missing_rows: 0, duplicate_keys: 1 },
            unmatched_rows: 0,
            left_join_rows: 4,
            extra_rows: 2,
          },
        },
      ],
      metrics: [],
    },
  },
  history: [{ revision: 3, created_at: "2026-09-27", reason: "initial" }],
  editable: true,
  affected_reports: [],
};
describe("versioned ER data model", () => {
  it("explains a single table without a redundant connection map and still opens its columns", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          ...response,
          model: {
            ...response.model,
            body: { tables: [tables[0]], relations: [], metrics: [] },
          },
        }),
      }),
    );
    render(<DataModelPanel business="business" analysis="analysis" inline />);
    await screen.findByRole("button", { name: "Ver tabla Table 0" });
    expect(screen.queryByRole("button", { name: /Ver relaciones/ })).toBeNull();
    expect(
      screen.queryByRole("group", {
        name: "Diagrama ER de esta revisión del modelo",
      }),
    ).toBeNull();
    expect(screen.queryByText("Conexiones entre tablas")).toBeNull();

    await userEvent.click(
      screen.getByRole("button", { name: "Ver tabla Table 0" }),
    );
    expect(
      screen.getByRole("button", { name: /Corregir o aclarar/ }),
    ).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: "Ver columnas y detalles" }),
    );
    expect(screen.getByRole("columnheader", { name: "Columna" })).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: "Cerrar detalles" }),
    );
    expect(screen.queryByRole("columnheader", { name: "Columna" })).toBeNull();
  });
  it("shows bounded graph, full selection, evidence and exact revision", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => response }),
    );
    render(<DataModelPanel business="business" analysis="analysis" />);
    await user.click(screen.getByRole("button", { name: /Ver relaciones/ }));
    await screen.findByLabelText("Buscar tabla");
    expect(screen.queryByText("Buscar y revisar versiones")).toBeNull();
    expect(screen.queryByLabelText("Historial del modelo")).toBeNull();
    expect(screen.getByText(/12 de 15 tablas/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Table 14" }));
    expect(
      await screen.findByRole("button", { name: "Tabla Table 14" }),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Ver todas las tablas" }),
    );
    await user.click(screen.getByRole("button", { name: "Table 0" }));
    await user.click(
      screen.getByRole("button", { name: /Conexiones y comprobaciones/ }),
    );
    await user.click(screen.getByRole("button", { name: /Table 0 → Table 1/ }));
    expect(
      screen.queryByText("Filas adicionales por multiplicación"),
    ).toBeNull();
    await user.click(
      screen.getByRole("button", { name: "Ver comprobaciones" }),
    );
    expect(
      screen.getByText("Filas adicionales por multiplicación"),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Muchos a muchos/).length).toBeGreaterThan(0);
    expect(screen.getByText("Por confirmar")).toBeInTheDocument();
    expect(
      screen.getByText(/propuesta del analista, comprobada sobre los datos/),
    ).toBeInTheDocument();
  });
  it("stores a revision guarded correction without exposing version controls", async () => {
    const user = userEvent.setup(),
      fetch = vi
        .fn()
        .mockResolvedValue({ ok: true, json: async () => response });
    vi.stubGlobal("fetch", fetch);
    render(<DataModelPanel business="business" analysis="analysis" />);
    await user.click(screen.getByRole("button", { name: /Ver relaciones/ }));
    await user.click(
      await screen.findByRole("button", { name: "Tabla Table 0" }),
    );
    await user.click(
      screen.getByRole("button", { name: /Corregir o aclarar/ }),
    );
    await user.type(
      screen.getByLabelText("Qué representa cada fila"),
      "Una factura",
    );
    await user.click(
      screen.getByRole("button", { name: "Guardar aclaraciones" }),
    );
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/business/data-model",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    const call = fetch.mock.calls.find((c) => c[1]?.method === "POST")!;
    expect(JSON.parse(call[1].body)).toMatchObject({
      business_id: "business",
      analysis_id: "analysis",
      expected_revision: 3,
      action: "table",
      payload: { id: "table-0", grain: "Una factura" },
    });
    expect(screen.queryByLabelText("Historial del modelo")).toBeNull();
  });
  it("keeps optional setup out of the default view and saves a clearly labelled calculation against the exact revision", async () => {
    const user = userEvent.setup(),
      fetch = vi
        .fn()
        .mockResolvedValue({ ok: true, json: async () => response });
    vi.stubGlobal("fetch", fetch);
    render(<DataModelPanel business="business" analysis="analysis" inline />);
    await screen.findByRole("button", { name: "Conexiones y comprobaciones" });
    expect(screen.queryByText("Cómo entendemos las métricas")).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Conectar dos tablas" }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Aclarar un cálculo" }),
    ).toBeNull();
    await user.click(
      screen.getByRole("button", { name: "Conexiones y comprobaciones" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Ajustar cómo usamos estos datos" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Conectar dos tablas" }),
    );
    expect(screen.getByLabelText("Tabla de origen")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    await user.click(
      screen.getByRole("button", { name: "Aclarar un cálculo" }),
    );
    await user.type(screen.getByLabelText("Nombre del resultado"), "Beneficio");
    await user.type(
      screen.getByLabelText("Cómo se define y calcula"),
      "Ventas menos coste de los productos",
    );
    expect(
      screen.getByRole("button", { name: "Guardar definición" }),
    ).toBeDisabled();
    await user.click(screen.getByLabelText("Table 0"));
    await user.click(
      screen.getByRole("button", { name: "Guardar definición" }),
    );
    await waitFor(() =>
      expect(fetch.mock.calls.some((c) => c[1]?.method === "POST")).toBe(true),
    );
    const call = fetch.mock.calls.find((c) => c[1]?.method === "POST")!;
    expect(JSON.parse(call[1].body)).toMatchObject({
      expected_revision: 3,
      action: "metric",
      payload: {
        name: "Beneficio",
        definition: "Ventas menos coste de los productos",
        table_ids: ["table-0"],
      },
    });
  });
  it("shows clean table names and only actionable warnings in the connection dialog", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          ...response,
          model: {
            ...response.model,
            body: {
              ...response.model.body,
              tables: [
                { ...tables[0], name: "ventas.csv" },
                { ...tables[1], name: "catalog.xlsx [Productos].csv" },
              ],
              relations: [
                {
                  ...response.model.body.relations[0],
                  semantic_status: "confirmed",
                  verification: "checked",
                },
              ],
            },
          },
        }),
      }),
    );
    render(<DataModelPanel business="business" analysis="analysis" inline />);
    await screen.findByRole("button", { name: "Conexiones y comprobaciones" });
    expect(screen.queryByText("Buscar y revisar versiones")).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Ajustar cómo usamos estos datos" }),
    ).toBeNull();
    expect(screen.queryByLabelText("Buscar tabla")).toBeNull();
    await userEvent.click(
      screen.getByRole("button", { name: "Conexiones y comprobaciones" }),
    );
    expect(
      screen.getByRole("button", { name: "Ventas → Productos" }),
    ).toBeVisible();
    expect(screen.queryByText("Significado confirmado")).toBeNull();
    expect(screen.queryByText("Datos comparados")).toBeNull();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });
  it("retains saved calculations in read-only history while hiding creation actions", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          ...response,
          editable: false,
          model: {
            ...response.model,
            body: {
              ...response.model.body,
              metrics: [
                {
                  key: "profit",
                  name: "Beneficio",
                  definition: "Ventas menos gastos",
                  unit: "EUR",
                  period: { from: null, until: null },
                  table_ids: ["table-0"],
                },
              ],
            },
          },
        }),
      }),
    );
    render(<DataModelPanel business="business" analysis="analysis" inline />);
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Conexiones y comprobaciones",
      }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Ajustar cómo usamos estos datos" }),
    );
    expect(screen.getByText("Ventas menos gastos")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Conectar dos tablas" }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Aclarar un cálculo" }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Corregir definición" }),
    ).toBeNull();
  });
});
