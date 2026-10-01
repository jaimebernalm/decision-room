import { expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PresentationChangeReceipt } from "./presentation-receipt";
import { WorkspaceState, type WorkspaceContext } from "@/lib/workspace";
const context = {
  workspace: {
    business: { id: "b", name: "Café", description: "", profile_revision: 1 },
    businesses: [],
    analyses: [],
    configured: true,
    memory: {},
  },
  listing: {
    business_id: "b",
    conversations: [],
    datasets: { items: [], more: false },
  },
  route: "home",
  refresh: vi.fn(),
  removeChat: vi.fn(),
} satisfies WorkspaceContext;
it("undo uses the receipt revision and original base hash, rather than overwriting later edits", async () => {
  const calls: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init: RequestInit) => {
      calls.push(JSON.parse(String(init.body)));
      return { ok: true, json: async () => ({ saved: true }) };
    }),
  );
  render(
    <WorkspaceState.Provider value={context}>
      <PresentationChangeReceipt
        receipt={{
          report_id: "r",
          base_version: "approved",
          revision: 4,
          previous_revision: 3,
          title: "Ventas",
          href: "#report/j",
        }}
      />
    </WorkspaceState.Provider>,
  );
  expect(screen.getByRole("link", { name: "Ver informe" })).toHaveAttribute(
    "href",
    "#report/j",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Deshacer este cambio" }),
  );
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Deshecho" })).toBeDisabled(),
  );
  expect(calls[0]).toMatchObject({
    business_id: "b",
    base_version: "approved",
    revision: 4,
    restore_revision: 3,
  });
});
it("keeps an older receipt readable after reload and disables undo over subsequent edits", () => {
  render(
    <WorkspaceState.Provider value={context}>
      <PresentationChangeReceipt
        receipt={{
          report_id: "r",
          base_version: "approved",
          revision: 3,
          current_revision: 4,
          previous_revision: 2,
          title: "Ventas",
          href: "#report/j",
        }}
      />
    </WorkspaceState.Provider>,
  );
  expect(
    screen.getByRole("button", { name: "Versión anterior" }),
  ).toBeDisabled();
});
