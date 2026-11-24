import { useEffect } from "react";
import { api, decideApi, type Lang } from "../api";
import { GraphTimeline } from "../components/GraphTimeline";
import { JourneyHeader } from "../components/JourneyHeader";
import { SectionNav } from "../components/SectionNav";
import { dayTime, duration, minutesBetween, time } from "../format";
import { t } from "../i18n";
import { activity, myJourneys } from "../myJourneys";
import { go } from "../router";
import { namesFromJourney } from "../trace";
import { useAssessment } from "../useAssessment";
import { useLoad } from "../useLoad";

const CALM = new Set(["ALL_CLEAR", "NOT_WATCHING_YET", "JOURNEY_OVER"]);
const OUTLOOK_WARN = new Set<string | undefined>(["CONNECTION_AT_RISK", "CONNECTION_BROKEN", "CONNECTION_TIGHT"]);

// Journey overview: the alert (what changed), the connected-journey timeline (Digital Twin + graph),
// and the booked tickets. On desktop the timeline and the tickets sit side by side.
export function JourneyScreen({ id, lang }: { id: string; lang: Lang }) {
  const { data, error } = useAssessment(id, lang);
  const twin = useLoad(() => api.twin(id), [id], 3000);
  const rec = useLoad(() => api.recovery(id), [id], 4000);
  // The Decide outlook also uses the delay trend and the route ahead; show it here too so screens never disagree.
  const outlook = useLoad(() => decideApi.decision(id), [id], 8000);
  useEffect(() => { myJourneys.add(id); activity.log(id, "opened"); }, [id]);

  if (error && !data) return <p className="error" role="alert">{t(lang, "err_network")}</p>;
  if (!data) return <p className="muted" aria-busy="true">…</p>;
  const j = data.journey;
  const sit = data.situation;
  const station = sit.detail?.station ? j.legs.find((l) => l.to.code === sit.detail.station)?.to[lang] ?? sit.detail.station : "";
  const calm = CALM.has(sit.type);
  const u = rec.data?.urgency;
  const names = namesFromJourney(j.legs);

  return (
    <div className="stack">
      <JourneyHeader j={j} lang={lang} title={t(lang, "my_journey")} />
      <SectionNav id={id} lang={lang} active="journey" />

      {!calm && (
        <section className={`alert ${sit.type === "STALE_DATA" ? "alert-grey" : "alert-amber"}`} role="alert" data-testid="situation-alert">
          <div className="row-between">
            <p className="eyebrow">{t(lang, "something_changed")}</p>
            {u && <span className={`urg urg-${u.level}`}>{t(lang, "urg_" + u.level)}</span>}
          </div>
          {/* If the connected-journey graph already shows the change is impossible, say so plainly. */}
          <p className="alert-text">{t(lang, sit.type === "CONNECTION_AT_RISK" && rec.data?.graph.status === "BROKEN" ? "s_CONNECTION_BROKEN" : "s_" + sit.type, { station })}</p>
          {u?.decide_by && <p className="small"><strong>{t(lang, "decide_by_t", { t: dayTime(u.decide_by) })}</strong>{u.minutes_left != null ? ` · ${duration(u.minutes_left, lang)}` : ""}</p>}
          {sit.type !== "STALE_DATA" && (
            <div className="row-gap">
              <button className="primary cta" data-testid="open-decide" onClick={() => go(`decide/${id}`)}>{t(lang, "dz_open")}</button>
              <button className="secondary" data-testid="see-options" onClick={() => go(`options/${id}`)}>{t(lang, "see_options")}</button>
              <button className="secondary" data-testid="open-disruption" onClick={() => go(`disruption/${id}`)}>{t(lang, "dc_open")}</button>
            </div>
          )}
        </section>
      )}
      {calm && (
        <section className={`alert ${OUTLOOK_WARN.has(outlook.data?.header.status) ? "alert-amber" : "alert-green"}`} data-testid="situation-calm">
          {OUTLOOK_WARN.has(outlook.data?.header.status)
            ? <p className="alert-text" data-testid="outlook-warning">{t(lang, "hs_" + outlook.data!.header.status)}</p>
            : <p className="alert-text">{t(lang, "s_" + sit.type)}</p>}
          {u?.level === "WATCH" && <p className="small"><span className="urg urg-WATCH">{t(lang, "urg_WATCH")}</span></p>}
          <div className="row-gap">
            <button className="secondary" onClick={() => go(`options/${id}`)}>{t(lang, "see_options")}</button>
            <button className="secondary" data-testid="open-decide-calm" onClick={() => go(`decide/${id}`)}>{t(lang, "dz_open")}</button>
          </div>
        </section>
      )}

      <div className="grid-2">
        {twin.data && rec.data ? <GraphTimeline graph={rec.data.graph} twin={twin.data} lang={lang} names={names} />
          : <div className="card muted" aria-busy="true">…</div>}

        <div className="stack">
          <h2 className="small-h">{t(lang, "booked_tickets")}</h2>
          <ol className="timeline">
            {j.legs.map((leg, i) => {
              const live = data.live[leg.train_no];
              const next = j.legs[i + 1];
              const delay = live?.delay_minutes ?? 0;
              return (
                <li key={leg.seq} className="card leg">
                  <div className="row-between">
                    <strong>{leg.train_no} · {leg.train_name}</strong>
                    <span className={`pill ${delay > 0 ? "pill-amber" : "pill-green"}`}>
                      {live?.cancelled ? "✕" : delay > 0 ? `${t(lang, "late_by")} ${duration(delay, lang)}` : t(lang, "on_time")}
                    </span>
                  </div>
                  <div className="leg-route">
                    <div><span className="big">{leg.from[lang]}</span><span className="muted small">{dayTime(leg.scheduled_departure)}</span></div>
                    <span aria-hidden className="arrow">→</span>
                    <div><span className="big">{leg.to[lang]}</span><span className="muted small">{dayTime(leg.scheduled_arrival)}</span></div>
                  </div>
                  <p className="small muted">
                    {leg.class} · {leg.status} · {leg.passengers} {t(lang, "passengers")} · {t(lang, "last_update")}: {live?.last_update ? time(live.last_update) : t(lang, "no_update")}
                  </p>
                  {next && (
                    <p className="small buffer detail-only">
                      {t(lang, "buffer")}: <strong>{duration(minutesBetween(leg.scheduled_arrival, next.scheduled_departure), lang)}</strong> ·{" "}
                      {j.min_transfer_minutes} min {t(lang, "min_transfer")} · {j.linked_pnr ? t(lang, "linked") : t(lang, "not_linked")}
                    </p>
                  )}
                </li>
              );
            })}
          </ol>
          <div className="row-gap">
            <button className="secondary" onClick={() => go(`copilot/${id}`)}>💬 {t(lang, "nav_copilot")}</button>
            <button className="secondary" onClick={() => go(`whatif/${id}`)}>{t(lang, "nav_whatif")}</button>
            <button className="secondary" data-testid="open-station" onClick={() => go(`station/${id}`)}>🚉 {t(lang, "sn_open")}</button>
          </div>
          <p className="small muted">{t(lang, "timetable_note")}</p>
        </div>
      </div>
    </div>
  );
}
