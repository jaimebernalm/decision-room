import type { QuestionContext, Chat, Turn, ContextReference } from "./types";
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}
export const store = {
  get<T>(key: string, fallback: T): T {
    try {
      return JSON.parse(localStorage.getItem(key) || "null") ?? fallback;
    } catch {
      return fallback;
    }
  },
  set(key: string, value: unknown) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      dispatchEvent(new CustomEvent("dr-draft", { detail: key }));
    } catch {
      /* Private browsing may disallow storage. */
    }
  },
  remove(key: string) {
    try {
      localStorage.removeItem(key);
      dispatchEvent(new CustomEvent("dr-draft", { detail: key }));
    } catch {
      /* Keep the in-memory draft usable. */
    }
  },
};
export async function api<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const multipart = body instanceof FormData;
  let response: globalThis.Response;
  try {
    response = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        "X-Decision-Room": "1",
        ...(body !== undefined && !multipart
          ? { "Content-Type": "application/json" }
          : {}),
      },
      body:
        body === undefined
          ? undefined
          : multipart
            ? body
            : JSON.stringify(body),
      credentials: "same-origin",
      signal,
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new Error(
      "No hay conexión con el servidor local. Tu progreso guardado se conserva.",
    );
  }
  const data = await response.json();
  if (!response.ok)
    throw new ApiError(
      data.error || "No hemos podido completar la petición.",
      response.status,
    );
  return data;
}
export const shortTitle = (text: string) =>
  text.replace(/\s+/g, " ").trim().length > 64
    ? text.replace(/\s+/g, " ").trim().slice(0, 61) + "…"
    : text.replace(/\s+/g, " ").trim();
export const date = (value?: string) =>
  value
    ? new Date(value).toLocaleDateString("es-ES", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "";
export const reportLink = (id: string, claim?: string) =>
  `/api/jobs/${encodeURIComponent(id)}/report${claim ? `#finding-${encodeURIComponent(claim)}` : ""}`;
export const statuses: Record<string, string> = {
  preparing: "En preparación",
  queued: "En cola",
  running: "En curso",
  waiting: "Necesita tu respuesta",
  completed: "Informe disponible",
  failed: "Interrumpido",
  blocked: "Necesita atención",
  outdated: "Contexto cambiado",
  historical: "Versión anterior",
  withdrawn: "Informe retirado",
  ready: "Respuesta revisada",
  routing: "Preparando respuesta",
  processing: "Analizando",
  stale: "Contexto actualizado",
};
export const reportState = (item: {
  presentation_status?: string;
  status: string;
  data_version?: { superseded_by?: string };
}) =>
  item.presentation_status ||
  (item.status === "completed" && item.data_version?.superseded_by
    ? "historical"
    : item.status);
export const analysisHref = (item: {
  id: string;
  status: string;
  presentation_status?: string;
  data_version?: { superseded_by?: string };
}) =>
  `#${["completed", "historical"].includes(reportState(item)) ? "report" : "analysis"}/${item.id}`;
export const contextKey = (business: string) =>
  `dr-question-context-${business}`;
export const homeDraftKey = (business: string) => `dr-home-prompt-${business}`;
export const messageKey = (chat: string) => `dr-chat-draft-${chat}`;
export const referenceWire = (r: ContextReference): ContextReference =>
  "source_id" in r
    ? {
        source_id: r.source_id,
        source_version: r.source_version,
        kind: r.kind,
        element_key: r.element_key,
      }
    : {
        report_id: r.report_id,
        report_version: r.report_version,
        kind: r.kind,
        element_key: r.element_key,
      };
export type MessageDraft = {
  disposition?: string;
  context_references?: ContextReference[];
  question_id?: string;
  text: string;
  key?: string;
  finding_reference?: QuestionContext["finding_reference"];
};
const launches = new Map<string, Promise<Chat>>();
export function launchChat(
  business: string,
  text: string,
  context: QuestionContext = {},
): Promise<Chat> {
  if (launches.has(business)) return launches.get(business)!;
  const run = async () => {
    const cacheKey = `dr-home-send-${business}`;
    type Pending = {
      text: string;
      context: QuestionContext;
      key: string;
      messageKey: string;
      chatId?: string;
    };
    const previous = store.get<Pending | null>(cacheKey, null);
    const pending: Pending =
      previous?.text === text &&
      JSON.stringify(previous.context) === JSON.stringify(context)
        ? previous
        : {
            text,
            context,
            key: crypto.randomUUID(),
            messageKey: crypto.randomUUID(),
          };
    store.set(cacheKey, pending);
    const chat = pending.chatId
      ? ({ id: pending.chatId } as Chat)
      : await api<Chat>("/api/chats", {
          business_id: business,
          title: shortTitle(text),
          analysis_id: context.analysis_id || "",
          request_key: pending.key,
        });
    pending.chatId = chat.id;
    store.set(cacheKey, pending);
    const key = messageKey(chat.id);
    store.set(key, {
      text,
      key: pending.messageKey,
      finding_reference: context.finding_reference,
      context_references: context.context_references?.map(referenceWire),
    });
    await api<Turn>(`/api/chats/${chat.id}/messages`, {
      business_id: business,
      text,
      request_key: pending.messageKey,
      ...(context.context_references?.length
        ? { context_references: context.context_references.map(referenceWire) }
        : {}),
      ...(context.finding_reference
        ? { finding_reference: context.finding_reference }
        : {}),
    });
    if (store.get<MessageDraft>(key, { text: "" }).key === pending.messageKey)
      store.remove(key);
    store.remove(cacheKey);
    if (store.get(homeDraftKey(business), "") === text) {
      store.remove(homeDraftKey(business));
      if (
        JSON.stringify(store.get(contextKey(business), {})) ===
        JSON.stringify(context)
      )
        store.remove(contextKey(business));
    }
    return chat;
  };
  const promise = run().finally(() => launches.delete(business));
  launches.set(business, promise);
  return promise;
}
export function queuePosition(turns: Turn[], index: number) {
  if (turns[index]?.status !== "queued") return 0;
  const earlier = turns.slice(0, index);
  return earlier.some((t) =>
    ["queued", "routing", "processing"].includes(t.status),
  )
    ? earlier.filter((t) => t.status === "queued").length + 1
    : 0;
}
export async function uploadPayload(key: string, metadata: object, file: File) {
  if (
    !file ||
    !file.name.toLowerCase().endsWith(".csv") ||
    !file.size ||
    file.size > 20 * 1024 ** 2
  )
    throw new Error("Elige un CSV con datos, de hasta 20 MB.");
  const hash = Array.from(
    new Uint8Array(
      await crypto.subtle.digest("SHA-256", await file.arrayBuffer()),
    ),
  )
    .map((v) => v.toString(16).padStart(2, "0"))
    .join("");
  const signature = JSON.stringify([metadata, file.name, hash]);
  const old = store.get<{ signature: string; key: string } | null>(key, null);
  const pending =
    old?.signature === signature
      ? old
      : { signature, key: crypto.randomUUID(), metadata };
  store.set(key, pending);
  const body = new FormData();
  body.append(
    "metadata",
    JSON.stringify({ ...metadata, request_key: pending.key }),
  );
  body.append("file", file);
  return body;
}
export const FOLDER_LIMIT = 2_000_000_000;
export type FolderFile = File & { webkitRelativePath?: string };
export const folderPath = (file: FolderFile) => file.webkitRelativePath || file.name;
export function selectedDataFiles(files: Iterable<FolderFile>) {
  const all = Array.from(files);
  return {
    supported: all.filter((file) => /\.(csv|xlsx)$/i.test(file.name)),
    ignored: all.filter((file) => !/\.(csv|xlsx)$/i.test(file.name)),
  };
}

export async function uploadFolder(
  key: string,
  metadata: Record<string, unknown>,
  files: FolderFile[],
  progress?: (uploaded: number, total: number) => void,
) {
  if (!files.length || files.some((file) => !file.size))
    throw new Error("Selecciona archivos CSV o Excel con datos.");
  const total = files.reduce((sum, file) => sum + file.size, 0);
  if (total > FOLDER_LIMIT)
    throw new Error("La carpeta supera el límite total de 2 GB.");
  const byPath = new Map(files.map((file) => [folderPath(file), file]));
  if (byPath.size !== files.length)
    throw new Error("Hay archivos con la misma ruta en la carpeta.");
  const listing = files.map((file) => ({ path: folderPath(file), size: file.size }));
  const signature = JSON.stringify([metadata, files.map((file) => [folderPath(file), file.size, file.lastModified]).sort()]);
  const old = store.get<{ signature: string; id: string } | null>(key, null);
  const pending = old?.signature === signature ? old : { signature, id: crypto.randomUUID() };
  store.set(key, pending);
  const base = `/api/datasets/bundles/${pending.id}`;
  const state = await api<{ files: { path: string; size: number; uploaded: number }[]; result?: { analysis_id: string; status: string; message?: string } }>(
    "/api/datasets/bundles",
    { ...metadata, request_key: pending.id, files: listing },
  );
  if (state.result) {
    return { ...state.result, upload_id: pending.id };
  }
  let uploaded = state.files.reduce((sum, file) => sum + file.uploaded, 0);
  progress?.(uploaded, total);
  for (const [index, item] of state.files.entries()) {
    const file = byPath.get(item.path);
    if (!file || file.size !== item.size)
      throw new Error("La carpeta seleccionada ha cambiado. Selecciónala de nuevo.");
    for (let offset = item.uploaded; offset < file.size; ) {
      const end = Math.min(offset + 8 * 1024 * 1024, file.size);
      let response: globalThis.Response;
      try {
        response = await fetch(`${base}/files/${index}`, {
          method: "POST",
          headers: {
            "X-Decision-Room": "1",
            "X-Upload-Offset": String(offset),
            "Content-Type": "application/octet-stream",
          },
          credentials: "same-origin",
          body: file.slice(offset, end),
        });
      } catch {
        throw new Error("Se ha interrumpido la subida. Vuelve a intentarlo para reanudarla.");
      }
      const answer = await response.json();
      if (!response.ok) throw new ApiError(answer.error || "No se pudo subir un fragmento.", response.status);
      uploaded += end - offset;
      offset = end;
      progress?.(uploaded, total);
    }
  }
  const result = await api<{ analysis_id: string; status: string; message?: string }>(`${base}/finish`, {});
  return { ...result, upload_id: pending.id };
}
