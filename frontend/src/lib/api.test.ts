import { describe, it, expect, vi } from "vitest";
import {
  launchChat,
  store,
  homeDraftKey,
  contextKey,
  queuePosition,
  shortTitle,
  reportState,
  uploadPayload,
  uploadFolder,
  FOLDER_LIMIT,
} from "./api";
import type { Turn } from "./types";
function server(fail = "") {
  const chats = new Map(),
    messages = new Map(),
    calls: { url: string; data: Record<string, unknown> }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, options: RequestInit) => {
      const data = JSON.parse(options.body as string);
      calls.push({ url, data });
      const records = url === "/api/chats" ? chats : messages;
      if (!records.has(data.request_key))
        records.set(data.request_key, { id: crypto.randomUUID() });
      if (fail === url || (fail === "message" && url.endsWith("/messages"))) {
        fail = "";
        throw new Error("response lost after save");
      }
      return { ok: true, json: async () => records.get(data.request_key) };
    }),
  );
  return { chats, messages, calls };
}
describe("durable chat handoff", () => {
  it("sends full text and short title without CSV, then clears matching draft", async () => {
    const s = server(),
      text = "Pregunta ".repeat(20);
    store.set(homeDraftKey("a"), text);
    const c = await launchChat("a", text);
    expect(s.calls[0].data.title).toBe(shortTitle(text));
    expect(s.calls[1].data.text).toBe(text);
    expect(s.calls[1].url).toBe(`/api/chats/${c.id}/messages`);
    expect(store.get(homeDraftKey("a"), null)).toBeNull();
  });
  for (const fail of ["/api/chats", "message"])
    it(`reuses identities after losing ${fail} response`, async () => {
      const s = server(fail);
      await expect(launchChat("a", "Pregunta")).rejects.toThrow();
      await launchChat("a", "Pregunta");
      expect(s.chats.size).toBe(1);
      expect(s.messages.size).toBe(1);
    });
  it("deduplicates concurrent submission", async () => {
    const s = server();
    const [a, b] = await Promise.all([
      launchChat("a", "Pregunta"),
      launchChat("a", "Pregunta"),
    ]);
    expect(a.id).toBe(b.id);
    expect(s.calls.length).toBe(2);
  });
  it("preserves a new draft and selected finding while the old request finishes", async () => {
    server();
    const context = {
      analysis_id: "dataset",
      finding_reference: {
        report_id: "report",
        report_version: "hash",
        claim_key: "claim",
      },
    };
    store.set(homeDraftKey("a"), "Pregunta");
    store.set(contextKey("a"), context);
    const pending = launchChat("a", "Pregunta", context);
    store.set(homeDraftKey("a"), "Nueva pregunta");
    await pending;
    expect(store.get(homeDraftKey("a"), "")).toBe("Nueva pregunta");
    expect(store.get(contextKey("a"), {})).toEqual(context);
  });
  it("preserves finding reference across retries and keeps different findings separate", async () => {
    const s = server("message"),
      context = {
        finding_reference: {
          report_id: "r",
          report_version: "v",
          claim_key: "first",
        },
      };
    await expect(launchChat("a", "Pregunta", context)).rejects.toThrow();
    await launchChat("a", "Pregunta", context);
    expect(s.calls.at(-1)!.data.finding_reference).toEqual(
      context.finding_reference,
    );
    await launchChat("a", "Pregunta", {
      finding_reference: { ...context.finding_reference, claim_key: "second" },
    });
    expect(s.chats.size).toBe(2);
  });
  it("does not send a message when model readiness rejects chat creation", async () => {
    const fetch = vi.fn(async () => ({
      ok: false,
      status: 409,
      json: async () => ({ error: "Modelo no disponible" }),
    }));
    vi.stubGlobal("fetch", fetch);
    await expect(launchChat("a", "Pregunta")).rejects.toThrow(
      "Modelo no disponible",
    );
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
it("only counts real queue predecessors", () => {
  for (const status of ["completed", "waiting", "stale", "failed"])
    expect(queuePosition([{ status }, { status: "queued" }] as Turn[], 1)).toBe(
      0,
    );
  expect(
    queuePosition(
      [
        { status: "processing" },
        { status: "queued" },
        { status: "queued" },
      ] as Turn[],
      2,
    ),
  ).toBe(2);
});
it("keeps withdrawn and historical reports distinct", () => {
  expect(
    reportState({ status: "blocked", presentation_status: "withdrawn" }),
  ).toBe("withdrawn");
  expect(
    reportState({
      status: "completed",
      data_version: { superseded_by: "new" },
    }),
  ).toBe("historical");
});
it("rejects unsupported or empty uploads before submitting", async () => {
  await expect(
    uploadPayload("upload", {}, new File(["x"], "x.xlsx")),
  ).rejects.toThrow("CSV");
  await expect(
    uploadPayload("upload", {}, new File([], "x.csv")),
  ).rejects.toThrow("CSV");
});

it("uploads a folder as one resumable batch and keeps the job identity", async () => {
  const files = [new File(["id,total\n1,10\n"], "ventas.csv")];
  Object.defineProperty(files[0], "webkitRelativePath", { value: "tienda/ventas.csv" });
  const calls: { url: string; body?: BodyInit | null; offset?: string | null }[] = [];
  let saved: { analysis_id: string; status: string } | null = null;
  vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit) => {
    calls.push({ url, body: options.body, offset: new Headers(options.headers).get("X-Upload-Offset") });
    if (url === "/api/datasets/bundles") {
      const data = JSON.parse(options.body as string);
      return { ok: true, json: async () => ({ files: [{ path: "tienda/ventas.csv", size: files[0].size, uploaded: saved ? files[0].size : 0 }], result: saved, id: data.request_key }) };
    }
    if (url.endsWith("/finish")) {
      saved = { analysis_id: "prepared", status: "ready" };
      throw new Error("response lost");
    }
    return { ok: true, json: async () => ({ uploaded: files[0].size }) };
  }));
  const key = "test-folder-retry";
  await expect(uploadFolder(key, { business_id: "shop", title: "Datos" }, files)).rejects.toThrow();
  const first = store.get<{ signature: string; id: string }>(key, { signature: "", id: "" });
  const recovered = await uploadFolder(key, { business_id: "shop", title: "Datos" }, files);
  expect(recovered.analysis_id).toBe("prepared");
  expect(recovered.upload_id).toBe(first.id);
  expect(calls.filter((call) => call.url.includes("/files/"))).toHaveLength(1);
  expect(calls.find((call) => call.url.includes("/files/"))?.offset).toBe("0");
  store.remove(key);
});

it("rejects folders over the total size before contacting the server", async () => {
  const file = new File(["x"], "a.csv");
  Object.defineProperty(file, "size", { value: FOLDER_LIMIT + 1 });
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  await expect(uploadFolder("too-large", {}, [file])).rejects.toThrow("2 GB");
  expect(fetch).not.toHaveBeenCalled();
});
