import type { Table, Relation } from "./data-model";

// Only generated IDs and fixed syntax enter the grammar; uploaded labels are literals.
const literal = (value: string) =>
  value.replace(/[^\p{L}\p{N} ._-]/gu, (c) => `#${c.codePointAt(0)};`);
const cardinality: Record<string, string> = {
  "one-to-one": "|o--o|",
  "one-to-many": "|o--o{",
  "many-to-one": "}o--o|",
  "many-to-many": "}o--o{",
};

export function dataModelMermaid(
  tables: Table[],
  relations: Relation[],
  direction: "LR" | "TB",
) {
  const nodes = tables.map((table, index) => ({
    table,
    id: `table${index}`,
    svgId: `entity-table${index}-${index}`,
  }));
  const byId = new Map(nodes.map((node) => [node.table.id, node]));
  const edges = relations
    .filter(
      (r) =>
        byId.has(r.source) && byId.has(r.target) && cardinality[r.cardinality],
    )
    .map((relation, index) => ({
      relation,
      source: byId.get(relation.source)!,
      target: byId.get(relation.target)!,
      svgId: `id_${byId.get(relation.source)!.svgId}_${byId.get(relation.target)!.svgId}_${index}`,
    }));
  const lines = ["erDiagram", `direction ${direction}`];
  for (const node of nodes) {
    lines.push(`${node.id}["${literal(node.table.name)}"] {`);
    // Prioritize the columns used by connections, then show up to eight per table.
    const linked = new Set(
      edges.flatMap(({ relation }) =>
        relation.source === node.table.id
          ? relation.source_columns
          : relation.target === node.table.id
            ? relation.target_columns
            : [],
      ),
    );
    const columns = [
      ...node.table.columns.filter((c) => linked.has(c.name)),
      ...node.table.columns.filter((c) => !linked.has(c.name)),
    ].slice(0, 8);
    columns.forEach((column, index) => {
      const safeName = column.name.replace(/[^\p{L}\p{N}_-]/gu, "_");
      const name = /^[\p{L}_]/u.test(safeName) ? safeName : `column_${index}`;
      const primary = node.table.declared_keys.some(
        (key) => key.valid && key.columns.includes(column.name),
      );
      lines.push(
        `  dato ${name}${primary ? " PK" : ""}${name !== column.name ? ` "${literal(column.name)}"` : ""}`,
      );
    });
    lines.push("}");
  }
  for (const { relation, source, target } of edges) {
    const keys =
      relation.source_columns.join(" + ") ===
      relation.target_columns.join(" + ")
        ? relation.source_columns.join(" + ")
        : `${relation.source_columns.join(" + ")} → ${relation.target_columns.join(" + ")}`;
    lines.push(
      `${source.id} ${cardinality[relation.cardinality]} ${target.id} : "${literal(keys)}"`,
    );
  }
  return { source: lines.join("\n"), nodes, edges };
}
