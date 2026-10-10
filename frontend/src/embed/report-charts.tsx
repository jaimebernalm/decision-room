/** Standalone renderer for report chart blocks: the platform's own EvidenceChart, mounted in
 * shadow roots so the app styles and the host page never affect each other. The host page
 * carries validated ChartData in #dr-charts and one .dr-chart-mount per block. */
import { createRoot } from "react-dom/client";
import css from "../index.css?inline";
import { setLanguage } from "@/lib/i18n";
import { EvidenceChart } from "@/components/workspace/report";
import type { ChartData } from "@/lib/types";

type Entry = { chart: ChartData } | { invalid: true };

function mount() {
  setLanguage("es");
  const fonts = css.match(/@font-face\s*{[^}]*}/g) ?? [];
  const head = document.createElement("style");
  head.textContent = fonts.join("\n");
  document.head.append(head);
  const source = document.getElementById("dr-charts");
  const entries: Entry[] = source ? JSON.parse(source.textContent || "[]") : [];
  let pending = 0;
  document.querySelectorAll<HTMLElement>(".dr-chart-mount").forEach((host) => {
    const entry = entries[Number(host.dataset.index)];
    const shadow = host.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = css.replace(/@font-face\s*{[^}]*}/g, "");
    const root = document.createElement("div");
    root.className = "dr-chart-root bg-background text-foreground font-sans";
    shadow.append(style, root);
    if (!entry || "invalid" in entry) {
      root.innerHTML =
        '<p class="rounded-lg border p-4 text-sm text-muted-foreground">Gráfico no disponible</p>';
      return;
    }
    pending += 1;
    createRoot(root).render(
      <div
        ref={(node) => {
          if (!node) return;
          pending -= 1;
          if (!pending) document.documentElement.dataset.drCharts = "ready";
        }}
      >
        <EvidenceChart chart={entry.chart} />
      </div>,
    );
  });
  if (!pending) document.documentElement.dataset.drCharts = "ready";
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
else mount();
