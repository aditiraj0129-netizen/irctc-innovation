import { api, type Lang } from "../api";
import { SectionNav } from "../components/SectionNav";
import { t } from "../i18n";
import { go } from "../router";
import { useLoad } from "../useLoad";

// "More" hub: the remaining tools for this journey.
export function MoreScreen({ id, lang }: { id: string; lang: Lang }) {
  const sc = useLoad(() => api.scenarios(), []);
  const group = sc.data?.find((s) => s.id === id)?.group;
  const items: [string, string, string][] = [
    ["resilience", "nav_resilience", "◔"], ["offline", "nav_offline", "⇩"], ["assistant", "nav_assistant", "🎙"],
    ["community", "nav_community", "⚑"], ["prefs", "nav_prefs", "♿"],
  ];
  return (
    <div className="stack">
      <h1>{t(lang, "more_title")}</h1>
      <SectionNav id={id} lang={lang} active="more" />
      <div className="tiles">
        {items.map(([route, label, icon]) => (
          <button key={route} className="tile" data-testid={`more-${route}`} onClick={() => go(`${route}/${id}`)}>
            <span aria-hidden className="tile-icon">{icon}</span>{t(lang, label)}
          </button>
        ))}
        {group && (
          <button className="tile" data-testid="more-family" onClick={() => go(`family/${group}`)}>
            <span aria-hidden className="tile-icon">👪</span>{t(lang, "nav_family")}
          </button>
        )}
      </div>
    </div>
  );
}
