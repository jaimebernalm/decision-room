import { it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { setLanguage } from "@/lib/i18n";
import { ReportOfferCard } from "./report-offer";

const offer = {
  id: "offer",
  objective: "Ventas por mes y por qué cambian.",
  analysis_id: "a",
  offer_sha256: "x",
  status: "open" as const,
  job_id: null,
};

afterEach(() => vi.unstubAllGlobals());

it("starts a report only from the button, with the edited objective and one key per objective", async () => {
  setLanguage("es");
  const calls: Record<string, string>[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init?: RequestInit) => {
      calls.push(JSON.parse(String(init?.body)));
      return new Response(JSON.stringify({ id: "t", job_id: "j" }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  const accepted = vi.fn();
  render(
    <ReportOfferCard
      offer={offer}
      chatId="c"
      businessId="b"
      onAccepted={accepted}
    />,
  );
  expect(calls).toEqual([]);
  const field = screen.getByLabelText("Objetivo del informe");
  await userEvent.clear(field);
  await userEvent.type(field, "Ventas por mes");
  await userEvent.click(
    screen.getByRole("button", { name: /Preparar informe/ }),
  );
  await waitFor(() => expect(accepted).toHaveBeenCalledTimes(1));
  await userEvent.click(
    screen.getByRole("button", { name: /Preparar informe/ }),
  );
  await waitFor(() => expect(calls).toHaveLength(2));
  expect(calls[0]).toMatchObject({
    offer_id: "offer",
    objective: "Ventas por mes",
    business_id: "b",
  });
  expect(calls[1].request_key).toBe(calls[0].request_key);
  await userEvent.type(field, " y canal");
  await userEvent.click(
    screen.getByRole("button", { name: /Preparar informe/ }),
  );
  await waitFor(() => expect(calls).toHaveLength(3));
  expect(calls[2].request_key).not.toBe(calls[0].request_key);
});

it("shows the request instead of the button once accepted", () => {
  setLanguage("es");
  render(
    <ReportOfferCard
      offer={{ ...offer, status: "accepted", job_id: "job" }}
      chatId="c"
      businessId="b"
      onAccepted={vi.fn()}
    />,
  );
  expect(screen.queryByRole("button", { name: /Preparar informe/ })).toBeNull();
  expect(screen.getByRole("link", { name: /Ver informe/ })).toHaveAttribute(
    "href",
    "#analysis/job",
  );
});
