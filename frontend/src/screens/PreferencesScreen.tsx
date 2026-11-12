import { useEffect, useState } from "react";
import { api, type Lang, type Profile } from "../api";
import { SectionNav } from "../components/SectionNav";
import { t } from "../i18n";

// Accessibility needs used by Station Transfer Intelligence. Only three simple settings, no personal data.
export function PreferencesScreen({ id, lang }: { id: string; lang: Lang }) {
  const [p, setP] = useState<Profile | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => { api.prefs(id).then((r) => setP(r.profile)).catch(() => setP({ walking_speed: "normal", step_free: false, senior: false })); }, [id]);
  if (!p) return <p className="muted">…</p>;
  const save = async () => { await api.savePrefs(id, { profile: p, priority: "time" }); setSaved(true); };
  const set = (patch: Partial<Profile>) => { setP({ ...p, ...patch }); setSaved(false); };
  return (
    <div className="stack">
      <h1>{t(lang, "pf_title")}</h1>
      <SectionNav id={id} lang={lang} active="more" />
      <p className="small muted">{t(lang, "pf_help")}</p>
      <fieldset className="segmented seg-2">
        <legend className="small muted">{t(lang, "pf_speed")}</legend>
        {(["normal", "slow"] as const).map((s) => (
          <button key={s} aria-pressed={p.walking_speed === s} data-testid={`speed-${s}`} onClick={() => set({ walking_speed: s })}>{t(lang, "pf_" + s)}</button>
        ))}
      </fieldset>
      <label className="check"><input type="checkbox" checked={p.step_free} data-testid="pf-step-free" onChange={(e) => set({ step_free: e.target.checked })} /> {t(lang, "pf_step_free")}</label>
      <label className="check"><input type="checkbox" checked={p.senior} data-testid="pf-senior" onChange={(e) => set({ senior: e.target.checked })} /> {t(lang, "pf_senior")}</label>
      <button className="primary" data-testid="pf-save" onClick={save}>{t(lang, "pf_save")}</button>
      {saved && <p className="note small" role="status">{t(lang, "pf_saved")}</p>}
    </div>
  );
}
