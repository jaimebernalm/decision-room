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
