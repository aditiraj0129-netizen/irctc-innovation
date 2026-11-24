// Turns the backend's cause-and-effect trace (codes + numbers) into plain sentences. Translation only:
// every number comes from the backend graph.
import type { Lang, TraceStep } from "./api";
import { duration, time } from "./format";
import { t } from "./i18n";

export type StationNames = Record<string, { en: string; hi: string }>;

export function traceSentence(s: TraceStep, lang: Lang, names: StationNames): string {
  const d = s.data || {};
  const stn = (c?: string) => (c ? names[c]?.[lang] ?? c : "");
  const late = d.must_arrive_by && d.margin_minutes != null ? duration(-d.margin_minutes, lang) : "";
  return t(lang, "tr_" + s.code, {
    train: d.train ?? d.next_train ?? "", delay: d.delay_minutes != null ? duration(d.delay_minutes, lang) : "",
    station: stn(d.station), time: time(d.expected_arrival), margin: d.margin_minutes != null ? duration(d.margin_minutes, lang) : "",
    req: d.required_minutes != null ? duration(d.required_minutes, lang) : "", must: time(d.must_arrive_by), late,
    leg: String(d.leg ?? ""), from_leg: String(d.from_leg ?? ""), age: d.age_minutes != null ? duration(d.age_minutes, lang) : "",
  });
}

export function traceTone(code: string): "bad" | "warn" | "" {
  if (["CONNECTION_BROKEN", "LEG_LIKELY_MISSED", "DOWNSTREAM_LEG_UNREACHABLE", "TRAIN_CANCELLED", "TICKET_NOT_CONFIRMED", "RECOVERY_NEEDED"].includes(code)) return "bad";
  if (["TRAIN_DELAYED", "CONNECTION_AT_RISK", "CONNECTION_TIGHT", "DATA_STALE"].includes(code)) return "warn";
  return "";
}

export function namesFromJourney(legs: { from: { code: string; en: string; hi: string }; to: { code: string; en: string; hi: string } }[]): StationNames {
  const n: StationNames = {};
  for (const l of legs) { n[l.from.code] = l.from; n[l.to.code] = l.to; }
  return n;
}
