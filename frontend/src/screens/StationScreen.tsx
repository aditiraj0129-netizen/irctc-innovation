import { useEffect, useMemo, useState } from "react";
import { stationApi, type Lang, type PlatformInfo, type SNode, type SRoute, type StationMap as SMap, type StationSummary } from "../api";
import { JourneyHeader } from "../components/JourneyHeader";
import { SectionNav } from "../components/SectionNav";
import { StationMap } from "../components/StationMap";
import { time } from "../format";
import { t } from "../i18n";
import { go } from "../router";
import { useLoad } from "../useLoad";

const PROFILES = ["fastest", "step_free", "fewer_levels"] as const;
const FTYPES = ["EXIT", "TICKET_COUNTER", "WASHROOM", "WAITING_ROOM", "CLOAKROOM", "ENQUIRY", "DRINKING_WATER", "FOOD", "HELP_DESK", "RPF", "METRO", "PARKING"];

function queryAt(): string | null {
  const m = window.location.hash.match(/[?&]at=([A-Z0-9_]{1,40})/);
  return m ? m[1] : null;
}

// ---------- Journey mode: arrival platform -> walk -> connecting platform, and can I make it? ----------
export function StationJourneyScreen({ id, lang }: { id: string; lang: Lang }) {
  const linkAt = queryAt();
  const [at, setAt] = useState<string | null>(linkAt);
  const [profile, setProfile] = useState<string | null>(null);
  useEffect(() => { if (linkAt) setAt(linkAt); }, [linkAt]);
  const { data, error, reload } = useLoad(() => stationApi.journey(id, at, profile, linkAt && at === linkAt ? "LINK" : "MANUAL"), [id, at, profile], 15000);
  const map = useLoad(() => (data?.station_summary ? stationApi.get(data.station) : Promise.resolve(null)), [data?.station_summary?.code ?? ""]);
  if (error && !data) return <p className="error" role="alert">{t(lang, "err_network")}</p>;
  if (!data) return <p className="muted" aria-busy="true">…</p>;
  const c = data.connection;
  const stnName = data.station_summary?.name[lang] ?? data.station;
  const route = c?.route ?? null;

  return (
    <div className="stack">
      <JourneyHeader j={data.journey} lang={lang} title={t(lang, "sn_title")} />
      <SectionNav id={id} lang={lang} active="station" />
      <p className="small muted">{t(lang, "sn_sub")}</p>

      {c?.prepare_to_alight && c.departure_platform.platform && (
        <section className="sn-prepare" data-testid="sn-prepare">
          <strong>{t(lang, "sn_prepare", { p: String(c.departure_platform.platform) })}</strong>
          {c.minutes_to_arrival != null && <span className="small"> {t(lang, "sn_prepare_in", { m: String(c.minutes_to_arrival) })}</span>}
        </section>
      )}

      {!data.station_summary && (
        <section className="card stack-sm" data-testid="sn-no-map">
          <h2 className="small-h">{t(lang, "sn_no_map", { stn: stnName })}</h2>
          <p className="small">{t(lang, "sn_no_map_sub")}</p>
          <PlatformBadge p={data.arrival_platform} lang={lang} label={t(lang, "tl_arr_pf")} />
          {data.arrival_platform.platform == null && <p className="small" data-testid="sn-live-unavailable">{t(lang, "sn_live_unavailable")}</p>}
          <button className="secondary" onClick={() => go("stations")}>{t(lang, "nav_stations")}</button>
        </section>
      )}

      {c && <Verdict c={c} lang={lang} />}

      {c && (
        <div className="grid-2">
          <section className="card stack-sm" data-testid="sn-timeline" aria-labelledby="sn-tl-h">
            <h2 id="sn-tl-h" className="small-h">{stnName}</h2>
            <ol className="sn-tl">
              <li><span className="sn-tl-k">{t(lang, "tl_current")}</span><strong>{c.first_train} · {c.first_train_name}</strong>
                {data.prediction.current_delay_minutes != null && <span className="small"> · {t(lang, "tl_late", { m: String(data.prediction.current_delay_minutes) })}</span>}
                {data.prediction.latest_data_at && <div className="tiny muted">{t(lang, "tl_updated", { t: time(data.prediction.latest_data_at) })}</div>}</li>
              <li><span className="sn-tl-k">{t(lang, "tl_arrival")}</span>
                <strong>{c.arrival_expected ? t(lang, "tl_range", { a: time(c.arrival_early), b: time(c.arrival_late), m: time(c.arrival_expected) }) : "—"}</strong></li>
              <li><PlatformBadge p={c.arrival_platform} lang={lang} label={t(lang, "tl_arr_pf")} testid="sn-arr-pf" /></li>
              <li><span className="sn-tl-k">{t(lang, "tl_walk")}</span>
                <strong data-testid="sn-walk">{route?.found ? t(lang, "tl_walk_v", { lo: String(route.minutes_low), hi: String(route.minutes_high), m: String(route.distance_m), s: String(route.stairs), l: String(route.lifts) }) : "—"}</strong></li>
              <li><PlatformBadge p={c.departure_platform} lang={lang} label={t(lang, "tl_dep_pf")} testid="sn-dep-pf" /></li>
              <li><span className="sn-tl-k">{t(lang, "tl_dep")}</span><strong>{c.second_train} · {time(c.departure)}</strong></li>
            </ol>
            <EnterPlatform id={id} lang={lang} c={c} onDone={reload} />
          </section>

          <section className="card stack-sm" aria-labelledby="sn-loc-h">
            <h2 id="sn-loc-h" className="small-h">{t(lang, "loc_title")}</h2>
            {map.data && <LocationPicker map={map.data} lang={lang} value={c.location} arrival={c.arrival_platform.platform} onChange={setAt} />}
            <p className="tiny muted" data-testid="sn-loc-note">{c.location_source === "LINK" ? t(lang, "loc_link") : t(lang, "loc_demo")}</p>
            <ProfilePicker lang={lang} value={profile ?? c.profile} onChange={setProfile} />
            {route && <RouteView r={route} lang={lang} />}
          </section>
        </div>
      )}

      {map.data && c && <StationMap map={map.data} path={route?.path ?? []} lang={lang} start={c.location} end={route?.end ?? null} />}
      {map.data && <Details map={map.data} lang={lang} />}
    </div>
  );
}

function Verdict({ c, lang }: { c: NonNullable<import("../api").JourneyStation["connection"]>; lang: Lang }) {
  const r = c.route;
  const lv = { COMFORTABLE: "NONE", TIGHT: "WATCH", HIGH_RISK: "SOON", UNLIKELY: "NOW", NOT_FEASIBLE: "NOW", CANNOT_ASSESS: "UNKNOWN" }[c.result] ?? "UNKNOWN";
  return (
    <section className={`dc-head lv-${lv}`} data-testid="sn-verdict">
      <div className="row-between">
        <h2 className="dz-headline">{t(lang, "fz_" + c.result)}</h2>
        <span className="tiny">{t(lang, "sn_not_guarantee")}</span>
      </div>
      {c.result === "CANNOT_ASSESS" ? (
        <>
          <p data-testid="sn-missing">{t(lang, "sn_missing", { list: c.missing.map((m) => t(lang, "ms_" + m)).join(", ") })}</p>
          {(c.arrival_platform.platform == null || c.departure_platform.platform == null) && <p className="small" data-testid="sn-live-unavailable">{t(lang, "sn_live_unavailable")}</p>}
          <p className="small">{t(lang, "sn_enter_hint")}</p>
        </>
      ) : (
        <>
          <p data-testid="sn-sentence">{t(lang, "sn_verdict", { a: String(c.arrival_platform.platform), t2: c.second_train, d: String(c.departure_platform.platform),
            lo: String(r?.minutes_low), hi: String(r?.minutes_high), avl: String(c.available_minutes?.likely), ae: String(c.available_minutes?.early), al: String(c.available_minutes?.late) })}</p>
          <p className="small">{t(lang, "sn_why_" + c.result)}</p>
          {c.capped_by.length > 0 && <p className="small" data-testid="sn-capped">{t(lang, "sn_capped", { which: c.capped_by.map((x) => t(lang, "cap_" + x)).join(" / ") })} {t(lang, "sn_live_unavailable")}</p>}
        </>
      )}
    </section>
  );
}

function PlatformBadge({ p, lang, label, testid }: { p: PlatformInfo; lang: Lang; label: string; testid?: string }) {
  return (
    <div data-testid={testid}>
      <span className="sn-tl-k">{label}</span>
      <strong className="sn-pf">{p.platform != null ? `${lang === "hi" ? "प्लेटफॉर्म" : "Platform"} ${p.platform}` : t(lang, "ps_unknown_pf")}</strong>{" "}
      <span className={`pill ps-${p.status}`} data-testid={testid ? `${testid}-status` : undefined}>{t(lang, "ps_" + p.status)}</span>
      {p.stale && <span className="pill fresh-stale"> {t(lang, "ps_stale")}</span>}
      {p.changed_from != null && <span className="pill ps-changed" data-testid={testid ? `${testid}-changed` : undefined}> {t(lang, "ps_changed", { p: String(p.changed_from) })}</span>}
      <div className="tiny muted">{p.age_minutes != null ? t(lang, "ps_age", { m: String(p.age_minutes) }) + " · " : ""}
        {p.source === "PASSENGER_FROM_STATION_BOARD" ? t(lang, "ps_src_PASSENGER_FROM_STATION_BOARD") : p.source}</div>
    </div>
  );
}

function EnterPlatform({ id, lang, c, onDone }: { id: string; lang: Lang; c: NonNullable<import("../api").JourneyStation["connection"]>; onDone: () => void }) {
  const [kind, setKind] = useState<"ARRIVAL" | "DEPARTURE">("DEPARTURE");
  const [pf, setPf] = useState("");
  const [err, setErr] = useState("");
  async function save(e: React.FormEvent) {
    e.preventDefault();
    const n = Number(pf);
    if (!Number.isInteger(n) || n < 1 || n > 30) { setErr("1–30"); return; }
    try { await stationApi.enterPlatform(id, kind === "ARRIVAL" ? c.first_train : c.second_train, kind, n); setErr(""); setPf(""); onDone(); }
    catch { setErr(t(lang, "err_network")); }
  }
  return (
    <form className="sn-enter" onSubmit={save} data-testid="sn-enter">
      <p className="tiny muted">{t(lang, "sn_enter_hint")}</p>
      <div className="row-gap">
        <select aria-label={t(lang, "enter_pf")} value={kind} onChange={(e) => setKind(e.target.value as any)} data-testid="sn-enter-kind">
          <option value="DEPARTURE">{t(lang, "enter_dep")}</option><option value="ARRIVAL">{t(lang, "enter_arr")}</option>
        </select>
        <input aria-label={t(lang, "enter_pf")} inputMode="numeric" maxLength={2} value={pf} onChange={(e) => setPf(e.target.value.replace(/\D/g, ""))}
          placeholder="12" data-testid="sn-enter-pf" style={{ width: 70 }} />
        <button className="secondary" type="submit" data-testid="sn-enter-go">{t(lang, "enter_go")}</button>
      </div>
      {err && <p className="small error">{err}</p>}
    </form>
  );
}

function LocationPicker({ map, lang, value, arrival, onChange }: { map: SMap; lang: Lang; value: string | null; arrival?: number | null; onChange: (v: string | null) => void }) {
  const plats = map.nodes.filter((n) => n.kind === "PLATFORM").sort((a, b) => (a.platform ?? 0) - (b.platform ?? 0));
  const sides = map.nodes.filter((n) => n.kind === "SIDE");
  const facs = map.nodes.filter((n) => n.kind === "FACILITY");
  return (
    <label className="stack-sm">
      <span className="label">{t(lang, "loc_choose")}</span>
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value || null)} data-testid="sn-location">
        {!value && <option value="">{t(lang, "loc_choose")}</option>}
        <optgroup label={t(lang, "loc_platforms")}>
          {plats.map((n) => <option key={n.id} value={n.id}>{n.label[lang]}{arrival === n.platform ? ` ${t(lang, "loc_arrival")}` : ""}</option>)}
        </optgroup>
        <optgroup label={t(lang, "loc_entrances")}>{sides.map((n) => <option key={n.id} value={n.id}>{n.label[lang]}</option>)}</optgroup>
        <optgroup label={t(lang, "loc_facilities")}>{facs.map((n) => <option key={n.id} value={n.id}>{n.label[lang]}</option>)}</optgroup>
      </select>
    </label>
  );
}

function ProfilePicker({ lang, value, onChange }: { lang: Lang; value: string; onChange: (v: string) => void }) {
  return (
    <fieldset className="segmented seg-3" aria-label={t(lang, "rt_steps")}>
      {PROFILES.map((p) => <button key={p} type="button" aria-pressed={value === p} data-testid={`sn-profile-${p}`} onClick={() => onChange(p)}>{t(lang, "rp_" + p)}</button>)}
    </fieldset>
  );
}

const L = (v: any, lang: Lang) => (v && typeof v === "object" ? v[lang] ?? v.en : v ?? "");
const plats = (refs: number[] | undefined, lang: Lang) =>
  !refs?.length ? "" : refs.length === 1 ? `${lang === "hi" ? "प्लेटफॉर्म" : "Platform"} ${refs[0]}` : `${lang === "hi" ? "प्लेटफॉर्म" : "Platforms"} ${refs[0]}–${refs[refs.length - 1]}`;

export function stepText(s: { code: string; params: Record<string, any> }, lang: Lang): string {
  const p = s.params;
  switch (s.code) {
    case "START": return t(lang, "st_START", { at: L(p.at, lang) });
    case "WALK_PLATFORM": return p.toward ? t(lang, "st_WALK_PLATFORM", { p: plats(p.platforms, lang), to: L(p.toward, lang), m: String(p.m) })
      : t(lang, "st_WALK_PLATFORM_n", { p: plats(p.platforms, lang), m: String(p.m) });
    case "UP": case "DOWN": return t(lang, "st_" + s.code, { via: t(lang, "via_" + p.via), to: L(p.to, lang) }) + (p.via === "LIFT" ? t(lang, "st_lift_note") : "");
    case "CROSS_FOB": return t(lang, "st_CROSS_FOB", { fob: L(p.fob, lang), p: plats(p.last_platforms, lang), m: String(p.m) });
    case "WALK_CONCOURSE": return t(lang, "st_WALK_CONCOURSE", { m: String(p.m) });
    case "WALK_LINK": return t(lang, "st_WALK_LINK", { name: L(p.name, lang), m: String(p.m) });
    case "TO_CONCOURSE": return t(lang, "st_TO_CONCOURSE");
    case "TO_SIDE": return t(lang, "st_TO_SIDE", { name: L(p.name, lang) });
    case "ENTER_PLATFORM": return t(lang, "st_ENTER_PLATFORM", { p: plats(p.platforms, lang) });
    case "ARRIVE": return t(lang, "st_ARRIVE", { at: L(p.at, lang) });
    default: return s.code;
  }
}

export function RouteView({ r, lang }: { r: SRoute; lang: Lang }) {
  if (!r.found) return <p className="small" data-testid="sn-no-route">{t(lang, "rt_none")} {r.reason === "NO_STEP_FREE_ROUTE" ? t(lang, "ms_NO_STEP_FREE_ROUTE") : ""}</p>;
  return (
    <div className="stack-sm" data-testid="sn-route">
      <p className="sn-route-sum"><strong>{t(lang, "rt_summary", { lo: String(r.minutes_low), hi: String(r.minutes_high), m: String(r.distance_m) })}</strong>
        {" · "}{t(lang, "rt_stairs", { n: String(r.stairs) })} · {t(lang, "rt_lifts", { n: String(r.lifts) })}{r.escalators ? ` · ${t(lang, "rt_esc", { n: String(r.escalators) })}` : ""}</p>
      <h3 className="small-h">{t(lang, "rt_steps")}</h3>
      <ol className="sn-steps" data-testid="sn-steps">{r.steps.map((s, i) => <li key={i}>{stepText(s, lang)}</li>)}</ol>
      {r.lifts > 0 && <p className="tiny" data-testid="sn-lift-unknown">⚠ {t(lang, "rt_lift_unknown")}</p>}
      {r.escalators > 0 && <p className="tiny">⚠ {t(lang, "rt_esc_dir")}</p>}
      <p className="tiny muted">{t(lang, "rt_crowd")} {t(lang, "rt_conf")}</p>
    </div>
  );
}

function Details({ map, lang }: { map: SMap; lang: Lang }) {
  return (
    <details className="card small" data-testid="sn-details">
      <summary>{t(lang, "sn_details")}</summary>
      <p className="tiny">{t(lang, "sn_platform_src")}</p>
      <p className="tiny">{t(lang, "sn_schematic")}</p>
      <h3 className="small-h">{t(lang, "sn_sources")}</h3>
      <ul className="plain tiny">{Object.entries(map.sources).map(([k, s]) => (
        <li key={k}>{k}: <a href={s.url} target="_blank" rel="noreferrer noopener">{s.title}</a> · {t(lang, "sn_checked", { d: String(s.checked) })}</li>))}</ul>
    </details>
  );
}

// ---------- Find mode: "I am at the station. Help me find something." ----------
export function StationFindScreen({ code, lang }: { code: string | null; lang: Lang }) {
  const list = useLoad(() => stationApi.list(), []);
  const cleanCode = code?.split("?")[0] || null;
  if (!cleanCode) return (
    <div className="stack">
      <header className="page-head"><h1>{t(lang, "sn_find_title")}</h1><p className="sub">{t(lang, "sn_schematic")}</p></header>
      <h2 className="small-h">{t(lang, "sn_pick_station")}</h2>
      {!list.data ? <p className="muted" aria-busy="true">…</p> : (
        <div className="grid-3" data-testid="sn-stations">
          {list.data.stations.map((s: StationSummary) => (
            <button key={s.code} className="card sn-station" data-testid={`sn-station-${s.code}`} onClick={() => go(`stations/${s.code}`)}>
              <strong>{s.name[lang]}</strong><span className="small muted">{s.code} · {s.platforms.length} {t(lang, "loc_platforms")}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
  return <StationFind code={cleanCode} lang={lang} />;
}

function StationFind({ code, lang }: { code: string; lang: Lang }) {
  const linkAt = queryAt();
  const map = useLoad(() => stationApi.get(code), [code]);
  const [at, setAt] = useState<string | null>(() => linkAt ?? (() => { try { return window.sessionStorage.getItem(`aglaKadam.at.${code}`); } catch { return null; } })());
  const [q, setQ] = useState("");
  const [type, setType] = useState<string | null>(null);
  const [to, setTo] = useState<string | null>(null);
  const [profile, setProfile] = useState("fastest");
  const [r, setR] = useState<{ route: SRoute; alternatives: SRoute[] } | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { if (linkAt) setAt(linkAt); }, [linkAt]);              // a QR-style link was opened
  useEffect(() => { try { if (at) window.sessionStorage.setItem(`aglaKadam.at.${code}`, at); } catch { /* ignore */ } }, [at, code]);
  useEffect(() => {
    if (!at || !to) { setR(null); return; }
    stationApi.route(code, at, to, profile).then((x) => { setR(x); setErr(""); }).catch(() => setErr(t(lang, "err_network")));
  }, [code, at, to, profile, lang]);
  const results = useMemo(() => {
    if (!map.data) return [] as SNode[];
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    return map.data.nodes.filter((n) => {
      const isTarget = n.kind === "FACILITY" || n.kind === "SIDE" || n.kind === "PLATFORM";
      if (!isTarget) return false;
      const ftype = n.kind === "SIDE" ? "EXIT" : n.kind === "PLATFORM" ? "PLATFORM" : n.facility_type;
      if (type && ftype !== type) return false;
      const text = `${n.label.en} ${n.label.hi} ${ftype} ${t(lang, "ft_" + ftype)}`.toLowerCase().replace(/_/g, " ");
      return words.every((w) => text.includes(w));
    }).sort((a, b) => (a.kind === "PLATFORM" ? 1 : 0) - (b.kind === "PLATFORM" ? 1 : 0)).slice(0, 40);
  }, [map.data, q, type, lang]);
  if (map.error && !map.data) return <p className="error" role="alert">{t(lang, "err_network")}</p>;
  if (!map.data) return <p className="muted" aria-busy="true">…</p>;
  const m = map.data;
  return (
    <div className="stack">
      <header className="page-head"><p className="eyebrow">{t(lang, "sn_find_title")}</p><h1>{m.name[lang]}</h1>
        <p className="sub">{m.code} · {m.platforms.length} {t(lang, "loc_platforms")} · {t(lang, "sn_schematic")}</p></header>
      <div className="grid-2">
        <section className="card stack-sm">
          <h2 className="small-h">{t(lang, "loc_title")}</h2>
          <LocationPicker map={m} lang={lang} value={at} onChange={setAt} />
          <p className="tiny muted" data-testid="sn-loc-note">{linkAt && at === linkAt ? t(lang, "loc_link") : t(lang, "loc_demo")}</p>
          <label htmlFor="sn-q" className="label">{t(lang, "fd_search")}</label>
          <input id="sn-q" data-testid="sn-search" value={q} maxLength={60} onChange={(e) => setQ(e.target.value)} placeholder={t(lang, "fd_search")} />
          <div className="row-gap">
            {FTYPES.map((f) => <button key={f} type="button" className="chip" aria-pressed={type === f} data-testid={`sn-type-${f}`} onClick={() => setType(type === f ? null : f)}>{t(lang, "ft_" + f)}</button>)}
          </div>
          <h3 className="small-h">{t(lang, "fd_results")}</h3>
          {results.length === 0 ? <p className="small muted" data-testid="sn-results-empty">{t(lang, "fd_none")}</p> : (
            <ul className="plain sn-results" data-testid="sn-results">
              {results.map((n) => (
                <li key={n.id}>
                  <button className={`sn-result ${to === n.id ? "sn-result-on" : ""}`} data-testid={`sn-dest-${n.id}`} onClick={() => setTo(n.id)} aria-pressed={to === n.id}>
                    <span>{n.label[lang]}</span><span className="tiny muted">{t(lang, "vf_" + n.verification)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card stack-sm">
          <h2 className="small-h">{t(lang, "fd_to")}: {to ? m.nodes.find((n) => n.id === to)?.label[lang] : t(lang, "fd_choose_dest")}</h2>
          {!at && <p className="small" data-testid="sn-need-location">{t(lang, "loc_choose")}</p>}
          <ProfilePicker lang={lang} value={profile} onChange={setProfile} />
          {err && <p className="error small">{err}</p>}
          {r && <RouteView r={r.route} lang={lang} />}
          {r && r.alternatives.length > 0 && (
            <details className="small"><summary>{t(lang, "rt_alts")}</summary>
              <ul className="plain">{r.alternatives.map((a, i) => <li key={i}>{t(lang, "rp_" + a.profile)}: {a.found ? t(lang, "rt_summary", { lo: String(a.minutes_low), hi: String(a.minutes_high), m: String(a.distance_m) }) + ` · ${t(lang, "rt_stairs", { n: String(a.stairs) })} · ${t(lang, "rt_lifts", { n: String(a.lifts) })}` : t(lang, "rt_none")}</li>)}</ul>
            </details>
          )}
        </section>
      </div>
      <StationMap map={m} path={r?.route.path ?? []} lang={lang} start={at} end={to} />
      <Details map={m} lang={lang} />
    </div>
  );
}
