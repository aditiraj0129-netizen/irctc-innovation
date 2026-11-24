import { useEffect, useState } from "react";
import { api, type Lang } from "../api";
import { go } from "../router";
import { t } from "../i18n";

export const MAIN_DEMO = "bhopal_delhi_chandigarh";

export function AddJourney({ lang, embedded = false }: { lang: Lang; embedded?: boolean }) {
  const [pnr, setPnr] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [demos, setDemos] = useState<{ id: string; pnr: string; title: { en: string; hi: string } }[]>([]);

  useEffect(() => { api.scenarios().then(setDemos).catch(() => setError(t(lang, "err_network"))); }, [lang]);

  async function submit(value = pnr) {
    setError(null);
    if (!/^\d{10}$/.test(value)) { setError(t(lang, "err_pnr_format")); return; }
    setBusy(true);
    try {
      const j = await api.addJourney(value);
      go(`journey/${j.id}`);
    } catch (e) {
      setError((e as Error).message === "PNR_NOT_IN_DEMO_DATA" ? t(lang, "err_pnr_unknown") : t(lang, "err_network"));
    } finally { setBusy(false); }
  }

  return (
    <div className="stack">
      {!embedded && (
        <section className="hero">
          <h1>{t(lang, "app_name")}</h1>
          <p>{t(lang, "tagline")}</p>
        </section>
      )}

      <form className="card stack" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <h2 id="add-journey">{t(lang, "add_title")}</h2>
        <p className="muted">{t(lang, "add_help")}</p>
        <label htmlFor="pnr" className="label">{t(lang, "pnr")}</label>
        <input id="pnr" data-testid="pnr-input" inputMode="numeric" autoComplete="off" maxLength={10}
          value={pnr} onChange={(e) => setPnr(e.target.value.replace(/\D/g, ""))} placeholder="81XXXXXXXX"
          aria-invalid={!!error} aria-describedby={error ? "pnr-err" : undefined} />
        {error && <p id="pnr-err" className="error" role="alert">{error}</p>}
        <button className="primary" type="submit" disabled={busy} data-testid="pnr-submit">{t(lang, "continue")}</button>
      </form>

      <section className="card stack">
        <h3>{t(lang, "demo_pnrs")}</h3>
        {demos.map((d) => (
          <button key={d.id} className={`demo-row ${d.id === MAIN_DEMO ? "demo-hero" : ""}`} data-testid={`demo-${d.id}`} onClick={() => { setPnr(d.pnr); submit(d.pnr); }}>
            <span className="mono">{d.pnr}</span>
            <span>{d.title[lang]}{d.id === MAIN_DEMO && <> <span className="urg urg-SOON">{t(lang, "main_badge")}</span></>}</span>
          </button>
        ))}
      </section>
    </div>
  );
}
