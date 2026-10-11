import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { it, expect } from "vitest";
import { ReportView } from "./report";
import type { Report } from "@/lib/types";

const report: Report = {
  origin: "engine_html",
  title: "<script>owner text</script>",
  summary:
    "La entrega está guardada. Su presentación todavía no está disponible.",
  scope: { period: "", coverage: "" },
  claims: [],
  charts: [],
  highlights: [],
  limitations: [],
  engine_report: {
    document_id: "document",
    revision_id: "revision",
    state: "current",
    is_current: true,
    run_status: "delivered",
    raw_sha256: "a".repeat(64),
    raw_bytes: 100,
    profile_version: "html-v1",
    history: [
      {
        id: "revision",
        ordinal: 1,
        raw_sha256: "a".repeat(64),
        raw_bytes: 100,
        delivery_via: "file",
        created_at: "2026-10-10",
      },
    ],
  },
};
it("shows saved metadata and exact history without rendering HTML or verification", async () => {
  const { container } = render(<ReportView report={report} />);
  expect(screen.getByText("Entrega guardada")).toBeInTheDocument();
  expect(screen.queryByText("Revisado")).not.toBeInTheDocument();
  expect(
    container.querySelector("script, iframe, canvas, svg.recharts-surface"),
  ).toBeNull();
  expect(
    screen.getByRole("heading", { name: "<script>owner text</script>" }),
  ).toBeInTheDocument();
  await userEvent.click(screen.getByText("Detalles técnicos"));
  await userEvent.click(screen.getByText("Historial de entregas"));
  expect(screen.getByText("a".repeat(64))).toBeVisible();
});
it("keeps withdrawn metadata readable and asks for a new analysis", () => {
  render(
    <ReportView
      report={{
        ...report,
        engine_report: {
          ...report.engine_report!,
          state: "withdrawn",
          is_current: false,
        },
      }}
    />,
  );
  expect(screen.getByText("Informe retirado")).toBeInTheDocument();
  expect(
    screen.getByText(
      "Crea un análisis nuevo para usar los datos y definiciones actuales.",
    ),
  ).toBeInTheDocument();
  expect(screen.queryByText("Revisado")).not.toBeInTheDocument();
});
it("missing engine metadata cannot fall through to the reviewed legacy view", () => {
  render(<ReportView report={{ ...report, engine_report: undefined }} />);
  expect(
    screen.getByText("Registro de entrega no disponible"),
  ).toBeInTheDocument();
  expect(screen.queryByText("Revisado")).not.toBeInTheDocument();
});
it("frames only the renderer snapshot without scripts and offers its canonical text", async () => {
  const { container } = render(
    <ReportView
      report={{
        ...report,
        summary: "",
        view: {
          mode: "snapshot",
          policy_version: "v1-snapshot-only-1",
          receipt: "allowed",
          reason: null,
          canonical_text: "Ventas por canal",
          sandbox: "",
          srcdoc: "<h1>Ventas</h1>",
        },
      }}
    />,
  );
  const frame = container.querySelector("iframe")!;
  expect(frame.getAttribute("sandbox")).toBe("");
  expect(frame.getAttribute("srcdoc")).toBe("<h1>Ventas</h1>");
  expect(frame.getAttribute("referrerpolicy")).toBe("no-referrer");
  expect(container.querySelector("script")).toBeNull();
  await userEvent.click(screen.getByText("Texto del informe"));
  expect(screen.getByText("Ventas por canal")).toBeVisible();
  expect(screen.queryByText("Revisado")).not.toBeInTheDocument();
});
it("never frames pending or blocked reports", () => {
  for (const mode of ["pending", "blocked"] as const) {
    const { container, unmount } = render(
      <ReportView
        report={{
          ...report,
          view: {
            mode,
            policy_version: "v1-snapshot-only-1",
            receipt: mode === "blocked" ? "blocked" : "allowed",
            reason: mode === "blocked" ? "element:base" : null,
            canonical_text: null,
          },
        }}
      />,
    );
    expect(container.querySelector("iframe")).toBeNull();
    expect(
      screen.getByText(
        mode === "pending" ? /Preparando la vista/ : /Presentación bloqueada/,
      ),
    ).toBeInTheDocument();
    unmount();
  }
});
