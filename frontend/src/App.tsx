import { useEffect, useState } from "react";
import type { Lang } from "./api";
import { applyA11y, loadA11y } from "./a11y";
import { t } from "./i18n";
import { myJourneys } from "./myJourneys";
import { go } from "./router";
import { AddJourney } from "./screens/AddJourney";
import { JourneyScreen } from "./screens/JourneyScreen";
import { OptionsScreen } from "./screens/OptionsScreen";
import { HowToScreen } from "./screens/HowToScreen";
import { SummaryScreen } from "./screens/SummaryScreen";
import { Presenter } from "./screens/Presenter";
import { WhatIfScreen } from "./screens/WhatIfScreen";
import { WalletScreen } from "./screens/WalletScreen";
import { MoreScreen } from "./screens/MoreScreen";
import { ResilienceScreen } from "./screens/ResilienceScreen";
import { PreferencesScreen } from "./screens/PreferencesScreen";
import { OfflineCardScreen } from "./screens/OfflineCardScreen";
import { AssistantScreen } from "./screens/AssistantScreen";
import { CommunityScreen } from "./screens/CommunityScreen";
import { FamilyScreen } from "./screens/FamilyScreen";
import { HomeScreen } from "./screens/HomeScreen";
import { MyJourneysScreen } from "./screens/MyJourneysScreen";
import { DisruptionScreen } from "./screens/DisruptionScreen";
import { CopilotScreen } from "./screens/CopilotScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { DecideScreen } from "./screens/DecideScreen";

function useHash(): string[] {
  const [h, setH] = useState(window.location.hash.slice(2) || "");
  useEffect(() => {
    const on = () => setH(window.location.hash.slice(2) || "");
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return h.split("/").filter(Boolean);
}

// Main app navigation (desktop: left side; mobile: bottom bar). Journey-specific
// sections stay in the SectionNav on each journey page.
const MAIN = [
  { key: "home", icon: "⌂", label: "nav_home" },
  { key: "journeys", icon: "🗂", label: "nav_journeys" },
  { key: "copilot", icon: "💬", label: "nav_copilot" },
  { key: "offline", icon: "⤓", label: "nav_off_main" },
  { key: "settings", icon: "⚙", label: "nav_settings" },
] as const;

function navTarget(key: string): string {
  const last = myJourneys.last();
  if (key === "home") return "";
  if (key === "copilot" || key === "offline") return last ? `${key}/${last}` : "";
  return key;
}

export default function App() {
  const [lang, setLang] = useState<Lang>(() => (localStorageGet("lang") as Lang) || "en");
  const parts = useHash();
  useEffect(() => { localStorageSet("lang", lang); document.documentElement.lang = lang; }, [lang]);
  useEffect(() => { applyA11y(loadA11y()); }, []);

  const [screen, id, planId] = parts;
  let body;
  if (screen === "journey" && id) body = <JourneyScreen id={id} lang={lang} />;
  else if (screen === "options" && id) body = <OptionsScreen id={id} lang={lang} />;
  else if (screen === "disruption" && id) body = <DisruptionScreen id={id} lang={lang} />;
  else if (screen === "decide" && id) body = <DecideScreen id={id} lang={lang} />;
  else if (screen === "howto" && id && planId) body = <HowToScreen id={id} planId={planId} lang={lang} />;
  else if (screen === "summary" && id) body = <SummaryScreen id={id} lang={lang} />;
  else if (screen === "presenter") body = <Presenter lang={lang} />;
  else if (screen === "whatif" && id) body = <WhatIfScreen id={id} lang={lang} />;
  else if (screen === "wallet" && id) body = <WalletScreen id={id} lang={lang} />;
  else if (screen === "more" && id) body = <MoreScreen id={id} lang={lang} />;
  else if (screen === "resilience" && id) body = <ResilienceScreen id={id} lang={lang} />;
  else if (screen === "prefs" && id) body = <PreferencesScreen id={id} lang={lang} />;
  else if (screen === "offline" && id) body = <OfflineCardScreen id={id} lang={lang} />;
  else if (screen === "assistant" && id) body = <AssistantScreen id={id} lang={lang} />;
  else if (screen === "copilot" && id) body = <CopilotScreen id={id} lang={lang} />;
  else if (screen === "community" && id) body = <CommunityScreen id={id} lang={lang} />;
  else if (screen === "family" && id) body = <FamilyScreen gid={id} lang={lang} />;
  else if (screen === "journeys") body = <MyJourneysScreen lang={lang} />;
  else if (screen === "settings") body = <SettingsScreen lang={lang} setLang={setLang} />;
  else if (screen === "add") body = <AddJourney lang={lang} />;
  else body = <HomeScreen lang={lang} />;

  const active = !screen ? "home" : MAIN.some((m) => m.key === screen) ? screen : "";
  const navItems = (cls: string, tid: string) => MAIN.map((m) => (
    <button key={m.key} className={cls} data-testid={`${tid}-${m.key}`} aria-current={active === m.key ? "page" : undefined}
      onClick={() => go(navTarget(m.key))}>
      <span aria-hidden className="nav-ico">{m.icon}</span><span>{t(lang, m.label)}</span>
    </button>
  ));

  return (
    <div className={`app lang-${lang}`}>
      <a href="#main" className="skip-link" onClick={(e) => { e.preventDefault(); document.getElementById("main")?.focus(); }}>{t(lang, "skip")}</a>
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
      <div className="shell">
        <nav className="sidenav" aria-label="Main">
          {navItems("sn-item", "side")}
          <p className="nav-foot">{t(lang, "nav_foot")}</p>
        </nav>
        <main id="main" tabIndex={-1} className="container">{body}</main>
      </div>
      <nav className="bottomnav" aria-label="Main (mobile)">{navItems("bn-item", "main")}</nav>
    </div>
  );
}

// Browser storage can be unavailable (private mode); never crash because of it.
function localStorageGet(k: string): string | null { try { return window.localStorage.getItem(k); } catch { return null; } }
function localStorageSet(k: string, v: string) { try { window.localStorage.setItem(k, v); } catch { /* ignore */ } }
