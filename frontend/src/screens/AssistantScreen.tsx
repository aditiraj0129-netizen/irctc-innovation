import { useRef, useState } from "react";
import { api, type AssistantReply, type Lang } from "../api";
import { SectionNav } from "../components/SectionNav";
import { t } from "../i18n";

// Browser speech APIs (not in every browser). We use them only when present.
type SR = { lang: string; interimResults: boolean; onresult: (e: any) => void; onend: () => void; onerror: () => void; start: () => void; stop: () => void };
function makeRecognizer(): SR | null {
  const C = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  return C ? (new C() as SR) : null;
}

// Multilingual assistant: voice or text in, answer built only from backend facts, read aloud on request.
export function AssistantScreen({ id, lang }: { id: string; lang: Lang }) {
  const [text, setText] = useState("");
  const [reply, setReply] = useState<AssistantReply | null>(null);
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [err, setErr] = useState("");
  const rec = useRef<SR | null>(null);
  const voiceIn = typeof window !== "undefined" && !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
  const voiceOut = typeof window !== "undefined" && "speechSynthesis" in window;

  const ask = async (q: string) => {
    if (!q.trim()) return;
    setBusy(true); setErr("");
    try { setReply(await api.ask(id, q.trim().slice(0, 300), lang)); }
    catch { setErr(t(lang, "err_network")); }
    finally { setBusy(false); }
  };

  const listen = () => {
    const r = makeRecognizer();
    if (!r) { setErr(t(lang, "as_no_voice")); return; }
    r.lang = lang === "hi" ? "hi-IN" : "en-IN";
    r.interimResults = false;
    r.onresult = (e) => { const said = e.results[0][0].transcript as string; setText(said); ask(said); };
    r.onend = () => setListening(false);
    r.onerror = () => { setListening(false); setErr(t(lang, "as_no_voice")); };
    rec.current = r; setListening(true); r.start();
  };

  const speak = () => {
    if (!reply || !voiceOut) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(reply.answer);
    u.lang = reply.lang === "hi" ? "hi-IN" : "en-IN";
    u.rate = 0.9;
    window.speechSynthesis.speak(u);
  };

  return (
    <div className="stack">
      <h1>{t(lang, "as_title")}</h1>
      <SectionNav id={id} lang={lang} active="more" />
      <p className="small muted">{t(lang, "as_help")}</p>
      <div className="row-gap">
        {["as_q1", "as_q2", "as_q3", "as_q4"].map((k) => (
          <button key={k} className="chip" data-testid={`ask-${k}`} onClick={() => { setText(t(lang, k)); ask(t(lang, k)); }}>{t(lang, k)}</button>
        ))}
      </div>
      <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); ask(text); }}>
        <label className="label" htmlFor="ask">{t(lang, "as_ask")}</label>
        <input id="ask" value={text} maxLength={300} placeholder={t(lang, "as_placeholder")} data-testid="ask-input"
          onChange={(e) => setText(e.target.value)} />
        <div className="row-gap">
          <button className="primary big-btn" type="submit" disabled={busy} data-testid="ask-submit">{t(lang, "as_ask")}</button>
          <button className="secondary big-btn" type="button" onClick={listening ? () => rec.current?.stop() : listen}
            aria-pressed={listening} disabled={!voiceIn} data-testid="ask-voice">
            🎙 {listening ? t(lang, "as_listening") : t(lang, "as_speak")}</button>
        </div>
        {!voiceIn && <p className="tiny muted">{t(lang, "as_no_voice")}</p>}
      </form>
      {err && <p className="error" role="alert">{err}</p>}
      {reply && (
        <section className="card stack-sm" aria-live="polite" data-testid="ask-reply">
          <p className="answer">{reply.answer}</p>
          {reply.rule_ids.length > 0 && <p className="tiny mono">{t(lang, "as_rules")}: {reply.rule_ids.join(", ")}</p>}
          <p className="tiny muted">{t(lang, "as_source")} · {t(lang, "simulated")}</p>
          {voiceOut && <button className="secondary" onClick={speak} data-testid="ask-speak">🔊 {t(lang, "as_read")}</button>}
        </section>
      )}
    </div>
  );
}
