import { useState } from "react";
import type { Lang, Plan, Priority } from "../api";
import { go } from "../router";
import { RightsClock } from "../components/RightsClock";
import { dayTime, duration, rupees, time } from "../format";
import { t } from "../i18n";
import { useAssessment } from "../useAssessment";
import { SectionNav } from "../components/SectionNav";
import { RecommendationBox } from "../components/RecommendationBox";
import { tc } from "../i18n";

// Screen 4: ranked plans + the Rights Clock. Every amount here comes from the rules engine.
export function OptionsScreen({ id, lang }: { id: string; lang: Lang }) {
  const [priority, setPriority] = useState<Priority>("time");
  const { data, error } = useAssessment(id, lang, priority);
  if (error && !data) return <p className="error" role="alert">{t(lang, "err_network")}</p>;
  if (!data) return <p className="muted">…</p>;

  return (
    <div className="stack">
      <button className="link" onClick={() => go(`journey/${id}`)}>← {t(lang, "back")}</button>
      <h1>{t(lang, "your_options")}</h1>
      <SectionNav id={id} lang={lang} active="options" />
      <p className="muted small">{t(lang, "s_" + data.situation.type, {
        station: data.journey.legs.find((l) => l.to.code === data.situation.detail?.station)?.to[lang] ?? data.situation.detail?.station ?? "",
      })}</p>

      <fieldset className="segmented" aria-label={t(lang, "priority")}>
        <legend className="small muted">{t(lang, "priority")}</legend>
        {(["time", "money", "risk", "transfers"] as Priority[]).map((p) => (
          <button key={p} aria-pressed={priority === p} data-testid={`priority-${p}`} onClick={() => setPriority(p)}>
            {t(lang, "p_" + p)}
          </button>
        ))}
      </fieldset>

      <RightsClock clock={data.rights_clock} lang={lang} />

      {data.recommendation && <RecommendationBox rec={data.recommendation} plans={data.plans} lang={lang} />}

      <ol className="plans" data-testid="plans">
        {data.plans.map((p) => <PlanCard key={p.id} plan={p} lang={lang} onOpen={() => go(`howto/${id}/${p.id}`)} />)}
      </ol>
    </div>
  );
}

function PlanCard({ plan, lang, onOpen }: { plan: Plan; lang: Lang; onOpen: () => void }) {
  const top = plan.rank === 1;
  const d = plan.decisions[0];
  return (
    <li className={`card plan ${top ? "plan-top" : ""}`} data-testid={`plan-${plan.kind}`}>
      <div className="row-between">
        <span className="rank">#{plan.rank}</span>
        <span className={`pill cert-${plan.certainty}`}>{t(lang, "c_" + plan.certainty)}</span>
      </div>
      <h3>{plan.explanation.headline}</h3>

      <div className="money">
        {plan.money_back_paise > 0 ? (
          <>
            <span className="amount" data-testid="amount">{rupees(plan.money_back_paise)}</span>
            <span> {t(lang, "money_back")}{plan.money_back_if_approved ? ` · ${t(lang, "if_approved")}` : ""}</span>
          </>
        ) : plan.money_lost_paise > 0 ? (
          <span className="amount lost">{rupees(plan.money_lost_paise)} {t(lang, "lost")}</span>
        ) : (
          <span className="amount ok">{t(lang, "nothing_lost")}</span>
        )}
        {plan.needs_new_ticket && <div className="small muted">{t(lang, "new_ticket")}</div>}
      </div>

      <p>{plan.explanation.body}</p>

      <dl className="facts small">
        <div><dt>{t(lang, "arrive")}</dt><dd>{plan.travels ? dayTime(plan.arrival) : t(lang, "not_travelling")}</dd></div>
        {plan.deadline && (
          <div><dt>{t(lang, "act_by")}</dt><dd className="deadline">{time(plan.deadline)}{plan.deadline_unverified ? ` (${t(lang, "deadline_unverified")})` : ""}</dd></div>
        )}
      </dl>

      {plan.rides.length > 0 && (
        <ul className="rides small">
          {plan.rides.map((r) => <li key={r.train_no + r.dep}>{r.train_no} {r.train_name}: {r.from_stn} {time(r.dep)} → {r.to_stn} {dayTime(r.arr)}</li>)}
        </ul>
      )}

      {plan.transfers && plan.transfers.length > 0 && (
        <p className="small row-gap" data-testid="transfer-badges">
          {plan.transfers.map((x) => (
            <span key={x.station + x.arrive} className={`badge xb-${x.cls}`}>{tc(lang, "x_", x.cls)} · {x.station} · {duration(x.margin_minutes, lang)}</span>
          ))}
        </p>
      )}

      {top && plan.reasons.length > 0 && (
        <div className="why small">
          <strong>{t(lang, "why_first")}:</strong>
          <ul>
            {plan.reasons.map((r, i) => (
              <li key={i}>{t(lang, "r_" + r.key, { m: r.minutes ? duration(r.minutes, lang) : "", amt: r.paise ? rupees(r.paise) : "" })}</li>
            ))}
          </ul>
        </div>
      )}

      {d && (
        <p className="rule small">
          <span className={`badge ${d.legal_status === "ANNOUNCED" ? "badge-amber" : "badge-blue"}`}>
            {d.legal_status === "ANNOUNCED" ? t(lang, "announced") : t(lang, "notified")}
          </span>{" "}
          {t(lang, "rule")}: {d.rule_ids.join(", ")}
        </p>
      )}

      <button className={top ? "primary" : "secondary"} onClick={onOpen} data-testid={`open-${plan.id}`}>{t(lang, "how_to")} →</button>
    </li>
  );
}
