import { useEffect, useId, useRef, useState } from "react";
import { Minus, Plus, Maximize2 } from "lucide-react";
import { translate as tr, useLanguage } from "@/lib/i18n";
import { Button } from "@/components/ui/button";
import { Loading, Notice } from "./shared";
import type { Table, Relation } from "./data-model";
import { dataModelMermaid } from "./data-model-mermaid";
import "./data-model-diagram.css";

// Mermaid queues its renders. Initialize once so concurrent dataset diagrams share settings.
let renderer: Promise<(typeof import("mermaid"))["default"]> | undefined;
function getRenderer() {
  return (renderer ||= import("mermaid").then(({ default: mermaid }) => {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      suppressErrorRendering: true,
      theme: "base",
      look: "classic",
      layout: "dagre",
      htmlLabels: false,
      // ER syntax needs a type token; keep that implementation detail out of the map.
      themeCSS: ".attribute-type { display: none; }",
      themeVariables: {
        fontFamily: "Geist Variable, sans-serif",
        fontSize: "13px",
        primaryColor: "#ffffff",
        primaryTextColor: "#202024",
        primaryBorderColor: "#d8dce1",
        lineColor: "#62819a",
      },
      er: { useMaxWidth: false, nodeSpacing: 48, rankSpacing: 72 },
    });
    return mermaid;
  }));
}

function relationExplanation(relation: Relation, from: Table, to: Table) {
  const cardinalities: Record<string, string> = {
    "many-to-one":
      "Varias filas de «{0}» pueden corresponder a una misma fila de «{1}».",
    "one-to-many":
      "Una fila de «{0}» puede corresponder a varias filas de «{1}».",
    "one-to-one": "Una fila de «{0}» puede corresponder a una fila de «{1}».",
    "many-to-many":
      "Varias filas de «{0}» pueden corresponder a varias filas de «{1}».",
  };
  const summary =
    relation.description ||
    tr(
      cardinalities[relation.cardinality] ||
        "Esta conexión permite combinar información de «{0}» y «{1}».",
      { 0: from.name, 1: to.name },
    );
  const keys = tr("Se conectan comparando «{0}» con «{1}».", {
    0: relation.source_columns.join(" + "),
    1: relation.target_columns.join(" + "),
  });
  const status =
    relation.semantic_status === "proposed"
      ? tr("Conexión propuesta: su significado aún está por confirmar.")
      : relation.semantic_status === "rejected"
        ? tr("Esta conexión está descartada.")
        : "";
  return { summary, keys, status };
}

export function ERDiagram({
  tables,
  relations,
  selected,
  edge,
  chooseTable,
  chooseEdge,
}: {
  tables: Table[];
  relations: Relation[];
  selected: string;
  edge: string;
  chooseTable: (id: string) => void;
  chooseEdge: (id: string) => void;
}) {
  const { language } = useLanguage();
  const id = `data-map-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const container = useRef<HTMLDivElement>(null);
  const drawing = useRef<HTMLDivElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const drag = useRef<{
    id: number;
    x: number;
    y: number;
    panX: number;
    panY: number;
    moved: boolean;
  } | null>(null);
  const suppressClick = useRef(false);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [size, setSize] = useState({ width: 640, height: 400 });
  const [hover, setHover] = useState<{
    id: string;
    x: number;
    y: number;
  } | null>(null);
  const [direction, setDirection] = useState<"LR" | "TB">("TB");
  const [rendered, setRendered] = useState<{
    source: string;
    svg: string;
    width: number;
    height: number;
  } | null>(null);
  const [error, setError] = useState("");
  const [zoom, setZoom] = useState(1);
  const graph = dataModelMermaid(tables, relations, direction);
  const source = graph.source;
  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const measure = () => {
      setDirection(element.clientWidth >= 650 ? "LR" : "TB");
      if (viewport.current)
        setSize({
          width: viewport.current.clientWidth,
          height: viewport.current.clientHeight,
        });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    if (viewport.current) observer.observe(viewport.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    let cancelled = false;
    void getRenderer()
      .then((mermaid) => mermaid.render(id, source))
      .then(({ svg }) => {
        if (cancelled) return;
        const doc = new DOMParser().parseFromString(svg, "image/svg+xml");
        const root = doc.documentElement;
        root.setAttribute("role", "presentation");
        root.removeAttribute("aria-roledescription");
        // Remove the generic type column and its separator; retain row borders and declared keys.
        root
          .querySelectorAll(".attribute-type, .divider")
          .forEach((node) => node.remove());
        for (const { table, svgId } of graph.nodes) {
          const node =
            doc.getElementById(`${id}-${svgId}`) || doc.getElementById(svgId);
          if (!node) continue;
          node.setAttribute("role", "button");
          node.setAttribute("tabindex", "0");
          node.setAttribute("aria-label", tr("Tabla {0}", { 0: table.name }));
          node.setAttribute("data-table-id", table.id);
        }
        for (const [
          index,
          { relation, source: from, target: to, svgId },
        ] of graph.edges.entries()) {
          const path = doc.querySelector(`[data-edge][data-id="${svgId}"]`);
          if (!path) continue;
          const connection = doc.createElementNS(
            "http://www.w3.org/2000/svg",
            "g",
          );
          connection.setAttribute("role", "button");
          connection.setAttribute("tabindex", "0");
          connection.setAttribute(
            "aria-label",
            tr("Relación {0} con {1}", {
              0: from.table.name,
              1: to.table.name,
            }),
          );
          connection.setAttribute("data-relation-id", relation.id);
          connection.setAttribute(
            "aria-describedby",
            `${id}-relation-${index}`,
          );
          const label = doc.querySelector(
            `.edgeLabel [data-id="${svgId}"]`,
          )?.parentElement;
          label?.setAttribute("data-relation-id", relation.id);
          path.setAttribute("data-status", relation.semantic_status);
          const hit = path.cloneNode(true) as Element;
          hit.removeAttribute("id");
          hit.removeAttribute("role");
          hit.removeAttribute("tabindex");
          hit.removeAttribute("marker-start");
          hit.removeAttribute("marker-end");
          hit.setAttribute("aria-hidden", "true");
          hit.setAttribute("class", "data-map-hit");
          path.parentElement?.replaceChild(connection, path);
          connection.append(path, hit);
        }
        const width =
          Number(root.getAttribute("viewBox")?.split(/\s+/)[2]) || 640;
        const height =
          Number(root.getAttribute("viewBox")?.split(/\s+/)[3]) || 400;
        setRendered({
          source,
          svg: new XMLSerializer().serializeToString(root),
          width,
          height,
        });
        setPan({ x: 0, y: 0 });
        setHover(null);
        setError("");
      })
      .catch(() => {
        if (!cancelled)
          setError(
            tr(
              "No se pudo dibujar el mapa. Puedes consultar las tablas y conexiones debajo.",
            ),
          );
      });
    return () => {
      cancelled = true;
    };
    // source represents the complete graph; callback/selection changes don't trigger a layout.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, source, language]);
  useEffect(() => {
    drawing.current
      ?.querySelectorAll("[data-table-id], [data-relation-id]")
      .forEach((node) => {
        const active =
          node.getAttribute("data-table-id") === selected ||
          node.getAttribute("data-relation-id") === edge;
        node.setAttribute("data-selected", String(active));
        if (node.getAttribute("role") === "button")
          node.setAttribute("aria-pressed", String(active));
      });
  }, [rendered, selected, edge]);
  const activate = (target: EventTarget | null) => {
    if (!(target instanceof Element)) return;
    const node = target.closest("[data-table-id], [data-relation-id]");
    if (node?.getAttribute("data-table-id"))
      chooseTable(node.getAttribute("data-table-id")!);
    else if (node?.getAttribute("data-relation-id"))
      chooseEdge(node.getAttribute("data-relation-id")!);
  };
  const hoveredEdge = graph.edges.find(
    ({ relation }) => relation.id === hover?.id,
  );
  const explanation =
    hoveredEdge &&
    relationExplanation(
      hoveredEdge.relation,
      hoveredEdge.source.table,
      hoveredEdge.target.table,
    );
  const fit = rendered
    ? Math.max(
        0.05,
        Math.min(
          (size.width - 48) / rendered.width,
          (size.height - 48) / rendered.height,
          1,
        ),
      )
    : 1;
  const showExplanation = (
    target: EventTarget | null,
    x: number,
    y: number,
  ) => {
    const relationId =
      target instanceof Element
        ? target.closest("[data-relation-id]")?.getAttribute("data-relation-id")
        : null;
    setHover(relationId ? { id: relationId, x, y } : null);
  };
  return (
    <div
      ref={container}
      className="data-model-map min-w-0 rounded-xl border bg-muted/10"
    >
      <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
        <span className="text-xs text-muted-foreground">
          {tr("Mapa de tablas")}
        </span>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="size-7"
            aria-label={tr("Alejar mapa")}
            disabled={zoom <= 0.5}
            onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}
          >
            <Minus className="size-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            aria-label={tr("Ajustar mapa")}
            onClick={() => {
              setZoom(1);
              setPan({ x: 0, y: 0 });
              setHover(null);
            }}
          >
            <Maximize2 className="size-3.5" />
            {tr("Ajustar")}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="size-7"
            aria-label={tr("Acercar mapa")}
            disabled={zoom >= 4}
            onClick={() => setZoom((z) => Math.min(4, z + 0.25))}
          >
            <Plus className="size-3.5" />
          </Button>
        </div>
      </div>
      <Notice error>{error}</Notice>
      <div
        ref={viewport}
        className="data-map-viewport"
        data-dragging={dragging}
        role="group"
        tabIndex={0}
        aria-label={tr("Diagrama ER de esta revisión del modelo")}
        onPointerDown={(e) => {
          if (e.button !== 0 || drag.current) return;
          suppressClick.current = false;
          drag.current = {
            id: e.pointerId,
            x: e.clientX,
            y: e.clientY,
            panX: pan.x,
            panY: pan.y,
            moved: false,
          };
        }}
        onPointerMove={(e) => {
          const active = drag.current;
          if (active && active.id === e.pointerId) {
            const dx = e.clientX - active.x,
              dy = e.clientY - active.y;
            if (!active.moved && Math.hypot(dx, dy) <= 4) return;
            if (!active.moved) {
              active.moved = true;
              e.currentTarget.setPointerCapture(e.pointerId);
              setDragging(true);
            }
            suppressClick.current = true;
            setHover(null);
            setPan({ x: active.panX + dx, y: active.panY + dy });
          } else {
            const bounds = e.currentTarget.getBoundingClientRect();
            showExplanation(
              e.target,
              e.clientX - bounds.left,
              e.clientY - bounds.top,
            );
          }
        }}
        onPointerUp={(e) => {
          if (drag.current?.id !== e.pointerId) return;
          drag.current = null;
          setDragging(false);
          if (e.currentTarget.hasPointerCapture(e.pointerId))
            e.currentTarget.releasePointerCapture(e.pointerId);
        }}
        onPointerCancel={() => {
          drag.current = null;
          setDragging(false);
          setHover(null);
        }}
        onLostPointerCapture={() => {
          drag.current = null;
          setDragging(false);
        }}
        onPointerLeave={() => {
          setHover(null);
          if (!drag.current?.moved) drag.current = null;
        }}
        onClickCapture={(e) => {
          if (suppressClick.current) {
            e.stopPropagation();
            suppressClick.current = false;
          }
        }}
        onFocusCapture={(e) => {
          if (!(e.target instanceof Element)) return;
          const node = e.target.getBoundingClientRect(),
            bounds = e.currentTarget.getBoundingClientRect();
          showExplanation(
            e.target,
            node.x + node.width / 2 - bounds.x,
            node.y + node.height / 2 - bounds.y,
          );
        }}
        onBlurCapture={() => setHover(null)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setHover(null);
          if (e.target !== e.currentTarget) return;
          const offsets: Record<string, [number, number]> = {
            ArrowLeft: [48, 0],
            ArrowRight: [-48, 0],
            ArrowUp: [0, 48],
            ArrowDown: [0, -48],
          };
          if (offsets[e.key]) {
            e.preventDefault();
            setHover(null);
            const [x, y] = offsets[e.key];
            setPan((p) => ({ x: p.x + x, y: p.y + y }));
          }
        }}
      >
        {!error && rendered?.source !== source && <Loading />}
        {rendered?.source === source && (
          <div
            ref={drawing}
            className="data-map-drawing"
            style={{
              width: rendered.width,
              transform: `translate(-50%, -50%) translate(${pan.x}px, ${pan.y}px) scale(${fit * zoom})`,
            }}
            onClick={(e) => activate(e.target)}
            onKeyDown={(e) => {
              if (
                (e.key === "Enter" || e.key === " ") &&
                e.target instanceof Element &&
                e.target.closest('[role="button"]')
              ) {
                e.preventDefault();
                activate(e.target);
              }
            }}
            dangerouslySetInnerHTML={{ __html: rendered.svg }}
          />
        )}
        {hover && explanation && (
          <div
            role="tooltip"
            className="data-map-tooltip"
            style={{
              left: Math.max(12, Math.min(hover.x - 130, size.width - 272)),
              top: Math.max(12, Math.min(hover.y + 16, size.height - 176)),
            }}
          >
            <p className="line-clamp-3">{explanation.summary}</p>
            <p className="mt-1 line-clamp-2 text-muted-foreground">
              {explanation.keys}
            </p>
            {explanation.status && (
              <p className="mt-1 line-clamp-2 font-medium">
                {explanation.status}
              </p>
            )}
          </div>
        )}
      </div>
      {graph.edges.map(({ relation, source: from, target: to }, index) => {
        const text = relationExplanation(relation, from.table, to.table);
        return (
          <p
            key={relation.id}
            id={`${id}-relation-${index}`}
            className="sr-only"
          >
            {text.summary} {text.keys} {text.status}
          </p>
        );
      })}
      <p className="border-t px-3 py-2 text-[11px] leading-4 text-muted-foreground">
        {tr(
          "Arrastra para moverte por el mapa. Pasa por una conexión para entenderla; selecciona una tabla para ver sus columnas.",
        )}
        {tables.some((t) => t.columns.length > 8) &&
          " " +
            tr(
              "El mapa muestra hasta ocho columnas por tabla; los detalles incluyen todas.",
            )}
      </p>
    </div>
  );
}
