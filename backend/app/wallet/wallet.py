"""Passenger Rights Wallet.

One place for every money right on this journey: what you paid, what the
rules say you could get back, which rule that is, the deadline, and the claim
status. The rules engine is the only source of amounts. Claim progress
(filed / approved / received) is only what the PASSENGER reports; we never infer it.

The lifecycle keeps estimates and outcomes clearly apart:
ESTIMATE -> ELIGIBLE_TO_FILE -> FILED -> APPROVED -> RECEIVED (or REJECTED)
AUTOMATIC_DUE -> RECEIVED
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.domain.models import Event, Journey
from app.plan.models import Plan
from app.rules.engine import cancellation_refund
from app.rules.models import Decision, Outcome
from app.plan.service import registry


class Stage(str, Enum):
    ESTIMATE = "ESTIMATE"                      # what cancelling now WOULD return
    ELIGIBLE_TO_FILE = "ELIGIBLE_TO_FILE"      # a TDR can be filed; refund not decided
    AUTOMATIC_DUE = "AUTOMATIC_DUE"            # the rules say it is refunded automatically
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    FILED = "FILED"                            # reported by the passenger
    APPROVED = "APPROVED"                      # reported by the passenger
    RECEIVED = "RECEIVED"                      # reported by the passenger
    REJECTED = "REJECTED"                      # reported by the passenger


USER_REPORTED = {Stage.FILED, Stage.APPROVED, Stage.RECEIVED, Stage.REJECTED}
ALLOWED_NEXT = {
    Stage.ELIGIBLE_TO_FILE: {Stage.FILED},
    Stage.FILED: {Stage.APPROVED, Stage.REJECTED},
    Stage.APPROVED: {Stage.RECEIVED},
    Stage.AUTOMATIC_DUE: {Stage.RECEIVED},
}


class RuleInfo(BaseModel):
    rule_ids: list[str]
    rule_set_id: str | None
    rule_version: str | None
    rule_name: str | None
    applies_to: list[str]
    effective_from: str | None
    legal_status: str | None
    source_title: str | None
    source_url: str | None
    last_verified: str | None
    unresolved: list[str]


class RightItem(BaseModel):
    id: str
    leg_seq: int
    kind: str                          # CANCELLATION, TDR_LATE_RUNNING, TDR_MISSED_CONNECTION, WL_AFTER_CHART, ...
    ticket_amount_paise: int
    estimated_refund_paise: int
    deduction_paise: int
    estimate_only: bool = True         # always true: these are estimates under the rules, not payments
    if_approved: bool = False
    stage: Stage
    rule_stage: Stage                  # what the rules say, before any passenger report
    deadline: datetime | None = None
    minutes_left: int | None = None
    deadline_unverified: bool = False
    rule: RuleInfo
    actions_needed: list[str] = Field(default_factory=list)


class HistoryEntry(BaseModel):
    at: datetime
    kind: str                          # EVENT, ACTION, CLAIM_UPDATE
    detail: dict


class Wallet(BaseModel):
    journey_id: str
    now: datetime
    total_paid_paise: int
    best_estimate_paise: int           # sum of the best available estimate per leg; NOT a promise
    best_estimate_needs_approval: bool
    items: list[RightItem]
    history: list[HistoryEntry]
    disclaimer: str = "ESTIMATES_NOT_GUARANTEED"
    data_label: str = "SIMULATED"


def _rule(d: Decision) -> RuleInfo:
    return RuleInfo(rule_ids=d.rule_ids, rule_set_id=d.rule_set_id, rule_version=d.rule_version,
                    rule_name=d.rule_name, applies_to=[c.value for c in d.applies_to_categories],
                    effective_from=d.effective_from.isoformat() if d.effective_from else None,
                    legal_status=d.legal_status.value if d.legal_status else None, source_title=d.source_title,
                    source_url=d.source_url, last_verified=d.last_verified.isoformat() if d.last_verified else None,
                    unresolved=d.unresolved)


def _stage(d: Decision) -> Stage:
    return {Outcome.REFUND_ON_CANCEL: Stage.ESTIMATE, Outcome.NO_REFUND: Stage.NOT_ELIGIBLE,
            Outcome.AUTO_REFUND: Stage.AUTOMATIC_DUE, Outcome.ELIGIBLE_TO_FILE_TDR: Stage.ELIGIBLE_TO_FILE,
            Outcome.NOT_ELIGIBLE: Stage.NOT_ELIGIBLE, Outcome.NEEDS_VERIFICATION: Stage.NEEDS_VERIFICATION,
            Outcome.NOT_MODELLED: Stage.NEEDS_VERIFICATION}[d.outcome]


ACTIONS = {
    Stage.ESTIMATE: ["CANCEL_ONLY_IF_YOU_WILL_NOT_TRAVEL"],
    Stage.ELIGIBLE_TO_FILE: ["FILE_TDR_BEFORE_DEADLINE", "KEEP_TDR_REFERENCE"],
    Stage.AUTOMATIC_DUE: ["NO_ACTION_NEEDED", "CHECK_ORIGINAL_PAYMENT_METHOD"],
    Stage.NEEDS_VERIFICATION: ["CHECK_OFFICIAL_CHANNEL"],
    Stage.FILED: ["TRACK_TDR_STATUS_ON_IRCTC"],
    Stage.APPROVED: ["CHECK_ORIGINAL_PAYMENT_METHOD"],
    Stage.REJECTED: ["CONTACT_RAILMADAD_OR_139"],
}


def build_wallet(journey: Journey, events: list[Event], now: datetime, plans: list[Plan],
                 claims: list[dict], actions: list[dict]) -> Wallet:
    items: dict[str, RightItem] = {}

    def add(item_id: str, seq: int, d: Decision, unverified_deadline: bool = False):
        leg = journey.legs[seq - 1]
        st = _stage(d)
        refund = d.refund_paise if st in (Stage.ESTIMATE, Stage.ELIGIBLE_TO_FILE, Stage.AUTOMATIC_DUE) else 0
        items[item_id] = RightItem(
            id=item_id, leg_seq=seq, kind=d.kind, ticket_amount_paise=leg.ticket.total_fare_paise,
            estimated_refund_paise=refund, deduction_paise=d.deduction_paise,
            if_approved=d.outcome == Outcome.ELIGIBLE_TO_FILE_TDR, stage=st, rule_stage=st, deadline=d.deadline,
            minutes_left=int((d.deadline - now).total_seconds() // 60) if d.deadline else None,
            deadline_unverified=unverified_deadline, rule=_rule(d), actions_needed=list(ACTIONS.get(st, [])))

    # Rights coming out of the current plans (TDR, automatic refunds, cancellation)
    for p in plans:
        for d in p.decisions:
            seq = p.decision_leg
            add(f"{d.kind}:{seq}", seq, d, p.deadline_unverified and d.kind == "TDR_MISSED_CONNECTION")

    # Always show what cancelling each not-yet-departed leg would return now (an estimate)
    for leg in journey.legs:
        key = f"CANCELLATION:{leg.seq}"
        auto = any(i.leg_seq == leg.seq and i.stage == Stage.AUTOMATIC_DUE for i in items.values())
        if key not in items and not auto and now < leg.scheduled_departure:
            try:
                add(key, leg.seq, cancellation_refund(leg.ticket, now, registry()))
            except Exception:
                pass

    # Apply what the passenger reported (only valid transitions)
    for c in claims:
        it = items.get(c["item_id"])
        if it is None:
            continue
        new = Stage(c["status"])
        if new in ALLOWED_NEXT.get(it.stage, set()):
            it.stage = new
            it.actions_needed = list(ACTIONS.get(new, []))

    history = [HistoryEntry(at=e.observed_at, kind="EVENT",
                            detail={"train_no": e.train_no, "type": e.type.value, "delay_minutes": e.delay_minutes,
                                    "chart_status": e.chart_status.value if e.chart_status else None,
                                    "source": e.source.value})
               for e in events if e.observed_at <= now]
    history += [HistoryEntry(at=datetime.fromisoformat(a["at"]), kind="ACTION", detail=a) for a in actions]
    history += [HistoryEntry(at=datetime.fromisoformat(c["at"]), kind="CLAIM_UPDATE", detail=c) for c in claims]
    history.sort(key=lambda h: h.at)

    best, approval = 0, False
    for leg in journey.legs:
        cand = [i for i in items.values() if i.leg_seq == leg.seq and i.stage != Stage.NOT_ELIGIBLE]
        if cand:
            b = max(cand, key=lambda i: i.estimated_refund_paise)
            best += b.estimated_refund_paise
            approval = approval or b.if_approved
    return Wallet(journey_id=journey.id, now=now, total_paid_paise=sum(l.ticket.total_fare_paise for l in journey.legs),
                  best_estimate_paise=best, best_estimate_needs_approval=approval,
                  items=sorted(items.values(), key=lambda i: (i.leg_seq, i.kind)), history=history)


def valid_transition(wallet: Wallet, item_id: str, status: str) -> bool:
    it = next((i for i in wallet.items if i.id == item_id), None)
    try:
        st = Stage(status)
    except ValueError:
        return False
    return it is not None and st in USER_REPORTED and st in ALLOWED_NEXT.get(it.stage, set())


def export_text(w: Wallet, lang: str = "en") -> str:
    """Plain-text summary the passenger can save or share. Deterministic."""
    def rs(p: int) -> str:
        return f"Rs {p // 100:,}"
    lines = ["Agla Kadam: journey rights summary (SIMULATED DATA, not an official document)",
             f"Journey: {w.journey_id}   Generated: {w.now:%d %b %Y %H:%M} IST",
             f"Total paid: {rs(w.total_paid_paise)}",
             f"Best estimate under the rules: {rs(w.best_estimate_paise)}"
             + (" (needs TDR approval)" if w.best_estimate_needs_approval else ""),
             "Estimates are not guaranteed. A TDR refund is decided by the Zonal Railway.", ""]
    for i in w.items:
        lines.append(f"- Leg {i.leg_seq} | {i.kind} | stage: {i.stage.value} | estimate: {rs(i.estimated_refund_paise)}"
                     + (" if approved" if i.if_approved else "")
                     + (f" | deadline: {i.deadline:%d %b %H:%M}" if i.deadline else "")
                     + (" (deadline unverified)" if i.deadline_unverified else ""))
        lines.append(f"  Rule {i.rule.rule_set_id} v{i.rule.rule_version} ({i.rule.legal_status}), effective "
                     f"{i.rule.effective_from}; source: {i.rule.source_title}"
                     + (f"; UNRESOLVED: {', '.join(i.rule.unresolved)}" if i.rule.unresolved else ""))
    lines += ["", "History:"]
    lines += [f"  {h.at:%d %b %H:%M}  {h.kind}  {h.detail}" for h in w.history]
    lines += ["", "Help: Rail enquiry 139 | Railway security 182 | Cyber fraud 1930"]
    return "\n".join(lines)
