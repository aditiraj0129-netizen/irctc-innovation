import type { Lang, Twin } from "../api";
import { dayTime, duration } from "../format";
import { t, tc } from "../i18n";

const TONE: Record<string, string> = { ON_TRACK: "green", COMPLETED: "green", DISRUPTED: "amber", BROKEN: "red" };
const XTONE: Record<string, string> = { COMFORTABLE: "green", TIGHT: "amber", HIGH_RISK: "red", NOT_FEASIBLE: "red" };

// Journey Digital Twin: every leg, every change of train, how fresh each fact is.
export function TwinPanel({ twin, lang }: { twin: Twin; lang: Lang }) {
  return (
    <section className="card stack-sm" data-testid="twin">
      <div className="row-between">
        <h2>{t(lang, "twin_title")}</h2>
        <span className={`pill pill-${TONE[twin.status]}`} data-testid="twin-status">{tc(lang, "twin_", twin.status)}</span>
      </div>
      <ol className="twin-list">
        {twin.legs.map((leg, i) => {
          const x = twin.transfers.find((tr) => tr.from_seq === leg.seq);
          return (
            <li key={leg.seq}>
              <div className="twin-leg">
                <span className={`dot dot-${leg.affected ? "amber" : "green"}`} aria-hidden />
                <div className="grow">
                  <div className="row-between">
                    <strong>{leg.train_no} {leg.from_stn} → {leg.to_stn}</strong>
                    <span className="pill pill-soft" data-testid={`leg-state-${i + 1}`}>{tc(lang, "st_", leg.state)}</span>
                  </div>
                  <p className="small muted">
                    {dayTime(leg.expected_departure)} → {dayTime(leg.expected_arrival)}
                    {leg.delay_minutes > 0 ? ` · +${duration(leg.delay_minutes, lang)}` : ""}
                    {" · "}{tc(lang, "fr_", leg.info.freshness)}{leg.info.age_minutes != null ? ` (${duration(leg.info.age_minutes, lang)})` : ""}
                  </p>
                </div>
              </div>
              {x && (
                <div className={`transfer transfer-${XTONE[x.check.cls]}`} data-testid="transfer">
                  <strong>{tc(lang, "x_", x.check.cls)}</strong> · {x.check.station}
                  <div className="small">
                    {t(lang, "x_detail", { gap: duration(x.check.gap_minutes, lang), req: duration(x.check.required_minutes, lang), margin: duration(x.check.margin_minutes, lang) })}
                  </div>
                  <div className="small muted">{t(lang, "latest_safe")}: {dayTime(x.latest_safe_arrival)}</div>
                </div>
              )}
            </li>
          );
        })}
      </ol>
      <dl className="facts small">
        <div><dt>{t(lang, "final_arrival")}</dt><dd>{twin.expected_final_arrival ? dayTime(twin.expected_final_arrival) : "—"}</dd></div>
        <div><dt>{t(lang, "delay_dest")}</dt><dd>{twin.delay_at_destination_minutes != null ? duration(twin.delay_at_destination_minutes, lang) : "—"}</dd></div>
      </dl>
      {twin.transfers.length > 0 && <p className="tiny muted">{t(lang, "est_label")}</p>}
    </section>
  );
}
