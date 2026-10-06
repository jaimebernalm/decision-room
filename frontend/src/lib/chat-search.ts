import { useEffect, useState } from "react";
import { api } from "./api";
import { translate as tr } from "./i18n";
import type { ChatListing } from "./types";

export function useChatSearch(search: string, listing: ChatListing) {
  const query = search.trim();
  const key = JSON.stringify([listing.business_id, query]);
  const [revision, retry] = useState(0);
  const [result, setResult] = useState<{
    key: string;
    data?: ChatListing;
    error?: string;
  } | null>(null);
  useEffect(() => {
    if (!query) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const data = await api<ChatListing>(
          `/api/chats?query=${encodeURIComponent(query)}`,
          undefined,
          controller.signal,
        );
        if (controller.signal.aborted) return;
        if (data.business_id !== listing.business_id)
          throw new Error(
            tr("El negocio activo ha cambiado. Actualizando el espacio…"),
          );
        setResult({ key, data });
      } catch (error) {
        if (!controller.signal.aborted)
          setResult({ key, error: (error as Error).message });
      }
    }, 200);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, key, listing, revision]);
  const current = result?.key === key ? result : null;
  return {
    chats: query ? current?.data?.conversations || [] : listing.conversations,
    pending: Boolean(query && !current),
    error: query ? current?.error || "" : "",
    retry: () => {
      setResult(null);
      retry((n) => n + 1);
    },
  };
}
