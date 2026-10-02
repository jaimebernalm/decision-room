import { expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WorkspaceState, type WorkspaceContext } from "@/lib/workspace";
import type { ChatListing } from "@/lib/types";
import { Chats } from "./overview";

const chat = {
  id: "old",
  business_id: "b",
  title: "Notas del negocio",
  created_at: "2026-10-02",
};
const listing: ChatListing = {
  business_id: "b",
  conversations: [chat],
  datasets: { items: [], more: false },
};
const business = {
  id: "b",
  name: "Tienda",
  description: "Prueba",
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
  listing,
  route: "chats",
  refresh: vi.fn(),
  removeChat: vi.fn(),
};
const response = (data: ChatListing) => ({ ok: true, json: async () => data });
function mount() {
  return render(
    <WorkspaceState.Provider value={context}>
      <Chats />
    </WorkspaceState.Provider>,
  );
}
it("searches saved messages through the server, shows a safe excerpt and clears to the complete list", async () => {
  const fetcher = vi.fn(async () =>
    response({
      ...listing,
      conversations: [
        {
          ...chat,
          search_match: {
            role: "assistant",
            text: "<img src=x onerror=alert(1)> C++ & café",
          },
        },
      ],
    }),
  );
  vi.stubGlobal("fetch", fetcher);
  mount();
  const user = userEvent.setup();
  const input = screen.getByRole("searchbox", { name: "Buscar chats" });
  expect(fetcher).not.toHaveBeenCalled();
  await user.type(input, "C++ & café");
  expect(screen.getByRole("status")).toHaveTextContent("Buscando chats");
  expect(await screen.findByText(/Asistente: <img/)).toBeVisible();
  expect(document.querySelector("img")).toBeNull();
  expect(fetcher).toHaveBeenCalledWith(
    "/api/chats?query=C%2B%2B%20%26%20caf%C3%A9",
    expect.objectContaining({ method: "GET" }),
  );
  await user.clear(input);
  expect(screen.queryByText(/Asistente: <img/)).toBeNull();
  expect(screen.getByText("Notas del negocio")).toBeVisible();
});
it("ignores a late search response after the query changes", async () => {
  let resolveFirst!: (value: ReturnType<typeof response>) => void;
  const fetcher = vi.fn(async (url: string) => {
    if (url.endsWith("=uno"))
      return await new Promise<ReturnType<typeof response>>((resolve) => {
        resolveFirst = resolve;
      });
    return response({
      ...listing,
      conversations: [{ ...chat, title: "Resultado dos" }],
    });
  });
  vi.stubGlobal("fetch", fetcher);
  mount();
  const user = userEvent.setup(),
    input = screen.getByRole("searchbox");
  await user.type(input, "uno");
  await waitFor(() => expect(fetcher).toHaveBeenCalledOnce());
  await user.clear(input);
  await user.type(input, "dos");
  expect(await screen.findByText("Resultado dos")).toBeVisible();
  resolveFirst(
    response({
      ...listing,
      conversations: [{ ...chat, title: "Resultado uno" }],
    }),
  );
  await waitFor(() => expect(screen.queryByText("Resultado uno")).toBeNull());
  expect(screen.getByText("Resultado dos")).toBeVisible();
});
it("distinguishes a failed search from no matches and supports retry", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: async () => ({ error: "Búsqueda interrumpida" }),
    })
    .mockResolvedValue(response({ ...listing, conversations: [] }));
  vi.stubGlobal("fetch", fetcher);
  mount();
  const user = userEvent.setup();
  await user.type(screen.getByRole("searchbox"), "ausente");
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Búsqueda interrumpida",
  );
  expect(
    screen.queryByText("No hay chats que coincidan con tu búsqueda."),
  ).toBeNull();
  await user.click(screen.getByRole("button", { name: "Reintentar" }));
  expect(
    await screen.findByText("No hay chats que coincidan con tu búsqueda."),
  ).toBeVisible();
  expect(
    screen.queryByText("Tus chats se guardan dentro de cada negocio."),
  ).toBeNull();
});
it("does not display search results returned for another business", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      response({
        ...listing,
        business_id: "other",
        conversations: [{ ...chat, title: "Chat ajeno" }],
      }),
    ),
  );
  mount();
  await userEvent.type(screen.getByRole("searchbox"), "ventas");
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "El negocio activo ha cambiado",
  );
  expect(screen.queryByText("Chat ajeno")).toBeNull();
});
