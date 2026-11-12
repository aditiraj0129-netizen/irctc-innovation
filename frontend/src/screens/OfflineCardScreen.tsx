import { useEffect, useState } from "react";
import { api, type Lang, type OfflineCard } from "../api";
import { SectionNav } from "../components/SectionNav";
import { dayTime, rupees, time } from "../format";
import { t, tc } from "../i18n";
import { offlineStore, type SavedCard } from "../offlineStore";

function useOnline() {
  const [on, setOn] = useState(navigator.onLine);
  useEffect(() => {
    const up = () => setOn(true), down = () => setOn(false);
    window.addEventListener("online", up); window.addEventListener("offline", down);
    return () => { window.removeEventListener("online", up); window.removeEventListener("offline", down); };
  }, []);
  return on;
}

// Offline Journey Guardian: a saved snapshot, always labelled "not live", with the time it was made.
export function OfflineCardScreen({ id, lang }: { id: string; lang: Lang }) {
  const online = useOnline();
  const [fresh, setFresh] = useState<OfflineCard | null>(null);
  const [saved, setSaved] = useState<SavedCard | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => { offlineStore.get(id).then((s) => setSaved(s ?? null)).catch(() => setSaved(null)); }, [id]);
  useEffect(() => {
    if (!online) return;
    api.offlineCard(id).then(setFresh).catch(() => setFresh(null));
  }, [id, online]);

  const save = async () => {
    if (!fresh) return;
    try { await offlineStore.save(fresh); setSaved(await offlineStore.get(id) ?? null); setMsg(t(lang, "off_saved")); }
    catch { setMsg(t(lang, "err_network")); }
  };
  const remove = async () => { await offlineStore.remove(id).catch(() => undefined); setSaved(null); };

  const showSaved = !online || !fresh;
  const card = showSaved ? saved?.card : fresh;
  return (
    <div className="stack">
      <h1>{t(lang, "off_title")}</h1>
      {online && <SectionNav id={id} lang={lang} active="more" />}
      {!online && <p className="alert alert-grey" role="status" data-testid="offline-banner">{t(lang, "off_offline")}</p>}
      {online && fresh && (
        <div className="row-gap">
          <button className="primary" data-testid="off-save" onClick={save}>{t(lang, "off_save")}</button>
          {saved && <button className="danger" onClick={remove}>{t(lang, "off_delete")}</button>}
        </div>
      )}
      {msg && <p className="note small" role="status">{msg}</p>}
      {saved && <p className="small muted" data-testid="off-saved-at">{t(lang, "off_saved")} · {dayTime(saved.saved_at)}</p>}
      {card ? <CardView card={card} lang={lang} savedAt={showSaved ? saved?.saved_at ?? null : null} /> : <p className="muted" data-testid="off-none">{t(lang, "off_none")}</p>}
    </div>
  );
}

function CardView({ card, lang, savedAt }: { card: OfflineCard; lang: Lang; savedAt: string | null }) {
  // The demo clock and the phone clock differ, so "possibly out of date" is measured on the phone:
  // real time passed since the card was saved, against the card's own validity window.
  const validMs = new Date(card.stale_after).getTime() - new Date(card.generated_at).getTime();
  const stale = savedAt != null && Date.now() - new Date(savedAt).getTime() > validMs;
  return (
    <article className="card stack-sm offline-card" data-testid="offline-card">
      <p className="badge badge-amber" data-testid="off-label">{t(lang, "off_sim")}</p>
      <p className="small">{t(lang, "off_snapshot", { t: dayTime(card.generated_at) })}</p>
      {stale && <p className="con small">{t(lang, "off_stale")}</p>}
      <p className="mono small">{card.pnr_label} · {tc(lang, "twin_", card.status)}</p>
      <ol className="plain small">
        {card.legs.map((l) => (
          <li key={l.seq}><strong>{l.train_no}</strong> {l.from[lang]} → {l.to[lang]} · {dayTime(l.scheduled_departure)} · {tc(lang, "st_", l.state)}</li>
        ))}
      </ol>
      {card.transfers.map((x) => <p key={x.station.code} className="small">{tc(lang, "x_", x.class)} · {x.station[lang]}</p>)}
      <h3>{t(lang, "your_options")}</h3>
      <ol className="plain small">
        {card.plans.map((p) => (
          <li key={p.rank}>#{p.rank} {p.rides.map((r) => `${r.train_no} ${r.from}→${r.to} ${time(r.dep)}`).join(" + ") || tc(lang, "", p.kind)}
            {p.money_back_paise > 0 ? ` · ${rupees(p.money_back_paise)}${p.if_approved ? ` (${t(lang, "if_approved")})` : ""}` : ""}
            {p.deadline ? ` · ${t(lang, "act_by")} ${dayTime(p.deadline)}` : ""}</li>
        ))}
      </ol>
      <ul className="plain small">{card.instructions.map((i) => <li key={i}>→ {tc(lang, "in_", i)}</li>)}</ul>
      <h3>{t(lang, "off_emergency")}</h3>
      <ul className="plain small" data-testid="off-emergency">
        {card.emergency.map((e) => <li key={e.id}><a href={`tel:${e.number}`}>{e.number}</a> · {tc(lang, "em_", e.id)}</li>)}
      </ul>
    </article>
  );
}
