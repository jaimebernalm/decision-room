import { translate as tr } from "@/lib/i18n";
import type { ContextAttachment } from "@/lib/types";
import { tableName } from "@/lib/table-name";
import type { DataModel, Table } from "./data-model";

export function tableAttachment(
  model: DataModel,
  table: Table,
): ContextAttachment {
  const key = `table:${table.id}`;
  const title = tr("Tabla: {0}", { 0: tableName(table.name) });
  return {
    kind: "data_model",
    source_id: model.analysis_id,
    source_version: String(model.revision),
    element_key: key,
    title,
    report_title: tr("Datos"),
    href: "#my-business",
    content: {
      key,
      title,
      statement:
        tr("{0} filas", { 0: table.row_count }) +
        " · " +
        table.columns.map((column) => column.name).join(", "),
    },
  };
}
