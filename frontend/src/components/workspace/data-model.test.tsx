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
  it("shows the model immediately inside Relations and explains a single table without invented connections", async () => {
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
    expect(
      await screen.findByRole("group", {
        name: "Diagrama ER de esta revisión del modelo",
      }),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: /Ver relaciones/ })).toBeNull();
    expect(
      screen.getByText(/Este conjunto tiene una sola tabla/),
    ).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: "Tabla Table 0" }),
    );
    expect(
      screen.getByRole("button", { name: /Corregir o aclarar/ }),
    ).toBeVisible();
  });
  it("shows bounded graph, full selection, evidence and exact revision", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => response }),
    );
    render(<DataModelPanel business="business" analysis="analysis" />);
    await user.click(screen.getByRole("button", { name: /Ver relaciones/ }));
    expect(await screen.findByText("Modelo · revisión 3")).toBeInTheDocument();
    expect(screen.getByText(/12 de 15 tablas/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Table 14" }));
    await user.click(
      screen.getByRole("button", { name: /Centrar en esta tabla/ }),
    );
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
      screen.getByText("Filas adicionales por multiplicación"),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Muchos a muchos/).length).toBeGreaterThan(0);
    expect(screen.getByText("Por confirmar")).toBeInTheDocument();
    expect(
      screen.getByText(/propuesta del analista, comprobada sobre los datos/),
    ).toBeInTheDocument();
  });
  it("stores a revision guarded correction and disables editing history", async () => {
    const user = userEvent.setup(),
      fetch = vi
        .fn()
        .mockResolvedValue({ ok: true, json: async () => response });
    vi.stubGlobal("fetch", fetch);
    render(<DataModelPanel business="business" analysis="analysis" />);
    await user.click(screen.getByRole("button", { name: /Ver relaciones/ }));
    await user.click(await screen.findByRole("button", { name: "Table 0" }));
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
    await user.click(
      screen.getByRole("button", { name: "Buscar y revisar versiones" }),
    );
    await user.selectOptions(
      screen.getByLabelText("Historial del modelo"),
      "3",
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: /Corregir o aclarar/ }),
      ).not.toBeInTheDocument(),
    );
  });
});
