import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { it, expect } from "vitest";
import { ReportSection, reportLead } from "./report-section";
it("shows reviewed first sentences without cutting decimal amounts or inventing a conclusion", () => {
  expect(reportLead("Sube a 20.005 EUR. La causa no está confirmada.")).toBe(
    "Sube a 20.005 EUR.",
  );
  expect(reportLead("No demuestra un cambio de demanda")).toBe(
    "No demuestra un cambio de demanda",
  );
});
it("opens independently with keyboard and retains full reviewed details", async () => {
  render(
    <>
      <ReportSection title="Primero" preview="Resultado breve">
        <p>Explicación completa</p>
      </ReportSection>
      <ReportSection title="Segundo">
        <p>Otro detalle</p>
      </ReportSection>
    </>,
  );
  const first = screen.getByRole("button", { name: /Primero/ });
  expect(first).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByText("Explicación completa")).not.toBeInTheDocument();
  first.focus();
  await userEvent.keyboard("{Enter}");
  expect(first).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByText("Explicación completa")).toBeVisible();
  expect(screen.getByRole("button", { name: /Segundo/ })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  await userEvent.click(first);
  expect(first).toHaveAttribute("aria-expanded", "false");
});
