import { it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider } from "next-themes";
import { SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SpaceMenu } from "./space-menu";

function mount() {
  return render(
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      enableSystem
      scriptProps={{ type: "application/json" }}
    >
      <TooltipProvider>
        <SidebarProvider>
          <SpaceMenu />
        </SidebarProvider>
      </TooltipProvider>
    </ThemeProvider>,
  );
}
it.each([
  ["Claro", "light"],
  ["Oscuro", "dark"],
  ["Automático", "system"],
])(
  "persists the %s appearance choice and marks it when the menu reopens",
  async (label, value) => {
    const user = userEvent.setup();
    const rendered = mount();
    await user.click(
      screen.getByRole("button", { name: "Opciones del espacio local" }),
    );
    await user.click(screen.getByRole("menuitemradio", { name: label }));
    await waitFor(() => expect(localStorage.getItem("theme")).toBe(value));
    rendered.unmount();
    mount();
    await user.click(
      screen.getByRole("button", { name: "Opciones del espacio local" }),
    );
    expect(screen.getByRole("menuitemradio", { name: label })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(
      screen.getByRole("menuitem", { name: "Cómo funciona" }),
    ).toHaveAttribute("href", "#how");
  },
);
it("opens by keyboard and returns focus to the real local-space control on Escape", async () => {
  const user = userEvent.setup();
  mount();
  const trigger = screen.getByRole("button", {
    name: "Opciones del espacio local",
  });
  trigger.focus();
  await user.keyboard("{Enter}");
  expect(
    await screen.findByRole("menuitemradio", { name: "Automático" }),
  ).toBeVisible();
  await user.keyboard("{Escape}");
  await waitFor(() => expect(screen.queryByRole("menu")).toBeNull());
  expect(trigger).toHaveFocus();
});
