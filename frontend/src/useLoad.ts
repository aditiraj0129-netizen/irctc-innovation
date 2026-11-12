import { useCallback, useEffect, useState } from "react";

// Generic loader: calls fn(), optionally re-polls, never throws into the UI.
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[], pollMs = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const load = useCallback(async () => {
    try { setData(await fn()); setError(null); } catch (e) { setError((e as Error).message); }
  }, deps);
  useEffect(() => {
    load();
    if (!pollMs) return;
    const h = window.setInterval(load, pollMs);
    return () => window.clearInterval(h);
  }, [load, pollMs]);
  return { data, error, reload: load };
}
