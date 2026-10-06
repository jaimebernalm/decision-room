import { expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ResizeHandle } from "./resize-handle";

function mount(direction: 1 | -1, getWidth?: () => number) {
  const onResize = vi.fn();
  render(
    <ResizeHandle
      label="Anchura"
      className=""
      width={256}
      min={216}
      max={420}
      step={16}
      direction={direction}
      onResize={onResize}
      getWidth={getWidth}
    />,
  );
  const handle = screen.getByRole("separator", { name: "Anchura" });
  handle.setPointerCapture = vi.fn();
  handle.hasPointerCapture = () => true;
  handle.releasePointerCapture = vi.fn();
  return { handle, onResize };
}
function pointer(handle: HTMLElement, type: string, x: number) {
  fireEvent(
    handle,
    new MouseEvent(type, { bubbles: true, clientX: x, button: 0 }),
  );
}

it("resizes by the drag distance without jumping to the offset hit area, then stops on release", () => {
  const { handle, onResize } = mount(1);
  pointer(handle, "pointerdown", 270);
  pointer(handle, "pointermove", 290);
  expect(onResize).toHaveBeenLastCalledWith(276);
  pointer(handle, "pointerup", 290);
  pointer(handle, "pointermove", 310);
  expect(onResize).toHaveBeenCalledTimes(1);
  expect(handle.releasePointerCapture).toHaveBeenCalled();
});

it("starts the right panel drag from its rendered width and stops on cancellation", () => {
  const { handle, onResize } = mount(-1, () => 360);
  pointer(handle, "pointerdown", 599);
  pointer(handle, "pointermove", 579);
  expect(onResize).toHaveBeenLastCalledWith(380);
  pointer(handle, "pointercancel", 579);
  pointer(handle, "pointermove", 560);
  expect(onResize).toHaveBeenCalledTimes(1);
  expect(handle).not.toHaveAttribute("data-dragging");
});

it.each([1, -1] as const)(
  "supports keyboard resizing in direction %s and width limits",
  (direction) => {
    const { handle, onResize } = mount(direction);
    fireEvent.keyDown(handle, { key: "ArrowRight" });
    expect(onResize).toHaveBeenLastCalledWith(256 + direction * 16);
    fireEvent.keyDown(handle, { key: "ArrowLeft" });
    expect(onResize).toHaveBeenLastCalledWith(256 - direction * 16);
    fireEvent.keyDown(handle, { key: "Home" });
    expect(onResize).toHaveBeenLastCalledWith(216);
    fireEvent.keyDown(handle, { key: "End" });
    expect(onResize).toHaveBeenLastCalledWith(420);
  },
);
