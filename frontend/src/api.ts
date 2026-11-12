// Small API client. All railway data from the backend is SIMULATED.
export type Lang = "en" | "hi";
export type Priority = "time" | "money" | "risk";

export interface Station { code: string; en: string; hi: string }
export interface LegOut {
  seq: number; train_no: string; train_name: string; from: Station; to: Station;
  scheduled_departure: string; scheduled_arrival: string; class: string; status: string;
  quota: string; category: string; passengers: number; fare_paise: number;
}
export interface JourneyOut {
  id: string; pnr_label: string; title: { en: string; hi: string }; linked_pnr: boolean;
  min_transfer_minutes: number; legs: LegOut[];
}
export interface Ride { train_no: string; train_name: string; from_stn: string; dep: string; to_stn: string; arr: string }
export interface Decision {
  kind: string; outcome: string; refund_paise: number; deduction_paise: number; deadline: string | null;
  rule_ids: string[]; rule_set_id: string | null; legal_status: "NOTIFIED" | "ANNOUNCED" | null;
  source_title: string | null; source_url: string | null; last_verified: string | null;
  approval_note: string | null; warnings: string[]; reason_key: string;
}
export interface Plan {
  id: string; kind: string; travels: boolean; arrival: string | null; rides: Ride[];
  money_back_paise: number; money_back_if_approved: boolean; money_lost_paise: number;
  needs_new_ticket: boolean; deadline: string | null; deadline_unverified: boolean;
  certainty: number; decisions: Decision[]; warnings: string[];
  reasons: { key: string; minutes?: number; paise?: number }[]; rank: number;
  explanation: { headline: string; body: string; source: string };
}
export interface Window {
  id: string; kind: string; start: string; end: string; amount_paise: number | null;
  if_approved: boolean; verified: boolean; status: "OPEN" | "UPCOMING" | "CLOSED";
}
export interface RightsClock {
  now: string; horizon_end: string; windows: Window[];
  next_drop: { at: string; from_paise: number; to_paise: number } | null;
  decision_deadline: string | null; then_plan_kind: string | null;
}
export interface Situation { type: string; leg_seq: number | null; train_no: string | null;
  delay_minutes: number | null; buffer_minutes: number | null; detail: Record<string, string> }
export interface Assessment {
  journey: JourneyOut; now: string; priority: Priority; lang: Lang; data_label: string; timetable_label: string;
  situation: Situation; situations: Situation[];
  live: Record<string, { delay_minutes: number; cancelled: boolean; departed: boolean; chart_status: string | null; last_update: string | null }>;
  plans: Plan[]; rights_clock: RightsClock; actions: { plan_id: string; plan_kind: string; at: string }[];
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const base = (import.meta as any).env?.VITE_API_URL ?? "";
  const r = await fetch(base + path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail ?? detail; } catch { /* ignore */ }
    throw new Error(typeof detail === "string" ? detail : "REQUEST_FAILED");
  }
  return r.json() as Promise<T>;
}

export const api = {
  scenarios: () => req<{ id: string; pnr: string; title: { en: string; hi: string } }[]>("/api/scenarios"),
  addJourney: (pnr: string) => req<JourneyOut>("/api/journeys", { method: "POST", body: JSON.stringify({ pnr }) }),
  assessment: (id: string, priority: Priority, lang: Lang) =>
    req<Assessment>(`/api/journeys/${id}/assessment?priority=${priority}&lang=${lang}`),
  action: (id: string, plan: Plan) =>
    req(`/api/journeys/${id}/actions`, { method: "POST", body: JSON.stringify({ plan_id: plan.id, plan_kind: plan.kind }) }),
  reset: (id: string) => req(`/api/demo/${id}/reset`, { method: "POST" }),
  clock: (id: string, advance_minutes: number) =>
    req(`/api/demo/${id}/clock`, { method: "POST", body: JSON.stringify({ advance_minutes }) }),
  event: (id: string, body: object) => req(`/api/demo/${id}/events`, { method: "POST", body: JSON.stringify(body) }),
};
