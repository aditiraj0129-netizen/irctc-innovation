import { useEffect, useState } from "react";
import { api, type Lang } from "../api";
import { dayTime, rupees } from "../format";
import { t } from "../i18n";
import { useAssessment } from "../useAssessment";

// Presenter panel: demo only. Moves the clock and injects SIMULATED events.
// Open the passenger view on a phone and this panel on a laptop.
export function Presenter({ lang }: { lang: Lang }) {
  const [scenarios, setScenarios] = useState<{ id: string; pnr: string; title: { en: string; hi: string } }[]>([]);
  const [sid, setSid] = useState("edge_three_hours");
  const [delay, setDelay] = useState(190);
  const { data, reload } = useAssessment(sid, lang, "time", 2000);

  useEffect(() => { api.scenarios().then(setScenarios); }, []);
  const legs = data?.journey.legs ?? [];
  const [train, setTrain] = useState<string>("");
  useEffect(() => { if (legs[0]) setTrain(legs[0].train_no); }, [sid, legs.length]);

  const [err, setErr] = useState("");
  async function run(p: Promise<unknown>) {
    try { await p; setErr(""); } catch (e) { setErr((e as Error).message); }
    await reload();
  }

  return (
    <div className="stack presenter">
      <h1>{t(lang, "presenter")}</h1>
      <DemoTokenBox />
      {err && <p className="error" role="alert" data-testid="presenter-error">{err}</p>}
      <label className="label" htmlFor="sc">Scenario</label>
      <select id="sc" value={sid} onChange={(e) => setSid(e.target.value)} data-testid="presenter-scenario">
        {scenarios.map((s) => <option key={s.id} value={s.id}>{s.title.en}</option>)}
      </select>
      <p className="small">Passenger view: <a href={`#/journey/${sid}`} target="_blank" rel="noreferrer">#/journey/{sid}</a></p>

      <section className="card stack">
        <p><strong>Clock:</strong> <span data-testid="presenter-clock">{data ? dayTime(data.now) : "…"}</span></p>
        <div className="row-gap">
          <button className="secondary" onClick={() => run(api.clock(sid, 15))}>+15 min</button>
          <button className="secondary" onClick={() => run(api.clock(sid, 60))}>+1 h</button>
          <button className="secondary" onClick={() => run(api.clock(sid, 240))}>+4 h</button>
          <button className="danger" onClick={() => run(api.reset(sid))} data-testid="presenter-reset">Reset scenario</button>
        </div>
      </section>

      <section className="card stack">
        <label className="label" htmlFor="tr">Train</label>
        <select id="tr" value={train} onChange={(e) => setTrain(e.target.value)}>
          {legs.map((l) => <option key={l.train_no} value={l.train_no}>{l.train_no} {l.train_name}</option>)}
        </select>
        <label className="label" htmlFor="dl">Delay: {delay} min</label>
        <input id="dl" type="range" min={0} max={360} step={5} value={delay} onChange={(e) => setDelay(+e.target.value)} data-testid="presenter-delay" />
        <div className="row-gap">
          <button className="primary" data-testid="presenter-apply-delay"
            onClick={() => run(api.event(sid, { train_no: train, type: "DELAY", delay_minutes: delay }))}>Send delay update</button>
          <button className="secondary" onClick={() => run(api.event(sid, { train_no: train, type: "CHART_PREPARED", chart_status: "WAITLISTED" }))}>Chart: still WL</button>
          <button className="secondary" onClick={() => run(api.event(sid, { train_no: train, type: "CHART_PREPARED", chart_status: "CONFIRMED" }))}>Chart: confirmed</button>
          <button className="secondary" onClick={() => run(api.event(sid, { train_no: train, type: "DEPARTED" }))}>Train departed</button>
          <button className="danger" onClick={() => run(api.event(sid, { train_no: train, type: "CANCELLED" }))}>Cancel train</button>
        </div>
      </section>

      {data && (
        <section className="card small">
          <p><strong>Situation:</strong> <span data-testid="presenter-situation">{data.situation.type}</span></p>
          <ol>{data.plans.map((p) => <li key={p.id}>{p.kind} · {rupees(p.money_back_paise)} · {p.deadline ? dayTime(p.deadline) : "—"}</li>)}</ol>
          <p><strong>Decision deadline:</strong> {data.rights_clock.decision_deadline ? dayTime(data.rights_clock.decision_deadline) : "—"}</p>
        </section>
      )}
    </div>
  );
}

// Only needed when the deployment sets DEMO_TOKEN. Stored for this tab only (sessionStorage).
function DemoTokenBox() {
  const [v, setV] = useState(() => { try { return window.sessionStorage.getItem("demoToken") ?? ""; } catch { return ""; } });
  return (
    <label className="label small">Presenter token (only if the server asks for one)
      <input type="password" value={v} autoComplete="off" data-testid="demo-token"
        onChange={(e) => { setV(e.target.value); try { window.sessionStorage.setItem("demoToken", e.target.value); } catch { /* ignore */ } }} />
    </label>
  );
}
