"""Community Disruption Intelligence (optional, UNVERIFIED).

Passengers can report what they see at a station. Reports:
  * are timestamped and expire,
  * are merged when the same thing is reported again (counted once per reporter),
  * get a confidence level from how many DIFFERENT people reported it,
  * are flagged when they conflict,
  * are ALWAYS labelled as unverified passenger reports, and
  * NEVER change refund amounts, deadlines, eligibility or plan ranking.
    (Nothing in the rules engine or planner reads them; a test checks this.)
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.core.clock import ensure_aware
from app.store import Store


class ReportType(str, Enum):
    PLATFORM_CHANGE = "PLATFORM_CHANGE"
    CONGESTION = "CONGESTION"
    TRAIN_STOPPED = "TRAIN_STOPPED"
    ACCESS_PROBLEM = "ACCESS_PROBLEM"
    TRANSFER_DIFFICULTY = "TRANSFER_DIFFICULTY"


EXPIRY_MINUTES = {ReportType.PLATFORM_CHANGE: 60, ReportType.CONGESTION: 45, ReportType.TRAIN_STOPPED: 90,
                  ReportType.ACCESS_PROBLEM: 360, ReportType.TRANSFER_DIFFICULTY: 180}
MERGE_WINDOW = timedelta(minutes=20)
PHONE_LIKE = re.compile(r"\d[\d\s-]{5,}\d")


class ReportIn(BaseModel):
    station: str = Field(pattern=r"^[A-Z]{2,5}$")
    type: ReportType
    train_no: str | None = Field(default=None, pattern=r"^\d{5}$")
    note: str | None = Field(default=None, max_length=120)

    @field_validator("note")
    @classmethod
    def no_personal_data(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if PHONE_LIKE.search(v) or "@" in v:
            raise ValueError("Please don't include phone numbers or emails")
        return v.strip() or None


class Report(BaseModel):
    id: int
    jid: str
    station: str
    type: ReportType
    train_no: str | None
    note: str | None
    first_seen: datetime
    last_seen: datetime
    expires_at: datetime
    reporters: int
    confidence: str                  # LOW, MEDIUM, HIGH: about agreement between passengers, not truth
    conflicting: bool = False
    label: str = "UNVERIFIED_PASSENGER_REPORT"
    affects_recommendations: bool = False
    simulated_seed: bool = False


def _confidence(n: int) -> str:
    return "LOW" if n <= 1 else "MEDIUM" if n <= 3 else "HIGH"


class CommunityService:
    def __init__(self, store: Store):
        self.store = store

    def submit(self, jid: str, data: ReportIn, reporter_key: str, now: datetime, seed: bool = False) -> Report:
        now = ensure_aware(now, "now")
        who = hashlib.sha256(reporter_key.encode()).hexdigest()[:12]      # never store the raw IP
        for rid, d in self.store.reports():
            if (d["jid"], d["station"], d["type"], d.get("train_no")) == (jid, data.station, data.type.value, data.train_no) \
                    and now - datetime.fromisoformat(d["last_seen"]) <= MERGE_WINDOW \
                    and now < datetime.fromisoformat(d["expires_at"]):
                if who not in d["who"]:                 # the same person again is a duplicate, not new evidence
                    d["who"].append(who)
                d["last_seen"] = now.isoformat()
                d["expires_at"] = (now + timedelta(minutes=EXPIRY_MINUTES[data.type])).isoformat()
                if data.note and data.note not in d["notes"]:
                    d["notes"].append(data.note)
                self.store.update_report(rid, d)
                return self._out(rid, d)
        d = {"jid": jid, "station": data.station, "type": data.type.value, "train_no": data.train_no,
             "notes": [data.note] if data.note else [], "first_seen": now.isoformat(), "last_seen": now.isoformat(),
             "expires_at": (now + timedelta(minutes=EXPIRY_MINUTES[data.type])).isoformat(), "who": [who],
             "seed": seed}
        rid = self.store.add_report(d)
        return self._out(rid, d)

    def _out(self, rid: int, d: dict) -> Report:
        return Report(id=rid, jid=d["jid"], station=d["station"], type=ReportType(d["type"]), train_no=d.get("train_no"),
                      note=" / ".join(d["notes"]) or None, first_seen=datetime.fromisoformat(d["first_seen"]),
                      last_seen=datetime.fromisoformat(d["last_seen"]), expires_at=datetime.fromisoformat(d["expires_at"]),
                      reporters=len(d["who"]), confidence=_confidence(len(d["who"])),
                      conflicting=len(d["notes"]) > 1 and d["type"] == ReportType.PLATFORM_CHANGE.value,
                      simulated_seed=d.get("seed", False))

    def active(self, jid: str, now: datetime) -> list[Report]:
        now = ensure_aware(now, "now")
        out = [self._out(rid, d) for rid, d in self.store.reports()
               if d["jid"] == jid and datetime.fromisoformat(d["first_seen"]) <= now < datetime.fromisoformat(d["expires_at"])]
        return sorted(out, key=lambda r: r.last_seen, reverse=True)


# Simulated reports for the demo (clearly marked as seeded and simulated).
SEEDS = {
    "missed_connection": [
        (-25, "seed-a", ReportIn(station="PRYJ", type=ReportType.PLATFORM_CHANGE, train_no="90203", note="Board from the far platform")),
        (-20, "seed-b", ReportIn(station="PRYJ", type=ReportType.PLATFORM_CHANGE, train_no="90203", note="Announcement says a different platform")),
        (-10, "seed-c", ReportIn(station="PNBE", type=ReportType.TRANSFER_DIFFICULTY, note="Long queue at the foot overbridge")),
    ],
    "edge_three_hours": [
        (-15, "seed-a", ReportIn(station="LKO", type=ReportType.CONGESTION, note="Waiting hall very crowded")),
    ],
}


def seed(service: CommunityService, jid: str, clock_now: datetime) -> None:
    for minutes, who, r in SEEDS.get(jid, []):
        service.submit(jid, r, who, clock_now + timedelta(minutes=minutes), seed=True)
