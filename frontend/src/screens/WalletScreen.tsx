import { api, type Lang, type WalletItem } from "../api";
import { SectionNav } from "../components/SectionNav";
import { dayTime, duration, rupees } from "../format";
import { t, tc } from "../i18n";
import { useLoad } from "../useLoad";

// Which status the passenger may set next. The backend checks this again and rejects anything else.
const NEXT: Record<string, string[]> = {
  ELIGIBLE_TO_FILE: ["FILED"], FILED: ["APPROVED", "REJECTED"],
  APPROVED: ["RECEIVED"], AUTOMATIC_DUE: ["RECEIVED"],
};

// Passenger Rights Wallet: estimate → eligible → filed → approved → received, kept clearly apart.
export function WalletScreen({ id, lang }: { id: string; lang: Lang }) {
  const { data, error, reload } = useLoad(() => api.wallet(id), [id], 5000);
  if (error && !data) return <p className="error" role="alert">{t(lang, "err_network")}</p>;
  if (!data) return <p className="muted">…</p>;

  const mark = async (item: WalletItem, status: string) => {
    try { await api.claim(id, item.id, status); } finally { reload(); }
  };

  return (
    <div className="stack">
      <h1>{t(lang, "wallet_title")}</h1>
      <SectionNav id={id} lang={lang} active="wallet" />
      <section className="card row-between">
        <div><p className="small muted">{t(lang, "wallet_paid")}</p><p className="big">{rupees(data.total_paid_paise)}</p></div>
        <div className="right"><p className="small muted">{t(lang, "wallet_best")}</p>
          <p className="amount" data-testid="wallet-best">{rupees(data.best_estimate_paise)}</p>
          {data.best_estimate_needs_approval && <p className="tiny">{t(lang, "if_approved")}</p>}
        </div>
      </section>
      <p className="safety small" data-testid="wallet-disclaimer">{t(lang, "wallet_disc")}</p>

      <ul className="plans">
        {data.items.map((it) => (
          <li key={it.id} className="card stack-sm" data-testid={`wallet-${it.kind}`}>
            <div className="row-between">
              <h3>{tc(lang, "k_", it.kind)}</h3>
              <span className={`pill stage-${it.stage}`} data-testid="stage">{tc(lang, "stage_", it.stage)}</span>
            </div>
            <p>
              <strong>{rupees(it.estimated_refund_paise)}</strong> {t(lang, "money_back")}
              {it.if_approved ? ` · ${t(lang, "if_approved")}` : ""} · <span className="muted small">{tc(lang, "stage_", "ESTIMATE")}</span>
            </p>
            {it.deadline && (
              <p className="small deadline">{t(lang, "act_by")} {dayTime(it.deadline)}
                {it.minutes_left != null ? ` · ${t(lang, "minutes_left", { m: duration(it.minutes_left, lang) })}` : ""}
                {it.deadline_unverified ? ` (${t(lang, "deadline_unverified")})` : ""}</p>
            )}
            {it.actions_needed.length > 0 && (
              <ul className="small plain">{it.actions_needed.map((a) => <li key={a}>→ {tc(lang, "an_", a)}</li>)}</ul>
            )}
            <details className="small" data-testid="rule-details">
              <summary>{t(lang, "rule")}: <span className="mono">{it.rule.rule_set_id ?? it.rule.rule_ids.join(", ")}</span>{" "}
                <span className={`badge ${it.rule.legal_status === "ANNOUNCED" ? "badge-amber" : "badge-blue"}`}>
                  {it.rule.legal_status === "ANNOUNCED" ? t(lang, "announced") : t(lang, "notified")}</span></summary>
              <dl className="facts">
                <div><dt>{t(lang, "rule_version")}</dt><dd>{it.rule.rule_version ?? "—"}</dd></div>
                <div><dt>{t(lang, "rule_effective")}</dt><dd>{it.rule.effective_from ?? "—"}</dd></div>
                <div><dt>{t(lang, "rule_applies")}</dt><dd>{it.rule.applies_to.join(", ") || "—"}</dd></div>
                <div><dt>{t(lang, "rule_source")}</dt><dd>{it.rule.source_url ? <a href={it.rule.source_url} target="_blank" rel="noreferrer">{it.rule.source_title}</a> : it.rule.source_title ?? "—"}</dd></div>
              </dl>
              {it.rule.unresolved.length > 0 && (
                <p className="con">{t(lang, "rule_unresolved")}: {it.rule.unresolved.map((u) => tc(lang, "un_", u)).join("; ")}</p>
              )}
            </details>
            {(NEXT[it.stage] ?? []).length > 0 && (
              <div className="row-gap">
                {NEXT[it.stage].map((s) => (
                  <button key={s} className="secondary" data-testid={`mark-${s}`} onClick={() => mark(it, s)}>{t(lang, "mark_" + s)}</button>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>

      <a className="btn primary" href={api.exportUrl(id)} download data-testid="wallet-export">{t(lang, "export")}</a>

      <section className="card">
        <h3>{t(lang, "history")}</h3>
        <ul className="small plain" data-testid="wallet-history">
          {data.history.map((h, i) => (
            <li key={i}>{dayTime(h.at)} · {tc(lang, "h_", h.kind)} · <span className="mono tiny">{summary(h.detail)}</span></li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function summary(d: Record<string, unknown>): string {
  return Object.entries(d).filter(([, v]) => v != null && v !== "SIMULATED").map(([k, v]) => `${k}=${v}`).join(", ");
}
