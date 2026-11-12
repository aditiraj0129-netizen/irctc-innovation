"""Station Transfer Intelligence.

Is there really enough time to change trains? We compare the gap between
arrival and departure with the time this passenger needs at this station.

Station walking times are SIMULATED estimates (station_transfer.yaml), clearly
labelled. We never invent platform numbers.
"""
from __future__ import annotations

import math
from datetime import datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

FILE = Path(__file__).resolve().parents[1] / "data" / "station_transfer.yaml"


class TransferClass(str, Enum):
    COMFORTABLE = "COMFORTABLE"
    TIGHT = "TIGHT"
    HIGH_RISK = "HIGH_RISK"
    NOT_FEASIBLE = "NOT_FEASIBLE"


RISK_ORDER = {TransferClass.COMFORTABLE: 0, TransferClass.TIGHT: 1, TransferClass.HIGH_RISK: 2,
              TransferClass.NOT_FEASIBLE: 3}


class PassengerProfile(BaseModel):
    walking_speed: Literal["normal", "slow"] = "normal"
    step_free: bool = False        # needs lifts/ramps
    senior: bool = False           # a senior traveller (walks at "slow" pace unless set otherwise)

    @property
    def speed(self) -> str:
        return "slow" if self.senior else self.walking_speed


class TransferCheck(BaseModel):
    station: str
    arrive: datetime
    depart: datetime
    gap_minutes: int
    required_minutes: int
    margin_minutes: int
    cls: TransferClass
    complexity: str
    estimate_label: str


@lru_cache
def _data() -> dict:
    return yaml.safe_load(FILE.read_text(encoding="utf-8"))


def station_info(stn: str) -> dict:
    d = _data()
    return d["stations"].get(stn, d["default"])


def required_minutes(stn: str, profile: PassengerProfile | None = None, floor: int = 30) -> int:
    """Time this passenger needs to change trains at this station (never below `floor`)."""
    p = profile or PassengerProfile()
    d, info = _data(), station_info(stn)
    need = info["walk_minutes"] * d["profile_factors"]["walking_speed"][p.speed]
    if p.step_free:
        need += d["profile_factors"]["step_free_extra_minutes"][info["complexity"]]
    return max(floor, math.ceil(need))


def classify(margin: int) -> TransferClass:
    c = _data()["classes"]
    if margin < 0:
        return TransferClass.NOT_FEASIBLE
    if margin < c["high_risk_below"]:
        return TransferClass.HIGH_RISK
    if margin < c["tight_below"]:
        return TransferClass.TIGHT
    return TransferClass.COMFORTABLE


def check_transfer(stn: str, arrive: datetime, depart: datetime, profile: PassengerProfile | None = None,
                   floor: int = 30) -> TransferCheck:
    gap = int((depart - arrive).total_seconds() // 60)
    need = required_minutes(stn, profile, floor)
    return TransferCheck(station=stn, arrive=arrive, depart=depart, gap_minutes=gap, required_minutes=need,
                         margin_minutes=gap - need, cls=classify(gap - need),
                         complexity=station_info(stn)["complexity"], estimate_label=_data()["label"])


def worst(checks: list[TransferCheck]) -> TransferClass | None:
    return max((c.cls for c in checks), key=lambda c: RISK_ORDER[c], default=None)
