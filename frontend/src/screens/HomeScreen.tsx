import { useState } from "react";
import { api, type Lang } from "../api";
import { JourneyCard } from "../components/JourneyCard";
import { dayTime } from "../format";
import { t } from "../i18n";
import { activity, myJourneys } from "../myJourneys";
import { go } from "../router";
import { useLoad } from "../useLoad";
import { AddJourney, MAIN_DEMO } from "./AddJourney";

const ATTENTION = new Set(["NOW", "SOON", "WATCH", "UNKNOWN"]);

// Home dashboard: welcome, the main demo, journeys on this device, what needs attention,
// a question box for the Copilot, the add-journey form and recent activity.
// Note: no role="alert"/"status" here except the PNR form error, so screen readers hear one message.
export function HomeScreen({ lang }: { lang: Lang }) {
  const ids = myJourneys.list();
  const dash = useLoad(() => (ids.length ? api.dashboard(ids) : Promise.resolve({ journeys: [] })), [ids.join(",")], 15000);
  const [q, setQ] = useState("");
  const [hint, setHint] = useState<string | null>(null);
  const list = dash.data?.journeys ?? [];
  const attention = list.filter((d) => ATTENTION.has(d.urgency.level));
  const nextDep = list.map((d) => d.next_departure?.expected).filter(Boolean).sort()[0] as string | undefined;
  const acts = activity.list();

  function ask() {
    const target = ids[0];
    if (!target) { setHint(t(lang, "ask_need_journey")); return; }
    if (q.trim()) { try { window.sessionStorage.setItem("aglaKadam.pendingQ", q.trim().slice(0, 500)); } catch { /* ignore */ } }
    go(`copilot/${target}`);
  }

  return (
    <div className="stack">
      <section className="welcome">
        <h1>{t(lang, "app_name")}</h1>
        <p>{t(lang, "hello")}</p>
        <p className="small">{t(lang, "hello_sub")}</p>
        <div className="row-gap">
          <button className="cta" data-testid="demo-main" onClick={() => go(`journey/${MAIN_DEMO}`)}>▶ {t(lang, "try_demo")}</button>
        </div>
        <p className="small">{t(lang, "main_demo")}</p>
        {list.length > 0 && (
          <div className="kpis" aria-label={t(lang, "journey_health")}>
            <div className="kpi"><b data-testid="kpi-tracked">{list.length}</b><span>{t(lang, "kpi_tracked")}</span></div>
            <div className="kpi"><b data-testid="kpi-attention">{attention.length}</b><span>{t(lang, "kpi_disrupted")}</span></div>
            <div className="kpi"><b>{nextDep ? dayTime(nextDep) : "—"}</b><span>{t(lang, "kpi_next")}</span></div>
          </div>
        )}
        <span className="rail" aria-hidden />
      </section>

      <div className="grid-2">
        <div className="stack">
          <section className="stack-sm" aria-labelledby="h-attn">
            <div className="row-between">
              <h2 id="h-attn" className="small-h">{t(lang, "active_disruptions")}</h2>
              {list.length > 0 && <button className="link" onClick={() => go("journeys")}>{t(lang, "see_all")}</button>}
            </div>
            {list.length === 0 ? (
              <div className="empty" data-testid="home-empty">
                <div className="big-ico" aria-hidden>🚆</div>
                <strong>{t(lang, "empty_title")}</strong>
                <p className="small muted">{t(lang, "empty_text")}</p>
              </div>
            ) : attention.length === 0 ? (
              <p className="card small">{t(lang, "no_disruptions")}</p>
            ) : (
              attention.slice(0, 3).map((d) => <JourneyCard key={d.journey.id} d={d} lang={lang} />)
            )}
          </section>

          <section className="card stack-sm" aria-labelledby="h-ask">
            <h2 id="h-ask" className="small-h">{t(lang, "ask_title")}</h2>
            <form className="ask-box" onSubmit={(e) => { e.preventDefault(); ask(); }}>
              <label htmlFor="home-ask" className="sr-only">{t(lang, "cp_label")}</label>
              <input id="home-ask" data-testid="home-ask" maxLength={500} value={q} onChange={(e) => setQ(e.target.value)} placeholder={t(lang, "ask_hint")} />
              <button className="primary" type="submit" data-testid="home-ask-go">{t(lang, "ask_go")}</button>
            </form>
            {hint && <p className="small muted">{hint}</p>}
          </section>

          <section className="card stack-sm" aria-labelledby="h-recent">
            <h2 id="h-recent" className="small-h">{t(lang, "recent")}</h2>
            {acts.length === 0 ? <p className="small muted">{t(lang, "no_recent")}</p> : (
              <ul className="activity">
                {acts.map((a) => (
                  <li key={a.id + a.what}>
                    <button className="link" onClick={() => go(`journey/${a.id}`)}>{a.id.replace(/_/g, " ")}</button>
                    <span className="muted">{t(lang, "act_" + a.what)} · {dayTime(a.at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <AddJourney lang={lang} embedded />
      </div>
    </div>
  );
}
