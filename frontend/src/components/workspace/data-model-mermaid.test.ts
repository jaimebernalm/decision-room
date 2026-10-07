import { describe, it, expect } from "vitest";
import mermaid from "mermaid";
import { dataModelMermaid } from "./data-model-mermaid";
import type { Table, Relation } from "./data-model";

export const makeTable = (
  id: string,
  name = id,
  column = "producto_id",
): Table => ({
  id,
  name,
  row_count: 3,
  duplicate_rows: 0,
  description: "",
  grain: "",
  columns: [
    {
      name: column,
      logical_type: "text",
      missing: 0,
      distinct: 3,
      duplicate_nonempty: 0,
      date_parseable: 0,
      period: null,
      key_candidate: true,
      meaning: "",
      unit: "",
      conversion: "",
    },
  ],
  candidate_keys: [[column]],
  declared_keys: [],
});
export const makeRelation = (id = "rel"): Relation => ({
  id,
  source: "a",
  target: "b",
  source_columns: ["producto_id"],
  target_columns: ["producto_id"],
  description: "",
  cardinality: "many-to-one",
  semantic_status: "proposed",
  verification: "checked",
  origin: "agent",
  evidence: {
    source: { rows: 3, missing_rows: 0, duplicate_keys: 0, duplicate_rows: 0 },
    target: { rows: 3, missing_rows: 0, duplicate_keys: 0, duplicate_rows: 0 },
    unmatched_rows: 0,
    inner_join_rows: 3,
    left_join_rows: 3,
    extra_rows: 0,
    coverage: 1,
  },
});

describe("literal Mermaid data models", () => {
  it("parses real ER syntax with columns, measured cardinality and generated identifiers", async () => {
    const graph = dataModelMermaid(
      [makeTable("a", "Ventas.csv"), makeTable("b", "Productos.csv")],
      [makeRelation()],
      "LR",
    );
    mermaid.initialize({ securityLevel: "strict", startOnLoad: false });
    expect(await mermaid.parse(graph.source)).toMatchObject({
      diagramType: "er",
    });
    expect(graph.source).toContain('table0 }o--o| table1 : "producto_id"');
    expect(graph.source).not.toContain(" PK");
    expect(graph.edges[0].svgId).toBe("id_entity-table0-0_entity-table1-1_0");
  });
  it("keeps quotes, newlines, HTML and directive-like uploaded names out of the grammar", async () => {
    const graph = dataModelMermaid(
      [
        makeTable(
          "a",
          'Ventas"]\n%%{init: {securityLevel: "loose"}}%%\n<script>alert(1)</script>',
          'importe "}; click malicious',
        ),
      ],
      [],
      "TB",
    );
    expect(await mermaid.parse(graph.source)).toMatchObject({
      diagramType: "er",
    });
    expect(graph.source).not.toContain("<script>");
    expect(graph.source).not.toContain("%%{");
    expect(graph.source.split("\n")).toHaveLength(5);
    expect(graph.nodes).toHaveLength(1);
  });
  it("bounds columns, preserves composite keys and excludes edges to hidden tables", async () => {
    const table = makeTable("a");
    table.columns = Array.from({ length: 20 }, (_, i) => ({
      ...table.columns[0],
      name: `column_${i}`,
    }));
    table.declared_keys = [{ columns: ["column_0", "column_1"], valid: true }];
    const relation = {
      ...makeRelation(),
      source_columns: ["column_19", "column_18"],
      target_columns: ["producto_id", "producto_id"],
    };
    const graph = dataModelMermaid(
      [table, makeTable("b")],
      [relation, { ...relation, target: "hidden" }],
      "TB",
    );
    expect(graph.edges).toHaveLength(1);
    expect(graph.source).toContain("dato column_19");
    expect(graph.source).toContain("dato column_0 PK");
    expect(graph.source).not.toContain("dato column_15");
    expect(await mermaid.parse(graph.source)).toMatchObject({
      diagramType: "er",
    });
  });
});
