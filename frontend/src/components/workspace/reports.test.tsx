import { useState } from "react";
import { expect, it, vi } from "vitest";
import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import { WorkspaceState } from "@/lib/workspace";
import { AssistantProvider } from "@/lib/assistant";
import type { Analysis } from "@/lib/types";
import { Reports } from "./reports";
import { SelectionTool, ContextAttachments } from "./context-selection";
import { useAssistant } from "@/lib/assistant";
const available: Analysis = {
  id: "available",
  title: "Ventas revisadas",
  filename: "ventas.csv",
  status: "completed",
  created_at: "2026-09-27",
  context_reference: {
    kind: "report",
    element_key: "report",
    report_id: "review",
    report_version: "v1",
    title: "Ventas revisadas",
  },
};
const withdrawn: Analysis = {
  ...available,
  id: "withdrawn",
  title: "Informe retirado",
  status: "blocked",
  presentation_status: "withdrawn",
  context_reference: undefined,
};
function setup() {
  const deleted = new Set<string>();
  const calls: { url: string; body: unknown }[] = [];
  let fail = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, body: init?.body && JSON.parse(String(init.body)) });
      if (fail && init?.body)
        return {
          ok: false,
          status: 503,
          json: async () => ({ error: "No se pudo guardar" }),
        };
      if (url.endsWith("/delete")) deleted.add(url.split("/")[3]);
      if (url.endsWith("/restore")) deleted.delete(url.split("/")[3]);
      return {
        ok: true,
        json: async () =>
          url === "/api/reports/deleted"
            ? { items: [available, withdrawn].filter((a) => deleted.has(a.id)) }
            : { saved: true },
      };
    }),
  );
  function Tools() {
    const a = useAssistant()!;
    return (
      <>
        <SelectionTool />
        <ContextAttachments items={a.selected} />
      </>
    );
  }
  function Harness() {
    const [, refresh] = useState(0);
    return (
      <TooltipProvider>
        <WorkspaceState.Provider
          value={{
            workspace: {
              business: {
                id: "business",
                name: "Test",
                description: "Test",
                profile_revision: 1,
              },
              businesses: [],
              analyses: [available, withdrawn].filter(
                (a) => !deleted.has(a.id),
              ),
              configured: true,
              memory: {},
            },
            listing: {
              business_id: "business",
              conversations: [],
              datasets: { items: [], more: false },
            },
            route: "reports",
            refresh: () => refresh((n) => n + 1),
            removeChat: vi.fn(),
          }}
        >
          <AssistantProvider>
            <Reports />
            <Tools />
          </AssistantProvider>
        </WorkspaceState.Provider>
      </TooltipProvider>
    );
  }
  render(<Harness />);
  return {
    user: userEvent.setup(),
    calls,
    setFail: (value: boolean) => {
      fail = value;
    },
  };
}
it("selects the report while withdrawn rows explain unavailability and do not navigate", async () => {
  location.hash = "reports";
  const { user } = setup();
  await user.click(screen.getByRole("button", { name: "Seleccionar" }));
  const retired = screen.getByText("Retirado").closest("tr")!;
  expect(within(retired).getByText("No se puede seleccionar")).toBeVisible();
  expect(
    within(retired).queryByRole("button", { name: /Seleccionar:/ }),
  ).toBeNull();
  await user.click(retired);
  expect(location.hash).toBe("#reports");
  await user.click(
    screen.getByRole("button", { name: "Seleccionar: Ventas revisadas" }),
  );
  expect(location.hash).toBe("#reports");
  expect(
    screen.getByRole("button", { name: "Ver adjunto: Ventas revisadas" }),
  ).toHaveTextContent("Informe");
});
it("confirms deletion, preserves failures and restores reports from trash", async () => {
  const { user, calls, setFail } = setup();
  await user.click(
    screen.getByRole("button", { name: "Eliminar Informe retirado" }),
  );
  await user.click(screen.getByRole("button", { name: "Cancelar" }));
  expect(calls).toHaveLength(0);
  await user.click(
    screen.getByRole("button", { name: "Eliminar Informe retirado" }),
  );
  setFail(true);
  await user.click(screen.getByRole("button", { name: "Mover a la papelera" }));
  expect(await screen.findByText("No se pudo guardar")).toBeVisible();
  expect(screen.getByRole("alertdialog")).toBeVisible();
  setFail(false);
  await user.click(screen.getByRole("button", { name: "Mover a la papelera" }));
  await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  expect(screen.queryByRole("link", { name: "Informe retirado" })).toBeNull();
  expect(screen.getByRole("link", { name: "Ventas revisadas" })).toBeVisible();
  expect(calls.at(-1)).toEqual({
    url: "/api/jobs/withdrawn/delete",
    body: { business_id: "business" },
  });
  await user.click(screen.getByRole("button", { name: "Papelera" }));
  await user.click(
    await screen.findByRole("button", { name: "Restaurar Informe retirado" }),
  );
  await screen.findByText("La papelera está vacía.");
  await user.click(screen.getByRole("button", { name: "Volver a informes" }));
  expect(screen.getByRole("link", { name: "Informe retirado" })).toBeVisible();
});
