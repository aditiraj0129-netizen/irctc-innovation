"""Timetable for the demo corridor.

IMPORTANT: the trains in timetable.csv are SIMULATED (numbers 90xxx, names start
with "Sim"). Station codes are real. Before a public demo, either keep them
clearly labelled as simulated, or replace them with trains checked by hand
against the current official timetable ("Trains at a Glance").
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from app.core.clock import IST

TIMETABLE_FILE = Path(__file__).parent / "timetable.csv"
TIMETABLE_LABEL = "Simulated corridor timetable (not official)"

STATIONS: dict[str, dict[str, str]] = {
    "NDLS": {"en": "New Delhi", "hi": "नई दिल्ली"},
    "CNB": {"en": "Kanpur Central", "hi": "कानपुर सेंट्रल"},
    "LKO": {"en": "Lucknow", "hi": "लखनऊ"},
    "PRYJ": {"en": "Prayagraj Jn", "hi": "प्रयागराज जं."},
    "DDU": {"en": "Pt. DD Upadhyaya Jn", "hi": "पं. दीनदयाल उपाध्याय जं."},
    "PNBE": {"en": "Patna Jn", "hi": "पटना जं."},
    "DBG": {"en": "Darbhanga Jn", "hi": "दरभंगा जं."},
    "BPL": {"en": "Bhopal Jn", "hi": "भोपाल जं."},
    "JHS": {"en": "Jhansi Jn", "hi": "झाँसी जं."},
    "AGC": {"en": "Agra Cantt", "hi": "आगरा कैंट"},
    "UMB": {"en": "Ambala Cantt", "hi": "अंबाला कैंट"},
    "CDG": {"en": "Chandigarh", "hi": "चंडीगढ़"},
    "NZM": {"en": "Hazrat Nizamuddin", "hi": "हज़रत निज़ामुद्दीन"},
}


def train_schedule(stops: list[Stop], train_no: str, run_date: date) -> list[tuple[str, datetime | None, datetime | None]]:
    """(station, scheduled arrival, scheduled departure) for every stop of one run, in order."""
    out = []
    for s in sorted((s for s in stops if s.train_no == train_no), key=lambda s: s.seq):
        day = run_date + timedelta(days=s.day)
        out.append((s.stn, datetime.combine(day, s.arr, IST) if s.arr else None,
                    datetime.combine(day, s.dep, IST) if s.dep else None))
    return out


@dataclass(frozen=True)
class Stop:
    train_no: str
    train_name: str
    seq: int
    stn: str
    arr: time | None
    dep: time | None
    day: int           # days after the train's start date


@dataclass(frozen=True)
class Connection:
    """One hop of one train run, from a stop to the next stop."""
    train_no: str
    train_name: str
    run_date: date
    from_stn: str
    dep: datetime
    to_stn: str
    arr: datetime


def _t(s: str) -> time | None:
    return time.fromisoformat(s) if s else None


def load_stops(path: Path = TIMETABLE_FILE) -> list[Stop]:
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    stops = [Stop(r["train_no"], r["train_name"], int(r["seq"]), r["stn"], _t(r["arr"]), _t(r["dep"]),
                  int(r["day"])) for r in rows]
    return sorted(stops, key=lambda s: (s.train_no, s.seq))


def train_names(stops: list[Stop]) -> dict[str, str]:
    return {s.train_no: s.train_name for s in stops}


def build_connections(stops: list[Stop], from_date: date, days: int = 4) -> list[Connection]:
    """Every hop of every train starting on from_date .. from_date+days-1 (all trains run daily)."""
    by_train: dict[str, list[Stop]] = {}
    for s in stops:
        by_train.setdefault(s.train_no, []).append(s)
    conns: list[Connection] = []
    for d in range(days):
        run = from_date + timedelta(days=d)
        for train_no, seq in by_train.items():
            for a, b in zip(seq, seq[1:]):
                dep = datetime.combine(run + timedelta(days=a.day), a.dep, IST)
                arr = datetime.combine(run + timedelta(days=b.day), b.arr, IST)
                if arr <= dep:
                    raise ValueError(f"Bad timetable row for {train_no}: arrival before departure")
                conns.append(Connection(train_no, a.train_name, run, a.stn, dep, b.stn, arr))
    return sorted(conns, key=lambda c: c.dep)


def scheduled_times(stops: list[Stop], train_no: str, run_date: date, from_stn: str, to_stn: str
                    ) -> tuple[datetime, datetime]:
    """Scheduled departure from from_stn and arrival at to_stn for one run."""
    seq = [s for s in stops if s.train_no == train_no]
    a = next(s for s in seq if s.stn == from_stn)
    b = next(s for s in seq if s.stn == to_stn)
    if b.seq <= a.seq:
        raise ValueError("to_stn must come after from_stn")
    return (datetime.combine(run_date + timedelta(days=a.day), a.dep, IST),
            datetime.combine(run_date + timedelta(days=b.day), b.arr, IST))
