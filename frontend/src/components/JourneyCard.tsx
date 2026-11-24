import type { DashJourney, Lang } from "../api";
import { dayTime, duration } from "../format";
import { t, tc } from "../i18n";
import { go } from "../router";

// One journey as a card: route, health, urgency, next departure and the change-of-train margin.
export function JourneyCard({ d, lang, onRemove }: { d: DashJourney; lang: Lang; onRemove?: () => void }) {
  const j = d.journey, first = j.legs[0], last = j.legs[j.legs.length - 1];
  const via = j.legs.slice(0, -1).map((l) => l.to[lang]);
  const c = d.consequence || {};
  const id = j.id;
  return (
    <article className="jcard" data-testid={`jcard-${id}`}>
      <div className="row-between">
        <span className={`status st-${d.status}`}>{tc(lang, "twin_", d.status)}</span>
        <span className={`urg urg-${d.urgency.level}`}>{t(lang, "urg_" + d.urgency.level)}</span>
      </div>
      <div className="route">
        <span>{first.from[lang]}</span><span aria-hidden>→</span>
        {via.length > 0 && <span className="via">{t(lang, "via")} {via.join(", ")} →</span>}
        <span>{last.to[lang]}</span>
      </div>
      <div className="meta">
        <span>{j.legs.map((l) => l.train_no).join(" + ")}</span>
        <span>{t(lang, "departs")}: {dayTime(first.scheduled_departure)}</span>
        {c.connection_margin_minutes != null && (
          c.broken_from_leg
            ? <span className="bad-text">{t(lang, "conn_broken")}</span>
            : <span>{t(lang, "margin_left", { m: duration(Math.max(0, c.connection_margin_minutes), lang) })}</span>
        )}
        {d.urgency.decide_by && <span><strong>{t(lang, "decide_by_t", { t: dayTime(d.urgency.decide_by) })}</strong></span>}
        <span>{d.data_fresh ? t(lang, "fresh_ok") : t(lang, "fresh_stale")}</span>
      </div>
      <div className="row-gap">
        <button className="primary" data-testid={`open-${id}`} onClick={() => go(`journey/${id}`)}>{t(lang, "open_btn")}</button>
        {d.urgency.level !== "NONE" && <button className="secondary" onClick={() => go(`disruption/${id}`)}>{t(lang, "nav_disruption")}</button>}
        {onRemove && <button className="link" data-testid={`remove-${id}`} onClick={onRemove}>{t(lang, "remove")}</button>}
      </div>
    </article>
  );
}
