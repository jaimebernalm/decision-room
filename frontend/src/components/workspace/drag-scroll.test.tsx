import { fireEvent, render } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { DragScroll } from "./drag-scroll";

beforeEach(() => {
  class Pointer extends MouseEvent {
    pointerId: number;
    pointerType: string;
    constructor(
      type: string,
      init: MouseEventInit & { pointerId?: number; pointerType?: string } = {},
    ) {
      super(type, init);
      this.pointerId = init.pointerId ?? 1;
      this.pointerType = init.pointerType ?? "mouse";
    }
  }
  vi.stubGlobal("PointerEvent", Pointer);
});
function setup() {
  const open = vi.fn();
  const { container } = render(
    <div style={{ overflowY: "auto" }}>
      <DragScroll>
        <button data-table-row onClick={open}>
          Tabla
        </button>
        <a href="#file">Download</a>
        <div className="data-model-map">Mapa</div>
        <p>Historial</p>
      </DragScroll>
    </div>,
  );
  const scroll = container.firstElementChild!;
  Object.defineProperties(scroll, {
    scrollHeight: { value: 1000 },
    clientHeight: { value: 200 },
  });
  return {
    scroll,
    pan: scroll.firstElementChild!,
    row: container.querySelector("button")!,
    open,
    container,
  };
}
it("scrolls a table drag without opening its preview, then allows a normal click", () => {
  const { scroll, pan, row, open } = setup();
  fireEvent.pointerDown(row, { clientX: 100, clientY: 150 });
  fireEvent.pointerMove(pan, { clientX: 100, clientY: 148 });
  expect(scroll.scrollTop).toBe(0);
  fireEvent.pointerMove(pan, { clientX: 100, clientY: 50 });
  expect(scroll.scrollTop).toBe(100);
  fireEvent.pointerUp(pan);
  fireEvent.click(row);
  expect(open).not.toHaveBeenCalled();
  expect(pan).not.toHaveAttribute("data-dragging");
  fireEvent.pointerDown(row);
  fireEvent.pointerUp(row);
  fireEvent.click(row);
  expect(open).toHaveBeenCalledOnce();
});
it("leaves touch, shift text selection, links and map gestures to their normal controls", () => {
  const { scroll, pan, container } = setup();
  for (const [target, init] of [
    [pan, { pointerType: "touch" }],
    [pan, { shiftKey: true }],
    [container.querySelector("a")!, {}],
    [container.querySelector(".data-model-map")!, {}],
  ] as const) {
    fireEvent.pointerDown(target, { clientY: 150, ...init });
    fireEvent.pointerMove(pan, { clientY: 50 });
    fireEvent.pointerUp(pan);
    expect(scroll.scrollTop).toBe(0);
  }
});
it("releases a cancelled drag without leaving the view stuck in a grabbing state", () => {
  const { scroll, pan } = setup();
  fireEvent.pointerDown(pan, { clientY: 150 });
  fireEvent.pointerMove(pan, { clientY: 50 });
  fireEvent.pointerCancel(pan);
  fireEvent.pointerMove(pan, { clientY: 0 });
  expect(scroll.scrollTop).toBe(100);
  expect(pan).not.toHaveAttribute("data-dragging");
});
