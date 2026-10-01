import { it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { Composer } from "./composer";
import { ReportView } from "./report";
import { FloatingAssistant } from "./floating-assistant";
import { StartChat, Reports } from "./overview";
import { WorkspaceState, type WorkspaceContext } from "@/lib/workspace";
import { store } from "@/lib/api";
const workspace = {
  workspace: {
    business: {
      id: "a",
      name: "Negocio",
      description: "Descripción",
      profile_revision: 1,
    },
    businesses: [],
    analyses: [],
    configured: true,
    memory: {},
  },
  listing: {
    business_id: "a",
    conversations: [],
    datasets: { items: [], more: false },
  },
  route: "ask",
  refresh: vi.fn(),
  removeChat: vi.fn(),
} satisfies WorkspaceContext;
it("opens available reports directly and keeps progress or recovery for other states", () => {
  const states = [
    "completed",
    "running",
    "waiting",
    "outdated",
    "withdrawn",
    "historical",
  ];
  render(
    <WorkspaceState.Provider
      value={{
        ...workspace,
        workspace: {
          ...workspace.workspace,
          analyses: states.map((status) => ({
            id: status,
            title: status,
            status,
            presentation_status: status,
            filename: "datos.csv",
            created_at: "2026-09-26",
          })),
        },
      }}
    >
      <Reports />
    </WorkspaceState.Provider>,
  );
  for (const status of states)
    expect(screen.getByRole("link", { name: status })).toHaveAttribute(
      "href",
      `#${["completed", "historical"].includes(status) ? "report" : "analysis"}/${status}`,
    );
  expect(screen.getByText("En preparación")).toBeInTheDocument();
});
it("opens an empty standalone conversation with one focused composer", () => {
  render(
    <WorkspaceState.Provider value={workspace}>
      <StartChat />
    </WorkspaceState.Provider>,
  );
  expect(
    screen.getByRole("heading", { name: "Nueva conversación" }),
  ).toBeInTheDocument();
  expect(screen.getAllByRole("textbox", { name: "Mensaje" })).toHaveLength(1);
  expect(screen.getByRole("textbox", { name: "Mensaje" })).toHaveFocus();
  expect(
    screen.queryByRole("region", { name: "Conversaciones recientes" }),
  ).toBeNull();
  expect(
    screen.queryByRole("button", { name: "Minimizar asistente" }),
  ).toBeNull();
});
it("official composer keeps controlled draft after submit failure and supports Shift+Enter", async () => {
  const send = vi.fn(async () => {
    throw new Error("offline");
  });
  function Form() {
    const [text, setText] = useState("Mi pregunta");
    return (
      <Composer
        text={text}
        onChange={setText}
        busy={false}
        onSend={async () => {
          try {
            await send();
          } catch {
            /* owner draft stays editable */
          }
        }}
      />
    );
  }
  render(<Form />);
  const user = userEvent.setup(),
    input = screen.getByRole("textbox", { name: "Mensaje" });
  await user.click(input);
  await user.keyboard("{Shift>}{Enter}{/Shift}");
  expect(send).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Enviar mensaje" }));
  expect(send).toHaveBeenCalledOnce();
  expect(input).toHaveValue("Mi pregunta\n");
});
it("unmounting the floating assistant prevents a late response redirecting another business", async () => {
  let finish: () => void = () => {};
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url === "/api/chats")
        await new Promise<void>((r) => {
          finish = r;
        });
      return { ok: true, json: async () => ({ id: "chat" }) };
    }),
  );
  store.set("dr-home-prompt-a", "Pregunta");
  const rendered = render(
    <WorkspaceState.Provider value={workspace}>
      <FloatingAssistant inline />
    </WorkspaceState.Provider>,
  );
  await userEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));
  rendered.unmount();
  location.hash = "businesses";
  finish();
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  expect(location.hash).toBe("#businesses");
});
it("shows approved formatting and exact values, with escaped claim text", async () => {
  render(
    <ReportView
      report={{
        title: "Ventas",
        scope: { period: "Junio", coverage: "Solo datos seleccionados" },
        highlights: [
          { label: "Total", value: "1.234,56", unit: "EUR", claim_key: "c" },
        ],
        charts: [],
        claims: [
          {
            key: "c",
            title: "Resultado",
            statement: "<img src=x onerror=alert(1)>",
            interpretation: "Interpretación",
            method: "Suma",
            next_step: "Revisar detalle",
          },
        ],
        limitations: ["No incluye julio"],
      }}
    />,
  );
  expect(screen.getByText("1.234,56")).toBeInTheDocument();
  expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
  expect(document.querySelector("img")).toBeNull();
  expect(screen.getByText(/Revisar detalle/)).toBeInTheDocument();
  expect(screen.queryByText("Suma")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Resultado/ }));
  await userEvent.click(screen.getByRole("button", { name: /Cómo se ha calculado/ }));
  expect(screen.getByText("Suma")).toBeInTheDocument();
  expect(screen.getByText(/Revisar detalle/)).toBeInTheDocument();
});

it("preserves explicit analysis context without showing a dataset selector", async () => {
  const calls: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, options: RequestInit) => {
      calls.push({ url, body: JSON.parse(options.body as string) });
      return { ok: true, json: async () => ({ id: "chat" }) };
    }),
  );
  const context = {
    ...workspace,
    listing: {
      ...workspace.listing,
      datasets: {
        items: [
          {
            id: "table-id",
            analysis_id: "analysis-id",
            description: "Ventas junio",
            dataset_version: 2,
            names: ["sales.csv"],
            columns: ["amount"],
          },
        ],
        more: false,
      },
    },
  };
  store.set("dr-question-context-a", {
    analysis_id: "analysis-id",
    label: "Ventas junio · v2",
  });
  render(
    <WorkspaceState.Provider value={context}>
      <FloatingAssistant inline />
    </WorkspaceState.Provider>,
  );
  const user = userEvent.setup();
  expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  expect(screen.getByText("Ventas junio · v2")).toBeInTheDocument();
  await user.type(screen.getByRole("textbox", { name: "Mensaje" }), "Pregunta");
  await user.click(screen.getByRole("button", { name: "Enviar mensaje" }));
  await waitFor(() => expect(calls.length).toBe(2));
  expect(calls[0].body.analysis_id).toBe("analysis-id");
});
