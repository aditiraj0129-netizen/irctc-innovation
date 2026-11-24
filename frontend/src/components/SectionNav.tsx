import type { Lang } from "../api";
import { t } from "../i18n";
import { go } from "../router";

const TABS = ["journey", "decide", "station", "disruption", "options", "whatif", "wallet", "more"] as const;
const LABEL: Record<string, string> = { journey: "nav_overview", decide: "nav_decide", station: "nav_station", disruption: "nav_disruption", options: "nav_options",
  whatif: "nav_whatif", wallet: "nav_wallet", more: "nav_more" };

// One navigation bar for every journey section, so the features feel like one product.
export function SectionNav({ id, lang, active }: { id: string; lang: Lang; active: string }) {
  return (
    <nav className="section-nav" aria-label="Journey sections" data-testid="section-nav">
      {TABS.map((tab) => (
        <button key={tab} aria-current={active === tab ? "page" : undefined} data-testid={`nav-${tab}`}
          onClick={() => go(`${tab}/${id}`)}>{t(lang, LABEL[tab])}</button>
      ))}
    </nav>
  );
}
