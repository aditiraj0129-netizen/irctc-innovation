// Small API client. All railway data from the backend is SIMULATED.
export type Lang = "en" | "hi";
export type Priority = "time" | "money" | "risk" | "transfers" | "family";

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
  transfers?: TransferCheck[]; worst_transfer?: string | null; changes?: number;
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
  recommendation: Recommendation | null; profile: Profile;
}

// ---------- upgrade: platform features ----------
export interface Profile { walking_speed: "normal" | "slow"; step_free: boolean; senior: boolean }
export interface Recommendation {
  plan_id: string; plan_kind: string; priority: Priority; why: string[];
  comparisons: { plan_id: string; plan_kind: string; arrival_diff_minutes: number | null; money_diff_paise: number; points: string[] }[];
  counterfactuals: { scenario: string; effect: string; detail: Record<string, number> }[];
}
export interface TransferCheck {
  station: string; arrive: string; depart: string; gap_minutes: number; required_minutes: number;
  margin_minutes: number; cls: "COMFORTABLE" | "TIGHT" | "HIGH_RISK" | "NOT_FEASIBLE"; complexity: string; estimate_label: string;
}
export interface TwinLeg {
  seq: number; train_no: string; train_name: string; from_stn: string; to_stn: string;
  scheduled_departure: string; scheduled_arrival: string; expected_departure: string; expected_arrival: string;
  delay_minutes: number; ticket_status: string; state: string; affected: boolean; affected_by: string[];
  info: { last_update: string | null; age_minutes: number | null; freshness: "FRESH" | "STALE" | "NONE"; source: string };
}
export interface Twin {
  journey_id: string; now: string; status: "ON_TRACK" | "DISRUPTED" | "BROKEN" | "COMPLETED"; legs: TwinLeg[];
  transfers: { from_seq: number; to_seq: number; check: TransferCheck; latest_safe_arrival: string }[];
  scheduled_final_arrival: string; expected_final_arrival: string | null; delay_at_destination_minutes: number | null;
  affected_segments: number[]; unaffected_segments: number[]; data_label: string;
}
export interface Outcome {
  id: string; applicable: boolean; not_applicable_reason: string | null; plan_id: string | null; plan_kind: string | null;
  travels: boolean; arrival: string | null; arrival_diff_minutes: number | null; money_back_paise: number;
  money_back_if_approved: boolean; money_lost_paise: number; needs_new_ticket: boolean; rule_ids: string[];
  deadline: string | null; minutes_to_deadline: number | null; changes: number; connection_risk: string | null;
  confidence: "HIGH" | "MEDIUM" | "LOW"; confidence_reasons: string[]; pros: string[]; cons: string[];
  lost_options: string[]; assumptions: string[];
}
export interface WhatIf { now: string; priority: Priority; delay_increase_minutes: number; wait_minutes: number; data_label: string; outcomes: Outcome[] }
export interface RuleInfo {
  rule_ids: string[]; rule_set_id: string | null; rule_version: string | null; rule_name: string | null; applies_to: string[];
  effective_from: string | null; legal_status: string | null; source_title: string | null; source_url: string | null;
  last_verified: string | null; unresolved: string[];
}
export interface WalletItem {
  id: string; leg_seq: number; kind: string; ticket_amount_paise: number; estimated_refund_paise: number; deduction_paise: number;
  estimate_only: boolean; if_approved: boolean; stage: string; rule_stage: string; deadline: string | null; minutes_left: number | null;
  deadline_unverified: boolean; rule: RuleInfo; actions_needed: string[];
}
export interface Wallet {
  journey_id: string; now: string; total_paid_paise: number; best_estimate_paise: number; best_estimate_needs_approval: boolean;
  items: WalletItem[]; history: { at: string; kind: string; detail: Record<string, unknown> }[]; disclaimer: string; data_label: string;
}
export interface Resilience {
  score: number; label: string; method_note: string; main_risks: string[]; suggestions: string[];
  factors: { id: string; weight: number; score: number; value: string; explanation: string }[];
}
export interface OfflineCard {
  journey_id: string; pnr_label: string; generated_at: string; stale_after: string; data_label: string; status: string;
  legs: { seq: number; train_no: string; train_name: string; from: Station; to: Station; scheduled_departure: string;
    scheduled_arrival: string; expected_arrival: string; delay_minutes: number; state: string; info_last_update: string | null }[];
  transfers: { station: Station; class: string; margin_minutes: number }[];
  plans: { rank: number; kind: string; travels: boolean; arrival: string | null; deadline: string | null; money_back_paise: number;
    if_approved: boolean; needs_new_ticket: boolean; rides: { train_no: string; train_name: string; from: string; to: string; dep: string; arr: string }[] }[];
  rights: { kind: string; stage: string; estimated_refund_paise: number; if_approved: boolean; deadline: string | null }[];
  rules: { rule_set_id: string | null; rule_version: string | null; legal_status: string | null; unresolved: string[] }[];
  instructions: string[]; emergency: { id: string; number: string }[];
}
export interface AssistantReply { intent: string; intent_source: string; lang: Lang; answer: string; facts: string[]; rule_ids: string[]; answer_source: string; data_label: string }
export interface Report {
  id: number; station: string; type: string; train_no: string | null; note: string | null; first_seen: string; last_seen: string;
  expires_at: string; reporters: number; confidence: string; conflicting: boolean; label: string; affects_recommendations: boolean; simulated_seed: boolean;
}
export interface MemberLine { member_id: string; label: { en: string; hi: string }; journey_id: string; travels: boolean; trains: string[]; arrival: string | null; status: string }
export interface GroupOption {
  id: string; kind: string; keeps_together: boolean; suitability: "GROUP" | "INDIVIDUAL"; members: MemberLine[];
  money_back_paise: number; money_lost_paise: number; money_needs_approval: boolean; new_tickets_needed: number;
  arrival_last: string | null; arrival_spread_minutes: number; changes: number; senior_friendly: boolean; step_free_ok: boolean;
  warnings: string[]; rule_ids: string[]; rank: number;
}
// ---------- next round: graph, recovery, dashboard, copilot ----------
export interface GraphNode {
  id: string; kind: "DEPART" | "ARRIVE"; leg_seq: number; station: string; train_no: string; scheduled: string;
  expected: string; delay_minutes: number; state: "OK" | "DELAYED" | "AT_RISK" | "BROKEN" | "DONE";
  freshness: "FRESH" | "STALE" | "NONE"; last_update: string | null;
}
export interface GraphEdge {
  id: string; kind: "RIDE" | "TRANSFER"; source: string; target: string; required_minutes: number | null;
  gap_minutes: number | null; margin_minutes: number | null; transfer_class: TransferCheck["cls"] | null; state: GraphNode["state"];
}
export interface TraceStep { code: string; node: string | null; edge: string | null; data: Record<string, any> }
export interface JourneyGraph {
  journey_id: string; now: string; status: Twin["status"]; nodes: GraphNode[]; edges: GraphEdge[]; trace: TraceStep[];
  broken_from_leg: number | null; data_label: string;
}
export interface Urgency { level: "NOW" | "SOON" | "LATER" | "WATCH" | "NONE" | "UNKNOWN"; decide_by: string | null; minutes_left: number | null }
export interface NextStep {
  plan_id: string; plan_kind: string; rank: number; travels: boolean; arrival: string | null; money_back_paise: number;
  money_back_if_approved: boolean; deadline: string | null; deadline_unverified: boolean; trains: string[]; rule_ids: string[];
}
export interface Recovery {
  journey: Assessment["journey"]; journey_id: string; now: string; situation: string; graph: JourneyGraph;
  what_happened: { train_no: string; type: string; delay_minutes: number | null; observed_at: string; source: string }[];
  last_updated: string | null; data_fresh: boolean; affected_legs: number[]; consequence: Record<string, any>;
  urgency: Urgency; next_steps: NextStep[];
  rights: { kind: string; stage: string; estimated_refund_paise: number; if_approved: boolean; deadline: string | null;
    rule_id: string | null; legal_status: string | null; unresolved: string[] }[];
  recommendation: Recommendation | null; data_label: string;
}
export interface DashJourney {
  journey: Assessment["journey"]; now: string; status: Twin["status"]; situation: string; urgency: Urgency; data_fresh: boolean;
  last_updated: string | null; next_departure: GraphNode | null; consequence: Record<string, any>; top_step: NextStep | null; profile: Profile;
}
export interface Citation { id: string; title: string; source_url: string | null; effective_from: string; version: string; status: string; unresolved: string[] }
export interface CopilotReply {
  intent: string; planner: string; answer: string; answer_source: string; clarify: boolean;
  tool_calls: { tool: string; args: Record<string, unknown>; ok: boolean; error: string | null }[];
  citations: Citation[]; next_actions: { key: string; route: string | null; tel: string | null }[];
  no_reliable_source: boolean; warnings: string[]; data_label: string;
}

export interface GroupView {
  group_id: string; name: { en: string; hi: string }; now: string; group_profile: Profile; divergence: string[];
  timeline: MemberLine[]; options: GroupOption[];
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const base = (import.meta as any).env?.VITE_API_URL ?? "";
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  // Presenter token (only if the deployment sets DEMO_TOKEN). Kept for this browser tab only.
  if (path.startsWith("/api/demo/")) {
    try { const tk = window.sessionStorage.getItem("demoToken"); if (tk) headers["X-Demo-Token"] = tk; } catch { /* ignore */ }
  }
  const r = await fetch(base + path, { headers, ...init });
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail ?? detail; } catch { /* ignore */ }
    throw new Error(typeof detail === "string" ? detail : "REQUEST_FAILED");
  }
  return r.json() as Promise<T>;
}

export const api = {
  scenarios: () => req<{ id: string; pnr: string; title: { en: string; hi: string }; group: string | null }[]>("/api/scenarios"),
  addJourney: (pnr: string) => req<JourneyOut>("/api/journeys", { method: "POST", body: JSON.stringify({ pnr }) }),
  assessment: (id: string, priority: Priority, lang: Lang) =>
    req<Assessment>(`/api/journeys/${id}/assessment?priority=${priority}&lang=${lang}`),
  action: (id: string, plan: Plan) =>
    req(`/api/journeys/${id}/actions`, { method: "POST", body: JSON.stringify({ plan_id: plan.id, plan_kind: plan.kind }) }),
  reset: (id: string) => req(`/api/demo/${id}/reset`, { method: "POST" }),
  clock: (id: string, advance_minutes: number) =>
    req(`/api/demo/${id}/clock`, { method: "POST", body: JSON.stringify({ advance_minutes }) }),
  event: (id: string, body: object) => req(`/api/demo/${id}/events`, { method: "POST", body: JSON.stringify(body) }),
  twin: (id: string) => req<Twin>(`/api/journeys/${id}/twin`),
  whatif: (id: string, priority: Priority, delay_increase: number, wait_minutes: number) =>
    req<WhatIf>(`/api/journeys/${id}/whatif?priority=${priority}&delay_increase=${delay_increase}&wait_minutes=${wait_minutes}`),
  wallet: (id: string) => req<Wallet>(`/api/journeys/${id}/wallet`),
  claim: (id: string, item_id: string, status: string) =>
    req(`/api/journeys/${id}/wallet/claims`, { method: "POST", body: JSON.stringify({ item_id, status }) }),
  exportUrl: (id: string) => `${(import.meta as any).env?.VITE_API_URL ?? ""}/api/journeys/${id}/wallet/export`,
  prefs: (id: string) => req<{ profile: Profile; priority: Priority }>(`/api/journeys/${id}/preferences`),
  savePrefs: (id: string, body: { profile: Profile; priority: Priority }) =>
    req(`/api/journeys/${id}/preferences`, { method: "PUT", body: JSON.stringify(body) }),
  resilience: (id: string) => req<Resilience>(`/api/journeys/${id}/resilience`),
  offlineCard: (id: string) => req<OfflineCard>(`/api/journeys/${id}/offline-card`),
  ask: (id: string, text: string, lang: Lang) =>
    req<AssistantReply>(`/api/journeys/${id}/assistant`, { method: "POST", body: JSON.stringify({ text, lang }) }),
  reports: (id: string) => req<Report[]>(`/api/journeys/${id}/community/reports`),
  report: (id: string, body: object) => req<Report>(`/api/journeys/${id}/community/reports`, { method: "POST", body: JSON.stringify(body) }),
  groups: () => req<{ id: string; name: { en: string; hi: string }; members: number }[]>("/api/groups"),
  group: (gid: string, priority: Priority) => req<GroupView>(`/api/groups/${gid}?priority=${priority}`),
  graph: (id: string) => req<JourneyGraph>(`/api/v1/journeys/${id}/graph`),
  recovery: (id: string) => req<Recovery>(`/api/v1/journeys/${id}/recovery`),
  dashboard: (ids: string[]) => req<{ journeys: DashJourney[] }>(`/api/v1/dashboard?ids=${encodeURIComponent(ids.join(","))}`),
  copilot: (id: string, message: string, lang: Lang, history: { role: "user" | "assistant"; text: string }[]) =>
    req<CopilotReply>(`/api/v1/journeys/${id}/copilot`, { method: "POST", body: JSON.stringify({ message, lang, history: history.slice(-6) }) }),
  knowledge: () => req<{ documents: (Omit<Citation, "unresolved"> & { applies_to: string[]; unresolved: string[]; publisher: string })[]; chunks: number }>("/api/v1/knowledge/sources"),
};

// ---------- PREDICT -> DECIDE -> RECOVER ----------
export interface DecisionCard {
  key: "CONTINUE" | "CANCEL" | "OTHER_TRAIN" | "UNRESERVED" | "BUS" | "NEXT_SERVICE";
  status: "AVAILABLE" | "NOT_APPLICABLE" | "DATA_MISSING" | "NONE_FOUND" | "NOT_CONFIGURED";
  recommended: boolean; meaning: string; outcome: Record<string, any>; money: Record<string, any>; risk: string | null;
  deadline: string | null; deadline_kind: string | null; next_action: Record<string, any>; items: Record<string, any>[];
  missing: string[]; reason: string | null;
}
export interface MoneyRow {
  key: string; at: string | null; applicable: boolean; reason: string | null; money_back_paise: number | null;
  charge_paise: number | null; certainty: string; deadline: string | null; travel_outcome: string; risk: string | null;
  next_step: string; rule_ids: string[]; legal_status: string | null;
}
export interface DecisionView {
  journey: Assessment["journey"]; journey_id: string; now: string; header: Record<string, any>;
  prediction: Record<string, any> | null; connection: Record<string, any> | null; recovery: Record<string, any>;
  cards: DecisionCard[]; money: MoneyRow[]; claims: Record<string, any>; recommendation: Record<string, any>;
  data_label: string;
}
export const decideApi = {
  decision: (id: string, priority: Priority = "time") => req<DecisionView>(`/api/v1/journeys/${id}/decision?priority=${priority}`),
};
