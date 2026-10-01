import { it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider } from "next-themes";
import { TooltipProvider } from "@/components/ui/tooltip";
import { WorkspaceState, type WorkspaceContext } from "@/lib/workspace";
import { setLanguage } from "@/lib/i18n";
import { Layout } from "./layout";
import { StartChat, How, Chats } from "./overview";
import { BusinessForm } from "./business";
import { Welcome } from "@/components/entry/welcome";
import { Status } from "./shared";

const business = { id: "lang", name: "Nombre propio", description: "Descripción del propietario", profile_revision: 1 };
const context: WorkspaceContext = {
  workspace: { business, businesses: [business], analyses: [], configured: true, memory: {} },
  listing: { business_id: "lang", conversations: [], datasets: { items: [], more: false } },
  route: "ask", refresh: vi.fn(), removeChat: vi.fn(),
};
function mount(children = <StartChat />, route = "ask") {
  return render(<ThemeProvider defaultTheme="light" scriptProps={{ type: "application/json" }}><TooltipProvider>
    <WorkspaceState.Provider value={{ ...context, route }}><Layout>{children}</Layout></WorkspaceState.Provider>
  </TooltipProvider></ThemeProvider>);
}
it("switches to English through Language without resetting the current draft", async () => {
  const user = userEvent.setup();
  mount();
  await user.type(screen.getByRole("textbox", { name: "Mensaje" }), "Borrador que debe conservarse");
  await user.click(screen.getByRole("button", { name: "Opciones del espacio local" }));
  await user.hover(screen.getByRole("menuitem", { name: "Idioma" }));
  const option = await screen.findByRole("menuitemradio", { name: "English" });
  option.focus(); await user.keyboard("{Enter}");
  await waitFor(() => expect(screen.getByRole("link", { name: "Home" })).toBeVisible());
  expect(screen.getByRole("textbox", { name: "Message" })).toHaveValue("Borrador que debe conservarse");
  expect(screen.getByRole("textbox", { name: "Message" })).toHaveAttribute("placeholder", "Ask a question or add context…");
  expect(document.documentElement.lang).toBe("en");
  expect(screen.getByRole("button", { name: "Nombre propio" })).toBeVisible();
});
it("renders the libraries, status labels and business form in English with original profile values", () => {
  setLanguage("en");
  const rendered = mount(<><Chats /><Status status="waiting" /></>, "chats");
  expect(screen.getByRole("heading", { name: "Conversations" })).toBeVisible();
  expect(screen.getByText("Needs your answer")).toBeVisible();
  rendered.unmount();
  mount(<BusinessForm />, "business");
  expect(screen.getByLabelText("Business name")).toHaveValue("Nombre propio");
  expect(screen.getByLabelText("Tell us what you do")).toHaveValue("Descripción del propietario");
});
it("renders public entry and help in English and returns to Spanish immediately", async () => {
  setLanguage("en");
  const rendered = render(<WorkspaceState.Provider value={context}><Welcome signedIn /></WorkspaceState.Provider>);
  expect(screen.getByRole("heading", { name: "Your data has a lot to tell you." })).toBeVisible();
  rendered.unmount();
  mount(<How />, "how");
  expect(screen.getByRole("heading", { name: "From data to a decision" })).toBeVisible();
  setLanguage("es");
  await screen.findByRole("heading", { name: "De tus datos a una decisión" });
});
