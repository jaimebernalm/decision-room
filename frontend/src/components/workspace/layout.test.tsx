import { it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { Layout } from "./layout";
import { WorkspaceState, type WorkspaceContext } from "@/lib/workspace";
import { TooltipProvider } from "@/components/ui/tooltip";

const business = {
  id: "b",
  name: "Café de prueba",
  description: "Café",
  profile_revision: 1,
};
function mount(route = "home", chats = 3, reports = 2) {
  const context = {
    workspace: {
      business,
      businesses: [business],
      configured: true,
      memory: {},
      analyses: Array.from({ length: reports }, (_, i) => ({
        id: `r${i}`,
        title: `Informe ${i}`,
        status: "completed",
        filename: "datos.csv",
        created_at: "2026-09-30",
      })),
    },
    listing: {
      business_id: "b",
      conversations: Array.from({ length: chats }, (_, i) => ({
        id: `c${i}`,
        business_id: "b",
        title: `Conversación ${i}`,
        created_at: "2026-09-30",
      })),
      datasets: { items: [], more: false },
    },
    route,
    refresh: vi.fn(),
    removeChat: vi.fn(),
  } satisfies WorkspaceContext;
  return render(
    <TooltipProvider>
      <WorkspaceState.Provider value={context}>
        <Layout>
          <main>Contenido</main>
        </Layout>
      </WorkspaceState.Provider>
    </TooltipProvider>,
  );
}
it("groups direct chats and reports once, with library access in the heading", () => {
  mount();
  const chats = within(screen.getByRole("region", { name: "Chats" }));
  const reports = within(screen.getByRole("region", { name: "Informes" }));
  expect(
    screen.queryByRole("link", { name: "Conversaciones" }),
  ).toBeNull();
  expect(screen.queryByText("Chats recientes")).toBeNull();
  expect(screen.queryByText("Informes recientes")).toBeNull();
  expect(
    chats.getByRole("link", { name: "Chats" }),
  ).toHaveAttribute("href", "#chats");
  expect(
    reports.getByRole("link", { name: "Informes" }),
  ).toHaveAttribute("href", "#reports");
  expect(chats.getByRole("link", { name: "Conversación 0" })).toHaveAttribute(
    "href",
    "#chat/c0",
  );
  expect(reports.getByRole("link", { name: "Informe 0" })).toHaveAttribute(
    "href",
    "#report/r0",
  );
  expect(screen.queryByRole("link", { name: /Ver todos los/ })).toBeNull();
});
it("keeps an older active chat visible and exposes complete libraries when bounded lists overflow", () => {
  mount("chat/c7", 8, 7);
  expect(screen.getByRole("link", { name: "Conversación 7" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(screen.queryByRole("link", { name: "Conversación 6" })).toBeNull();
  expect(
    screen.getByRole("link", { name: "Ver todos los chats" }),
  ).toHaveAttribute("href", "#chats");
  expect(
    screen.getByRole("link", { name: "Ver todos los informes" }),
  ).toHaveAttribute("href", "#reports");
});
it("keeps an older active report visible and identifies empty groups without hiding their library", () => {
  mount("report/r6", 0, 7);
  expect(screen.getByRole("link", { name: "Informe 6" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(screen.queryByRole("link", { name: "Informe 5" })).toBeNull();
  expect(screen.getByText("Todavía no hay chats")).toBeVisible();
  expect(
    screen.getByRole("link", { name: "Chats" }),
  ).toHaveAttribute("href", "#chats");
});

it("places the single new-chat action beside Chats, with no prominent header button", () => {
  const { container } = mount();
  const action = within(screen.getByRole("region", { name: "Chats" })).getByRole("link", { name: "Nuevo chat" });
  expect(action).toHaveAttribute("href", "#ask");
  expect(action).toHaveAttribute("title", "Nuevo chat");
  expect(screen.getAllByRole("link", { name: "Nuevo chat" })).toHaveLength(1);
  expect(container.querySelector('[data-slot="sidebar-header"] a[href="#ask"]')).toBeNull();
});
