import { useState } from "react";
import { api, type GroupOption, type Lang, type Priority } from "../api";
import { dayTime, duration, rupees } from "../format";
import { t, tc } from "../i18n";
import { go } from "../router";
import { useLoad } from "../useLoad";

// Family Journey Guardian: one view for a group on more than one PNR. Labels only, no names.
export function FamilyScreen({ gid, lang }: { gid: string; lang: Lang }) {
  const [priority, setPriority] = useState<Priority>("family");
  const { data, error } = useLoad(() => api.group(gid, priority), [gid, priority], 5000);
  if (error && !data) return <p className="error" role="alert">{t(lang, "err_network")}</p>;
  if (!data) return <p className="muted">…</p>;
  const prof = data.group_profile;
  const needs = [prof.senior && t(lang, "fam_senior"), prof.step_free && t(lang, "fam_stepfree"), prof.walking_speed === "slow" && t(lang, "fam_slow")].filter(Boolean);
  return (
    <div className="stack">
      <button className="link" onClick={() => history.back()}>← {t(lang, "back")}</button>
      <h1>{t(lang, "fam_title")}</h1>
      <p className="small muted">{data.name[lang]} · {t(lang, "fam_help")}</p>
      {data.divergence.length > 0 && (
        <section className="alert alert-amber" role="alert" data-testid="divergence">
          {data.divergence.map((d) => <p key={d} className="alert-text">{tc(lang, "dv_", d)}</p>)}
        </section>
      )}
      {needs.length > 0 && <p className="small">{t(lang, "fam_needs")}: {needs.join(", ")}</p>}
      <ul className="plans" data-testid="family-timeline">
        {data.timeline.map((m) => (
          <li key={m.member_id} className="card row-between">
            <div><strong>{m.label[lang]}</strong><p className="small muted">{m.trains.join(" + ")} · {m.arrival ? dayTime(m.arrival) : "—"}</p></div>
            <button className="pill pill-soft link" onClick={() => go(`journey/${m.journey_id}`)}>{tc(lang, "ms_", m.status)}</button>
          </li>
        ))}
      </ul>
      <fieldset className="segmented" aria-label={t(lang, "priority")}>
        <legend className="small muted">{t(lang, "priority")}</legend>
        {(["family", "time", "money"] as Priority[]).map((p) => (
          <button key={p} aria-pressed={priority === p} data-testid={`fam-priority-${p}`} onClick={() => setPriority(p)}>{t(lang, "p_" + p)}</button>
        ))}
      </fieldset>
      <ol className="plans" data-testid="group-options">
        {data.options.map((o) => <GroupCard key={o.id} o={o} lang={lang} />)}
      </ol>
    </div>
  );
}

function GroupCard({ o, lang }: { o: GroupOption; lang: Lang }) {
  return (
    <li className={`card stack-sm ${o.rank === 1 ? "plan-top" : ""}`} data-testid={`group-${o.kind}`}>
      <div className="row-between">
        <span className="rank">#{o.rank}</span>
        <span className={`pill ${o.suitability === "GROUP" ? "pill-green" : "pill-amber"}`} data-testid="suitability">{tc(lang, "suit_", o.suitability)}</span>
      </div>
      <h3>{tc(lang, "g_", o.kind)}</h3>
      <p>
        {o.money_back_paise > 0 && <span className="amount ok">{rupees(o.money_back_paise)} {t(lang, "money_back")}</span>}
        {o.money_lost_paise > 0 && <span className="small con"> · {rupees(o.money_lost_paise)} {t(lang, "lost")}</span>}
        {o.money_needs_approval && <span className="small"> · {t(lang, "if_approved")}</span>}
      </p>
      <ul className="plain small">
        {o.members.map((m) => (
          <li key={m.member_id}>{m.label[lang]}: {tc(lang, "ms_", m.status)}{m.travels ? ` · ${m.trains.join(" + ")} · ${dayTime(m.arrival)}` : ""}</li>
        ))}
      </ul>
      <p className="small muted">
        {o.new_tickets_needed > 0 ? t(lang, "new_tickets", { n: String(o.new_tickets_needed) }) + " · " : ""}
        {o.keeps_together ? t(lang, "together") : o.members.every((m) => m.travels) ? t(lang, "spread", { m: duration(o.arrival_spread_minutes, lang) }) : ""}
      </p>
      {o.warnings.length > 0 && <ul className="plain small con">{o.warnings.map((w) => <li key={w}>! {tc(lang, "w_", w)}</li>)}</ul>}
      <p className="tiny mono muted">{t(lang, "rule")}: {o.rule_ids.join(", ") || "—"}</p>
    </li>
  );
}
