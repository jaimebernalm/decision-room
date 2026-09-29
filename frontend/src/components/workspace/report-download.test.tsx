import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, it, expect, vi } from "vitest";
import { ReportDownload } from "./report-download";
import { TooltipProvider } from "@/components/ui/tooltip";
afterEach(() => vi.unstubAllGlobals());
it("offers an icon download with an accessible name and saves PDF bytes", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response("%PDF-1.7", {
          headers: { "Content-Type": "application/pdf" },
        }),
    ),
  );
  const create = vi.fn(() => "blob:pdf");
  const revoke = vi.fn();
  const click = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => {});
  vi.stubGlobal("URL", { createObjectURL: create, revokeObjectURL: revoke });
  render(
    <TooltipProvider>
      <ReportDownload url="/api/jobs/j/pdf" />
    </TooltipProvider>,
  );
  const button = screen.getByRole("button", { name: "Descargar informe" });
  expect(button.textContent).toBe("");
  await userEvent.click(button);
  await waitFor(() => expect(click).toHaveBeenCalledTimes(1));
  expect(create).toHaveBeenCalledTimes(1);
  click.mockRestore();
});
it("keeps publication errors visible without downloading JSON as a PDF", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({ error: "El informe necesita revisión." }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
    ),
  );
  render(
    <TooltipProvider>
      <ReportDownload url="/api/jobs/j/pdf" />
    </TooltipProvider>,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Descargar informe" }),
  );
  await screen.findByText("El informe necesita revisión.");
  expect(
    screen.getByRole("button", { name: "Descargar informe" }),
  ).toBeEnabled();
});
