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

const business = {
  id: "lang",
  name: "Nombre propio",
  description: "Descripción del propietario",
  profile_revision: 1,
};
const context: WorkspaceContext = {
  workspace: {
    business,
    businesses: [business],
    analyses: [],
    configured: true,
    memory: {},
  },
  listing: {
    business_id: "lang",
    conversations: [],
    datasets: { items: [], more: false },
  },
  route: "ask",
  refresh: vi.fn(),
  removeChat: vi.fn(),
};
function mount(children = <StartChat />, route = "ask") {
  return render(
    <ThemeProvider
      defaultTheme="light"
      scriptProps={{ type: "application/json" }}
    >
      <TooltipProvider>
        <WorkspaceState.Provider value={{ ...context, route }}>
          <Layout>{children}</Layout>
        </WorkspaceState.Provider>
      </TooltipProvider>
    </ThemeProvider>,
  );
}
it("switches to English through Language without resetting the current draft", async () => {
  const user = userEvent.setup();
  mount();
  await user.type(
    screen.getByRole("textbox", { name: "Mensaje" }),
    "Borrador que debe conservarse",
  );
  await user.click(
    screen.getByRole("button", { name: "Opciones del espacio local" }),
  );
  await user.hover(screen.getByRole("menuitem", { name: "Idioma" }));
  const option = await screen.findByRole("menuitemradio", { name: "English" });
  option.focus();
  await user.keyboard("{Enter}");
  await waitFor(() =>
    expect(screen.getByRole("link", { name: "Home" })).toBeVisible(),
  );
  expect(screen.getByRole("textbox", { name: "Message" })).toHaveValue(
    "Borrador que debe conservarse",
  );
  expect(screen.getByRole("textbox", { name: "Message" })).toHaveAttribute(
    "placeholder",
    "Ask a question or add context…",
  );
  expect(document.documentElement.lang).toBe("en");
  expect(screen.getByRole("button", { name: "Nombre propio" })).toBeVisible();
});
it("renders the libraries, status labels and business form in English with original profile values", () => {
  setLanguage("en");
  const rendered = mount(
    <>
      <Chats />
      <Status status="waiting" />
    </>,
    "chats",
  );
  expect(screen.getByRole("heading", { name: "Chats" })).toBeVisible();
  expect(screen.getByText("Needs your answer")).toBeVisible();
  rendered.unmount();
  mount(<BusinessForm />, "business");
  expect(screen.getByLabelText("Business name")).toHaveValue("Nombre propio");
  expect(screen.getByLabelText("Tell us what you do")).toHaveValue(
    "Descripción del propietario",
  );
});
it("keeps the chat library and search vocabulary consistent when switching languages", async () => {
  setLanguage("es");
  mount(<Chats />, "chats");
  expect(screen.getByRole("heading", { name: "Chats" })).toBeVisible();
  expect(
    screen.getByRole("searchbox", { name: "Buscar chats" }),
  ).toHaveAttribute("placeholder", "Buscar por título o mensaje…");
  expect(
    screen.getByText("Tus chats se guardan dentro de cada negocio."),
  ).toBeVisible();
  setLanguage("en");
  expect(
    await screen.findByRole("searchbox", { name: "Search chats" }),
  ).toHaveAttribute("placeholder", "Search titles or messages…");
  expect(screen.getByRole("heading", { name: "Chats" })).toBeVisible();
  expect(
    screen.getByText("Your chats are saved within each business."),
  ).toBeVisible();
});
it("renders public entry and help in English and returns to Spanish immediately", async () => {
  setLanguage("en");
  const rendered = render(
    <WorkspaceState.Provider value={context}>
      <Welcome signedIn />
    </WorkspaceState.Provider>,
  );
  expect(
    screen.getByRole("heading", { name: "Your data has a lot to tell you." }),
  ).toBeVisible();
  rendered.unmount();
  mount(<How />, "how");
  expect(
    screen.getByRole("heading", { name: "From data to a decision" }),
  ).toBeVisible();
  setLanguage("es");
  await screen.findByRole("heading", { name: "De tus datos a una decisión" });
});

it("localizes formatted report numbers while preserving category names and raw evidence decimals", async () => {
  const { ReportView } = await import("./report");
  const { within } = await import("@testing-library/react");
  setLanguage("en");
  mount(
    <ReportView
      report={{
        title: "Informe del propietario",
        scope: { period: "Julio", coverage: "Registros originales" },
        highlights: [
          {
            label: "Producto 1.000",
            value: "1.234,50",
            unit: "EUR",
            claim_key: "c",
          },
        ],
        claims: [
          {
            key: "c",
            title: "Mi conclusión",
            statement: "Texto original.",
            interpretation: "",
            method: "",
            next_step: "",
            evidence_details: {
              files: ["original.csv"],
              metrics: [{ label: "raw", value: "20.005" }],
              operations: [],
            },
          },
        ],
        charts: [
          {
            key: "chart",
            kind: "table",
            title: "Mi tabla",
            unit: "EUR",
            caption: "",
            claim_key: "c",
            points: [{ label: "1.000", value: "20.005", formatted: "20,005" }],
          },
        ],
        limitations: [],
      }}
    />,
    "report/test",
  );
  expect(screen.getByText("1,234.50")).toBeVisible();
  expect(screen.getByText("Producto 1.000")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: /Mi conclusión/ }));
  await userEvent.click(
    screen.getByRole("button", { name: "Sources and evidence" }),
  );
  expect(await screen.findByText("raw: 20.005")).toBeVisible();
  const table = within(screen.getByRole("table"));
  expect(table.getByText("1.000")).toBeVisible();
  expect(table.getByText("20.005")).toBeVisible();
});
