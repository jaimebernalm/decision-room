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
it("does not put corrected or single-table batches in the connections map", () => {
  render(
    <DossierDataGroups
      business="business"
      datasets={[
        { ...dataset, corrected: true },
        { ...dataset, id: "single", files: [dataset.files[0]] },
      ]}
      onUpload={vi.fn()}
    />,
  );
  expect(screen.queryByTestId("model")).toBeNull();
  expect(
    screen.getByText("No hay conexiones entre tablas todavía."),
  ).toBeVisible();
  expect(screen.getAllByText("Datos corregidos")).toHaveLength(2);
  expect(
    within(screen.getByRole("button", { name: /Tablas/ })).getByText("3"),
  ).toBeVisible();
});
it("preserves dotted table names and separates Excel worksheet names from source filenames", () => {
  expect(tableName("ventas.2026.csv")).toBe("Ventas.2026");
  expect(tableName("folder/catalog.xlsx [Ventas 2026].csv")).toBe(
    "Ventas 2026",
  );
  expect(tableName("Saldo diario")).toBe("Saldo diario");
});
