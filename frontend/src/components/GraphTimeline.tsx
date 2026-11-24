import type { JourneyGraph, Lang, Twin } from "../api";
import { duration, time } from "../format";
import { t, tc } from "../i18n";
import { type StationNames, traceSentence, traceTone } from "../trace";

const TONE: Record<string, string> = { ON_TRACK: "ON_TRACK", COMPLETED: "COMPLETED", DISRUPTED: "DISRUPTED", BROKEN: "BROKEN" };

// Journey Digital Twin as a connected timeline: stops (nodes), rides and changes of train (edges).
// Data comes from the backend graph (structure, buffers, propagation) and twin (leg states, freshness).
export function GraphTimeline({ graph, twin, lang, names }: { graph: JourneyGraph; twin: Twin; lang: Lang; names: StationNames }) {
  const stn = (c: string) => names[c]?.[lang] ?? c;
  const node = (id: string) => graph.nodes.find((n) => n.id === id)!;
  const legs = twin.legs;
  return (
    <section className="card stack" data-testid="twin" aria-labelledby="gt-title">
      <div className="row-between">
        <div>
          <h2 id="gt-title">{t(lang, "graph_title")}</h2>
          <p className="small muted detail-only">{t(lang, "graph_sub")}</p>
        </div>
        <span className={`status st-${TONE[twin.status]}`} data-testid="twin-status">{tc(lang, "twin_", twin.status)}</span>
      </div>

      <ol className="gt" aria-label={t(lang, "graph_title")}>
        {legs.map((leg, i) => {
          const dep = node(`L${leg.seq}:DEP`), arr = node(`L${leg.seq}:ARR`);
          const ride = graph.edges.find((e) => e.id === `L${leg.seq}:RIDE`)!;
          const xfer = graph.edges.find((e) => e.id === `T${leg.seq}-${leg.seq + 1}`);
          const tw = twin.transfers.find((x) => x.from_seq === leg.seq);
          return (
            <li key={leg.seq}>
              {i === 0 && <Stop lang={lang} name={stn(dep.station)} state={dep.state} sched={dep.scheduled} exp={dep.expected} delay={dep.delay_minutes} />}
              <div className="gt-seg">
                <span />
                <span className={`gt-line s-${ride.state}`} aria-hidden />
                <div className="gt-train">
                  <strong>{leg.train_no}</strong> {leg.train_name} ·{" "}
                  <span data-testid={`leg-state-${i + 1}`} className="pill pill-soft">{tc(lang, "st_", leg.state)}</span>
                  <span className="tiny muted detail-only"> · {tc(lang, "fr_", leg.info.freshness)}{leg.info.age_minutes != null ? ` (${duration(leg.info.age_minutes, lang)})` : ""}</span>
                </div>
              </div>
              <Stop lang={lang} name={stn(arr.station)} state={arr.state} sched={arr.scheduled} exp={arr.expected} delay={arr.delay_minutes} />
              {xfer && tw && (
                <div className="gt-seg">
                  <span />
                  <span className={`gt-line xfer s-${xfer.state}`} aria-hidden />
                  <div className={`transfer transfer-${xfer.state === "BROKEN" ? "red" : xfer.state === "AT_RISK" ? "amber" : "green"}`} data-testid="transfer">
                    <strong>{tc(lang, "x_", tw.check.cls)}</strong> · {t(lang, "change_here")} · {stn(tw.check.station)}
                    <div className="small">{t(lang, "x_detail", { gap: duration(tw.check.gap_minutes, lang), req: duration(tw.check.required_minutes, lang), margin: duration(tw.check.margin_minutes, lang) })}</div>
                    <Buffer gap={tw.check.gap_minutes} need={tw.check.required_minutes} />
                    <div className="small muted">{t(lang, "latest_safe")}: {time(tw.latest_safe_arrival)}</div>
                  </div>
                </div>
              )}
              {xfer && i + 1 < legs.length && (
                <Stop lang={lang} name={stn(node(`L${leg.seq + 1}:DEP`).station)} state={node(`L${leg.seq + 1}:DEP`).state}
                  sched={node(`L${leg.seq + 1}:DEP`).scheduled} exp={node(`L${leg.seq + 1}:DEP`).expected} delay={node(`L${leg.seq + 1}:DEP`).delay_minutes} />
              )}
            </li>
          );
        })}
      </ol>

      <div className="stack-sm">
        <h3>{t(lang, "how_spreads")}</h3>
        <ol className="trace" data-testid="trace">
          {graph.trace.map((s, i) => <li key={i} className={traceTone(s.code)}>{traceSentence(s, lang, names)}</li>)}
        </ol>
      </div>
      {twin.transfers.length > 0 && <p className="tiny muted">{t(lang, "est_label")}</p>}
    </section>
  );
}

function Stop({ lang, name, state, sched, exp, delay }: { lang: Lang; name: string; state: string; sched: string; exp: string; delay: number }) {
  const changed = delay > 0 && sched !== exp;
  return (
    <div className="gt-node">
      <div className="gt-time">
        {changed ? <><s aria-label={t(lang, "sched")}>{time(sched)}</s><b className="late">{time(exp)}</b></> : <b>{time(sched)}</b>}
      </div>
      <span className={`gt-dot s-${state}`} aria-hidden />
      <div className="gt-body"><span className="gt-stn">{name}</span></div>
    </div>
  );
}

// Visual buffer: how much of the gap between trains this passenger needs (marker) vs what they have.
function Buffer({ gap, need }: { gap: number; need: number }) {
  const max = Math.max(need * 2, gap, 1);
  const pct = Math.max(0, Math.min(100, (gap / max) * 100));
  const color = gap < need ? "var(--red)" : gap - need < 10 ? "var(--amber)" : gap - need < 25 ? "var(--saffron)" : "var(--green)";
  return (
    <div className="buffer-bar" role="img" aria-label={`${gap} / ${need}`}>
      <span style={{ width: `${pct}%`, background: color }} />
      <i className="need" style={{ left: `${(need / max) * 100}%` }} />
    </div>
  );
}
