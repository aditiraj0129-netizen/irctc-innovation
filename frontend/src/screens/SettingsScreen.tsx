import { useState } from "react";
import { api, type Lang } from "../api";
import { applyA11y, loadA11y, type A11y } from "../a11y";
import { t, tc } from "../i18n";
import { useLoad } from "../useLoad";

// Settings: accessibility, language, honest data sources, the rule documents in the knowledge base,
// and a button to clear everything this app saved on the device.
export function SettingsScreen({ lang, setLang }: { lang: Lang; setLang: (l: Lang) => void }) {
  const [a, setA] = useState<A11y>(loadA11y());
  const [cleared, setCleared] = useState(false);
  const kb = useLoad(() => api.knowledge(), []);
  const health = useLoad(() => fetch(((import.meta as any).env?.VITE_API_URL ?? "") + "/api/health").then((r) => r.json()), []);
  const set = (k: keyof A11y, v: boolean) => { const n = { ...a, [k]: v }; setA(n); applyA11y(n); };
  const providers: Record<string, string> = health.data?.providers ?? {};

  function clearDevice() {
    try {
      ["aglaKadam.myJourneys", "aglaKadam.activity"].forEach((k) => window.localStorage.removeItem(k));
    } catch { /* storage off */ }
    try { window.indexedDB?.deleteDatabase("agla-kadam"); } catch { /* ignore */ }
    setCleared(true);
  }

  return (
    <div className="stack">
      <header className="page-head"><h1>{t(lang, "settings")}</h1></header>
      <div className="grid-2">
        <div className="stack">
          <section className="card" aria-labelledby="h-a11y">
            <h2 id="h-a11y" className="small-h">{t(lang, "a11y")}</h2>
            {(["large", "contrast", "simple"] as const).map((k) => (
              <label key={k} className="switch-row">
                <span>{t(lang, "a11y_" + k)}</span>
                <input type="checkbox" data-testid={`a11y-${k}`} checked={a[k]} onChange={(e) => set(k, e.target.checked)} />
              </label>
            ))}
            <div className="switch-row">
              <span>{t(lang, "a11y_lang")}</span>
              <select data-testid="set-lang" value={lang} onChange={(e) => setLang(e.target.value as Lang)} aria-label={t(lang, "a11y_lang")}>
                <option value="en">English</option><option value="hi">हिन्दी</option>
              </select>
            </div>
          </section>
          <section className="card stack-sm" aria-labelledby="h-dev">
            <h2 id="h-dev" className="small-h">{t(lang, "clear_device")}</h2>
            <button className="secondary" data-testid="clear-device" onClick={clearDevice}>{t(lang, "clear_device")}</button>
            {cleared && <p className="small">✓ {t(lang, "cleared")}</p>}
          </section>
        </div>
        <div className="stack">
          <section className="card stack-sm" aria-labelledby="h-data" data-testid="data-sources">
            <h2 id="h-data" className="small-h">{t(lang, "data_sources")}</h2>
            <ul className="plain small">
              <li>{t(lang, "data_sim")}</li><li>{t(lang, "data_rules")}</li><li>{t(lang, "data_ai")}</li>
            </ul>
            {Object.keys(providers).length > 0 && (
              <>
                <p className="label">{t(lang, "data_providers")}</p>
                <ul className="plain tiny mono">{Object.entries(providers).map(([k, v]) => <li key={k}>{k}: {String(v)}</li>)}</ul>
              </>
            )}
          </section>
          <section className="card stack-sm" aria-labelledby="h-kb" data-testid="kb-docs">
            <h2 id="h-kb" className="small-h">{t(lang, "knowledge_docs")}</h2>
            {!kb.data ? <p className="muted small" aria-busy="true">…</p> : (
              <ul className="plain small">
                {kb.data.documents.map((d) => (
                  <li key={d.id}>
                    {d.source_url ? <a href={d.source_url} target="_blank" rel="noreferrer noopener">{d.title}</a> : d.title}
                    <span className="muted"> · {d.version} · {tc(lang, "st_", d.status)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
