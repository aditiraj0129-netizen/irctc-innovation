"""One call that runs the whole pipeline: detect -> build plans -> rank -> Rights Clock."""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache

from pydantic import BaseModel

from app.data.timetable import Connection, build_connections, load_stops
from app.detect.detector import Assessment, SituationType, detect
from app.domain.models import Event, Journey
from app.plan.builder import build_plans
from app.plan.models import Plan
from app.plan.ranker import Priority, rank
from app.plan.rights_clock import RightsClock, build_rights_clock
from app.plan.transfer import PassengerProfile
from app.rules.engine import RuleRegistry


@lru_cache
def registry() -> RuleRegistry:
    return RuleRegistry.from_yaml()


@lru_cache
def stops():
    return load_stops()


def connections_for(journey: Journey) -> list[Connection]:
    start = journey.legs[0].scheduled_departure.date() - timedelta(days=1)
    return build_connections(stops(), start, days=4)


# Cancelling the booked ticket is only a real choice in these situations.
CANCELLABLE = {SituationType.ALL_CLEAR, SituationType.NOT_WATCHING_YET, SituationType.NEAR_3H,
               SituationType.LATE_OVER_3H}


class Result(BaseModel):
    assessment: Assessment
    plans: list[Plan]
    rights_clock: RightsClock


def plans_at(journey: Journey, events: list[Event], now: datetime, priority: Priority,
             conns: list[Connection], assume_fresh: bool = False,
             profile: PassengerProfile | None = None) -> tuple[Assessment, list[Plan]]:
    a = detect(journey, events, now, assume_fresh=assume_fresh)
    return a, rank(build_plans(journey, a, conns, registry(), profile), priority)


def assess(journey: Journey, events: list[Event], now: datetime, priority: Priority = Priority.TIME,
           profile: PassengerProfile | None = None) -> Result:
    conns = connections_for(journey)
    a, plans = plans_at(journey, events, now, priority, conns, profile=profile)
    clock = build_rights_clock(journey, now, plans, registry(),
                               lambda t: plans_at(journey, events, t, priority, conns, assume_fresh=True,
                                                  profile=profile)[1],
                               show_cancel_windows=a.primary.type in CANCELLABLE)
    return Result(assessment=a, plans=plans, rights_clock=clock)
