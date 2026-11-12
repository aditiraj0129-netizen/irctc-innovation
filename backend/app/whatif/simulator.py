"""What-If Decision Simulator.

Every scenario re-runs the SAME deterministic pipeline (detector -> rules ->
route search -> ranker) with one thing changed: the clock, a hypothetical delay,
or the action taken. No AI is involved, and nothing is estimated by a model.
Hypothetical events are never stored and are labelled as hypothetical.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field

from app.domain.models import Event, EventSource, EventType, Journey
from app.plan.models import Plan, PlanKind
from app.plan.ranker import Priority
from app.plan.service import assess, registry
from app.plan.transfer import PassengerProfile, TransferClass
from app.rules.engine import cancellation_refund
from app.rules.models import Outcome, TicketStatus
from app.twin.twin import LegState, build_twin


class ScenarioId(str, Enum):
    BEST_NOW = "BEST_NOW"
    WAIT_30 = "WAIT_30"
    DELAY_GROWS = "DELAY_GROWS"
    CANCEL_NOW = "CANCEL_NOW"
    TAKE_ALTERNATIVE = "TAKE_ALTERNATIVE"
    MISS_CONNECTION = "MISS_CONNECTION"
    ONE_CHANGE_ROUTE = "ONE_CHANGE_ROUTE"


class Outcome_(BaseModel):
    id: ScenarioId
    applicable: bool = True
    not_applicable_reason: str | None = None
    plan_id: str | None = None
    plan_kind: PlanKind | None = None
    travels: bool = False
    arrival: datetime | None = None
    arrival_diff_minutes: int | None = None        # vs the booked (scheduled) final arrival
    money_back_paise: int = 0
    money_back_if_approved: bool = False
    money_lost_paise: int = 0
    needs_new_ticket: bool = False
    rule_ids: list[str] = Field(default_factory=list)
    deadline: datetime | None = None
    minutes_to_deadline: int | None = None
    changes: int = 0
    connection_risk: TransferClass | None = None
    confidence: str = "HIGH"                       # HIGH / MEDIUM / LOW, relative; all data is simulated
    confidence_reasons: list[str] = Field(default_factory=list)
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    lost_options: list[str] = Field(default_factory=list)   # options that disappear in this scenario
    assumptions: list[str] = Field(default_factory=list)


class WhatIfResult(BaseModel):
    now: datetime
    priority: Priority
    delay_increase_minutes: int
    wait_minutes: int = 30
    data_label: str = "SIMULATED"
    outcomes: list[Outcome_]


def _ride_key(p: Plan) -> str:
    return " + ".join(f"{r.train_no}@{r.dep.isoformat()}" for r in p.rides) or p.kind.value


def _from_plan(sid: ScenarioId, p: Plan, now: datetime, booked_final: datetime, assumptions: list[str]) -> Outcome_:
    o = Outcome_(id=sid, plan_id=p.id, plan_kind=p.kind, travels=p.travels, arrival=p.arrival,
                 arrival_diff_minutes=int((p.arrival - booked_final).total_seconds() // 60) if p.arrival else None,
                 money_back_paise=p.money_back_paise, money_back_if_approved=p.money_back_if_approved,
                 money_lost_paise=p.money_lost_paise, needs_new_ticket=p.needs_new_ticket,
                 rule_ids=[r for d in p.decisions for r in d.rule_ids], deadline=p.deadline,
                 minutes_to_deadline=int((p.deadline - now).total_seconds() // 60) if p.deadline else None,
                 changes=p.changes, connection_risk=p.worst_transfer, assumptions=list(assumptions))
    _confidence(o, p, assumptions)
    return o


def _confidence(o: Outcome_, p: Plan | None, assumptions: list[str]) -> None:
    reasons = ["SIMULATED_DATA"]
    level = 0                                   # 0 HIGH, 1 MEDIUM, 2 LOW
    if p is not None and any(d.unresolved for d in p.decisions):
        reasons.append("RULE_VERIFICATION_PENDING"); level = max(level, 1)
    if p is not None and p.deadline_unverified:
        reasons.append("DEADLINE_UNVERIFIED"); level = max(level, 1)
    if o.needs_new_ticket:
        reasons.append("SEATS_NOT_CHECKED"); level = max(level, 1)
    if o.money_back_if_approved:
        reasons.append("REFUND_NEEDS_APPROVAL"); level = max(level, 1)
    if "HYPOTHETICAL_EVENT" in assumptions or "IF_NOTHING_ELSE_CHANGES" in assumptions:
        reasons.append("HYPOTHETICAL"); level = max(level, 1)
    if p is not None and p.kind == PlanKind.USE_OFFICIAL_CHANNEL:
        reasons.append("NO_SAFE_ADVICE"); level = 2
    if o.connection_risk in (TransferClass.HIGH_RISK,):
        reasons.append("HIGH_RISK_TRANSFER"); level = max(level, 1)
    o.confidence = ["HIGH", "MEDIUM", "LOW"][level]
    o.confidence_reasons = reasons


def _hypo_delay(train_no: str, minutes: int, at: datetime) -> Event:
    return Event(train_no=train_no, type=EventType.DELAY, delay_minutes=min(minutes, 24 * 60), observed_at=at,
                 source=EventSource.SIMULATED)


def _pros_cons(o: Outcome_, ref: Outcome_ | None) -> None:
    if o.travels:
        o.pros.append("YOU_STILL_TRAVEL")
    else:
        o.cons.append("YOU_DO_NOT_TRAVEL")
    if o.money_back_paise > 0:
        (o.cons if o.money_back_if_approved else o.pros).append(
            "REFUND_IF_APPROVED" if o.money_back_if_approved else "AUTOMATIC_OR_RULE_REFUND")
    if o.money_lost_paise > 0:
        o.cons.append("MONEY_LOST")
    if o.needs_new_ticket:
        o.cons.append("NEW_TICKET_NEEDED_SEATS_NOT_CHECKED")
    if o.changes:
        o.cons.append("CHANGE_OF_TRAIN")
    if o.connection_risk in (TransferClass.TIGHT, TransferClass.HIGH_RISK):
        o.cons.append("TIGHT_OR_RISKY_TRANSFER")
    if o.minutes_to_deadline is not None and o.minutes_to_deadline < 60:
        o.cons.append("DEADLINE_UNDER_1_HOUR")
    if ref and ref.arrival and o.arrival and o.id != ref.id:
        d = int((o.arrival - ref.arrival).total_seconds() // 60)
        if d < 0:
            o.pros.append("ARRIVES_EARLIER_THAN_BEST_NOW")
        elif d > 0:
            o.cons.append("ARRIVES_LATER_THAN_BEST_NOW")
    if o.lost_options:
        o.cons.append("SOME_OPTIONS_DISAPPEAR")


def simulate(journey: Journey, events: list[Event], now: datetime, priority: Priority = Priority.TIME,
             profile: PassengerProfile | None = None, delay_increase: int = 60, wait_minutes: int = 30) -> WhatIfResult:
    if not 1 <= delay_increase <= 600 or not 5 <= wait_minutes <= 720:
        raise ValueError("delay_increase must be 1-600 and wait_minutes 5-720")
    base = assess(journey, events, now, priority, profile)
    booked_final = journey.legs[-1].scheduled_arrival
    out: list[Outcome_] = []
    plans = base.plans
    twin = build_twin(journey, events, now, profile)
    current_keys = {_ride_key(p) for p in plans if p.rides}

    # 1. Best option right now
    best = _from_plan(ScenarioId.BEST_NOW, plans[0], now, booked_final, [])
    out.append(best)

    # 2. Wait N minutes (default 30; nothing else changes)
    later_t = now + timedelta(minutes=wait_minutes)
    # look ahead: treat data as still fresh (otherwise "stale" hides the answer)
    from app.plan.service import connections_for, plans_at
    _, later_plans = plans_at(journey, events, later_t, priority, connections_for(journey), assume_fresh=True,
                              profile=profile)
    w = _from_plan(ScenarioId.WAIT_30, later_plans[0], now, booked_final, ["IF_NOTHING_ELSE_CHANGES"])
    w.lost_options = sorted(current_keys - {_ride_key(p) for p in later_plans if p.rides})
    for p in plans:
        if p.deadline and p.deadline <= later_t and p.kind not in {q.kind for q in later_plans}:
            w.lost_options.append(p.kind.value)
    out.append(w)

    # 3. The delay gets worse (hypothetical)
    active = next((l for l in twin.legs if l.state not in (LegState.ARRIVED,)), twin.legs[-1])
    hypo = [*events, _hypo_delay(active.train_no, active.delay_minutes + delay_increase, now)]
    worse = assess(journey, hypo, now, priority, profile)
    d = _from_plan(ScenarioId.DELAY_GROWS, worse.plans[0], now, booked_final, ["HYPOTHETICAL_EVENT"])
    d.lost_options = sorted(current_keys - {_ride_key(p) for p in worse.plans if p.rides})
    out.append(d)

    # 4. Cancel now (the next leg that hasn't left yet)
    leg = next((l for l in journey.legs if twin.legs[l.seq - 1].state not in
                (LegState.ARRIVED, LegState.IN_TRANSIT)), None)
    if leg is None:
        out.append(Outcome_(id=ScenarioId.CANCEL_NOW, applicable=False, not_applicable_reason="ALL_TRAINS_DEPARTED"))
    elif twin.legs[leg.seq - 1].state == LegState.WAITLISTED:
        out.append(Outcome_(id=ScenarioId.CANCEL_NOW, applicable=False, not_applicable_reason="AUTO_REFUND_ALREADY_DUE"))
    elif twin.legs[leg.seq - 1].state == LegState.CANCELLED:
        out.append(Outcome_(id=ScenarioId.CANCEL_NOW, applicable=False, not_applicable_reason="TRAIN_ALREADY_CANCELLED"))
    else:
        dec = cancellation_refund(leg.ticket, now, registry())
        refund = dec.refund_paise if dec.outcome == Outcome.REFUND_ON_CANCEL else 0
        c = Outcome_(id=ScenarioId.CANCEL_NOW, travels=False, money_back_paise=refund,
                     money_lost_paise=leg.ticket.total_fare_paise - refund, rule_ids=dec.rule_ids,
                     plan_kind=PlanKind.CANCEL_NOW)
        _confidence(c, None, [])
        if dec.unresolved:
            c.confidence, c.confidence_reasons = "MEDIUM", [*c.confidence_reasons, "RULE_VERIFICATION_PENDING"]
        out.append(c)

    # 5. Take an alternative train
    alts = [p for p in plans if p.needs_new_ticket]
    if alts:
        a = min(alts, key=lambda p: p.arrival)
        out.append(_from_plan(ScenarioId.TAKE_ALTERNATIVE, a, now, booked_final, []))
    else:
        out.append(Outcome_(id=ScenarioId.TAKE_ALTERNATIVE, applicable=False,
                            not_applicable_reason="NO_ALTERNATIVE_NEEDED_OR_FOUND"))

    # 6. Miss the connecting train
    if len(journey.legs) < 2:
        out.append(Outcome_(id=ScenarioId.MISS_CONNECTION, applicable=False, not_applicable_reason="NO_CONNECTION"))
    else:
        t = twin.transfers[0]
        if t.check.margin_minutes < 0:
            m = _from_plan(ScenarioId.MISS_CONNECTION, plans[0], now, booked_final, [])
        else:
            first = twin.legs[0]
            needed = first.delay_minutes + t.check.margin_minutes + 1
            hypo2 = [*events, _hypo_delay(first.train_no, needed, now)]
            miss = assess(journey, hypo2, now, priority, profile)
            m = _from_plan(ScenarioId.MISS_CONNECTION, miss.plans[0], now, booked_final, ["HYPOTHETICAL_EVENT"])
            m.assumptions.append(f"FIRST_TRAIN_DELAY_{needed}_MIN")
        out.append(m)

    # 7. A route with exactly one change of train
    one = [p for p in plans if p.changes == 1]
    if one:
        out.append(_from_plan(ScenarioId.ONE_CHANGE_ROUTE, min(one, key=lambda p: p.arrival), now, booked_final, []))
    else:
        out.append(Outcome_(id=ScenarioId.ONE_CHANGE_ROUTE, applicable=False, not_applicable_reason="NO_ONE_CHANGE_ROUTE"))

    for o in out:
        if o.applicable:
            _pros_cons(o, best)
    return WhatIfResult(now=now, priority=priority, delay_increase_minutes=delay_increase, wait_minutes=wait_minutes,
                        outcomes=out)
