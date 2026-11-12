import type { Lang, Plan, Recommendation } from "../api";
import { duration, rupees } from "../format";
import { t, tc } from "../i18n";

// Why the first option is first, compared with the rest, and what changes if things change.
// Counterfactuals come only from scenarios the backend actually calculated.
export function RecommendationBox({ rec, plans, lang }: { rec: Recommendation; plans: Plan[]; lang: Lang }) {
  const rank = (pid: string) => plans.find((p) => p.id === pid)?.rank ?? "?";
  return (
    <section className="card rec stack-sm" data-testid="recommendation">
      <h3>{t(lang, "rec_why")}</h3>
      <ul className="why-list small">{rec.why.map((w) => <li key={w}>{tc(lang, "why_", w)}</li>)}</ul>
      {rec.comparisons.length > 0 && (
        <>
          <p className="label">{t(lang, "rec_vs")}</p>
          <ul className="small plain">
            {rec.comparisons.slice(0, 3).map((c) => (
              <li key={c.plan_id}>
                {t(lang, "cmp_line", {
                  n: String(rank(c.plan_id)),
                  points: c.points.map((p) => tc(lang, "why_", p)).join(", ") +
                    (c.arrival_diff_minutes ? ` (${duration(c.arrival_diff_minutes, lang)})` : "") +
                    (c.money_diff_paise ? ` (${rupees(Math.abs(c.money_diff_paise))})` : ""),
                })}
              </li>
            ))}
          </ul>
        </>
      )}
      {rec.counterfactuals.length > 0 && (
        <>
          <p className="label">{t(lang, "rec_if")}</p>
          <ul className="small plain" data-testid="counterfactuals">
            {rec.counterfactuals.map((c) => (
              <li key={c.scenario}>
                {t(lang, "cf_" + c.scenario, { w: String(c.detail.wait_minutes ?? ""), d: String(c.detail.extra_delay_minutes ?? "") })}: {tc(lang, "cf_", c.effect)}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
