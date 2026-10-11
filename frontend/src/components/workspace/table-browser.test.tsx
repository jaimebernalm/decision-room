import { expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TableBrowser, type TableBlock } from "./table-browser";

function block(url: string, total = 1_000_000): TableBlock {
  const query = new URL(url, "http://localhost").searchParams;
  const offset = Number(query.get("offset") || 0);
  const filtered = !!(query.get("q") || query.get("filter_column"));
  const after = Number(query.get("after") || 0);
  const empty = query.get("q") === "missing";
  const cols = Number(query.get("column_offset") || 0);
  const names = Array.from({ length: 14 }, (_, i) => `column-${i}`);
  return {
    tables: [
      { id: "table", name: "public.csv", row_count: total, column_count: 14 },
    ],
    table_id: "table",
    columns: names.slice(cols, cols + 12),
    column_names: names,
    rows: empty
      ? []
      : Array.from(
          { length: Math.min(50, total - (filtered ? after : offset)) },
          (_, i) => ({
            number: (filtered ? after : offset) + i + 1,
            values: names
              .slice(cols, cols + 12)
              .map((_, col) =>
                col === 1
                  ? null
                  : `value-${(filtered ? after : offset) + i + 1}-${col + cols}`,
              ),
          }),
        ),
    offset,
    column_offset: cols,
    page_rows: 50,
    page_columns: 12,
    filtered,
    has_more: !empty && (filtered ? after : offset) + 50 < total,
    next_after: (filtered ? after : offset) + 50,
  };
}
function setup(total = 1_000_000) {
  const fetch = vi.fn(async (url: string) => ({
    ok: true,
    json: async () => block(url, total),
  }));
  vi.stubGlobal("fetch", fetch);
  render(<TableBrowser endpoint="/api/datasets/table/source" />);
  return { fetch, user: userEvent.setup() };
}
it("jumps directly to the last row of a million-row table without rendering or loading preceding rows", async () => {
  const { fetch, user } = setup();
  expect(await screen.findByText("value-1-0")).toBeVisible();
  await user.type(
    screen.getByRole("spinbutton", { name: "Ir a fila" }),
    "1000000",
  );
  await user.click(screen.getByRole("button", { name: "Ir a fila" }));
  expect(await screen.findByText("value-1000000-0")).toBeVisible();
  expect(fetch.mock.calls.some(([url]) => url.includes("offset=999950"))).toBe(
    true,
  );
  expect(fetch.mock.calls.length).toBeLessThanOrEqual(3);
  expect(screen.getAllByRole("row").length).toBeLessThan(30);
  expect(screen.getByRole("table")).toHaveAttribute("aria-rowcount", "1000001");
  expect(
    screen.getByRole("button", { name: "Filas anteriores" }),
  ).toBeEnabled();
});
it("loads visible blocks on scroll and reloads evicted blocks with bounded rendered rows", async () => {
  const { fetch } = setup(1000);
  await screen.findByText("value-1-0");
  const viewport = screen.getByRole("region", { name: "Filas del archivo" });
  for (const row of [60, 110, 160, 210, 260, 310, 360, 410]) {
    fireEvent.scroll(viewport, { target: { scrollTop: row * 40 } });
    await screen.findByText(`value-${row}-0`);
    expect(screen.getAllByRole("row").length).toBeLessThan(30);
  }
  const before = fetch.mock.calls.filter(([url]) =>
    url.includes("&offset=0"),
  ).length;
  fireEvent.scroll(viewport, { target: { scrollTop: 0 } });
  await screen.findByText("value-1-0");
  expect(
    fetch.mock.calls.filter(([url]) => url.includes("&offset=0")),
  ).toHaveLength(before + 1);
});
it("debounces search, continues by cursor, combines a column filter, and clears empty results", async () => {
  const { fetch, user } = setup(1000);
  await screen.findByText("value-1-0");
  await user.type(
    screen.getByRole("textbox", { name: "Buscar en la tabla" }),
    "needle",
  );
  await waitFor(() =>
    expect(fetch.mock.calls.some(([url]) => url.includes("q=needle"))).toBe(
      true,
    ),
  );
  expect(
    fetch.mock.calls.filter(([url]) => url.includes("q=needle")),
  ).toHaveLength(1);
  const viewport = await screen.findByRole("region", {
    name: "Filas del archivo",
  });
  fireEvent.scroll(viewport, { target: { scrollTop: 60 * 40 } });
  await screen.findByText("value-60-0");
  expect(fetch.mock.calls.some(([url]) => url.includes("after=50"))).toBe(true);
  await user.click(screen.getByRole("button", { name: "Filtrar" }));
  await user.selectOptions(
    screen.getByRole("combobox", { name: "Columna" }),
    "column-13",
  );
  await user.selectOptions(
    screen.getByRole("combobox", { name: "Condición" }),
    "empty",
  );
  await user.click(screen.getByRole("button", { name: "Aplicar" }));
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(
        ([url]) =>
          url.includes("filter_column=column-13") &&
          url.includes("filter_op=empty") &&
          url.includes("q=needle"),
      ),
    ).toBe(true),
  );
  await user.click(
    screen.getByRole("button", { name: "Quitar búsqueda y filtros" }),
  );
  await screen.findByText("value-1-0");
  await user.type(
    screen.getByRole("textbox", { name: "Buscar en la tabla" }),
    "missing",
  );
  expect(await screen.findByText("No hay resultados.")).toBeVisible();
  expect(screen.queryByText("value-1-0")).toBeNull();
});
it("keeps search when switching column blocks and preserves empty values", async () => {
  const { fetch, user } = setup(55);
  await screen.findByText("value-1-0");
  expect(screen.getAllByText("Vacío").length).toBeGreaterThan(0);
  await user.type(
    screen.getByRole("textbox", { name: "Buscar en la tabla" }),
    "needle",
  );
  await waitFor(() =>
    expect(fetch.mock.calls.some(([url]) => url.includes("q=needle"))).toBe(
      true,
    ),
  );
  await screen.findByRole("button", { name: "Columnas siguientes" });
  await user.click(screen.getByRole("button", { name: "Columnas siguientes" }));
  expect(
    await screen.findByRole("columnheader", { name: "column-13" }),
  ).toBeVisible();
  expect(fetch.mock.calls.at(-1)?.[0]).toContain("column_offset=12&q=needle");
});
it("shows a failed block error and retries without closing the window", async () => {
  const { fetch, user } = setup();
  await screen.findByText("value-1-0");
  fetch.mockResolvedValueOnce({
    ok: false,
    status: 503,
    json: async () => ({ error: "Archivo cambiado" }),
  } as never);
  fireEvent.scroll(screen.getByRole("region"), {
    target: { scrollTop: 60 * 40 },
  });
  expect(await screen.findByText("Archivo cambiado")).toBeVisible();
  await user.click(
    screen.getByRole("button", { name: "Reintentar vista de datos" }),
  );
  expect(await screen.findByText("value-60-0")).toBeVisible();
  expect(screen.queryByText("Archivo cambiado")).toBeNull();
});
it("aborts a pending read when a search replaces it and ignores its stale response", async () => {
  let resolve: (value: unknown) => void = () => {};
  const fetch = vi
    .fn()
    .mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    )
    .mockImplementation(async (url: string) => ({
      ok: true,
      json: async () => block(url, 55),
    }));
  vi.stubGlobal("fetch", fetch);
  render(<TableBrowser endpoint="/api/datasets/table/source" />);
  const user = userEvent.setup();
  await user.type(
    screen.getByRole("textbox", { name: "Buscar en la tabla" }),
    "missing",
  );
  await screen.findByText("No hay resultados.");
  expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
  resolve({ ok: true, json: async () => block("http://localhost", 55) });
  await waitFor(() => expect(screen.queryByText("value-1-0")).toBeNull());
});

it("keeps the end of filtered results after evicting and reloading earlier blocks", async () => {
  const { fetch, user } = setup(405);
  await screen.findByText("value-1-0");
  await user.type(
    screen.getByRole("textbox", { name: "Buscar en la tabla" }),
    "needle",
  );
  await waitFor(() =>
    expect(fetch.mock.calls.some(([url]) => url.includes("q=needle"))).toBe(
      true,
    ),
  );
  const viewport = await screen.findByRole("region", { name: "Filas del archivo" });
  for (const row of [45, 95, 145, 195, 245, 295, 345, 395]) {
    fireEvent.scroll(viewport, { target: { scrollTop: row * 40 } });
    await screen.findByText(`value-${row + 10}-0`);
  }
  expect(screen.queryByRole("rowheader", { name: "406" })).toBeNull();
  fireEvent.scroll(viewport, { target: { scrollTop: 0 } });
  await screen.findByText("value-1-0");
  fireEvent.scroll(viewport, { target: { scrollTop: 395 * 40 } });
  await screen.findByText("value-405-0");
  // No blank placeholder rows beyond the known final match.
  expect(screen.queryAllByRole("rowheader", { name: "…" })).toHaveLength(0);
});

it("clears previously visible values when access or integrity is rejected", async () => {
  const { fetch, user } = setup();
  await screen.findByText("value-1-0");
  fetch.mockResolvedValueOnce({
    ok: false,
    status: 409,
    json: async () => ({ error: "Datos guardados cambiados" }),
  } as never);
  fireEvent.scroll(screen.getByRole("region"), {
    target: { scrollTop: 60 * 40 },
  });
  await screen.findByText("Datos guardados cambiados");
  expect(screen.queryByRole("table")).toBeNull();
  await user.click(
    screen.getByRole("button", { name: "Reintentar vista de datos" }),
  );
  expect(await screen.findByText("value-1-0")).toBeVisible();
});
