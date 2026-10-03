import { useRef, useState } from "react";

export function ResizeHandle({
  label,
  className,
  width,
  min,
  max,
  direction,
  step,
  onResize,
  getWidth,
}: {
  label: string;
  className: string;
  width: number;
  min: number;
  max: number;
  direction: 1 | -1;
  step: number;
  onResize: (width: number) => void;
  getWidth?: () => number;
}) {
  const start = useRef<{ x: number; width: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  return (
    <div
      role="separator"
      tabIndex={0}
      aria-label={label}
      aria-orientation="vertical"
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={Math.round(width)}
      className={`workspace-resize ${className}`}
      data-dragging={dragging || undefined}
      onPointerDown={(event) => {
        if (event.button !== 0) return;
        start.current = { x: event.clientX, width: getWidth?.() ?? width };
        event.currentTarget.setPointerCapture(event.pointerId);
        setDragging(true);
        event.preventDefault();
      }}
      onPointerMove={(event) => {
        if (
          start.current &&
          event.currentTarget.hasPointerCapture(event.pointerId)
        ) {
          onResize(
            start.current.width + direction * (event.clientX - start.current.x),
          );
        }
      }}
      onPointerUp={(event) => {
        if (event.currentTarget.hasPointerCapture(event.pointerId)) {
          event.currentTarget.releasePointerCapture(event.pointerId);
        }
        start.current = null;
        setDragging(false);
      }}
      onLostPointerCapture={() => {
        start.current = null;
        setDragging(false);
      }}
      onPointerCancel={() => {
        start.current = null;
        setDragging(false);
      }}
      onKeyDown={(event) => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
          return;
        event.preventDefault();
        onResize(
          Math.max(
            min,
            Math.min(
              max,
              event.key === "Home"
                ? min
                : event.key === "End"
                  ? max
                  : width +
                    direction * (event.key === "ArrowRight" ? step : -step),
            ),
          ),
        );
      }}
    />
  );
}
