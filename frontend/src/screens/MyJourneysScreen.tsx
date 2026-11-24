import { useState } from "react";
import { api, type Lang } from "../api";
import { JourneyCard } from "../components/JourneyCard";
import { t } from "../i18n";
import { myJourneys } from "../myJourneys";
import { go } from "../router";
import { useLoad } from "../useLoad";

// All journeys saved on this device, most urgent first (the server sorts by urgency).
export function MyJourneysScreen({ lang }: { lang: Lang }) {
  const [ids, setIds] = useState(myJourneys.list());
  const dash = useLoad(() => (ids.length ? api.dashboard(ids) : Promise.resolve({ journeys: [] })), [ids.join(",")], 15000);
  const list = dash.data?.journeys ?? [];
  return (
    <div className="stack">
      <header className="page-head">
        <h1>{t(lang, "my_journeys")}</h1>
        <p className="sub">{t(lang, "my_journeys_sub")}</p>
      </header>
      {ids.length === 0 ? (
        <div className="empty" data-testid="journeys-empty">
          <div className="big-ico" aria-hidden>🗂️</div>
          <strong>{t(lang, "dash_none")}</strong>
          <button className="primary" onClick={() => go("")}>{t(lang, "add_journey")}</button>
        </div>
      ) : !dash.data ? <p className="muted" aria-busy="true">…</p> : (
        <div className="grid-2" data-testid="journey-list">
          {list.map((d) => (
            <JourneyCard key={d.journey.id} d={d} lang={lang}
              onRemove={() => { myJourneys.remove(d.journey.id); setIds(myJourneys.list()); }} />
          ))}
        </div>
      )}
      {ids.length > 0 && <button className="secondary" onClick={() => go("")}>{t(lang, "journeys_add_more")}</button>}
    </div>
  );
}
