import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useResource } from "@/lib/hooks";
import type { Question } from "@/lib/types";
import { ChoiceSelect, Disclosure, Loading, Notice } from "./shared";

type Preview = {
  tables: {
    id: string;
    name: string;
    row_count: number;
    column_count: number;
  }[];
  table_id: string;
  columns: string[];
  rows: { number: number; values: (string | null)[] }[];
  offset: number;
  column_offset: number;
  page_rows: number;
  page_columns: number;
  cell_characters: number;
};

export function DataPreview({
  jobId,
  questions = [],
  endpoint,
}: {
  jobId?: string;
  endpoint?: string;
  questions?: Question[];
}) {
  const refs = questions.flatMap((q) => q.references || []);
  const first = refs.find(
    (ref) => ref.kind === "column" || ref.kind === "table",
  );
  const [table, setTable] = useState(first?.id || "");
  const [offset, setOffset] = useState(0);
  const [columnOffset, setColumnOffset] = useState<number | null>(null);
  const query = new URLSearchParams({ offset: String(offset) });
  if (table) query.set("table", table);
  if (columnOffset !== null) query.set("column_offset", String(columnOffset));
  else if (first?.column && table === first.id)
    query.set("column", first.column);
  const resource = useResource<Preview>(
    `${endpoint || `/api/jobs/${jobId}/data`}?${query}`,
  );
  const data = resource.data;
  const selected = data?.tables.find((item) => item.id === data.table_id);
  const highlighted = new Set(
    refs
      .filter((ref) => ref.id === data?.table_id && ref.kind === "column")
      .map((ref) => ref.column),
  );
  return (
    <Disclosure title="Datos para responder" defaultOpen>
      <p className="text-xs text-muted-foreground">
        Consulta las filas del archivo mientras respondes. Las columnas
        mencionadas en la pregunta aparecen destacadas.
      </p>
      <Notice error>{resource.error}</Notice>
      {resource.error && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={resource.refresh}
        >
          Reintentar vista de datos
        </Button>
      )}
      {!data && !resource.error && <Loading />}
      {data && selected && (
        <>
          <ChoiceSelect
            label="Archivo o tabla"
            value={data.table_id}
            options={data.tables.map((item) => ({
              value: item.id,
              label: item.name,
            }))}
            onChange={(value) => {
              setTable(value);
              setOffset(0);
              setColumnOffset(0);
            }}
          />
          <p className="text-xs text-muted-foreground">
            {selected.row_count} filas · {selected.column_count} columnas ·
            Vista del archivo, sin cálculos
          </p>
          <div
            className="max-h-72 min-w-0 overflow-auto rounded-lg border"
            tabIndex={0}
            role="region"
            aria-label="Filas del archivo"
          >
            <table className="w-full text-left text-xs">
              <caption className="sr-only">Datos de {selected.name}</caption>
              <thead className="sticky top-0 z-10 bg-muted">
                <tr>
                  <th scope="col" className="p-3">
                    Fila
                  </th>
                  {data.columns.map((column) => (
                    <th
                      key={column}
                      scope="col"
                      aria-label={
                        highlighted.has(column)
                          ? `${column} (mencionada en la pregunta)`
                          : undefined
                      }
                      className={`whitespace-nowrap p-3 font-medium ${highlighted.has(column) ? "bg-primary/15 text-primary" : ""}`}
                    >
                      {column}
                      {highlighted.has(column) && (
                        <span className="sr-only">
                          {" "}
                          (mencionada en la pregunta)
                        </span>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <tr key={row.number} className="border-t">
                    <th
                      scope="row"
                      className="p-3 font-normal text-muted-foreground"
                    >
                      {row.number}
                    </th>
                    {row.values.map((value, i) => (
                      <td
                        key={i}
                        className={`max-w-64 break-words whitespace-pre-wrap p-3 ${highlighted.has(data.columns[i]) ? "bg-primary/5" : ""}`}
                      >
                        {value === null ? (
                          <span className="text-muted-foreground">Vacío</span>
                        ) : value === "" ? (
                          <span className="text-muted-foreground">
                            Texto vacío
                          </span>
                        ) : (
                          value
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!data.offset}
              onClick={() =>
                setOffset(Math.max(0, data.offset - data.page_rows))
              }
            >
              Filas anteriores
            </Button>
            <span className="text-xs">
              Filas {data.rows.length ? data.offset + 1 : 0}–
              {data.offset + data.rows.length} de {selected.row_count}
            </span>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={data.offset + data.rows.length >= selected.row_count}
              onClick={() => setOffset(data.offset + data.page_rows)}
            >
              Filas siguientes
            </Button>
          </div>
          {selected.column_count > data.page_columns && (
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={!data.column_offset}
                onClick={() =>
                  setColumnOffset(
                    Math.max(0, data.column_offset - data.page_columns),
                  )
                }
              >
                Columnas anteriores
              </Button>
              <span className="text-xs">
                Columnas {data.column_offset + 1}–
                {data.column_offset + data.columns.length} de{" "}
                {selected.column_count}
              </span>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={
                  data.column_offset + data.columns.length >=
                  selected.column_count
                }
                onClick={() =>
                  setColumnOffset(data.column_offset + data.page_columns)
                }
              >
                Columnas siguientes
              </Button>
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            Se muestran hasta {data.page_rows} filas por página. Las celdas de
            más de {data.cell_characters} caracteres se acortan con «…».
          </p>
        </>
      )}
    </Disclosure>
  );
}
