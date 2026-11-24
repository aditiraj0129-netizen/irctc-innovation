import type { Assessment, Lang } from "../api";
import { dayTime } from "../format";
import { t } from "../i18n";

// One header for every journey page: route, trains, masked PNR. Same everywhere, so pages feel connected.
export function JourneyHeader({ j, lang, title }: { j: Assessment["journey"]; lang: Lang; title?: string }) {
  const first = j.legs[0], last = j.legs[j.legs.length - 1];
  const via = j.legs.slice(0, -1).map((l) => l.to[lang]);
  return (
    <header className="page-head">
      {title && <p className="eyebrow">{title}</p>}
      <h1>{first.from[lang]} → {last.to[lang]}</h1>
      <p className="sub">
        {via.length > 0 && <>{t(lang, "via")} {via.join(", ")} · </>}
        {j.legs.map((l) => l.train_no).join(" + ")} · {dayTime(first.scheduled_departure)} · <span className="mono">{j.pnr_label}</span>
      </p>
    </header>
  );
}
