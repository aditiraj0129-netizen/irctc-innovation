"""Journey Recovery view: one answer to "what happened, what does it mean, what do I do, by when?".

Everything here is assembled from the deterministic engines (graph, detector, planner, rules, wallet).
Nothing is invented: when data is stale, the urgency is UNKNOWN and the only next step is the official channel.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.detect.detector import SituationType
from app.domain.models import Event, Journey
from app.graph.journey_graph import JourneyGraph, build_graph, minutes_between
from app.plan.counterfactual import Recommendation, recommend
from app.plan.ranker import Priority
from app.plan.service import assess
from app.plan.transfer import PassengerProfile
from app.twin.twin import Freshness
from app.wallet.wallet import build_wallet
from app.whatif.simulator import simulate


class EventOut(BaseModel):
    train_no: str
    type: str
    delay_minutes: int | None
    observed_at: datetime
    source: str


class Urgency(BaseModel):
    level: str     # NOW (<=60 min) | SOON (<=4 h) | LATER | WATCH (at risk, no decision yet) | NONE | UNKNOWN (stale)
    decide_by: datetime | None
    minutes_left: int | None


class NextStep(BaseModel):
    plan_id: str
    plan_kind: str
    rank: int
    travels: bool
    arrival: datetime | None
    money_back_paise: int
    money_back_if_approved: bool
    deadline: datetime | None
    deadline_unverified: bool
    trains: list[str]
    rule_ids: list[str]


class RightsLine(BaseModel):
    kind: str
    stage: str
    estimated_refund_paise: int
    if_approved: bool
    deadline: datetime | None
    rule_id: str | None
    legal_status: str | None
    unresolved: list[str]


class Recovery(BaseModel):
    journey_id: str
    now: datetime
    situation: str
    graph: JourneyGraph
    what_happened: list[EventOut]
    last_updated: datetime | None
    data_fresh: bool
    affected_legs: list[int]
    consequence: dict
    urgency: Urgency
    next_steps: list[NextStep]
    rights: list[RightsLine]
    recommendation: Recommendation | None
    data_label: str = "SIMULATED"


def _level(mins: int | None) -> str:
    if mins is None:
        return "NONE"
    return "NOW" if mins <= 60 else "SOON" if mins <= 240 else "LATER"


def build_recovery(journey: Journey, events: list[Event], now: datetime, priority: Priority = Priority.TIME,
                   profile: PassengerProfile | None = None) -> Recovery:
    graph = build_graph(journey, events, now, profile)
    r = assess(journey, events, now, priority, profile)
    sit = r.assessment.primary
    stale = sit.type == SituationType.STALE_DATA or any(n.freshness == Freshness.STALE for n in graph.nodes)
    mine = {l.train_no for l in journey.legs}
    happened = sorted((EventOut(train_no=e.train_no, type=e.type.value, delay_minutes=e.delay_minutes,
                                observed_at=e.observed_at, source=e.source.value)
                       for e in events if e.train_no in mine and e.observed_at <= now),
                      key=lambda e: e.observed_at, reverse=True)
    last = happened[0].observed_at if happened else None

    # consequence: numbers only, from the graph and the twin
    arr_nodes = [n for n in graph.nodes if n.kind.value == "ARRIVE"]
    final = arr_nodes[-1]
    transfer = next((e for e in graph.edges if e.kind.value == "TRANSFER"), None)
    affected = sorted({n.leg_seq for n in graph.nodes if n.state.value in ("DELAYED", "AT_RISK", "BROKEN")})
    fare_at_risk = sum(l.ticket.total_fare_paise for l in journey.legs
                       if graph.broken_from_leg and l.seq >= graph.broken_from_leg)
    consequence = {
        "journey_status": graph.status.value,
        "booked_final_arrival": final.scheduled.isoformat(),
        "expected_final_arrival": None if graph.broken_from_leg else final.expected.isoformat(),
        "delay_at_destination_minutes": None if graph.broken_from_leg else final.delay_minutes,
        "connection_margin_minutes": transfer.margin_minutes if transfer else None,
        "connection_class": transfer.transfer_class.value if transfer and transfer.transfer_class else None,
        "broken_from_leg": graph.broken_from_leg,
        "fare_of_unusable_legs_paise": fare_at_risk,
    }

    steps = [NextStep(plan_id=p.id, plan_kind=p.kind.value, rank=p.rank, travels=p.travels, arrival=p.arrival,
                      money_back_paise=p.money_back_paise, money_back_if_approved=p.money_back_if_approved,
                      deadline=p.deadline, deadline_unverified=p.deadline_unverified,
                      trains=[x.train_no for x in p.rides], rule_ids=[i for d in p.decisions for i in d.rule_ids])
             for p in r.plans[:3]]

    if stale:
        urgency = Urgency(level="UNKNOWN", decide_by=None, minutes_left=None)
    else:
        decide_by = r.rights_clock.decision_deadline or (r.plans[0].deadline if r.plans else None)
        mins = minutes_between(now, decide_by) if decide_by else None
        level = _level(mins)
        if level == "NONE" and any(e.state.value == "AT_RISK" for e in graph.edges):
            level = "WATCH"     # nothing to decide yet, but the next change of train is at risk
        urgency = Urgency(level=level, decide_by=decide_by, minutes_left=mins)

    wallet = build_wallet(journey, events, now, r.plans, [], [])
    rights = [RightsLine(kind=i.kind, stage=i.stage.value, estimated_refund_paise=i.estimated_refund_paise,
                         if_approved=i.if_approved, deadline=i.deadline, rule_id=i.rule.rule_set_id,
                         legal_status=i.rule.legal_status, unresolved=i.rule.unresolved) for i in wallet.items]

    rec = None if stale else recommend(r.plans, priority, simulate(journey, events, now, priority, profile))
    return Recovery(journey_id=journey.id, now=now, situation=sit.type.value, graph=graph, what_happened=happened,
                    last_updated=last, data_fresh=not stale, affected_legs=affected, consequence=consequence,
                    urgency=urgency, next_steps=steps, rights=rights, recommendation=rec)
