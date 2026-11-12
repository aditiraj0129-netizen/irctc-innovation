import { useState } from "react";
import { api, type Lang, type Outcome, type Priority } from "../api";
import { SectionNav } from "../components/SectionNav";
import { dayTime, duration, rupees, time } from "../format";
import { t, tc } from "../i18n";
import { useLoad } from "../useLoad";

// What-If Decision Simulator. Every number is calculated by the backend rules engine and planner.
export function WhatIfScreen({ id, lang }: { id: string; lang: Lang }) {
  const [priority, setPriority] = useState<Priority>("time");
  const [delay, setDelay] = useState(60);
  const [wait, setWait] = useState(30);
  const { data, error } = useLoad(() => api.whatif(id, priority, delay, wait), [id, priority, delay, wait]);

  return (
    <div className="stack">
      <h1>{t(lang, "whatif_title")}</h1>
      <SectionNav id={id} lang={lang} active="whatif" />
      <p className="note small">{t(lang, "whatif_help")}</p>

      <fieldset className="segmented seg-5" aria-label={t(lang, "priority")}>
        <legend className="small muted">{t(lang, "priority")}</legend>
        {(["time", "money", "risk", "transfers", "family"] as Priority[]).map((p) => (
          <button key={p} aria-pressed={priority === p} data-testid={`wi-priority-${p}`} onClick={() => setPriority(p)}>{t(lang, "p_" + p)}</button>
        ))}
      </fieldset>

      <label className="stack-sm">
        <span className="label">{t(lang, "delay_slider")}: {duration(delay, lang)}</span>
        <input type="range" min={15} max={300} step={15} value={delay} data-testid="delay-slider"
          onChange={(e) => setDelay(Number(e.target.value))} />
      </label>
      <label className="stack-sm">
        <span className="label">{t(lang, "wait_slider")}: {duration(wait, lang)}</span>
        <input type="range" min={15} max={480} step={15} value={wait} data-testid="wait-slider"
          onChange={(e) => setWait(Number(e.target.value))} />
      </label>

      {error && !data && <p className="error" role="alert">{t(lang, "err_network")}</p>}
      {data && (
        <ul className="plans" data-testid="whatif-outcomes">
          {data.outcomes.map((o) => <OutcomeCard key={o.id} o={o} lang={lang} delay={delay} wait={wait} />)}
        </ul>
      )}
    </div>
  );
}

function OutcomeCard({ o, lang, delay, wait }: { o: Outcome; lang: Lang; delay: number; wait: number }) {
  const title = o.id === "WAIT_30" ? `${t(lang, "sc_WAIT_30")} (${duration(wait, lang)})`
    : o.id === "DELAY_GROWS" ? `${t(lang, "sc_DELAY_GROWS")} (+${duration(delay, lang)})` : tc(lang, "sc_", o.id);
  if (!o.applicable) {
    return (
      <li className="card muted" data-testid={`wi-${o.id}`}>
        <h3>{title}</h3>
        <p className="small">{tc(lang, "na_", o.not_applicable_reason ?? "")}</p>
      </li>
    );
  }
  return (
    <li className="card stack-sm" data-testid={`wi-${o.id}`}>
      <div className="row-between">
        <h3>{title}</h3>
        <span className={`pill conf-${o.confidence}`}>{t(lang, "conf_" + o.confidence)}</span>
      </div>
      <dl className="facts small">
        <div><dt>{t(lang, "col_arrival")}</dt><dd>{o.travels ? dayTime(o.arrival) : t(lang, "not_travelling")}</dd></div>
        <div><dt>{t(lang, "col_vs_now")}</dt><dd>{o.arrival_diff_minutes != null ? `+${duration(o.arrival_diff_minutes, lang)}` : "—"}</dd></div>
        <div><dt>{t(lang, "col_money")}</dt><dd data-testid="wi-money">
          {o.money_back_paise > 0 ? `${rupees(o.money_back_paise)} ${t(lang, "money_back")}${o.money_back_if_approved ? ` (${t(lang, "if_approved")})` : ""}`
            : o.money_lost_paise > 0 ? `${rupees(o.money_lost_paise)} ${t(lang, "lost")}` : t(lang, "nothing_lost")}
        </dd></div>
        <div><dt>{t(lang, "col_deadline")}</dt><dd>{o.deadline ? `${time(o.deadline)}${o.minutes_to_deadline != null ? ` · ${t(lang, "minutes_left", { m: duration(o.minutes_to_deadline, lang) })}` : ""}` : "—"}</dd></div>
        <div><dt>{t(lang, "col_changes")}</dt><dd>{o.changes}{o.connection_risk ? ` · ${tc(lang, "x_", o.connection_risk)}` : ""}</dd></div>
        <div><dt>{t(lang, "col_rules")}</dt><dd className="mono tiny">{o.rule_ids.join(", ") || "—"}</dd></div>
      </dl>
      {(o.pros.length > 0 || o.cons.length > 0) && (
        <ul className="small plain">
          {o.pros.map((p) => <li key={p} className="pro">✓ {tc(lang, "pc_", p)}</li>)}
          {o.cons.map((c) => <li key={c} className="con">! {tc(lang, "pc_", c)}</li>)}
        </ul>
      )}
      {o.lost_options.length > 0 && <p className="small con" data-testid="lost-options">{t(lang, "lost_opts")}: {o.lost_options.length}</p>}
      {o.assumptions.length > 0 && <p className="tiny muted">{o.assumptions.map((a) => tc(lang, "as_", a)).join(" · ")}</p>}
    </li>
  );
}
