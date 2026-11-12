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
    const tick = () => { if (!document.hidden) load(); };   // pause while the tab is hidden
    const h = window.setInterval(tick, pollMs);
    document.addEventListener("visibilitychange", tick);
    return () => { window.clearInterval(h); document.removeEventListener("visibilitychange", tick); };
  }, [load, pollMs]);
  return { data, error, reload: load };
}
