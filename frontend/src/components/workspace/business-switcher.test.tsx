import { it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WorkspaceState, type WorkspaceContext } from "@/lib/workspace";
import { SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { BusinessSwitcher } from "./business-switcher";

function mount() {
  const business = {
    id: "a",
    name: "Café A",
    description: "Café",
    profile_revision: 1,
  };
  const context = {
    workspace: {
      business,
      businesses: [business, { ...business, id: "b", name: "Café B" }],
      analyses: [],
      configured: true,
      memory: {},
    },
    listing: {
      business_id: "a",
      conversations: [],
      datasets: { items: [], more: false },
    },
    route: "reports",
    refresh: vi.fn(),
    removeChat: vi.fn(),
  } satisfies WorkspaceContext;
  render(
    <TooltipProvider>
      <WorkspaceState.Provider value={context}>
        <SidebarProvider>
          <BusinessSwitcher />
        </SidebarProvider>
      </WorkspaceState.Provider>
    </TooltipProvider>,
  );
  return context;
}
it("shows actual businesses and waits for selection before navigating and refreshing", async () => {
  location.hash = "reports";
  let finish!: () => void;
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      await new Promise<void>((resolve) => {
        finish = resolve;
      });
      return { ok: true, json: async () => ({}) };
    }),
  );
  const context = mount();
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Café A" }));
  expect(
    screen.getByRole("menuitem", { name: "Café A, negocio activo" }),
  ).toBeVisible();
  expect(
    screen.getByRole("menuitem", { name: "Gestionar negocios" }),
  ).toHaveAttribute("href", "#businesses");
  expect(
    screen.getByRole("menuitem", { name: "Crear negocio" }),
  ).toHaveAttribute("href", "#business-new");
  await user.click(screen.getByRole("menuitem", { name: "Café B" }));
  expect(screen.getByRole("status")).toHaveTextContent("Cambiando de negocio");
  expect(location.hash).toBe("#reports");
  expect(context.refresh).not.toHaveBeenCalled();
  expect(fetch).toHaveBeenCalledWith(
    "/api/business/select",
    expect.objectContaining({ body: JSON.stringify({ business_id: "b" }) }),
  );
  finish();
  await waitFor(() => expect(context.refresh).toHaveBeenCalledTimes(1));
  expect(location.hash).toBe("#home");
  expect(screen.queryByRole("menu")).toBeNull();
});
it("keeps the active business and offers retry when selection fails", async () => {
  location.hash = "reports";
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: false,
      status: 409,
      json: async () => ({ error: "No se pudo cambiar de negocio" }),
    })),
  );
  const context = mount();
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Café A" }));
  await user.click(screen.getByRole("menuitem", { name: "Café B" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "No se pudo cambiar de negocio",
  );
  expect(screen.getByRole("menuitem", { name: "Café B" })).not.toHaveAttribute(
    "data-disabled",
  );
  expect(
    screen.getByRole("menuitem", { name: "Café A, negocio activo" }),
  ).toBeInTheDocument();
  expect(location.hash).toBe("#reports");
  expect(context.refresh).not.toHaveBeenCalled();
});
