"""Platform Information Service: which platform, and how sure are we?

Every platform value has exactly one status:
  CONFIRMED  - from a current authoritative source (in this demo: SIMULATED stand-ins, labelled as such)
  REPORTED   - from a current public source, or typed in by the passenger from the station board
  SCHEDULED  - the platform the timetable normally assigns
  PREDICTED  - documented rule: the same platform on at least 5 of the last 7 runs
  UNKNOWN    - nothing reliable

There is NO documented public API for live Indian Railways platform data, so `OfficialPlatformProvider`
refuses (ProviderNotConfigured). We never turn an unknown platform into a guess.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from app.providers import ProviderNotConfigured

FILE = Path(__file__).resolve().parents[1] / "data" / "platforms.yaml"
STALE_MIN = 45
PREDICT_MIN_AGREE, PREDICT_WINDOW = 5, 7
RANK = {"CONFIRMED": 0, "REPORTED": 1, "SCHEDULED": 2, "PREDICTED": 3, "UNKNOWN": 4}


class PStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    REPORTED = "REPORTED"
    SCHEDULED = "SCHEDULED"
    PREDICTED = "PREDICTED"
    UNKNOWN = "UNKNOWN"


class PlatformObservation(BaseModel):
    train_no: str = Field(pattern=r"^\d{5}$")
    station: str = Field(pattern=r"^[A-Z]{2,5}$")
    kind: str = Field(pattern=r"^(ARRIVAL|DEPARTURE)$")
    platform: int | None = Field(default=None, ge=1, le=30)
    status: PStatus
    observed_at: datetime
    source: str


class PlatformInfo(BaseModel):
    train_no: str
    station: str
    kind: str
    platform: int | None
    status: PStatus
    source: str
    observed_at: datetime | None = None
    age_minutes: int | None = None
    stale: bool = False
    changed_from: int | None = None
    trusted: bool = False              # CONFIRMED or REPORTED, and not stale
    message: str | None = None         # e.g. LIVE_PLATFORM_UNAVAILABLE_CHECK_BOARDS
    history: list[dict] = Field(default_factory=list)


@lru_cache
def _data() -> dict:
    return yaml.safe_load(FILE.read_text(encoding="utf-8"))


def scheduled(train: str, station: str, kind: str) -> int | None:
    return next((s["platform"] for s in _data()["scheduled"]
                 if s["train"] == train and s["station"] == station and s["kind"] == kind), None)


def predicted(train: str, station: str, kind: str) -> int | None:
    h = next((s["last_runs"] for s in _data()["history"]
              if s["train"] == train and s["station"] == station and s["kind"] == kind), None)
    if not h:
        return None
    p, n = Counter(h[-PREDICT_WINDOW:]).most_common(1)[0]
    return p if n >= PREDICT_MIN_AGREE else None


class OfficialPlatformProvider:
    """Placeholder: no documented, licensed public API for live platform data was found."""
    def observations(self, *_a, **_k) -> list[PlatformObservation]:
        raise ProviderNotConfigured("No authorised live platform source is connected")


def platform_info(train: str, station: str, kind: str, observations: list[PlatformObservation], now: datetime,
                  live_available: bool = True) -> PlatformInfo:
    obs = sorted([o for o in observations if o.train_no == train and o.station == station and o.kind == kind
                  and o.observed_at <= now], key=lambda o: o.observed_at)
    sch, pred = scheduled(train, station, kind), predicted(train, station, kind)
    hist = ([{"platform": sch, "status": "SCHEDULED", "at": None, "source": "SIMULATED_TIMETABLE"}] if sch else []) + \
        [{"platform": o.platform, "status": o.status.value, "at": o.observed_at.isoformat(), "source": o.source} for o in obs]
    base = dict(train_no=train, station=station, kind=kind, history=hist)
    live = [o for o in obs if o.status in (PStatus.CONFIRMED, PStatus.REPORTED) and o.platform]
    if live:
        o = live[-1]
        age = int((now - o.observed_at).total_seconds() // 60)
        earlier = [h["platform"] for h in hist[:-1] if h["platform"]]
        prev = earlier[-1] if earlier else None
        stale = age > STALE_MIN
        return PlatformInfo(**base, platform=o.platform, status=o.status, source=o.source, observed_at=o.observed_at,
                            age_minutes=age, stale=stale, changed_from=prev if prev and prev != o.platform else None,
                            trusted=not stale, message="PLATFORM_DATA_STALE_CHECK_BOARDS" if stale else None)
    msg = None if live_available else "LIVE_PLATFORM_UNAVAILABLE_CHECK_BOARDS"
    if sch:
        return PlatformInfo(**base, platform=sch, status=PStatus.SCHEDULED, source="SIMULATED_TIMETABLE",
                            message=msg or "SCHEDULED_ONLY_CHECK_BOARDS")
    if pred:
        return PlatformInfo(**base, platform=pred, status=PStatus.PREDICTED, source="RULE_5_OF_LAST_7_RUNS (simulated history)",
                            message=msg or "PREDICTED_ONLY_CHECK_BOARDS")
    return PlatformInfo(**base, platform=None, status=PStatus.UNKNOWN, source="NONE",
                        message="LIVE_PLATFORM_UNAVAILABLE_CHECK_BOARDS")
