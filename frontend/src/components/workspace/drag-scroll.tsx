import { useRef, type ReactNode } from "react";

/** Mouse panning follows the existing scroll container; touch keeps native scrolling. */
export function DragScroll({ children }: { children: ReactNode }) {
  const drag = useRef<{
    id: number;
    x: number;
    y: number;
    left: number;
    top: number;
    scroll: Element;
    moved: boolean;
  } | null>(null);
  const suppressClick = useRef(false);
  return (
    <div
      className="dossier-drag-scroll min-w-0"
      onClickCapture={(event) => {
        if (suppressClick.current) {
          suppressClick.current = false;
          event.preventDefault();
          event.stopPropagation();
        }
      }}
      onPointerDown={(event) => {
        suppressClick.current = false;
        if (
          event.pointerType !== "mouse" ||
          event.button !== 0 ||
          event.shiftKey ||
          !(event.target instanceof Element) ||
          (!event.target.closest("[data-table-row]") &&
            event.target.closest(
              "button, a, input, textarea, select, [role=button], [contenteditable=true], .data-model-map",
            ))
        )
          return;
        let scroll: Element | null = event.currentTarget;
        while (scroll) {
          const style = getComputedStyle(scroll);
          if (
            (/(auto|scroll)/.test(style.overflowY) &&
              scroll.scrollHeight > scroll.clientHeight) ||
            (/(auto|scroll)/.test(style.overflowX) &&
              scroll.scrollWidth > scroll.clientWidth)
          )
            break;
          scroll = scroll.parentElement;
        }
        scroll ||= document.scrollingElement;
        if (scroll)
          drag.current = {
            id: event.pointerId,
            x: event.clientX,
            y: event.clientY,
            left: scroll.scrollLeft,
            top: scroll.scrollTop,
            scroll,
            moved: false,
          };
      }}
      onPointerMove={(event) => {
        const active = drag.current;
        if (!active || event.pointerId !== active.id) return;
        const dx = event.clientX - active.x,
          dy = event.clientY - active.y;
        if (!active.moved && Math.hypot(dx, dy) < 6) return;
        if (!active.moved) {
          active.moved = true;
          event.currentTarget.setPointerCapture(event.pointerId);
          event.currentTarget.dataset.dragging = "true";
        }
        suppressClick.current = true;
        event.preventDefault();
        window.getSelection()?.removeAllRanges();
        active.scroll.scrollLeft = active.left - dx;
        active.scroll.scrollTop = active.top - dy;
      }}
      onPointerUp={(event) => {
        if (drag.current?.id !== event.pointerId) return;
        drag.current = null;
        delete event.currentTarget.dataset.dragging;
        if (event.currentTarget.hasPointerCapture(event.pointerId))
          event.currentTarget.releasePointerCapture(event.pointerId);
      }}
      onPointerCancel={(event) => {
        suppressClick.current = false;
        drag.current = null;
        delete event.currentTarget.dataset.dragging;
      }}
      onLostPointerCapture={(event) => {
        drag.current = null;
        delete event.currentTarget.dataset.dragging;
      }}
    >
      {children}
    </div>
  );
}
