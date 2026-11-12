import type { Lang, RightsClock as RC } from "../api";
import { dayTime, rupees, time } from "../format";
import { t } from "../i18n";

// The Rights Clock: one lane per right/option, from "now" to the horizon.
export function RightsClock({ clock, lang }: { clock: RC; lang: Lang }) {
  const start = new Date(clock.now).getTime();
  const lastEnd = Math.max(start + 60 * 60000, ...clock.windows.map((w) => new Date(w.end).getTime()));
  const end = Math.min(new Date(clock.horizon_end).getTime(), lastEnd + 30 * 60000);
  const span = end - start;
  const pct = (iso: string) => Math.max(0, Math.min(100, ((new Date(iso).getTime() - start) / span) * 100));
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => new Date(start + f * span).toISOString());

  if (!clock.windows.length) return null;
  return (
    <section className="card clock" aria-label={t(lang, "rights_clock")} data-testid="rights-clock">
      <div className="clock-head">
        <h3>{t(lang, "rights_clock")}</h3>
        <span className="muted small">{t(lang, "if_nothing_changes")}</span>
      </div>
      <p className="muted small">{t(lang, "rights_clock_help")}</p>

      {clock.decision_deadline && (
        <div className="deadline-banner" data-testid="decision-deadline">
          <strong>{t(lang, "decide_by")} {time(clock.decision_deadline)}</strong>
        </div>
      )}

      <div className="lanes">
        {clock.windows.map((w) => {
          const left = pct(w.start), right = pct(w.end);
          const cls = w.status === "CLOSED" ? "closed" : w.kind === "BOOK_ALTERNATIVE" ? "book"
            : (w.amount_paise ?? 0) === 0 ? "zero" : w.if_approved ? "approve" : "money";
          return (
            <div className="lane" key={w.id}>
              <div className="lane-label">
                <span>{t(lang, "w_" + w.kind)}</span>
                <span className="lane-amt">
                  {w.amount_paise !== null ? rupees(w.amount_paise) : ""}
                  {w.if_approved ? ` (${t(lang, "if_approved")})` : ""}
                </span>
              </div>
              <div className="track">
                <div className={`bar ${cls} ${w.verified ? "" : "unverified"}`}
                  style={{ left: `${left}%`, width: `${Math.max(1.5, right - left)}%` }}
                  title={`${dayTime(w.start)} → ${dayTime(w.end)}`} />
              </div>
              <div className="lane-foot small muted">
                {t(lang, w.status.toLowerCase())} · {time(w.start)}–{time(w.end)}
                {!w.verified && w.kind !== "BOOK_ALTERNATIVE" ? " · " + t(lang, "not_verified") : ""}
              </div>
            </div>
          );
        })}
        <div className="now-line" aria-hidden />
      </div>
      <div className="ticks small muted">{ticks.map((x, i) => <span key={i}>{i === 0 ? t(lang, "now") : time(x)}</span>)}</div>

      {clock.next_drop && (
        <p className="small">{t(lang, "next_drop")} <strong>{time(clock.next_drop.at)}</strong>: {rupees(clock.next_drop.from_paise)} → {rupees(clock.next_drop.to_paise)}</p>
      )}
    </section>
  );
}
