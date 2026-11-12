import type { Lang } from "../api";
import { go } from "../router";
import { dayTime } from "../format";
import { t } from "../i18n";
import { useAssessment } from "../useAssessment";

// Screen 6: what happened and what to expect. Never says "refund guaranteed".
export function SummaryScreen({ id, lang }: { id: string; lang: Lang }) {
  const { data } = useAssessment(id, lang, "time", 10000);
  if (!data) return <p className="muted">…</p>;
  const last = data.actions[data.actions.length - 1];
  const text = last ? `${t(lang, "you_chose")}: ${last.plan_kind} · ${t(lang, "at")} ${dayTime(last.at)}` : "";

  async function share() {
    const msg = `${t(lang, "app_name")} — ${data!.journey.pnr_label}\n${text}\n${t(lang, "approval_note")}`;
    try {
      if ((navigator as any).share) await (navigator as any).share({ text: msg });
      else await navigator.clipboard.writeText(msg);
    } catch { /* user cancelled */ }
  }

  return (
    <div className="stack">
      <h1>{t(lang, "summary")}</h1>
      <section className="card stack" data-testid="summary">
        <p>{t(lang, "kept_case")}</p>
        {last && <p><strong>{text}</strong></p>}
        <p className="note">{t(lang, "approval_note")}</p>
        <p className="safety small">{t(lang, "safety")}</p>
      </section>
      <div className="row-gap">
        <button className="secondary" onClick={share}>{t(lang, "share")}</button>
        <button className="primary" onClick={() => go("")}>{t(lang, "start_over")}</button>
      </div>
    </div>
  );
}
