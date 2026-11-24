import { useState } from "react";
import { api, type Lang, type Outcome, type Priority } from "../api";
import { SectionNav } from "../components/SectionNav";
import { dayTime, duration, rupees, time } from "../format";
import { t, tc } from "../i18n";
import { useLoad } from "../useLoad";
import { go } from "../router";

// What-If Decision Simulator. Every number is calculated by the backend rules engine and planner.
export function WhatIfScreen({ id, lang }: { id: string; lang: Lang }) {
  const [priority, setPriority] = useState<Priority>("time");
  const [delay, setDelay] = useState(60);
  const [wait, setWait] = useState(30);
  const { data, error } = useLoad(() => api.whatif(id, priority, delay, wait), [id, priority, delay, wait]);
  const [picked, setPicked] = useState<string[]>([]);
  const usable = data?.outcomes.filter((o) => o.applicable) ?? [];
  // Default comparison: the first two outcomes that apply. The person can change it.
  const chosen = (picked.length ? picked : usable.slice(0, 2).map((o) => o.id))
    .map((pid) => usable.find((o) => o.id === pid)).filter(Boolean) as Outcome[];
  const toggle = (pid: string) => {
    const cur = picked.length ? picked : chosen.map((o) => o.id);
    setPicked(cur.includes(pid) ? cur.filter((x) => x !== pid) : [...cur, pid].slice(-2));
  };
  const titleOf = (o: Outcome) => o.id === "WAIT_30" ? `${t(lang, "sc_WAIT_30")} (${duration(wait, lang)})`
    : o.id === "DELAY_GROWS" ? `${t(lang, "sc_DELAY_GROWS")} (+${duration(delay, lang)})` : tc(lang, "sc_", o.id);

  return (
    <div className="stack">
      <h1>{t(lang, "whatif_title")}</h1>
      <SectionNav id={id} lang={lang} active="whatif" />
      <p className="note small">{t(lang, "whatif_help")}</p>
      <button className="primary cta" data-testid="whatif-to-decide" onClick={() => go(`decide/${id}`)}>{t(lang, "dz_whatif_link")} →</button>

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
      {chosen.length === 2 && <Compare a={chosen[0]} b={chosen[1]} lang={lang} titleOf={titleOf} />}
      {data && (
        <ul className="plans" data-testid="whatif-outcomes">
          {data.outcomes.map((o) => (
            <OutcomeCard key={o.id} o={o} lang={lang} delay={delay} wait={wait}
              picked={chosen.some((c) => c.id === o.id)} onPick={() => toggle(o.id)} />
          ))}
        </ul>
      )}
    </div>
  );
}

// Two outcomes side by side, row by row. Every value is from the backend; nothing is invented here.
function Compare({ a, b, lang, titleOf }: { a: Outcome; b: Outcome; lang: Lang; titleOf: (o: Outcome) => string }) {
  const money = (o: Outcome) => o.money_back_paise > 0 ? `${rupees(o.money_back_paise)} ${t(lang, "money_back")}${o.money_back_if_approved ? ` (${t(lang, "if_approved")})` : ""}`
    : o.money_lost_paise > 0 ? `${rupees(o.money_lost_paise)} ${t(lang, "lost")}` : t(lang, "nothing_lost");
  const rows: [string, (o: Outcome) => string][] = [
    ["col_arrival", (o) => o.travels ? dayTime(o.arrival) : t(lang, "not_travelling")],
    ["wi_extra", (o) => o.arrival_diff_minutes != null ? `+${duration(o.arrival_diff_minutes, lang)}` : t(lang, "wi_none")],
    ["wi_cost", money],
    ["col_deadline", (o) => o.deadline ? time(o.deadline) : t(lang, "wi_none")],
    ["wi_risk", (o) => o.connection_risk ? tc(lang, "x_", o.connection_risk) : t(lang, "wi_none")],
    ["wi_rights", (o) => o.rule_ids.join(", ") || t(lang, "wi_none")],
    ["wi_conf", (o) => t(lang, "conf_" + o.confidence)],
  ];
  return (
    <section className="card stack-sm" data-testid="wi-compare" aria-labelledby="wi-cmp-h">
      <h2 id="wi-cmp-h" className="small-h">{t(lang, "wi_compare")}</h2>
      <table className="cmp-table small">
        <thead><tr><th scope="col"><span className="sr-only">{t(lang, "wi_compare")}</span></th><th scope="col">{titleOf(a)}</th><th scope="col">{titleOf(b)}</th></tr></thead>
        <tbody>
          {rows.map(([k, f]) => (
            <tr key={k}><th scope="row">{t(lang, k)}</th><td>{f(a)}</td><td>{f(b)}</td></tr>
          ))}
        </tbody>
      </table>
      {(a.needs_new_ticket || b.needs_new_ticket) && <p className="tiny muted">{t(lang, "wi_new_ticket")}</p>}
      <p className="tiny muted">{t(lang, "wi_heuristic")}</p>
    </section>
  );
}

function OutcomeCard({ o, lang, delay, wait, picked, onPick }: { o: Outcome; lang: Lang; delay: number; wait: number; picked: boolean; onPick: () => void }) {
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
    <li className={`card stack-sm ${picked ? "compare-card picked" : ""}`} data-testid={`wi-${o.id}`}>
      <div className="row-between">
        <h3>{title}</h3>
        <span className={`pill conf-${o.confidence}`}>{t(lang, "conf_" + o.confidence)}</span>
      </div>
      <button className="link small" aria-pressed={picked} data-testid={`wi-pick-${o.id}`} onClick={onPick}>
        {picked ? `✓ ${t(lang, "wi_picked")}` : t(lang, "wi_pick")}
      </button>
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
