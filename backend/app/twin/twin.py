"""Journey Digital Twin.

A live model of the WHOLE itinerary: every leg's scheduled vs expected times,
every change of train, and which parts are affected by the latest events.
It is rebuilt from events each time (no hidden state), so it always matches
what the detector and the planner see.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field

from app.core.clock import ensure_aware
from app.detect.detector import STALE_MINUTES
from app.domain.models import Event, Journey, expected_arrival, expected_departure, live_state
from app.plan.transfer import PassengerProfile, TransferCheck, TransferClass, check_transfer
from app.rules.models import TicketStatus


class LegState(str, Enum):
    SCHEDULED = "SCHEDULED"        # no live data yet
    ON_TIME = "ON_TIME"
    DELAYED = "DELAYED"
    IN_TRANSIT = "IN_TRANSIT"
    ARRIVED = "ARRIVED"
    CANCELLED = "CANCELLED"
    WAITLISTED = "WAITLISTED"      # still waitlisted after the chart
    AT_RISK = "AT_RISK"            # the change of train into this leg is high-risk
    LIKELY_MISSED = "LIKELY_MISSED"  # the change into this leg is not feasible


class Freshness(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    NONE = "NONE"


class InfoQuality(BaseModel):
    last_update: datetime | None
    age_minutes: int | None
    freshness: Freshness
    source: str            # SIMULATED or OFFICIAL


class TwinLeg(BaseModel):
    seq: int
    train_no: str
    train_name: str
    from_stn: str
    to_stn: str
    scheduled_departure: datetime
    scheduled_arrival: datetime
    expected_departure: datetime
    expected_arrival: datetime
    delay_minutes: int
    ticket_status: TicketStatus
    state: LegState
    affected: bool
    affected_by: list[str] = Field(default_factory=list)
    info: InfoQuality


class TwinTransfer(BaseModel):
    from_seq: int
    to_seq: int
    check: TransferCheck
    latest_safe_arrival: datetime      # leg A must arrive by this time for the change to work


class JourneyStatus(str, Enum):
    ON_TRACK = "ON_TRACK"
    DISRUPTED = "DISRUPTED"            # delays, but the itinerary still works
    BROKEN = "BROKEN"                  # a leg is cancelled, missed or waitlisted
    COMPLETED = "COMPLETED"


class JourneyTwin(BaseModel):
    journey_id: str
    now: datetime
    status: JourneyStatus
    legs: list[TwinLeg]
    transfers: list[TwinTransfer]
    scheduled_final_arrival: datetime
    expected_final_arrival: datetime | None      # None when the itinerary is broken
    delay_at_destination_minutes: int | None
    affected_segments: list[int]
    unaffected_segments: list[int]
    data_label: str = "SIMULATED"


def _info(live, now: datetime) -> InfoQuality:
    if live.last_update is None:
        return InfoQuality(last_update=None, age_minutes=None, freshness=Freshness.NONE, source="SIMULATED")
    age = int((now - live.last_update).total_seconds() // 60)
    return InfoQuality(last_update=live.last_update, age_minutes=age,
                       freshness=Freshness.FRESH if age <= STALE_MINUTES else Freshness.STALE,
                       source=live.source.value if live.source else "SIMULATED")


def build_twin(journey: Journey, events: list[Event], now: datetime,
               profile: PassengerProfile | None = None) -> JourneyTwin:
    now = ensure_aware(now, "now")
    legs: list[TwinLeg] = []
    for leg in journey.legs:
        lv = live_state(leg.train_no, events, now)
        exp_dep, exp_arr = expected_departure(leg, lv), expected_arrival(leg, lv)
        reasons: list[str] = []
        if lv.cancelled:
            state = LegState.CANCELLED
            reasons.append("TRAIN_CANCELLED")
        elif now >= exp_arr:
            state = LegState.ARRIVED
        elif lv.departed or now >= exp_dep:
            state = LegState.IN_TRANSIT
        elif lv.chart_status == TicketStatus.WAITLISTED and leg.ticket.status == TicketStatus.WAITLISTED:
            state = LegState.WAITLISTED
            reasons.append("WAITLISTED_AFTER_CHART")
        elif lv.delay_minutes > 0:
            state = LegState.DELAYED
        elif lv.last_update is None:
            state = LegState.SCHEDULED
        else:
            state = LegState.ON_TIME
        if lv.delay_minutes > 0 and not lv.cancelled:
            reasons.append("DELAYED")
        legs.append(TwinLeg(seq=leg.seq, train_no=leg.train_no, train_name=leg.train_name, from_stn=leg.from_stn,
                            to_stn=leg.to_stn, scheduled_departure=leg.scheduled_departure,
                            scheduled_arrival=leg.scheduled_arrival, expected_departure=exp_dep,
                            expected_arrival=exp_arr, delay_minutes=lv.delay_minutes,
                            ticket_status=leg.ticket.status, state=state, affected=bool(reasons),
                            affected_by=reasons, info=_info(lv, now)))

    # Changes of train: is each one still possible for THIS passenger?
    transfers: list[TwinTransfer] = []
    for a, b in zip(legs, legs[1:]):
        chk = check_transfer(a.to_stn, a.expected_arrival, b.expected_departure, profile, journey.min_transfer_minutes)
        transfers.append(TwinTransfer(from_seq=a.seq, to_seq=b.seq, check=chk,
                                      latest_safe_arrival=b.expected_departure - timedelta(minutes=chk.required_minutes)))
        if a.state in (LegState.CANCELLED, LegState.LIKELY_MISSED):
            b.affected, b.affected_by = True, [*b.affected_by, "UPSTREAM_LEG_BROKEN"]
            if b.state not in (LegState.CANCELLED, LegState.ARRIVED):
                b.state = LegState.LIKELY_MISSED
        elif b.state not in (LegState.CANCELLED, LegState.ARRIVED, LegState.IN_TRANSIT):
            if chk.cls == TransferClass.NOT_FEASIBLE:
                b.state, b.affected = LegState.LIKELY_MISSED, True
                b.affected_by.append("CONNECTION_NOT_FEASIBLE")
            elif chk.cls == TransferClass.HIGH_RISK:
                b.state, b.affected = LegState.AT_RISK, True
                b.affected_by.append("CONNECTION_HIGH_RISK")

    last = legs[-1]
    broken = any(l.state in (LegState.CANCELLED, LegState.LIKELY_MISSED, LegState.WAITLISTED) for l in legs)
    if last.state == LegState.ARRIVED:
        status = JourneyStatus.COMPLETED
    elif broken:
        status = JourneyStatus.BROKEN
    elif any(l.affected for l in legs):
        status = JourneyStatus.DISRUPTED
    else:
        status = JourneyStatus.ON_TRACK
    final = None if broken else last.expected_arrival
    return JourneyTwin(
        journey_id=journey.id, now=now, status=status, legs=legs, transfers=transfers,
        scheduled_final_arrival=last.scheduled_arrival, expected_final_arrival=final,
        delay_at_destination_minutes=None if final is None else int((final - last.scheduled_arrival).total_seconds() // 60),
        affected_segments=[l.seq for l in legs if l.affected],
        unaffected_segments=[l.seq for l in legs if not l.affected],
    )
