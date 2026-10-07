import { createContext, useContext, type ReactNode } from "react";
import { useResource } from "@/lib/hooks";
import { translate as tr } from "@/lib/i18n";
import type { ContextAttachment } from "@/lib/types";
import { tableName } from "@/lib/table-name";
import type { DataModel } from "./data-model";
import { Selectable } from "./context-selection";

const TableModelContext = createContext<DataModel | null>(null);

export function DataTableContext({
  business,
  analysis,
  children,
}: {
  business: string;
  analysis: string;
  children: ReactNode;
}) {
  const { data } = useResource<{
    model: DataModel | null;
    needs_refresh?: boolean;
  }>(
    `/api/business/data-model?business_id=${business}&analysis_id=${analysis}`,
  );
  return (
    <TableModelContext.Provider
      value={data?.needs_refresh ? null : data?.model || null}
    >
      {children}
    </TableModelContext.Provider>
  );
}

export function TableSelection({
  source,
  children,
}: {
  source: string;
  children: ReactNode;
}) {
  const model = useContext(TableModelContext);
  const table = model?.body.tables.find((table) => table.source_id === source);
  const title = table && tr("Tabla: {0}", { 0: tableName(table.name) });
  const item: ContextAttachment | undefined =
    table && model
      ? {
          kind: "data_model",
          source_id: model.analysis_id,
          source_version: String(model.revision),
          element_key: `table:${table.id}`,
          title,
          report_title: tr("Datos"),
          href: "#my-business",
          content: {
            key: `table:${table.id}`,
            title: title!,
            statement:
              tr("{0} filas", { 0: table.row_count }) +
              " · " +
              table.columns.map((column) => column.name).join(", "),
          },
        }
      : undefined;
  return (
    <div className="min-w-0 flex-1">
      <Selectable item={item}>{children}</Selectable>
    </div>
  );
}
