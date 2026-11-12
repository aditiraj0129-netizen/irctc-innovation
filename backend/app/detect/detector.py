"""Disruption detector: turns train events into "is MY journey at risk?".

Pure rules, no AI. Thresholds:
  * connection: expected arrival + minimum transfer time must be before the
    next train's expected departure,
  * late running: more than 180 minutes late at the boarding station,
  * near 3 hours: 150-180 minutes (a warning, rights may appear soon),
  * chart prepared and the ticket is still fully waitlisted,
  * train cancelled.
If live data is older than STALE_MINUTES while we should be watching, we refuse
to advise rather than guess.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel

from app.core.clock import ensure_aware
from app.domain.models import Event, Journey, TrainLive, expected_arrival, expected_departure, live_state
from app.rules.models import TicketStatus

STALE_MINUTES = 15
WATCH_FROM_HOURS = 12        # start live watching 12 h before the first departure
LATE_THRESHOLD = 180
NEAR_LATE_FROM = 150


class SituationType(str, Enum):
    ALL_CLEAR = "ALL_CLEAR"
    NOT_WATCHING_YET = "NOT_WATCHING_YET"
    STALE_DATA = "STALE_DATA"
    CONNECTION_AT_RISK = "CONNECTION_AT_RISK"
    LATE_OVER_3H = "LATE_OVER_3H"
    NEAR_3H = "NEAR_3H"
    WAITLISTED_AFTER_CHART = "WAITLISTED_AFTER_CHART"
    TRAIN_CANCELLED = "TRAIN_CANCELLED"
    JOURNEY_OVER = "JOURNEY_OVER"


class Situation(BaseModel):
    type: SituationType
    leg_seq: int | None = None
    train_no: str | None = None
    delay_minutes: int | None = None
    buffer_minutes: int | None = None        # connection margin after the minimum transfer time
    detail: dict = {}


class Assessment(BaseModel):
    now: datetime
    situations: list[Situation]
    live: dict[str, TrainLive]

    @property
    def primary(self) -> Situation:
        order = [SituationType.STALE_DATA, SituationType.TRAIN_CANCELLED, SituationType.WAITLISTED_AFTER_CHART,
                 SituationType.CONNECTION_AT_RISK, SituationType.LATE_OVER_3H, SituationType.NEAR_3H,
                 SituationType.JOURNEY_OVER, SituationType.NOT_WATCHING_YET, SituationType.ALL_CLEAR]
        return sorted(self.situations, key=lambda s: order.index(s.type))[0]


def detect(journey: Journey, events: list[Event], now: datetime, assume_fresh: bool = False) -> Assessment:
    """assume_fresh=True is used only by the Rights Clock when it looks ahead
    ("if nothing else changes"), so a future moment isn't treated as stale."""
    now = ensure_aware(now, "now")
    live = {leg.train_no: live_state(leg.train_no, events, now) for leg in journey.legs}
    first, last = journey.legs[0], journey.legs[-1]
    out: list[Situation] = []

    if now >= expected_arrival(last, live[last.train_no]):
        return Assessment(now=now, situations=[Situation(type=SituationType.JOURNEY_OVER)], live=live)

    watching = now >= first.scheduled_departure - timedelta(hours=WATCH_FROM_HOURS)
    if not watching:
        return Assessment(now=now, situations=[Situation(type=SituationType.NOT_WATCHING_YET)], live=live)

    # Stale data: while watching, we need a recent update for the train that matters now.
    current = next((l for l in journey.legs if now < expected_arrival(l, live[l.train_no])), first)
    lv = live[current.train_no]
    if not assume_fresh and (lv.last_update is None or now - lv.last_update > timedelta(minutes=STALE_MINUTES)):
        out.append(Situation(type=SituationType.STALE_DATA, train_no=current.train_no,
                             detail={"last_update": lv.last_update.isoformat() if lv.last_update else None}))
        return Assessment(now=now, situations=out, live=live)

    for leg in journey.legs:
        st = live[leg.train_no]
        if st.cancelled:
            out.append(Situation(type=SituationType.TRAIN_CANCELLED, leg_seq=leg.seq, train_no=leg.train_no))
        if st.chart_status == TicketStatus.WAITLISTED and leg.ticket.status == TicketStatus.WAITLISTED:
            out.append(Situation(type=SituationType.WAITLISTED_AFTER_CHART, leg_seq=leg.seq,
                                 train_no=leg.train_no))

    # Late at the boarding station (only before the passenger's first train leaves).
    st1 = live[first.train_no]
    if not st1.departed and not st1.cancelled and now < expected_departure(first, st1):
        if st1.delay_minutes > LATE_THRESHOLD:
            out.append(Situation(type=SituationType.LATE_OVER_3H, leg_seq=1, train_no=first.train_no,
                                 delay_minutes=st1.delay_minutes))
        elif st1.delay_minutes >= NEAR_LATE_FROM:
            out.append(Situation(type=SituationType.NEAR_3H, leg_seq=1, train_no=first.train_no,
                                 delay_minutes=st1.delay_minutes))

    # Connections.
    for a, b in zip(journey.legs, journey.legs[1:]):
        arr = expected_arrival(a, live[a.train_no])
        dep = expected_departure(b, live[b.train_no])
        buffer = int((dep - arr).total_seconds() // 60) - journey.min_transfer_minutes
        if buffer < 0 and not live[b.train_no].cancelled:
            out.append(Situation(type=SituationType.CONNECTION_AT_RISK, leg_seq=b.seq, train_no=b.train_no,
                                 delay_minutes=live[a.train_no].delay_minutes, buffer_minutes=buffer,
                                 detail={"expected_arrival": arr.isoformat(), "next_departure": dep.isoformat(),
                                         "station": a.to_stn}))

    if not out:
        out.append(Situation(type=SituationType.ALL_CLEAR))
    return Assessment(now=now, situations=out, live=live)
