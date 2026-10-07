import { it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DossierDataGroups } from "./dossier-data";
import { contextKey, store } from "@/lib/api";
import { tableName } from "@/lib/table-name";
const dock = vi.fn();
vi.mock("@/lib/assistant", () => ({ useAssistant: () => ({ setDock: dock }) }));
vi.mock("@/lib/workspace", () => ({
  useWorkspace: () => ({ route: "my-business" }),
}));
vi.mock("./data-model", () => ({
  DataModelPanel: ({ analysis }: { analysis: string }) => (
    <div data-testid="model">{analysis}</div>
  ),
}));
const dataset = {
  id: "batch",
  title: "Ejemplo: ventas y productos",
  version: 1,
  status: "ready",
  original_files: [
    { path: "sales.csv", size: 90 },
    { path: "catalog.xlsx", size: 120 },
  ],
  files: [
    { id: "sales-source", name: "sales.csv", rows: 12 },
    { id: "sheet-source", name: "catalog.xlsx [Products].csv", rows: 5 },
  ],
};
it("lists actual files and worksheet tables without batch headings or versions", async () => {
  const upload = vi.fn(),
    user = userEvent.setup();
  render(
    <DossierDataGroups
      business="business"
      datasets={[dataset]}
      onUpload={upload}
    />,
  );
  expect(screen.queryByText(dataset.title)).toBeNull();
  expect(screen.queryByText("v1")).toBeNull();
  expect(
    screen.getByRole("link", { name: "Descargar catalog.xlsx" }),
  ).toHaveAttribute("href", "/api/datasets/original/batch?path=catalog.xlsx");
  expect(screen.getByText("Sales")).toBeVisible();
  expect(screen.getByText("Products")).toBeVisible();
  expect(screen.queryByText("catalog.xlsx [Products].csv")).toBeNull();
  expect(
    screen.getByRole("link", { name: "Descargar Products" }),
  ).toHaveAttribute("href", "/api/datasets/file/sheet-source");
  await user.click(screen.getByRole("button", { name: "Subir datos" }));
  expect(upload).toHaveBeenCalledOnce();
  await user.click(
    screen.getByRole("button", { name: "Preguntar sobre estas tablas" }),
  );
  expect(store.get(contextKey("business"), {})).toEqual({
    analysis_id: "batch",
    label: "Sales, Products",
  });
  expect(dock).toHaveBeenCalledWith({ open: true, origin: "my-business" });
});
it("hides archived and superseded data from the library without hiding current independent uploads", () => {
  render(
    <DossierDataGroups
      business="business"
      datasets={[
        { ...dataset, corrected: true },
        { ...dataset, id: "history", library_hidden: true },
        { ...dataset, id: "previous", superseded_by: "single" },
        { ...dataset, id: "single", files: [dataset.files[0]] },
      ]}
      onUpload={vi.fn()}
    />,
  );
  expect(screen.queryByTestId("model")).toBeNull();
  expect(
    screen.getByText("No hay conexiones entre tablas todavía."),
  ).toBeVisible();
  expect(screen.queryByText("Datos corregidos")).toBeNull();
  expect(screen.getAllByRole("link", { name: "Descargar Sales" })).toHaveLength(
    1,
  );
  expect(
    within(screen.getByRole("button", { name: /Tablas/ })).getByText("1"),
  ).toBeVisible();
});
it("preserves dotted table names and separates Excel worksheet names from source filenames", () => {
  expect(tableName("ventas.2026.csv")).toBe("Ventas.2026");
  expect(tableName("folder/catalog.xlsx [Ventas 2026].csv")).toBe(
    "Ventas 2026",
  );
  expect(tableName("Saldo diario")).toBe("Saldo diario");
});

it("opens the clicked table with actual columns and rows without reopening the map or changing context", async () => {
  const user = userEvent.setup();
  const fetch = vi.fn(async (url: string) => ({
    ok: true,
    json: async () => ({
      tables: [
        {
          id: "products-table",
          name: "catalog.xlsx [Products].csv",
          row_count: 55,
          column_count: 2,
        },
      ],
      table_id: "products-table",
      columns: ["producto_id", "nombre"],
      column_names: ["producto_id", "nombre"],
      rows: Array.from(
        { length: url.includes("offset=50") ? 5 : 50 },
        (_, i) => ({
          number: (url.includes("offset=50") ? 51 : 1) + i,
          values: [
            String((url.includes("offset=50") ? 51 : 1) + i),
            "Cuaderno",
          ],
        }),
      ),
      offset: url.includes("offset=50") ? 50 : 0,
      column_offset: 0,
      page_rows: 50,
      page_columns: 12,
      cell_characters: 500,
    }),
  }));
  vi.stubGlobal("fetch", fetch);
  store.set(contextKey("business"), {
    analysis_id: "unchanged",
    label: "Previous selection",
  });
  render(
    <DossierDataGroups
      business="business"
      datasets={[dataset]}
      onUpload={vi.fn()}
    />,
  );
  await user.click(screen.getByRole("button", { name: "Ver tabla Products" }));
  const dialog = await screen.findByRole("dialog", { name: "Products" });
  expect(
    await within(dialog).findByRole("columnheader", { name: "nombre" }),
  ).toBeVisible();
  expect(within(dialog).getAllByText("Cuaderno")[0]).toBeVisible();
  expect(within(dialog).queryByText("Datos para responder")).toBeNull();
  expect(within(dialog).queryByText("Archivo o tabla")).toBeNull();
  expect(fetch).toHaveBeenCalledWith(
    "/api/datasets/table/sheet-source?column_offset=0&offset=0",
    expect.anything(),
  );
  await user.type(
    within(dialog).getByRole("spinbutton", { name: "Ir a fila" }),
    "51",
  );
  await user.click(within(dialog).getByRole("button", { name: "Ir a fila" }));
  expect(await within(dialog).findByRole("cell", { name: "51" })).toBeVisible();
  expect(store.get(contextKey("business"), {})).toEqual({
    analysis_id: "unchanged",
    label: "Previous selection",
  });
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(
    screen.getByRole("button", { name: "Ver tabla Products" }),
  ).toHaveFocus();
});
it("keeps failed tables visibly unavailable and lets a failed preview retry", async () => {
  const user = userEvent.setup();
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ error: "Datos no disponibles" }),
    }),
  );
  render(
    <DossierDataGroups
      business="business"
      datasets={[
        {
          ...dataset,
          files: [
            ...dataset.files,
            { id: "bad", name: "failed.csv", status: "failed" },
          ],
        },
      ]}
      onUpload={vi.fn()}
    />,
  );
  expect(
    screen.getByRole("button", { name: "Ver tabla Failed" }),
  ).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Ver tabla Products" }));
  expect(await screen.findByText("Datos no disponibles")).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Reintentar vista de datos" }),
  ).toBeVisible();
});
