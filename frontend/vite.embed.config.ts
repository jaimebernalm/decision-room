import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import { fileURLToPath, URL } from "node:url";
// One self-contained script (styles and fonts inlined) for rendering report chart blocks offline.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    outDir: "dist-embed",
    emptyOutDir: true,
    assetsInlineLimit: 50_000_000,
    lib: {
      entry: fileURLToPath(new URL("./src/embed/report-charts.tsx", import.meta.url)),
      formats: ["iife"],
      name: "DecisionRoomCharts",
      fileName: () => "report-charts.js",
    },
  },
});
