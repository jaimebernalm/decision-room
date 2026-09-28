import { useCallback, useSyncExternalStore } from "react";
import { api, ApiError } from "./api";

export type ActivityTask = {
  id: string; parent_id: string | null; status: string; text: string;
  purpose: string; kind: string; sequence: number;
  references: { kind: string; id: string; column: string }[];
  data_endpoint?: string | null; started_at?: string; finished_at?: string;
  question_id?: string | null;
};
export type ActivityEvent = {
  id: string; task_id: string; sequence: number; type: string; status: string;
  occurred_at?: string; recorded_at: string; reconstructed: boolean;
  text?: string;
};
export type Activity = {
  schema_version: number; trace_id: string | null; status: string;
  headline: string; terminal: boolean; history_complete: boolean;
  task_updates: ActivityTask[]; active_tasks: ActivityTask[];
  events: ActivityEvent[]; next_cursor: string | null;
  previous_cursor: string | null; has_more: boolean;
  worker_health: string; last_activity_at?: string;
  actors?: { id: string; role: string; task_id: string; parent_id: string | null; status: string; source: Record<string, unknown> }[];
  resources?: { logical_calls: number; http_attempts: number; unknown_http_calls?: number; executions: number; cache_hits: number;
    input_tokens: number | null; output_tokens: number | null; unknown_usage_calls: number;
    wall_seconds: number; owner_wait_seconds: number; provider_wait_seconds: number };
  business?: string;
};
type Snapshot = { data: Activity | null; tasks: ActivityTask[]; events: ActivityEvent[]; error: string; errorStatus: number | null; loadingOlder: boolean };
type Entry = { endpoint: string; listeners: Set<() => void>; snapshot: Snapshot;
  timer?: ReturnType<typeof setTimeout>; controller?: AbortController; fetching: boolean; failures: number };
const entries = new Map<string, Entry>();
const empty: Snapshot = { data: null, tasks: [], events: [], error: "", errorStatus: null, loadingOlder: false };

function entry(key: string, endpoint: string): Entry {
  let found = entries.get(key);
  if (!found) {
    found = { endpoint, listeners: new Set(), snapshot: empty, fetching: false, failures: 0 };
    entries.set(key, found);
  }
  return found;
}
function publish(e: Entry, next: Snapshot) {
  e.snapshot = next;
  e.listeners.forEach((listener) => listener());
}
function merge(e: Entry, data: Activity, older = false) {
  const tasks = new Map(e.snapshot.tasks.map((task) => [task.id, task]));
  for (const task of [...data.task_updates, ...data.active_tasks]) {
    if ((tasks.get(task.id)?.sequence ?? -1) <= task.sequence) tasks.set(task.id, task);
  }
  const events = new Map(e.snapshot.events.map((event) => [event.id, event]));
  data.events.forEach((event) => events.set(event.id, event));
  const current = older && e.snapshot.data ? { ...e.snapshot.data, previous_cursor: data.previous_cursor } : data;
  publish(e, { data: current, tasks: [...tasks.values()].sort((a,b) => (a.started_at || "").localeCompare(b.started_at || "") || a.id.localeCompare(b.id)),
    events: [...events.values()].sort((a,b) => a.sequence-b.sequence), error: "", errorStatus: null, loadingOlder: false });
}
async function fetchActivity(e: Entry, mode: "forward" | "refresh" | "older" = "forward") {
  if (e.fetching || !e.listeners.size) return;
  e.fetching = true; e.controller = new AbortController(); clearTimeout(e.timer); e.timer = undefined;
  if (mode === "older") publish(e, { ...e.snapshot, loadingOlder: true });
  try {
    let more = false;
    do {
      const query = new URLSearchParams();
      const cursor = mode === "older" ? e.snapshot.data?.previous_cursor : mode === "forward" ? e.snapshot.data?.next_cursor : null;
      if (cursor) query.set(mode === "older" ? "before" : "after", cursor);
      const data = await api<Activity>(`${e.endpoint}${query.size ? `?${query}` : ""}`, undefined, e.controller.signal);
      if (e.controller.signal.aborted || !e.listeners.size) return;
      if (e.snapshot.data?.trace_id && data.trace_id !== e.snapshot.data.trace_id) publish(e, empty);
      merge(e, data, mode === "older");
      more = data.has_more && mode !== "older";
      mode = "forward";
    } while (more);
    e.failures = 0;
  } catch (error) {
    if (!e.controller.signal.aborted) {
      e.failures++;
      const errorStatus = error instanceof ApiError ? error.status : null;
      publish(e, { ...([401,403].includes(errorStatus || 0) ? empty : e.snapshot), error: (error as Error).message, errorStatus, loadingOlder: false });
    }
  } finally {
    e.fetching = false;
    if (e.listeners.size && ![401,403].includes(e.snapshot.errorStatus || 0) && (!e.snapshot.data?.terminal || e.snapshot.error)) {
      const interval = e.failures ? Math.min(15000,2000 * 2 ** Math.min(e.failures,3)) : e.snapshot.data?.status === "waiting" ? 5000 : 2000;
      e.timer = setTimeout(() => { if (!document.hidden) void fetchActivity(e); else scheduleVisible(e); }, interval);
    }
  }
}
function scheduleVisible(e: Entry) {
  if (!e.listeners.size) return;
  e.timer = setTimeout(() => { if (!document.hidden) void fetchActivity(e); else scheduleVisible(e); }, 5000);
}
function wake() {
  if (document.hidden) return;
  entries.forEach((e) => { if (e.listeners.size) void fetchActivity(e, "refresh"); });
}
if (typeof window !== "undefined") {
  window.addEventListener("focus", wake);
  document.addEventListener("visibilitychange", wake);
}
export function useActivity(endpoint: string, traceId?: string | null, internal = false) {
  const key = `${internal ? "internal" : "client"}:${traceId || endpoint}`;
  const e = entry(key, endpoint);
  const subscribe = useCallback((listener: () => void) => {
    e.listeners.add(listener);
    if (!e.timer && !e.fetching) void fetchActivity(e);
    return () => {
      e.listeners.delete(listener);
      if (!e.listeners.size) { clearTimeout(e.timer); e.timer = undefined; e.controller?.abort(); }
    };
  }, [e]);
  const get = useCallback(() => e.snapshot, [e]);
  const snapshot = useSyncExternalStore(subscribe, get, get);
  return { ...snapshot, refresh: () => fetchActivity(e,"refresh"), loadOlder: () => fetchActivity(e,"older") };
}
// Test teardown also prevents cross-account cache retention after explicit logout.
export function clearActivityCache() {
  entries.forEach((e) => { clearTimeout(e.timer); e.controller?.abort(); });
  entries.clear();
}
