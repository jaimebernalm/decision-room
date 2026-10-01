import { useEffect, useSyncExternalStore } from "react";
import english from "./locales/en.json";

export type Language = "en" | "es";
export const LANGUAGE_KEY = "dr-language";
const translations: Record<string, string> = english;
export function getLanguage(): Language {
  try {
    return localStorage.getItem(LANGUAGE_KEY) === "es" ? "es" : "en";
  } catch {
    return "en";
  }
}
let unavailableStorageLanguage: Language | undefined;
const snapshot = () => unavailableStorageLanguage || getLanguage();
export const locale = () => (snapshot() === "en" ? "en-US" : "es-ES");
function subscribe(update: () => void) {
  const stored = (event: StorageEvent) => {
    if (!event.key || event.key === LANGUAGE_KEY) update();
  };
  addEventListener("dr-language", update);
  addEventListener("storage", stored);
  return () => {
    removeEventListener("dr-language", update);
    removeEventListener("storage", stored);
  };
}
export function setLanguage(language: Language) {
  try {
    localStorage.setItem(LANGUAGE_KEY, language);
    unavailableStorageLanguage = undefined;
  } catch {
    unavailableStorageLanguage = language;
  }
  dispatchEvent(new Event("dr-language"));
}
export function useLanguage() {
  const language = useSyncExternalStore(
    subscribe,
    snapshot,
    () => "en" as Language,
  );
  useEffect(() => {
    document.documentElement.lang = language;
    document
      .querySelector('meta[name="description"]')
      ?.setAttribute(
        "content",
        translate("Tu espacio local para entender los datos de tu negocio."),
      );
  }, [language]);
  return { language, setLanguage };
}
/** Source-language keys keep Spanish readable; substitutions are never translated. */
export function translate(
  input: string,
  values: Record<string, unknown> = {},
): string {
  const key = input.trim().replace(/\s+/g, " ");
  const translated = snapshot() === "en" ? translations[key] : undefined;
  const body =
    translated === undefined
      ? input
      : input.slice(0, input.length - input.trimStart().length) +
        translated +
        input.slice(input.trimEnd().length);
  return body.replace(/\{(\d+)\}/g, (match, index) =>
    index in values ? String(values[index]) : match,
  );
}
