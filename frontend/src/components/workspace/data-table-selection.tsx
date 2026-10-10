import { createContext, useContext, type ReactNode } from "react";
import { useResource } from "@/lib/hooks";
import { tableAttachment } from "./data-table-context";
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
  const item = table && model ? tableAttachment(model, table) : undefined;
  return (
    <div className="min-w-0 flex-1">
      <Selectable item={item}>{children}</Selectable>
    </div>
  );
}
