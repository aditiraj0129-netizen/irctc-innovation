"""Offline Journey Card.

A compact snapshot the browser saves so the passenger still has their plan
with no network. It holds NO personal data: the PNR is masked and there are no
names. It always carries the time it was made, and it is labelled as a
snapshot, never as live information.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel

from app.data.timetable import STATIONS
from app.domain.models import Journey
from app.plan.models import Plan
from app.twin.twin import JourneyTwin
from app.wallet.wallet import Wallet

EMERGENCY = [
    {"id": "RAIL_ENQUIRY", "number": "139"},
    {"id": "RAILWAY_SECURITY", "number": "182"},
    {"id": "CYBER_FRAUD", "number": "1930"},
    {"id": "EMERGENCY", "number": "112"},
]

STALE_AFTER_MINUTES = 30     # the app marks the card "possibly outdated" after this


class OfflineCard(BaseModel):
    journey_id: str
    pnr_label: str
    generated_at: datetime
    stale_after: datetime
    data_label: str = "SIMULATED_SNAPSHOT_NOT_LIVE"
    status: str
    legs: list[dict]
    transfers: list[dict]
    plans: list[dict]
    rights: list[dict]
    rules: list[dict]
    instructions: list[str]
    emergency: list[dict]


def build_card(journey: Journey, twin: JourneyTwin, plans: list[Plan], wallet: Wallet) -> OfflineCard:
    now = twin.now
    stn = lambda c: {"code": c, **STATIONS.get(c, {"en": c, "hi": c})}
    legs = [{"seq": l.seq, "train_no": l.train_no, "train_name": l.train_name, "from": stn(l.from_stn),
             "to": stn(l.to_stn), "scheduled_departure": l.scheduled_departure.isoformat(),
             "scheduled_arrival": l.scheduled_arrival.isoformat(), "expected_arrival": l.expected_arrival.isoformat(),
             "delay_minutes": l.delay_minutes, "state": l.state.value,
             "info_last_update": l.info.last_update.isoformat() if l.info.last_update else None}
            for l in twin.legs]
    transfers = [{"station": stn(t.check.station), "class": t.check.cls.value, "margin_minutes": t.check.margin_minutes}
                 for t in twin.transfers]
    top = [{"rank": p.rank, "kind": p.kind.value, "travels": p.travels,
            "arrival": p.arrival.isoformat() if p.arrival else None,
            "deadline": p.deadline.isoformat() if p.deadline else None,
            "money_back_paise": p.money_back_paise, "if_approved": p.money_back_if_approved,
            "needs_new_ticket": p.needs_new_ticket,
            "rides": [{"train_no": r.train_no, "train_name": r.train_name, "from": r.from_stn, "to": r.to_stn,
                       "dep": r.dep.isoformat(), "arr": r.arr.isoformat()} for r in p.rides]}
           for p in plans[:3]]
    rights = [{"kind": i.kind, "leg_seq": i.leg_seq, "stage": i.stage.value,
               "estimated_refund_paise": i.estimated_refund_paise, "if_approved": i.if_approved,
               "deadline": i.deadline.isoformat() if i.deadline else None,
               "deadline_unverified": i.deadline_unverified} for i in wallet.items]
    seen, rules = set(), []
    for i in wallet.items:
        if i.rule.rule_set_id not in seen:
            seen.add(i.rule.rule_set_id)
            rules.append({"id": i.rule.rule_set_id, "version": i.rule.rule_version, "status": i.rule.legal_status,
                          "last_verified": i.rule.last_verified, "source": i.rule.source_title,
                          "unresolved": i.rule.unresolved})
    instructions = ["CARD_IS_A_SNAPSHOT", "CHECK_LIVE_STATUS_WHEN_ONLINE", "NEVER_SHARE_OTP"]
    if any(p.money_back_if_approved for p in plans[:1]):
        instructions.insert(0, "FILE_TDR_BEFORE_DEADLINE")
    return OfflineCard(journey_id=journey.id, pnr_label=journey.pnr_label, generated_at=now,
                       stale_after=now + timedelta(minutes=STALE_AFTER_MINUTES), status=twin.status.value, legs=legs,
                       transfers=transfers, plans=top, rights=rights, rules=rules, instructions=instructions,
                       emergency=EMERGENCY)
