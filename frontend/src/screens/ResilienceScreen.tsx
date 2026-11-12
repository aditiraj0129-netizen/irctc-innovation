import { api, type Lang } from "../api";
import { SectionNav } from "../components/SectionNav";
import { t, tc } from "../i18n";
import { useLoad } from "../useLoad";

// Journey Resilience Score: experimental and fully transparent (every factor and weight shown).
export function ResilienceScreen({ id, lang }: { id: string; lang: Lang }) {
  const { data, error } = useLoad(() => api.resilience(id), [id], 5000);
  if (error && !data) return <p className="error" role="alert">{t(lang, "err_network")}</p>;
  if (!data) return <p className="muted">…</p>;
  return (
    <div className="stack">
      <h1>{t(lang, "res_title")}</h1>
      <SectionNav id={id} lang={lang} active="more" />
      <section className="card center">
        <span className="badge badge-amber" data-testid="res-label">{t(lang, "experimental")}</span>
        <p className="score" data-testid="res-score">{data.score}<span className="muted small">/100</span></p>
        <p className="small muted">{t(lang, "res_exp")}</p>
      </section>
      <ul className="plans">
        {data.factors.map((f) => (
          <li key={f.id} className="card stack-sm" data-testid={`factor-${f.id}`}>
            <div className="row-between"><strong>{tc(lang, "f_", f.id)}</strong><span className="small muted">{t(lang, "res_weight")} {f.weight}%</span></div>
            <div className="bar" role="meter" aria-valuenow={f.score} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${f.score}%` }} /></div>
            <p className="small muted">{f.value} · {f.score}/100</p>
          </li>
        ))}
      </ul>
      {data.main_risks.length > 0 && <p className="small"><strong>{t(lang, "res_risks")}:</strong> {data.main_risks.map((r) => tc(lang, "f_", r)).join(", ")}</p>}
      {data.suggestions.length > 0 && (
        <section className="note small"><strong>{t(lang, "res_tips")}</strong>
          <ul className="plain">{data.suggestions.map((s) => <li key={s}>→ {tc(lang, "tip_", s)}</li>)}</ul>
        </section>
      )}
    </div>
  );
}
