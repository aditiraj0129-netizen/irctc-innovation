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
    const h = window.setInterval(load, pollMs);
    return () => window.clearInterval(h);
  }, [load, pollMs]);

  return { data, error, reload: load };
}
