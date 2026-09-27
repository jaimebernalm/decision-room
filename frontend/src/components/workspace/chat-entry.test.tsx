import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AssistantProvider, useAssistant } from "@/lib/assistant";
import { WorkspaceState } from "@/lib/workspace";
import { ChatPage } from "./chat";
const preference = vi.hoisted(() => ({ reduced: false }));
vi.mock("motion/react", async (original) => ({
  ...(await original<typeof import("motion/react")>()),
  useReducedMotion: () => preference.reduced,
}));
const originalAnimate = HTMLElement.prototype.animate;
afterEach(() => {
  preference.reduced = false;
  vi.restoreAllMocks();
  if (originalAnimate) HTMLElement.prototype.animate = originalAnimate;
  else delete (HTMLElement.prototype as Partial<HTMLElement>).animate;
});
function setup(reduced = false) {
  preference.reduced = reduced;
  let finish!: () => void;
  const finished = new Promise<Animation>((resolve) => {
    finish = () => resolve({} as Animation);
  });
  const cancel = vi.fn();
  const animate = vi.fn(function (this: HTMLElement) {
    return {
      finished: this.hasAttribute("data-composer-entry")
        ? finished
        : Promise.resolve(),
      cancel,
      play: vi.fn(),
      pause: vi.fn(),
      effect: { getKeyframes: () => [] },
    } as unknown as Animation;
  });
  HTMLElement.prototype.animate = animate;
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    x: 100,
    y: 600,
    width: 672,
    height: 56,
    top: 600,
    bottom: 656,
    left: 100,
    right: 772,
    toJSON: () => ({}),
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        conversation: { id: "chat", business_id: "a" },
        turns: [
          {
            id: "turn",
            payload: { text: "Mi primera pregunta" },
            status: "completed",
            response: { kind: "answer", text: "Respuesta de prueba" },
          },
        ],
        memory_items: [],
        memory: {},
      }),
    })),
  );
  function Page() {
    const a = useAssistant()!;
    const [open, setOpen] = useState(false);
    return open ? (
      <ChatPage id="chat" />
    ) : (
      <button
        onClick={() => {
          a.setChatEntry({
            chatId: "chat",
            rect: { x: 100, y: 240, width: 672, height: 56 },
          });
          setOpen(true);
        }}
      >
        Abrir prueba
      </button>
    );
  }
  const mounted = render(
    <TooltipProvider>
      <WorkspaceState.Provider
        value={{
          workspace: {
            business: {
              id: "a",
              name: "Test",
              description: "Test",
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
          route: "chat/chat",
          refresh: vi.fn(),
          removeChat: vi.fn(),
        }}
      >
        <AssistantProvider>
          <Page />
        </AssistantProvider>
      </WorkspaceState.Provider>
    </TooltipProvider>,
  );
  return { user: userEvent.setup(), animate, finish, cancel, mounted };
}
it("keeps one composer and waits for its arrival before displaying messages", async () => {
  const { user, animate, finish } = setup();
  await user.click(screen.getByRole("button", { name: "Abrir prueba" }));
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(animate).toHaveBeenCalled();
  expect(screen.getAllByRole("textbox", { name: "Mensaje" })).toHaveLength(1);
  expect(screen.queryByText("Mi primera pregunta")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Enviar mensaje" })).toBeDisabled();
  await act(async () => finish());
  expect(await screen.findByText("Mi primera pregunta")).toBeVisible();
  expect(screen.getByRole("textbox", { name: "Mensaje" })).toHaveFocus();
});
it("shows messages immediately when reduced motion is preferred", async () => {
  const { user, animate } = setup(true);
  await user.click(screen.getByRole("button", { name: "Abrir prueba" }));
  expect(await screen.findByText("Mi primera pregunta")).toBeVisible();
  expect(animate).not.toHaveBeenCalled();
});
it("cancels the entry animation when leaving the conversation", async () => {
  const { user, mounted, cancel, finish } = setup();
  await user.click(screen.getByRole("button", { name: "Abrir prueba" }));
  mounted.unmount();
  expect(cancel).toHaveBeenCalled();
  await act(async () => finish());
  expect(screen.queryByText("Mi primera pregunta")).not.toBeInTheDocument();
});
