import { useState } from "react";
import { decideApi, type DecisionCard, type DecisionView, type Lang, type MoneyRow, type Priority } from "../api";
import { JourneyHeader } from "../components/JourneyHeader";
import { SectionNav } from "../components/SectionNav";
import { dayTime, duration, rupees, time } from "../format";
import { t, tc } from "../i18n";
import { useLoad } from "../useLoad";

type Names = Record<string, { en: string; hi: string }>;

// PREDICT -> DECIDE -> RECOVER. One screen that answers: what is happening, what may happen next, how sure we
// are, what each option means and costs, and what to do now. Every number comes from the backend engines.
export function DecideScreen({ id, lang }: { id: string; lang: Lang }) {
  const [priority, setPriority] = useState<Priority>("time");
  const { data, error } = useLoad(() => decideApi.decision(id, priority), [id, priority], 5000);
  if (error && !data) return <p className="error" role="alert">{t(lang, "err_network")}</p>;
  if (!data) return <p className="muted" aria-busy="true">…</p>;
  const names: Names = {};
  data.journey.legs.forEach((l) => { names[l.from.code] = l.from; names[l.to.code] = l.to; });
  const stn = (c?: string | null) => (c ? names[c]?.[lang] ?? STN_EXTRA[c]?.[lang] ?? c : "");

  return (
    <div className="stack">
      <JourneyHeader j={data.journey} lang={lang} title={t(lang, "dz_title")} />
      <SectionNav id={id} lang={lang} active="decide" />
      <p className="small muted">{t(lang, "dz_sub")}</p>
      <Header d={data} lang={lang} stn={stn} />
      <Recommendation d={data} lang={lang} stn={stn} />

      <fieldset className="segmented" aria-label={t(lang, "priority")}>
        <legend className="small muted">{t(lang, "priority")}</legend>
        {(["time", "money", "risk", "transfers"] as Priority[]).map((p) => (
          <button key={p} aria-pressed={priority === p} data-testid={`dz-priority-${p}`} onClick={() => setPriority(p)}>{t(lang, "p_" + p)}</button>
        ))}
      </fieldset>

      <section aria-labelledby="dz-opts" className="stack">
        <h2 id="dz-opts">{t(lang, "dz_options")}</h2>
        <div className="dz-cards">
          {data.cards.map((c) => <OptionCard key={c.key} c={c} lang={lang} stn={stn} />)}
        </div>
      </section>

      <div className="grid-2">
        <Money rows={data.money} lang={lang} />
        <div className="stack">
          <Prediction d={data} lang={lang} stn={stn} />
          <Claims claims={data.claims} lang={lang} />
        </div>
      </div>
      <p className="tiny muted" data-testid="dz-disclaimer">{t(lang, "dz_disc")} {data.data_label}</p>
    </div>
  );
}

const STN_EXTRA: Names = { NZM: { en: "Hazrat Nizamuddin", hi: "हज़रत निज़ामुद्दीन" }, UMB: { en: "Ambala Cantt", hi: "अंबाला कैंट" },
  AGC: { en: "Agra Cantt", hi: "आगरा कैंट" }, JHS: { en: "Jhansi Jn", hi: "झाँसी जं." } };
const LV: Record<string, string> = { CONNECTION_BROKEN: "NOW", CONNECTION_AT_RISK: "SOON", CONNECTION_TIGHT: "WATCH",
  CONNECTION_UNKNOWN: "UNKNOWN", TRAIN_LATE: "WATCH", TRAIN_CANCELLED: "NOW", NOT_CONFIRMED: "NOW", STALE: "UNKNOWN",
  ON_TRACK: "NONE", CONNECTION_OK: "NONE", JOURNEY_OVER: "NONE" };
const mins = (m: number | null | undefined, lang: Lang) => (m == null ? "—" : m < 0 ? `−${duration(-m, lang)}` : duration(m, lang));

function Header({ d, lang, stn }: { d: DecisionView; lang: Lang; stn: (c?: string | null) => string }) {
  const h = d.header;
  const status: string = h.status ?? "ON_TRACK";
  return (
    <section className={`dc-head lv-${LV[status] ?? "NONE"}`} data-testid="dz-head" aria-labelledby="dz-h">
      <h2 id="dz-h" className="dz-headline">{t(lang, "hs_" + status)}</h2>
      <dl className="dz-facts">
        {h.first_train && (
          <div><dt>{t(lang, "h_first")}</dt>
            <dd><strong>{h.first_train}</strong> · {h.current_delay_minutes != null ? t(lang, "h_late", { m: String(h.current_delay_minutes) }) : t(lang, "h_not_running")}</dd></div>
        )}
        {h.first_train && (
          <div><dt>{t(lang, "h_expected", { stn: stn(h.arrival_station) })}</dt>
            <dd data-testid="dz-arrival">{h.arrival_early
              ? <>{t(lang, "h_range", { a: time(h.arrival_early), b: time(h.arrival_late) })} · {t(lang, "h_likely", { t: time(h.expected_arrival) })}</>
              : dayTime(h.scheduled_arrival)}</dd></div>
        )}
        {h.second_train && (
          <div><dt>{t(lang, "h_second")}</dt><dd><strong>{h.second_train}</strong> · {t(lang, "h_leaves", { t: time(h.next_departure) })}</dd></div>
        )}
        {h.second_train && (
          <div><dt>{t(lang, "h_available")}</dt><dd>{mins(h.time_available_minutes, lang)} · {t(lang, "h_need")} {mins(h.transfer_needed_minutes, lang)}</dd></div>
        )}
        {h.risk && <div><dt>{t(lang, "h_risk")}</dt><dd><span className={`risk risk-${h.risk}`} data-testid="dz-risk">{t(lang, "r_" + h.risk)}</span></dd></div>}
        {h.latest_data_at && (
          <div><dt>{t(lang, "h_fresh")}</dt><dd>{time(h.latest_data_at)} · {t(lang, "h_age", { m: String(h.data_age_minutes) })}
            {" "}<span className={`pill ${h.data_fresh ? "fresh-ok" : "fresh-stale"}`}>{t(lang, h.data_fresh ? "fresh_ok" : "fresh_stale")}</span></dd></div>
        )}
      </dl>
    </section>
  );
}

function Recommendation({ d, lang, stn }: { d: DecisionView; lang: Lang; stn: (c?: string | null) => string }) {
  const r = d.recommendation;
  const code: string = r.code;
  const lines: string[] = [];
  const opt = (o: any) => `${o.train} · ${dayTime(o.dep)} → ${dayTime(o.arr)}${o.from ? ` (${stn(o.from)})` : ""}`;
  if (code === "STAY_AND_WATCH" || code === "STAY_BUT_PREPARE") {
    lines.push(t(lang, "rec_" + code, { stn: stn(r.watch?.station), max: String(r.watch?.max_delay_minutes ?? "—"),
      backup: r.backup ? opt(r.backup) : "—" }));
    if (r.dont_cancel) lines.push(t(lang, "rec_dont_cancel", { cancel: rupees(r.dont_cancel.cancel_paise), tdr: rupees(r.dont_cancel.tdr_paise) }));
  } else if (code === "BOOK_ALTERNATIVE") {
    lines.push(t(lang, "rec_BOOK_ALTERNATIVE", { option: opt(r.option) }));
    if (r.tatkal) lines.push(t(lang, "rec_tatkal", { t: dayTime(r.tatkal.opens_at), state: t(lang, "tk_" + r.tatkal.state) }));
  } else if (code === "TRAVEL_AS_BOOKED") {
    lines.push(t(lang, "rec_TRAVEL_AS_BOOKED"));
    if (r.if_not_travelling?.decide_by) lines.push(t(lang, "rec_if_not", { by: dayTime(r.if_not_travelling.decide_by), amount: rupees(r.if_not_travelling.cancel_paise) }));
    if (r.if_not_travelling?.tdr_if_over_3h) lines.push(t(lang, "rec_tdr_3h"));
  } else if (code === "FILE_TDR_BEFORE_DEPARTURE") {
    lines.push(t(lang, code, { amount: rupees(r.claim?.paise ?? 0), by: r.claim?.deadline ? dayTime(r.claim.deadline) : "—" }));
  } else if (code === "AUTO_REFUND_FIND_TRAIN") {
    lines.push(t(lang, "rec_" + code, { amount: rupees(r.refund_paise ?? 0) }));
  } else {
    lines.push(t(lang, "rec_" + code));
  }
  if (r.claim?.code === "FILE_TDR_MISSED_CONNECTION") lines.push(t(lang, "rec_claim", { by: dayTime(r.claim.deadline), amount: rupees(r.claim.paise) }));
  if (r.claim?.code === "TDR_NOT_ELIGIBLE") lines.push(t(lang, "rec_claim_no", { reason: tc(lang, "mr_", r.claim.reason) }));
  return (
    <section className="card dz-rec" data-testid="dz-rec" aria-labelledby="dz-rec-h">
      <p id="dz-rec-h" className="eyebrow">{t(lang, "dz_rec")}</p>
      {lines.map((l, i) => <p key={i} className={i === 0 ? "dz-rec-main" : "small"}>{l}</p>)}
      {r.why?.length > 0 && <p className="tiny muted">{t(lang, "dz_why")}: {r.why.map((w: string) => tc(lang, "why_", w)).join(" · ")}</p>}
    </section>
  );
}

function OptionCard({ c, lang, stn }: { c: DecisionCard; lang: Lang; stn: (c?: string | null) => string }) {
  const o = c.outcome, m = c.money, n = c.next_action;
  const happens = (() => {
    if (o.code === "ARRIVE_AT" && o.early) return t(lang, "co_ARRIVE_AT", { a: time(o.early), b: time(o.late), m: time(o.expected) });
    if (o.code === "ARRIVE_AT") return t(lang, "co_ARRIVE_SIMPLE", { m: dayTime(o.expected) });
    if (o.code === "NOT_RUNNING_YET") return t(lang, "co_NOT_RUNNING_YET", { d: dayTime(o.departure) });
    if (o.code === "CANCEL_LEG") return t(lang, "co_CANCEL_LEG", { train: o.train, from: stn(o.from), to: stn(o.to), cls: o.class, status: o.status });
    return null;
  })();
  const money = (() => {
    if (!m.kind) return null;
    if (m.kind === "CANCELLATION_REFUND") return t(lang, "m_CANCELLATION_REFUND", { amount: rupees(m.paise), charge: rupees(m.charge_paise) });
    if (m.kind === "SAMPLE_FARE_NOT_REAL") return t(lang, "m_SAMPLE_FARE_NOT_REAL", { amount: rupees(m.paise ?? 0) });
    return t(lang, "m_" + m.kind);
  })();
  const next = n.code ? t(lang, "na_" + n.code, { stn: stn(n.station), max: String(n.max_delay ?? ""), train: n.train ?? "",
    tdr: rupees(n.tdr_paise ?? 0), cancel: rupees(n.cancel_paise ?? 0) }) : null;
  const trains = c.items.filter((x) => x.legs);
  const rules = c.items.find((x) => x.code === "RULES");
  const tdr = c.items.find((x) => x.code === "TDR_STATUS");
  return (
    <article className={`card dz-card ${c.recommended ? "dz-card-rec" : ""} st-card-${c.status}`} data-testid={`card-${c.key}`} aria-labelledby={`ck-${c.key}`}>
      <div className="row-between">
        <h3 id={`ck-${c.key}`}>{t(lang, "ck_" + c.key)}</h3>
        <span className="row-gap-sm">
          {c.recommended && <span className="urg urg-SOON" data-testid="card-recommended">{t(lang, "c_recommended")}</span>}
          <span className={`pill cs-${c.status}`} data-testid="card-status">{t(lang, "cs_" + c.status)}</span>
        </span>
      </div>
      <p className="small muted">{t(lang, "cm_" + c.meaning)}</p>
      {c.reason && <p className="small" data-testid="card-reason">{t(lang, "cr_" + c.reason)}</p>}
      {c.missing.length > 0 && <p className="small">{t(lang, "c_missing", { list: c.missing.map((x) => x.replace(/_/g, " ").toLowerCase()).join(", ") })}</p>}
      <dl className="facts small">
        {happens && <div><dt>{t(lang, "c_happens")}</dt><dd>{happens}{o.slack_expected != null && <><br />{t(lang, "co_slack", { e: mins(o.slack_early, lang), x: mins(o.slack_expected, lang), l: mins(o.slack_late, lang) })}</>}
          {o.refund_after_change_paise != null && <><br />{t(lang, "co_after_change", { t: dayTime(c.deadline), amount: rupees(o.refund_after_change_paise), m: String(o.minutes_left) })}</>}</dd></div>}
        {money && <div><dt>{t(lang, "c_money")}</dt><dd data-testid="card-money">{money}
          {m.legal_status === "ANNOUNCED" && <span className="pill cert-1"> {t(lang, "m_announced")}</span>}
          {m.rule_ids?.length > 0 && <span className="mono tiny detail-only"> · {t(lang, "m_rule", { rule: m.rule_ids[0] })}</span>}</dd></div>}
        {c.risk && <div><dt>{t(lang, "c_risk")}</dt><dd><span className={`risk risk-${c.risk}`}>{tc(lang, "r_", c.risk)}</span></dd></div>}
        {c.deadline && <div><dt>{c.deadline_kind ? t(lang, "dk_" + c.deadline_kind) : t(lang, "c_deadline")}</dt><dd>{dayTime(c.deadline)}</dd></div>}
      </dl>
      {tdr && tdr.eligibility !== "NOT_RELEVANT" && (
        <p className="small">TDR: {t(lang, "ce_" + tdr.eligibility)}{tdr.tdr_paise ? ` · ${rupees(tdr.tdr_paise)} (${t(lang, "mc_IF_APPROVED")})` : ""}{tdr.deadline ? ` · ${dayTime(tdr.deadline)}` : ""}</p>
      )}
      {trains.length > 0 && <Trains items={trains} lang={lang} stn={stn} />}
      {rules && <Rules r={rules} lang={lang} />}
      {next && <p className="dz-next" data-testid="card-next"><strong>{t(lang, "c_next")}:</strong> {next}</p>}
    </article>
  );
}

function Trains({ items, lang, stn }: { items: Record<string, any>[]; lang: Lang; stn: (c?: string | null) => string }) {
  return (
    <ol className="dz-trains small">
      {items.map((x) => {
        const train = x.legs.filter((l: any) => l.mode === "TRAIN" || l.mode === "BUS");
        const access = x.legs[0]?.mode === "ACCESS" && x.kind === "NEARBY_STATION" ? x.legs[0] : null;
        const first = train[0];
        return (
          <li key={x.id} data-testid="dz-option">
            <div className="row-between">
              <strong>{t(lang, "it_rank", { n: String(x.rank) })} {train.map((l: any) => l.train_no ?? l.name).join(" + ")}</strong>
              <span className="tiny">{x.transfers ? t(lang, "it_change", { n: String(x.transfers) }) : t(lang, "it_direct")} · {t(lang, "it_" + x.service)}</span>
            </div>
            <div>{first ? `${stn(first.from_stn)} ${dayTime(first.dep)}` : ""} → {dayTime(x.arrival)} ({duration(x.duration_minutes, lang)})</div>
            {access && <div className="tiny">{t(lang, "it_nearby", { stn: stn(access.to_stn), m: String(Math.round((Date.parse(access.arr) - Date.parse(access.dep)) / 60000)) })}</div>}
            {x.tatkal && <div className="tiny">{t(lang, "it_tatkal", { t: dayTime(x.tatkal.opens_at) })} ({t(lang, "tk_" + x.tatkal.state)})</div>}
            <div className="tiny muted">
              {x.fare_status === "SAMPLE_NOT_REAL" ? `${t(lang, "it_sample")} · ${rupees(x.fare_paise)}` : t(lang, "it_fare")} · {t(lang, "it_seats")} · {t(lang, "it_" + x.result_type)}
              {x.last_updated && <> · {t(lang, "it_src", { s: `${x.data_source}, ${time(x.last_updated)}` })}</>}
            </div>
            <details className="tiny detail-only"><summary>{t(lang, "it_why")}</summary>
              <ul className="plain">{x.score_parts.filter((p: any) => p.points || p.code.endsWith("UNKNOWN")).map((p: any, i: number) => (
                <li key={i}>{t(lang, "sp_" + p.code, { m: String(p.minutes ?? ""), n: String(p.count ?? ""), r: p.risk ? t(lang, "r_" + p.risk) : "" })} (+{p.points})</li>))}</ul>
            </details>
          </li>
        );
      })}
    </ol>
  );
}

function Rules({ r, lang }: { r: Record<string, any>; lang: Lang }) {
  const pre = r.id === "GUIDE-TATKAL" ? "tk_" : "ur_";
  return (
    <details className="small" data-testid={`rules-${r.id}`}>
      <summary>{t(lang, pre === "tk_" ? "tk_rules" : "ur_rules")}</summary>
      <ul className="plain">{(r.points as string[]).map((p) => <li key={p}>• {t(lang, pre + p)}</li>)}</ul>
    </details>
  );
}

function Money({ rows, lang }: { rows: MoneyRow[]; lang: Lang }) {
  return (
    <section className="card stack-sm" data-testid="dz-money" aria-labelledby="dz-money-h">
      <h2 id="dz-money-h" className="small-h">{t(lang, "dz_money")}</h2>
      <table className="cmp-table small">
        <thead><tr><th scope="col">{t(lang, "mt_action")}</th><th scope="col">{t(lang, "mt_back")}</th><th scope="col">{t(lang, "mt_next")}</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} data-testid={`money-${r.key}`}>
              <th scope="row">{t(lang, "mk_" + r.key, { t: r.at ? time(r.at) : "" })}
                {r.at && r.key !== "WAIT_UNTIL" && <div className="tiny muted">{dayTime(r.at)}</div>}</th>
              <td>{!r.applicable || (r.certainty === "NONE" && r.reason) ? <span className="muted">{tc(lang, "mr_", r.reason ?? "")}</span>
                : r.money_back_paise == null ? t(lang, "mc_UNKNOWN")
                : <>{rupees(r.money_back_paise)} <span className="tiny muted">({t(lang, "mc_" + r.certainty)})</span></>}
                {r.legal_status === "ANNOUNCED" && <div className="tiny">{t(lang, "m_announced")}</div>}
                {r.deadline && r.key === "KEEP_AND_CLAIM" && <div className="tiny">{t(lang, "c_deadline")}: {dayTime(r.deadline)}</div>}</td>
              <td>{t(lang, "ms_" + r.next_step)}<div className="tiny muted">{t(lang, "mto_" + r.travel_outcome)}</div></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function Prediction({ d, lang, stn }: { d: DecisionView; lang: Lang; stn: (c?: string | null) => string }) {
  const p = d.prediction;
  if (!p) return null;
  const cong = p.congestion;
  const counted = cong.checks.filter((c: any) => c.counted);
  const skipped = cong.checks.filter((c: any) => !c.counted);
  return (
    <section className="card stack-sm" data-testid="dz-prediction" aria-labelledby="dz-pred-h">
      <h2 id="dz-pred-h" className="small-h">{t(lang, "dz_pred")}</h2>
      <p><strong data-testid="dz-outlook">{t(lang, "out_" + p.outlook)}</strong> · <span className={`risk risk-${p.growth_risk}`}>{t(lang, "r_" + p.growth_risk)}</span></p>
      <dl className="facts small">
        <div><dt>{t(lang, "ev_trend")}</dt><dd>{t(lang, "tr_" + p.trend, { s: String(Math.abs(p.slope_min_per_hour ?? 0)) })}
          {p.observations.length > 0 && <div className="tiny muted">{t(lang, "ev_steps")}: {p.observations.map((o: any) => `${o.station ? stn(o.station) + " " : ""}${o.delay_minutes}m`).join(" → ")}</div>}</dd></div>
        <div><dt>{t(lang, "ev_cong")}</dt><dd data-testid="dz-congestion">{t(lang, "cg_" + (cong.level === "UNKNOWN" ? "NONE" : cong.level))}
          {counted.length > 0 && <div className="tiny">{t(lang, "cg_counted", { list: counted.map((c: any) => `${c.train_no} (+${c.its_delay_minutes}m)`).join(", ") })}</div>}
          {skipped.length > 0 && <div className="tiny muted">{t(lang, "cg_skipped", { list: skipped.map((c: any) => `${c.train_no}: ${t(lang, "cgr_" + c.reason)}`).join(", ") })}</div>}
          {(counted.length > 0 || skipped.length > 0) && <div className="tiny muted">{t(lang, "cg_note")}</div>}</dd></div>
        <div><dt>{t(lang, "ev_fog")}</dt><dd data-testid="dz-fog">{p.weather.status !== "OK" ? t(lang, "fog_unavailable")
          : p.weather.applied.length ? p.weather.applied.map((w: any) => t(lang, "fog_on", { sev: w.severity.toLowerCase(), sec: w.section, t: dayTime(w.valid_to), src: w.source })).join("; ")
          : t(lang, "fog_none")}
          {p.weather.ignored.filter((w: any) => w.reason === "EXPIRED").map((w: any) => <div key={w.id} className="tiny muted">{t(lang, "fog_expired", { id: w.id })}</div>)}</dd></div>
        <div><dt>{t(lang, "ev_recover")}</dt><dd>{t(lang, "ev_recover_v", { m: String(p.remaining.recovery_allowance_minutes), secs: p.remaining.sections.join(", ") || "—" })}</dd></div>
      </dl>
      <p className="tiny muted">{t(lang, "pred_quality", { q: t(lang, "q_" + p.quality) })}{p.missing_inputs.length > 0 && <> · {t(lang, "pred_missing", { list: p.missing_inputs.map((x: string) => x.replace(/_/g, " ").toLowerCase()).join(", ") })}</>}</p>
      <p className="tiny muted" data-testid="dz-no-prob">{t(lang, "no_prob")}</p>
    </section>
  );
}

function Claims({ claims, lang }: { claims: Record<string, any>; lang: Lang }) {
  const rows: [string, string][] = [
    ["cl_estimate", claims.cancellation_refund_estimate_paise != null ? rupees(claims.cancellation_refund_estimate_paise) : "—"],
    ["cl_elig", t(lang, "ce_" + claims.tdr_eligibility)], ["cl_sub", t(lang, "ce_" + claims.tdr_submission)],
    ["cl_appr", t(lang, "ce_" + claims.railway_approval)], ["cl_recv", t(lang, "ce_" + claims.refund_received)],
  ];
  return (
    <section className="card stack-sm" data-testid="dz-claims" aria-labelledby="dz-cl-h">
      <h2 id="dz-cl-h" className="small-h">{t(lang, "dz_claims")}</h2>
      <dl className="facts small">{rows.map(([k, v]) => <div key={k}><dt>{t(lang, k)}</dt><dd>{v}</dd></div>)}</dl>
    </section>
  );
}
