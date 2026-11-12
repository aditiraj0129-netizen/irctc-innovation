import { useState } from "react";
import { api, type Lang } from "../api";
import { SectionNav } from "../components/SectionNav";
import { dayTime, time } from "../format";
import { t, tc } from "../i18n";
import { useLoad } from "../useLoad";

const TYPES = ["PLATFORM_CHANGE", "CONGESTION", "TRAIN_STOPPED", "ACCESS_PROBLEM", "TRANSFER_DIFFICULTY"];

// Community Disruption Intelligence: unverified, expiring reports. Shown beside, never inside, the advice.
export function CommunityScreen({ id, lang }: { id: string; lang: Lang }) {
  const { data, reload } = useLoad(() => api.reports(id), [id], 5000);
  const [station, setStation] = useState("");
  const [type, setType] = useState(TYPES[0]);
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.report(id, { station: station.trim().toUpperCase(), type, note: note.trim() || null });
      setMsg({ ok: true, text: t(lang, "cm_sent") }); setNote(""); reload();
    } catch (err) { setMsg({ ok: false, text: (err as Error).message }); }
  };

  return (
    <div className="stack">
      <h1>{t(lang, "cm_title")}</h1>
      <SectionNav id={id} lang={lang} active="more" />
      <p className="safety small" data-testid="cm-unverified">{t(lang, "cm_unverified")}</p>
      {data && data.length === 0 && <p className="muted">{t(lang, "cm_none")}</p>}
      <ul className="plans" data-testid="reports">
        {data?.map((r) => (
          <li key={r.id} className="card stack-sm">
            <div className="row-between">
              <strong>{tc(lang, "rt_", r.type)} · {r.station}{r.train_no ? ` · ${r.train_no}` : ""}</strong>
              <span className={`pill conf-${r.confidence}`}>{t(lang, "conf_" + r.confidence)} {t(lang, "conf_word")}</span>
            </div>
            {r.note && <p className="small">"{r.note}"</p>}
            <p className="tiny muted">
              {t(lang, "cm_reporters", { n: String(r.reporters) })} · {dayTime(r.last_seen)} · {t(lang, "cm_expires", { t: time(r.expires_at) })}
              {r.simulated_seed ? ` · ${t(lang, "cm_seed")}` : ""}
            </p>
            {r.conflicting && <p className="con small">⚠ {t(lang, "cm_conflict")}</p>}
          </li>
        ))}
      </ul>
      <form className="card stack-sm" onSubmit={send} data-testid="report-form">
        <h3>{t(lang, "cm_add")}</h3>
        <label className="label">{t(lang, "cm_station")}
          <input value={station} onChange={(e) => setStation(e.target.value)} maxLength={5} placeholder="PRYJ" required data-testid="cm-station" /></label>
        <label className="label">{t(lang, "cm_type")}
          <select value={type} onChange={(e) => setType(e.target.value)} data-testid="cm-type">
            {TYPES.map((x) => <option key={x} value={x}>{tc(lang, "rt_", x)}</option>)}
          </select></label>
        <label className="label">{t(lang, "cm_note")}
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={120} data-testid="cm-note" /></label>
        <button className="primary" type="submit" data-testid="cm-send">{t(lang, "cm_send")}</button>
        {msg && <p className={msg.ok ? "note small" : "error small"} role={msg.ok ? "status" : "alert"}>{msg.text}</p>}
      </form>
    </div>
  );
}
