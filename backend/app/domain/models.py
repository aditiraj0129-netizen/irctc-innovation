"""Journey, leg and event models.

A Journey is what the passenger booked: one or more legs (trains).
Events are things that happen to a train (delay, chart, cancellation).
Every event says where it came from: SIMULATED now, OFFICIAL later.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.core.clock import ensure_aware
from app.rules.models import Ticket, TicketStatus


class Leg(BaseModel):
    seq: int = Field(ge=1)
    ticket: Ticket
    train_name: str
    from_stn: str = Field(pattern=r"^[A-Z]{2,5}$")
    to_stn: str = Field(pattern=r"^[A-Z]{2,5}$")
    scheduled_arrival: datetime

    @field_validator("scheduled_arrival")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return ensure_aware(v, "scheduled_arrival")

    @property
    def train_no(self) -> str:
        return self.ticket.train_no

    @property
    def scheduled_departure(self) -> datetime:
        return self.ticket.scheduled_departure


class Journey(BaseModel):
    id: str
    pnr_label: str                      # masked, e.g. "81xxxxxx01 (simulated)"
    title: str
    legs: list[Leg] = Field(min_length=1, max_length=2)
    linked_pnr: bool = False
    vikalp_opted: bool = False
    min_transfer_minutes: int = Field(default=30, ge=5, le=240)   # OUR assumption, user can change

    @field_validator("legs")
    @classmethod
    def legs_connect(cls, legs: list[Leg]) -> list[Leg]:
        for a, b in zip(legs, legs[1:]):
            if a.to_stn != b.from_stn:
                raise ValueError("each leg must start where the previous one ends")
            if b.scheduled_departure <= a.scheduled_arrival:
                raise ValueError("the next train must leave after the previous one arrives")
        return legs

    @property
    def origin(self) -> str:
        return self.legs[0].from_stn

    @property
    def destination(self) -> str:
        return self.legs[-1].to_stn


class EventType(str, Enum):
    DELAY = "DELAY"                    # running late by delay_minutes (dep and arr)
    CHART_PREPARED = "CHART_PREPARED"  # chart_status = status after charting
    CANCELLED = "CANCELLED"            # whole run cancelled
    DEPARTED = "DEPARTED"              # train has actually left the boarding station


class EventSource(str, Enum):
    SIMULATED = "SIMULATED"
    OFFICIAL = "OFFICIAL"


class Event(BaseModel):
    train_no: str = Field(pattern=r"^\d{5}$")
    type: EventType
    delay_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    chart_status: TicketStatus | None = None
    observed_at: datetime
    source: EventSource = EventSource.SIMULATED

    @field_validator("observed_at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return ensure_aware(v, "observed_at")


class TrainLive(BaseModel):
    """Latest known state of one train, built from its events."""
    train_no: str
    delay_minutes: int = 0
    cancelled: bool = False
    departed: bool = False
    chart_status: TicketStatus | None = None
    last_update: datetime | None = None
    source: EventSource | None = None


def live_state(train_no: str, events: list[Event], now: datetime) -> TrainLive:
    """Fold all events up to `now` (never future ones) into the train's current state."""
    state = TrainLive(train_no=train_no)
    for e in sorted((e for e in events if e.train_no == train_no and e.observed_at <= now),
                    key=lambda e: e.observed_at):
        state.last_update = e.observed_at
        state.source = e.source
        if e.type == EventType.DELAY and e.delay_minutes is not None:
            state.delay_minutes = e.delay_minutes
        elif e.type == EventType.CANCELLED:
            state.cancelled = True
        elif e.type == EventType.DEPARTED:
            state.departed = True
        elif e.type == EventType.CHART_PREPARED:
            state.chart_status = e.chart_status
    return state


def expected_departure(leg: Leg, live: TrainLive) -> datetime:
    return leg.scheduled_departure + timedelta(minutes=live.delay_minutes)


def expected_arrival(leg: Leg, live: TrainLive) -> datetime:
    return leg.scheduled_arrival + timedelta(minutes=live.delay_minutes)
