"""Clock service.

Every piece of time logic in Agla Kadam asks a Clock for "now" instead of
calling datetime.now() directly. This lets us:
  * replay demo scenarios at any time we like (DemoClock), and
  * write repeatable tests (FixedClock).

All times are timezone-aware and in Indian Standard Time (IST).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


class NaiveDatetimeError(ValueError):
    """Raised when a datetime without a timezone is passed in."""


def ensure_aware(value: datetime, name: str = "datetime") -> datetime:
    """Reject naive datetimes so we never mix up IST and UTC by accident."""
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise NaiveDatetimeError(f"{name} must include a timezone (e.g. +05:30)")
    return value.astimezone(IST)


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    """Real time, used in production."""

    def now(self) -> datetime:
        return datetime.now(IST)


class FixedClock:
    """A clock that never moves unless you move it. Used in tests and demos."""

    def __init__(self, at: datetime):
        self._at = ensure_aware(at, "clock time")

    def now(self) -> datetime:
        return self._at

    def set(self, at: datetime) -> None:
        self._at = ensure_aware(at, "clock time")

    def advance(self, minutes: int = 0, hours: int = 0) -> None:
        self._at = self._at + timedelta(minutes=minutes, hours=hours)


# The presenter panel will move this clock during the live demo.
DemoClock = FixedClock
