import { StrictMode } from "react";
import { act, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ProgressiveAnswer } from "./progressive-answer";
import type { Response } from "@/lib/types";
const text =
  "Esta es una respuesta revisada que aparece poco a poco y después muestra todas sus fuentes.";
const response = {
  kind: "grounded_answer",
  text,
  sources: [{ label: "Informe" }],
} as Response;
function View({
  id = "new",
  answer = response,
  animate = true,
}: {
  id?: string;
  answer?: Response;
  animate?: boolean;
}) {
  return (
    <ProgressiveAnswer id={id} response={answer} animate={animate}>
      {(value, revealing) => (
        <>
          <span data-testid="answer">{value?.text}</span>
          <span>{revealing ? "Mostrando" : "Listo"}</span>
          {value?.sources?.length ? <span>Fuentes</span> : null}
        </>
      )}
    </ProgressiveAnswer>
  );
}
it("reveals only new approved text then shows sources and completion together", async () => {
  vi.useFakeTimers();
  const view = render(<StrictMode><View /></StrictMode>);
  expect(screen.getByTestId("answer").textContent).toBe("");
  expect(screen.queryByText("Fuentes")).toBeNull();
  await act(async () => {
    vi.advanceTimersByTime(200);
  });
  expect(screen.getByTestId("answer").textContent!.length).toBeGreaterThan(0);
  expect(screen.getByTestId("answer").textContent).not.toBe(text);
  await act(async () => {
    vi.advanceTimersByTime(5000);
  });
  expect(screen.getByTestId("answer")).toHaveTextContent(text);
  expect(screen.getByText("Fuentes")).toBeVisible();
  expect(screen.getByText("Listo")).toBeVisible();
  view.unmount();
  render(<View />);
  expect(screen.queryByText("Mostrando")).toBeNull();
  vi.useRealTimers();
});
it("shows historical replies immediately and allows skipping a new one", () => {
  const view = render(<View id="history" animate={false} />);
  expect(screen.getByTestId("answer")).toHaveTextContent(text);
  view.unmount();
  render(<View id="skip" />);
  act(() =>
    screen.getByRole("button", { name: "Mostrar respuesta completa" }).click(),
  );
  expect(screen.getByText("Fuentes")).toBeVisible();
});
it("honors reduced motion and does not start a presentation timer", () => {
  const previous = window.matchMedia;
  window.matchMedia = () => ({ matches: true }) as MediaQueryList;
  render(<View id="reduced" />);
  expect(screen.getByText("Listo")).toBeVisible();
  expect(screen.queryByRole("button")).toBeNull();
  window.matchMedia = previous;
});
it("animates completion of a pending turn even when it existed on page load", async () => {
  vi.useFakeTimers();
  const view = render(
    <ProgressiveAnswer id="pending" animate={false}>
      {(value, revealing) => (
        <span>{revealing ? "Mostrando" : value?.text || "Esperando"}</span>
      )}
    </ProgressiveAnswer>,
  );
  view.rerender(
    <ProgressiveAnswer id="pending" animate={false} response={response}>
      {(value, revealing) => (
        <span>{revealing ? "Mostrando" : value?.text}</span>
      )}
    </ProgressiveAnswer>,
  );
  expect(screen.getByText("Mostrando")).toBeVisible();
  view.unmount();
  await act(async () => {
    vi.advanceTimersByTime(5000);
  });
  vi.useRealTimers();
});
