import { useEffect, useState } from "react";
import type { Lang } from "./api";
import { t } from "./i18n";
import { go } from "./router";
import { AddJourney } from "./screens/AddJourney";
import { JourneyScreen } from "./screens/JourneyScreen";
import { OptionsScreen } from "./screens/OptionsScreen";
import { HowToScreen } from "./screens/HowToScreen";
import { SummaryScreen } from "./screens/SummaryScreen";
import { Presenter } from "./screens/Presenter";

function useHash(): string[] {
  const [h, setH] = useState(window.location.hash.slice(2) || "");
  useEffect(() => {
    const on = () => setH(window.location.hash.slice(2) || "");
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return h.split("/").filter(Boolean);
}

export default function App() {
  const [lang, setLang] = useState<Lang>(() => (localStorageGet("lang") as Lang) || "en");
  const parts = useHash();
  useEffect(() => { localStorageSet("lang", lang); document.documentElement.lang = lang; }, [lang]);

  const [screen, id, planId] = parts;
  let body;
  if (screen === "journey" && id) body = <JourneyScreen id={id} lang={lang} />;
  else if (screen === "options" && id) body = <OptionsScreen id={id} lang={lang} />;
  else if (screen === "howto" && id && planId) body = <HowToScreen id={id} planId={planId} lang={lang} />;
  else if (screen === "summary" && id) body = <SummaryScreen id={id} lang={lang} />;
  else if (screen === "presenter") body = <Presenter lang={lang} />;
  else body = <AddJourney lang={lang} />;

  return (
    <div className={`app lang-${lang}`}>
      <header className="topbar">
        <button className="brand" onClick={() => go("")} aria-label={t(lang, "app_name")}>
          <span className="brand-mark" aria-hidden>➜</span>
          <span>{t(lang, "app_name")}</span>
        </button>
        <div className="lang-toggle" role="group" aria-label="Language">
          <button aria-pressed={lang === "en"} onClick={() => setLang("en")}>EN</button>
          <button aria-pressed={lang === "hi"} onClick={() => setLang("hi")}>हिं</button>
        </div>
      </header>
      <div className="sim-strip" role="note">{t(lang, "simulated")} · {t(lang, "not_official")}</div>
      <main className="container">{body}</main>
    </div>
  );
}

// Browser storage can be unavailable (private mode); never crash because of it.
function localStorageGet(k: string): string | null { try { return window.localStorage.getItem(k); } catch { return null; } }
function localStorageSet(k: string, v: string) { try { window.localStorage.setItem(k, v); } catch { /* ignore */ } }
