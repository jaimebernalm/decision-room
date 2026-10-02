import { useState } from "react";
import { expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { WorkspaceState, type WorkspaceContext } from "@/lib/workspace";
import { Chats } from "./overview";

vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));
function mount(fail = false) {
  let pinned = false;
  const request = vi.fn(async (_url: string, init?: RequestInit) => {
    if (fail)
      return {
        ok: false,
        status: 503,
        json: async () => ({ error: "No se pudo guardar" }),
      };
    pinned = JSON.parse(String(init?.body)).pinned;
    return { ok: true, json: async () => ({ saved: true }) };
  });
  vi.stubGlobal("fetch", request);
  const business = {
    id: "b",
    name: "Tienda",
    description: "Prueba",
    profile_revision: 1,
  };
  function Harness() {
    const [, setRevision] = useState(0);
    const old = {
      id: "old",
      business_id: "b",
      title: "Chat antiguo",
      created_at: "2026-09-01",
      pinned_at: pinned ? "2026-10-02" : null,
    };
    const recent = {
      id: "recent",
      business_id: "b",
      title: "Chat reciente",
      created_at: "2026-10-01",
    };
    const value: WorkspaceContext = {
      workspace: {
        business,
        businesses: [business],
        configured: true,
        analyses: [],
        memory: {},
      },
      listing: {
        business_id: "b",
        conversations: pinned ? [old, recent] : [recent, old],
        datasets: { items: [], more: false },
      },
      route: "chats",
      refresh: () => setRevision((n) => n + 1),
      removeChat: vi.fn(),
    };
    return (
      <WorkspaceState.Provider value={value}>
        <Chats />
      </WorkspaceState.Provider>
    );
  }
  render(<Harness />);
  return { request, user: userEvent.setup() };
}
it("pins from the three-dot menu, refreshes the order and offers unpin", async () => {
  const { request, user } = mount();
  await user.click(
    screen.getByRole("button", { name: "Opciones de Chat antiguo" }),
  );
  await user.click(screen.getByRole("menuitem", { name: "Fijar chat" }));
  await waitFor(() =>
    expect(screen.getAllByRole("link")[1]).toHaveAttribute("href", "#chat/old"),
  );
  expect(request).toHaveBeenCalledWith(
    "/api/chats/old/pin",
    expect.objectContaining({
      body: JSON.stringify({ business_id: "b", pinned: true }),
    }),
  );
  expect(screen.getByLabelText("Chat fijado")).toBeVisible();
  await user.click(
    screen.getByRole("button", { name: "Opciones de Chat antiguo" }),
  );
  await user.click(screen.getByRole("menuitem", { name: "Desfijar chat" }));
  await waitFor(() =>
    expect(screen.queryByLabelText("Chat fijado")).toBeNull(),
  );
  expect(screen.getAllByRole("link")[1]).toHaveAttribute(
    "href",
    "#chat/recent",
  );
});
it("keeps the order and reports a failed pin without marking it saved", async () => {
  const { user } = mount(true);
  await user.click(
    screen.getByRole("button", { name: "Opciones de Chat antiguo" }),
  );
  await user.click(screen.getByRole("menuitem", { name: "Fijar chat" }));
  await waitFor(() =>
    expect(toast.error).toHaveBeenCalledWith("No se pudo guardar"),
  );
  expect(screen.queryByLabelText("Chat fijado")).toBeNull();
  expect(screen.getAllByRole("link")[1]).toHaveAttribute(
    "href",
    "#chat/recent",
  );
});
