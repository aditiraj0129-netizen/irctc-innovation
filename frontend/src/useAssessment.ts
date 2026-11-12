import { useCallback, useEffect, useState } from "react";
import { api, type Assessment, type Lang, type Priority } from "./api";

// Loads the assessment and refreshes it every few seconds, so presenter changes appear live.
export function useAssessment(id: string, lang: Lang, priority: Priority = "time", pollMs = 3000) {
  const [data, setData] = useState<Assessment | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api.assessment(id, priority, lang));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id, lang, priority]);

  useEffect(() => {
    load();
    // Don't keep polling while the tab is hidden (saves battery and server load); refresh on return.
    const tick = () => { if (!document.hidden) load(); };
    const h = window.setInterval(tick, pollMs);
    document.addEventListener("visibilitychange", tick);
    return () => { window.clearInterval(h); document.removeEventListener("visibilitychange", tick); };
  }, [load, pollMs]);

  return { data, error, reload: load };
}
