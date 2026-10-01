import { it, expect, vi } from "vitest";
import {
  getLanguage,
  setLanguage,
  translate,
  locale,
  LANGUAGE_KEY,
} from "./i18n";
import { presentationNumber, displayNumber } from "./presentation";
import { date } from "./api";
import english from "./locales/en.json";
import spanish from "./locales/es.json";

it("uses chat terminology consistently, including legacy server messages", () => {
  for (const language of ["en", "es"] as const) {
    setLanguage(language);
    for (const key of Object.keys(english)) {
      expect(translate(key), key).not.toMatch(
        /\bconversaci[oó]n(?:es)?\b|\bconversations?\b/i,
      );
    }
    expect(translate("Conversaciones")).toBe("Chats");
    expect(translate("Nueva conversación")).toBe(
      language === "en" ? "New chat" : "Nuevo chat",
    );
    expect(translate("Conversación no encontrada.")).toBe(
      language === "en" ? "Chat not found." : "Chat no encontrado.",
    );
    expect(
      translate("Opciones de {0}", { 0: "Mi conversación favorita" }),
    ).toContain("Mi conversación favorita");
    expect(translate("Mi conversación favorita")).toBe(
      "Mi conversación favorita",
    );
    expect(translate("Opciones de {0}", { 0: "Conversaciones" })).toContain(
      "Conversaciones",
    );
  }
  for (const [key, value] of Object.entries(spanish)) {
    expect(Object.hasOwn(english, key)).toBe(true);
    expect(value.trim()).not.toBe("");
    const slots = (text: string) =>
      [...text.matchAll(/\{(\d+)\}/g)].map((match) => match[1]).sort();
    expect(slots(value)).toEqual(slots(key));
  }
});

it("defaults to English and persists supported language choices", () => {
  localStorage.removeItem(LANGUAGE_KEY);
  expect(getLanguage()).toBe("en");
  setLanguage("es");
  expect(getLanguage()).toBe("es");
  expect(translate("Inicio")).toBe("Inicio");
  setLanguage("en");
  expect(localStorage.getItem(LANGUAGE_KEY)).toBe("en");
  expect(translate("Inicio")).toBe("Home");
  expect(translate("Unknown business name")).toBe("Unknown business name");
  expect(translate("constructor")).toBe("constructor");
});
it("preserves names and user content in substitutions, including whitespace and markup", () => {
  setLanguage("en");
  expect(translate(" Opciones de {0} ", { 0: "Bruma <café> {0}" })).toBe(
    " Options for Bruma <café> {0} ",
  );
  expect(translate("El nombre de mi negocio es Inicio")).toBe(
    "El nombre de mi negocio es Inicio",
  );
});
it("has nonempty translations with identical substitution slots", () => {
  expect(Object.keys(english).length).toBeGreaterThan(850);
  for (const [key, value] of Object.entries(english)) {
    expect(value.trim(), key).not.toBe("");
    const slots = (s: string) =>
      [...s.matchAll(/\{(\d+)\}/g)].map((m) => m[1]).sort();
    expect(slots(value), key).toEqual(slots(key));
  }
});
it("localizes dates and precise rounded numbers without converting values to floats", () => {
  setLanguage("en");
  expect(locale()).toBe("en-US");
  expect(date("2026-09-30T12:00:00Z")).toContain("Sep");
  expect(presentationNumber("12345678901234567890.555", 2)).toBe(
    "12,345,678,901,234,567,890.56",
  );
  setLanguage("es");
  expect(presentationNumber("12345678901234567890.555", 2)).toBe(
    "12.345.678.901.234.567.890,56",
  );
});
it("keeps language changes usable when browser storage is unavailable", () => {
  const stored = localStorage;
  vi.stubGlobal("localStorage", {
    getItem() {
      throw new Error("Denied");
    },
    setItem() {
      throw new Error("Denied");
    },
  });
  setLanguage("en");
  expect(translate("Informes")).toBe("Reports");
  vi.stubGlobal("localStorage", stored);
  setLanguage("es");
});

it("localizes existing exact report values while preserving units and content", () => {
  setLanguage("en");
  expect(displayNumber("-12.345.678.901.234.567.890,56")).toBe(
    "-12,345,678,901,234,567,890.56",
  );
  expect(displayNumber("410")).toBe("410");
  expect(displayNumber("P01 / 1.234 paquetes")).toBe("P01 / 1.234 paquetes");
  setLanguage("es");
  expect(displayNumber("1.778,50")).toBe("1.778,50");
});

it("sends the current interface language without changing user payload", async () => {
  const { api } = await import("./api");
  const fetch = vi.fn(async (_path: string, _options?: RequestInit) => ({
    ok: true,
    json: async () => ({ saved: true }),
  }));
  vi.stubGlobal("fetch", fetch);
  setLanguage("en");
  await api("/api/chats/test/messages", { text: "Hola Bruma Café" });
  expect(fetch.mock.calls[0]?.[1]).toMatchObject({
    headers: { "X-Decision-Room-Language": "en" },
    body: JSON.stringify({ text: "Hola Bruma Café" }),
  });
  setLanguage("es");
  await api("/api/workspace");
  expect(fetch.mock.calls[1]?.[1]).toMatchObject({
    headers: { "X-Decision-Room-Language": "es" },
  });
});
