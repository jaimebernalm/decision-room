import { it, expect } from "vitest";
import { findingHref, findingTarget } from "./report-navigation";
import type { HomeItem } from "./types";
it("round-trips a finding identity without interpreting its text as route segments", () => {
  const item: HomeItem = {
    id: "item",
    kind: "insight",
    title: "Conclusión",
    content: {
      key: "grupo/ventas #1",
      title: "Conclusión",
      statement: "Texto revisado",
    },
    source: {
      job_id: "job",
      report_id: "report/id",
      version: "v1:review",
      title: "Informe",
      period: "Septiembre",
      coverage: "Datos disponibles",
      filename: "ventas.csv",
      created_at: "2026-10-02",
      analysis_id: "a",
      limitations: [],
      href: "#report/job",
    },
  };
  const link = findingHref(item);
  expect(link).toContain("grupo%2Fventas%20%231");
  expect(findingTarget(link)).toEqual({
    key: "grupo/ventas #1",
    reportId: "report/id",
    version: "v1:review",
  });
});
it("ignores malformed or incomplete finding links", () => {
  expect(findingTarget("#report/job")).toBeNull();
  expect(findingTarget("#report/job/finding/key/review")).toBeNull();
  expect(findingTarget("#report/job/finding/%invalid/review/v1")).toBeNull();
});
