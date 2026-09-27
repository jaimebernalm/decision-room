import { useCallback, useEffect, useRef, useState } from "react";
import { api, store } from "./api";
export function useResource<T>(path: string, interval = 0) {
  const [saved, setData] = useState<{ path: string; data: T } | null>(null),
    [error, setError] = useState(""),
    [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((x) => x + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const read = async () => {
      try {
        const result = await api<T>(path, undefined, controller.signal);
        if (!controller.signal.aborted) {
          setData({ path, data: result });
          setError("");
        }
      } catch (e) {
        if (!controller.signal.aborted) setError((e as Error).message);
      } finally {
        if (interval && !controller.signal.aborted)
          timer = setTimeout(read, interval);
      }
    };
    void read();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [path, interval, revision]);
  return { data: saved?.path === path ? saved.data : null, error, refresh };
}
export function useDraft<T>(key: string, fallback: T) {
  const [value, setValue] = useState<T>(() => store.get(key, fallback));
  useEffect(() => {
    const sync = (event: Event) => {
      if ((event as CustomEvent).detail === key)
        setValue(store.get(key, fallback));
    };
    addEventListener("dr-draft", sync);
    return () => removeEventListener("dr-draft", sync);
    // The fallback only initializes an empty draft.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const set = useCallback(
    (next: T) => {
      store.set(key, next);
      setValue(next);
    },
    [key],
  );
  return [value, set] as const;
}
export function useAction() {
  const locked = useRef(false),
    mounted = useRef(true);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const run = async <T>(fn: () => Promise<T>) => {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError("");
    try {
      return await fn();
    } catch (e) {
      if (mounted.current) setError((e as Error).message);
    } finally {
      locked.current = false;
      if (mounted.current) setBusy(false);
    }
  };
  return { busy, error, run, setError, isMounted: () => mounted.current };
}
