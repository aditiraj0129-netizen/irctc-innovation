import type { Lang } from "../api";
import { go } from "../router";
import { dayTime, duration, minutesBetween } from "../format";
import { t } from "../i18n";
import { useAssessment } from "../useAssessment";

const CALM = new Set(["ALL_CLEAR", "NOT_WATCHING_YET", "JOURNEY_OVER"]);

// Screens 2 + 3: the journey timeline, and the "something changed" alert when a rule threshold is crossed.
export function JourneyScreen({ id, lang }: { id: string; lang: Lang }) {
  const { data, error } = useAssessment(id, lang);
  if (error && !data) return <p className="error" role="alert">{t(lang, "err_network")}</p>;
  if (!data) return <p className="muted">…</p>;
  const j = data.journey;
  const sit = data.situation;
  const station = sit.detail?.station ? j.legs.find((l) => l.to.code === sit.detail.station)?.to[lang] ?? sit.detail.station : "";
  const calm = CALM.has(sit.type);

  return (
    <div className="stack">
      <div className="row-between">
        <h1>{t(lang, "my_journey")}</h1>
        <span className="mono small muted">{j.pnr_label}</span>
      </div>

      {!calm && (
        <section className={`alert ${sit.type === "STALE_DATA" ? "alert-grey" : "alert-amber"}`} role="alert" data-testid="situation-alert">
          <p className="eyebrow">{t(lang, "something_changed")}</p>
          <p className="alert-text">{t(lang, "s_" + sit.type, { station })}</p>
          {sit.type !== "STALE_DATA" && (
            <button className="primary" data-testid="see-options" onClick={() => go(`options/${id}`)}>{t(lang, "see_options")}</button>
          )}
        </section>
      )}
      {calm && (
        <section className="alert alert-green" data-testid="situation-calm">
          <p className="alert-text">{t(lang, "s_" + sit.type)}</p>
          <button className="secondary" onClick={() => go(`options/${id}`)}>{t(lang, "see_options")}</button>
        </section>
      )}

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
                {leg.class} · {leg.status} · {leg.passengers} {t(lang, "passengers")} · {t(lang, "last_update")}: {live?.last_update ? dayTime(live.last_update) : t(lang, "no_update")}
              </p>
              {next && (
                <p className="small buffer">
                  {t(lang, "buffer")}: <strong>{duration(minutesBetween(leg.scheduled_arrival, next.scheduled_departure), lang)}</strong> ·{" "}
                  {j.min_transfer_minutes} min {t(lang, "min_transfer")} · {j.linked_pnr ? t(lang, "linked") : t(lang, "not_linked")}
                </p>
              )}
            </li>
          );
        })}
      </ol>
      <p className="small muted">{t(lang, "timetable_note")}</p>
    </div>
  );
}
