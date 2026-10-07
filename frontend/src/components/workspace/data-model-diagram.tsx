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
  const [direction, setDirection] = useState<"LR" | "TB">("TB");
  const [rendered, setRendered] = useState<{
    source: string;
    svg: string;
    width: number;
  } | null>(null);
  const [error, setError] = useState("");
  const [zoom, setZoom] = useState(1);
  const graph = dataModelMermaid(tables, relations, direction);
  const source = graph.source;
  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const measure = () =>
      setDirection(element.clientWidth >= 650 ? "LR" : "TB");
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
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
        for (const { table, svgId } of graph.nodes) {
          const node =
            doc.getElementById(`${id}-${svgId}`) || doc.getElementById(svgId);
          if (!node) continue;
          node.setAttribute("role", "button");
          node.setAttribute("tabindex", "0");
          node.setAttribute("aria-label", tr("Tabla {0}", { 0: table.name }));
          node.setAttribute("data-table-id", table.id);
        }
        for (const {
          relation,
          source: from,
          target: to,
          svgId,
        } of graph.edges) {
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
        setRendered({
          source,
          svg: new XMLSerializer().serializeToString(root),
          width,
        });
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
            onClick={() => setZoom(1)}
          >
            <Maximize2 className="size-3.5" />
            {tr("Ajustar")}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="size-7"
            aria-label={tr("Acercar mapa")}
            disabled={zoom >= 2}
            onClick={() => setZoom((z) => Math.min(2, z + 0.25))}
          >
            <Plus className="size-3.5" />
          </Button>
        </div>
      </div>
      <Notice error>{error}</Notice>
      {!error && rendered?.source !== source && <Loading />}
      {rendered?.source === source && (
        <div
          className="data-map-scroll"
          role="group"
          aria-label={tr("Diagrama ER de esta revisión del modelo")}
        >
          <div
            ref={drawing}
            className="data-map-drawing"
            style={{
              width:
                zoom === 1
                  ? `min(100%, ${rendered.width}px)`
                  : rendered.width * zoom,
              minWidth:
                zoom === 1
                  ? Math.min(rendered.width, 300)
                  : rendered.width * zoom,
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
        </div>
      )}
      <p className="border-t px-3 py-2 text-[11px] leading-4 text-muted-foreground">
        {tr(
          "Selecciona una tabla para ver sus columnas. Las líneas discontinuas indican conexiones por confirmar o descartadas.",
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
