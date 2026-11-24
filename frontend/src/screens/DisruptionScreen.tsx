import { api, type Lang } from "../api";
import { JourneyHeader } from "../components/JourneyHeader";
import { SectionNav } from "../components/SectionNav";
import { dayTime, duration, rupees, time } from "../format";
import { t, tc } from "../i18n";
import { go } from "../router";
import { namesFromJourney, traceSentence, traceTone } from "../trace";
import { useLoad } from "../useLoad";

// Disruption Centre: answers seven plain questions about the disruption, all from the backend's
// recovery view (graph + rules engine + planner). Nothing here is calculated by AI.
export function DisruptionScreen({ id, lang }: { id: string; lang: Lang }) {
  const { data, error } = useLoad(() => api.recovery(id), [id], 4000);
  if (error && !data) return <p className="error" role="alert">{t(lang, "err_network")}</p>;
  if (!data) return <p className="muted" aria-busy="true">…</p>;
  const j = data.journey;
  const names = namesFromJourney(j.legs);
  const u = data.urgency;
  const c = data.consequence || {};

  return (
    <div className="stack">
      <JourneyHeader j={j} lang={lang} title={t(lang, "dc_title")} />
      <SectionNav id={id} lang={lang} active="disruption" />

      <section className={`dc-head lv-${u.level}`} data-testid="dc-head" aria-labelledby="dc-urg">
        <div className="row-between">
          <h2 id="dc-urg" className="small-h">{t(lang, "q_urgent")}</h2>
          <span className={`urg urg-${u.level}`} data-testid="dc-urgency">{t(lang, "urg_" + u.level)}</span>
        </div>
        {u.minutes_left != null && <p className="countdown" data-testid="dc-countdown">{duration(Math.max(0, u.minutes_left), lang)}</p>}
        {u.decide_by && <p><strong>{t(lang, "decide_by_t", { t: dayTime(u.decide_by) })}</strong></p>}
        {!data.data_fresh && <p data-testid="dc-stale">{t(lang, "stale_msg")}</p>}
      </section>

      <div className="grid-2">
        <div className="stack">
          <section className="card stack-sm" data-testid="dc-what">
            <h2 className="small-h">{t(lang, "q_what")}</h2>
            {data.what_happened.length === 0 ? <p className="small">{t(lang, "tr_ALL_ON_SCHEDULE")}</p> : (
              <ul className="plain small">
                {data.what_happened.map((e, i) => (
                  <li key={i}>{tc(lang, "ev_", e.type, { train: e.train_no, delay: duration(e.delay_minutes ?? 0, lang) })}
                    <span className="muted"> · {time(e.observed_at)} · {e.source}</span></li>
                ))}
              </ul>
            )}
          </section>

          <section className="card stack-sm" data-testid="dc-when">
            <h2 className="small-h">{t(lang, "q_when")}</h2>
            <p className="small">
              {data.last_updated ? dayTime(data.last_updated) : t(lang, "no_update")} ·{" "}
              <span className={`pill ${data.data_fresh ? "fresh-ok" : "fresh-stale"}`}>{t(lang, data.data_fresh ? "fresh_ok" : "fresh_stale")}</span>
            </p>
            <p className="tiny muted">{data.data_label}</p>
          </section>

          <section className="card stack-sm" data-testid="dc-which">
            <h2 className="small-h">{t(lang, "q_which")}</h2>
            <p className="small">{data.affected_legs.length ? t(lang, "legs_affected", { legs: data.affected_legs.join(", ") }) : t(lang, "none_affected")}</p>
            <ol className="trace">
              {data.graph.trace.map((s, i) => <li key={i} className={traceTone(s.code)}>{traceSentence(s, lang, names)}</li>)}
            </ol>
          </section>

          <section className="card stack-sm" data-testid="dc-mean">
            <h2 className="small-h">{t(lang, "q_mean")}</h2>
            {c.broken_from_leg ? (
              <p className="small">{t(lang, "cons_broken", { leg: String(c.broken_from_leg), fare: rupees(c.fare_of_unusable_legs_paise ?? 0) })}</p>
            ) : c.delay_at_destination_minutes ? (
              <p className="small">{t(lang, "cons_arrival", { t: dayTime(c.expected_final_arrival), d: duration(c.delay_at_destination_minutes, lang) })}</p>
            ) : c.expected_final_arrival ? (
              <p className="small">{t(lang, "cons_on_time", { t: dayTime(c.expected_final_arrival) })}</p>
            ) : null}
            {c.connection_margin_minutes != null && !c.broken_from_leg && (
              <p className="small">{t(lang, "cons_margin", { m: duration(Math.max(0, c.connection_margin_minutes), lang) })}</p>
            )}
          </section>
        </div>

        <div className="stack">
          <section className="card stack-sm" data-testid="dc-next">
            <h2 className="small-h">{t(lang, "q_next")}</h2>
            {data.next_steps.length === 0 ? <p className="small muted">{t(lang, "stale_msg")}</p> : (
              <ol className="plain stack-sm">
                {data.next_steps.slice(0, 3).map((s) => (
                  <li key={s.plan_id} className={`card compare-card ${s.rank === 1 ? "plan-top" : ""}`} data-testid={`dc-step-${s.plan_kind}`}>
                    <div className="row-between"><strong>#{s.rank} {tc(lang, "pk_", s.plan_kind)}</strong></div>
                    <p className="small">
                      {s.trains.length > 0 && <>{s.trains.join(" + ")} · </>}
                      {s.travels && s.arrival ? t(lang, "arrive_at", { t: dayTime(s.arrival) }) : t(lang, "travels_no")}
                      {s.money_back_paise > 0 && <> · {t(lang, "money_back_short", { m: rupees(s.money_back_paise) })}{s.money_back_if_approved ? ` (${t(lang, "if_approved_short")})` : ""}</>}
                    </p>
                    {s.deadline && <p className="tiny">{t(lang, "act_by")} {dayTime(s.deadline)}{s.deadline_unverified ? ` · ${t(lang, "deadline_unverified")}` : ""}</p>}
                  </li>
                ))}
              </ol>
            )}
            {data.data_fresh && (
              <div className="row-gap">
                <button className="primary cta" data-testid="dc-decide" onClick={() => go(`decide/${id}`)}>{t(lang, "dz_open")}</button>
                <button className="secondary" data-testid="dc-options" onClick={() => go(`options/${id}`)}>{t(lang, "see_options")}</button>
                <button className="secondary" onClick={() => go(`whatif/${id}`)}>{t(lang, "nav_whatif")}</button>
              </div>
            )}
          </section>

          <section className="card stack-sm" data-testid="dc-rights">
            <h2 className="small-h">{t(lang, "q_rights")}</h2>
            {data.rights.length === 0 ? <p className="small muted">{t(lang, "rights_none")}</p> : (
              <ul className="plain stack-sm">
                {data.rights.map((r, i) => (
                  <li key={i} className="rulebox">
                    <strong>{tc(lang, "k_", r.kind)}</strong> · {tc(lang, "stage_", r.stage)}
                    {r.estimated_refund_paise > 0 && <> · {rupees(r.estimated_refund_paise)}{r.if_approved ? ` (${t(lang, "if_approved_short")})` : ""}</>}
                    {r.deadline && <div className="tiny">{t(lang, "deadline")}: {dayTime(r.deadline)}</div>}
                    {r.rule_id && <div className="tiny muted detail-only">{t(lang, "rule")}: <span className="mono">{r.rule_id}</span>{r.legal_status ? ` · ${tc(lang, "st_", r.legal_status)}` : ""}</div>}
                  </li>
                ))}
              </ul>
            )}
            <button className="secondary" onClick={() => go(`wallet/${id}`)}>{t(lang, "act_open_wallet")}</button>
          </section>

          <button className="secondary" onClick={() => go(`copilot/${id}`)}>💬 {t(lang, "nav_copilot")}</button>
          <p className="tiny muted">{t(lang, "conf_heuristic")}</p>
        </div>
      </div>
    </div>
  );
}
