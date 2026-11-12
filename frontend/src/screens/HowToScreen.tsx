import { useState } from "react";
import { api, type Lang } from "../api";
import { go } from "../router";
import { rupees, time } from "../format";
import { stepsFor, t } from "../i18n";
import { useAssessment } from "../useAssessment";

// Screen 5: the official steps. We never file, cancel or log in for the passenger.
export function HowToScreen({ id, planId, lang }: { id: string; planId: string; lang: Lang }) {
  const { data, error } = useAssessment(id, lang);
  const [busy, setBusy] = useState(false);
  if (error && !data) return <p className="error" role="alert">{t(lang, "err_network")}</p>;
  if (!data) return <p className="muted">…</p>;
  const plan = data.plans.find((p) => p.id === planId);
  if (!plan) {
    return (
      <div className="stack">
        <p className="alert alert-grey">{t(lang, "s_STALE_DATA")}</p>
        <button className="secondary" onClick={() => go(`options/${id}`)}>← {t(lang, "back")}</button>
      </div>
    );
  }

  async function done() {
    setBusy(true);
    try { await api.action(id, plan!); go(`summary/${id}`); } finally { setBusy(false); }
  }

  return (
    <div className="stack">
      <button className="link" onClick={() => go(`options/${id}`)}>← {t(lang, "back")}</button>
      <h1>{t(lang, "how_to")}</h1>
      <section className="card">
        <h3>{plan.explanation.headline}</h3>
        {plan.money_back_paise > 0 && (
          <p><span className="amount">{rupees(plan.money_back_paise)}</span> {t(lang, "money_back")}{plan.money_back_if_approved ? ` · ${t(lang, "if_approved")}` : ""}</p>
        )}
        {plan.deadline && <p className="deadline-banner"><strong>{t(lang, "act_by")} {time(plan.deadline)}</strong></p>}
      </section>

      <ol className="steps card" data-testid="steps">
        {stepsFor(lang, plan.kind).map((s, i) => <li key={i}>{s}</li>)}
      </ol>

      {plan.money_back_if_approved && <p className="note">{t(lang, "approval_note")}</p>}
      {plan.warnings.map((w) => <p key={w} className="note small">{t(lang, "warn_" + w)}</p>)}

      {plan.decisions.map((d, i) => (
        <section key={i} className="card small source">
          <p><strong>{t(lang, "rule")}:</strong> {d.rule_ids.join(", ")} · {d.legal_status === "ANNOUNCED" ? t(lang, "announced") : t(lang, "notified")}</p>
          <p><strong>{t(lang, "source")}:</strong> {d.source_url ? <a href={d.source_url} target="_blank" rel="noreferrer">{d.source_title}</a> : d.source_title}</p>
          <p><strong>{t(lang, "verified_on")}:</strong> {d.last_verified ?? t(lang, "not_verified")}</p>
          {d.warnings.filter((w) => !plan.warnings.includes(w)).map((w) => <p key={w} className="muted">{t(lang, "warn_" + w)}</p>)}
        </section>
      ))}

      <p className="safety small" role="note">{t(lang, "safety")}</p>

      <div className="row-gap">
        <a className="secondary btn" href="https://www.irctc.co.in" target="_blank" rel="noreferrer">{t(lang, "open_irctc")} ↗</a>
        <button className="primary" disabled={busy} onClick={done} data-testid="done">{t(lang, "done")}</button>
      </div>
    </div>
  );
}
