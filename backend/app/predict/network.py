"""Simulated route-section model: sections, train attributes, nearby stations, sample buses."""
from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from app.data.timetable import Stop, train_schedule

FILE = Path(__file__).resolve().parents[1] / "data" / "network.yaml"


class Section(BaseModel):
    a: str
    b: str
    km: int
    recovery_allowance_min: int

    @property
    def id(self) -> str:
        return f"{self.a}-{self.b}"


class TrainInfo(BaseModel):
    category: str
    priority: int
    general_coaches: bool
    reserved: bool
    verified: bool = False          # the simulated trains are never "verified"


class SectionPass(BaseModel):
    """One train run passing one section (scheduled times, direction a -> b)."""
    train_no: str
    section: str
    a: str
    b: str
    sched_enter: datetime            # departure from a
    sched_exit: datetime             # arrival at b


@lru_cache
def data() -> dict:
    return yaml.safe_load(FILE.read_text(encoding="utf-8"))


def label() -> str:
    return data()["label"]


@lru_cache
def sections() -> dict[tuple[str, str], Section]:
    """Keyed by (a, b) in BOTH directions: a section is the same track whichever way you run."""
    out = {}
    for s in data()["sections"]:
        sec = Section(**s)
        out[(sec.a, sec.b)] = sec
        out[(sec.b, sec.a)] = sec
    return out


def section_between(a: str, b: str) -> Section | None:
    return sections().get((a, b))


def train_info(train_no: str) -> TrainInfo:
    d = data()
    return TrainInfo(**{**d["default_train"], **(d["trains"].get(train_no) or {})})


def nearby(stn: str) -> list[dict]:
    return list(data().get("nearby", {}).get(stn, []))


def bus_samples() -> list[dict]:
    return list(data().get("bus_samples", []))


def passes(stops: list[Stop], train_no: str, run_date: date) -> list[SectionPass]:
    """Every section this train run uses, in order, with scheduled entry/exit and direction."""
    sched = train_schedule(stops, train_no, run_date)
    out = []
    for (a, _, dep), (b, arr, _) in zip(sched, sched[1:]):
        sec = section_between(a, b)
        if sec and dep and arr:
            out.append(SectionPass(train_no=train_no, section=sec.id, a=a, b=b, sched_enter=dep, sched_exit=arr))
    return out
