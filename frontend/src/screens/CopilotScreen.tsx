import { useEffect, useRef, useState } from "react";
import { api, type CopilotReply, type Lang } from "../api";
import { JourneyHeader } from "../components/JourneyHeader";
import { SectionNav } from "../components/SectionNav";
import { t, tc } from "../i18n";
import { activity } from "../myJourneys";
import { go } from "../router";
import { useAssessment } from "../useAssessment";

type Msg = { role: "user" | "assistant"; text: string; reply?: CopilotReply };
const SUGGEST = ["cp_q1", "cp_q2", "cp_q3", "cp_q4", "cp_q5", "cp_q6"];

function recognizer(): any | null {
  const C = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  return C ? new C() : null;
}

// Journey Copilot: a chat about ONE journey. The server plans read-only tool calls, the rules engine
// computes every number, and the answer shows its sources and the tools it used.
export function CopilotScreen({ id, lang }: { id: string; lang: Lang }) {
  const { data } = useAssessment(id, lang);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [listening, setListening] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  async function send(q: string) {
    const msg = q.trim().slice(0, 500);
    if (!msg || busy) return;
    const history = msgs.map((m) => ({ role: m.role, text: m.text }));
    setMsgs((m) => [...m, { role: "user", text: msg }]);
    setText(""); setBusy(true); setErr("");
    try {
      const r = await api.copilot(id, msg, lang, history);
      setMsgs((m) => [...m, { role: "assistant", text: r.answer, reply: r }]);
      activity.log(id, "asked");
    } catch { setErr(t(lang, "err_network")); }
    finally { setBusy(false); }
  }

  // A question typed on the Home screen arrives here once.
  useEffect(() => {
    let q: string | null = null;
    try { q = window.sessionStorage.getItem("aglaKadam.pendingQ"); window.sessionStorage.removeItem("aglaKadam.pendingQ"); } catch { /* ignore */ }
    if (q) send(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
  useEffect(() => { endRef.current?.scrollIntoView?.({ block: "end" }); }, [msgs.length]);

  function listen() {
    const r = recognizer();
    if (!r) { setErr(t(lang, "cp_voice_off")); return; }
    r.lang = lang === "hi" ? "hi-IN" : "en-IN"; r.interimResults = false;
    r.onresult = (e: any) => send(e.results[0][0].transcript as string);
    r.onend = () => setListening(false); r.onerror = () => { setListening(false); setErr(t(lang, "cp_voice_off")); };
    setListening(true); r.start();
  }

  return (
    <div className="stack">
      {data ? <JourneyHeader j={data.journey} lang={lang} title={t(lang, "cp_title")} /> : <h1>{t(lang, "cp_title")}</h1>}
      <SectionNav id={id} lang={lang} active="copilot" />
      <p className="small muted">{t(lang, "cp_sub")}</p>

      <div className="chat" data-testid="cp-chat" aria-live="polite">
        {msgs.length === 0 && (
          <div className="card stack-sm">
            <p className="small">{t(lang, "cp_empty")}</p>
            <div className="row-gap">
              {SUGGEST.map((k) => <button key={k} className="chip" data-testid={`cp-${k}`} onClick={() => send(t(lang, k))}>{t(lang, k)}</button>)}
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role === "user" ? "user" : "bot"}`} data-testid={m.role === "user" ? "cp-user" : "cp-reply"}>
            <span className="sr-only">{t(lang, m.role === "user" ? "cp_you" : "cp_bot")}: </span>
            {m.reply?.clarify && <strong className="small">{t(lang, "cp_clarify")}: </strong>}
            <div style={{ whiteSpace: "pre-line" }}>{m.text}</div>
            {m.reply && <Details r={m.reply} lang={lang} />}
          </div>
        ))}
        {busy && <div className="msg bot muted" aria-busy="true">{t(lang, "cp_thinking")}</div>}
        <div ref={endRef} />
      </div>

      {err && <p className="error">{err}</p>}
      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <label htmlFor="cp-input" className="sr-only">{t(lang, "cp_label")}</label>
        <input id="cp-input" data-testid="cp-input" maxLength={500} value={text} onChange={(e) => setText(e.target.value)} placeholder={t(lang, "ask_hint")} />
        <button type="button" className="secondary" onClick={listen} aria-pressed={listening} aria-label={t(lang, "cp_mic")}>{listening ? "…" : "🎤"}</button>
        <button type="submit" className="primary" data-testid="cp-send" disabled={busy}>{t(lang, "cp_send")}</button>
      </form>
      <p className="tiny muted" data-testid="cp-safe">{t(lang, "cp_safe")}</p>
    </div>
  );
}

function Details({ r, lang }: { r: CopilotReply; lang: Lang }) {
  return (
    <>
      <p className="tiny muted" data-testid="cp-source">
        {r.no_reliable_source ? t(lang, "cp_no_source") : tc(lang, "cp_src_", r.answer_source)} · {t(lang, r.planner === "llm" ? "cp_planner_llm" : "cp_planner_deterministic")}
      </p>
      {r.citations.length > 0 && (
        <div className="cites" data-testid="cp-citations">
          <strong>{t(lang, "cp_sources")}</strong>
          {r.citations.map((c) => (
            <span key={c.id}>
              {c.source_url ? <a href={c.source_url} target="_blank" rel="noreferrer noopener">{c.title}</a> : c.title}
              {" "}<span className="muted">· {c.version} · {tc(lang, "st_", c.status)}</span>
            </span>
          ))}
        </div>
      )}
      {r.tool_calls.length > 0 && (
        <details className="detail-only">
          <summary className="tiny">{t(lang, "cp_tools")}</summary>
          <div className="toolchips" data-testid="cp-tools">{r.tool_calls.map((c, i) => <span key={i}>{c.tool}{c.ok ? "" : " ✕"}</span>)}</div>
        </details>
      )}
      {r.next_actions.length > 0 && (
        <div className="actions">
          {r.next_actions.map((a) => a.tel
            ? <a key={a.key} className="button secondary" href={`tel:${a.tel}`}>{t(lang, a.key)}</a>
            : <button key={a.key} className="secondary" data-testid={`cp-${a.key}`} onClick={() => a.route && go(a.route)}>{t(lang, a.key)}</button>)}
        </div>
      )}
    </>
  );
}
