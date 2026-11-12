"""Route search over the timetable.

1. earliest_arrival(): the classic Connection Scan Algorithm (CSA). It scans all
   train hops in departure order once and finds the earliest possible arrival.
2. alternatives(): lists concrete options with at most one change of train,
   sorted by arrival. CSA is used in tests to prove the best alternative is
   truly the earliest one.

A change of train is only allowed if there are at least `min_transfer` minutes
between arriving and the next departure. No AI is involved: nothing here can
invent a train that isn't in the timetable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.data.timetable import Connection

def earliest_arrival(conns: list[Connection], origin: str, dest: str, start: datetime,
                     min_transfer: int, exclude_trains: set[str] = frozenset()) -> datetime | None:
    """Connection Scan: earliest arrival at dest leaving origin at/after start."""
    best: dict[str, datetime] = {origin: start}
    on_train: dict[tuple[str, object], bool] = {}   # (train, run_date) -> we can be on it
    mt = timedelta(minutes=min_transfer)
    for c in conns:                                  # already sorted by departure
        if c.train_no in exclude_trains:
            continue
        key = (c.train_no, c.run_date)
        reach = best.get(c.from_stn)
        can_board = reach is not None and (
            (c.from_stn == origin and c.dep >= reach) or (c.from_stn != origin and c.dep >= reach + mt))
        if on_train.get(key) or can_board:
            on_train[key] = True
            if c.to_stn not in best or c.arr < best[c.to_stn]:
                best[c.to_stn] = c.arr
    return best.get(dest) if dest != origin else start


@dataclass
class Ride:
    train_no: str
    train_name: str
    from_stn: str
    dep: datetime
    to_stn: str
    arr: datetime


@dataclass
class Option:
    rides: list[Ride] = field(default_factory=list)

    @property
    def dep(self) -> datetime:
        return self.rides[0].dep

    @property
    def arr(self) -> datetime:
        return self.rides[-1].arr

    @property
    def changes(self) -> int:
        return len(self.rides) - 1

    @property
    def key(self) -> tuple:
        return tuple((r.train_no, r.dep) for r in self.rides)


def _rides_from(conns: list[Connection], origin: str, start: datetime, exclude: set[str]) -> list[Ride]:
    """Every (train run, alighting station) you can ride from origin leaving at/after start."""
    runs: dict[tuple[str, object], list[Connection]] = {}
    for c in conns:
        runs.setdefault((c.train_no, c.run_date), []).append(c)
    rides: list[Ride] = []
    for (train_no, _), hops in runs.items():
        if train_no in exclude:
            continue
        hops.sort(key=lambda h: h.dep)
        for i, h in enumerate(hops):
            if h.from_stn == origin and h.dep >= start:
                for later in hops[i:]:
                    rides.append(Ride(train_no, h.train_name, origin, h.dep, later.to_stn, later.arr))
                break
    return rides


def alternatives(conns: list[Connection], origin: str, dest: str, start: datetime, min_transfer: int,
                 exclude_trains: set[str] = frozenset(), limit: int = 4) -> list[Option]:
    """Options with at most one change, earliest arrival first, then fewer changes."""
    mt = timedelta(minutes=min_transfer)
    options: dict[tuple, Option] = {}
    for r1 in _rides_from(conns, origin, start, set(exclude_trains)):
        if r1.to_stn == dest:
            o = Option([r1])
            options[o.key] = o
            continue
        for r2 in _rides_from(conns, r1.to_stn, r1.arr + mt, set(exclude_trains) | {r1.train_no}):
            if r2.to_stn == dest:
                o = Option([r1, r2])
                options[o.key] = o
    ranked = sorted(options.values(), key=lambda o: (o.arr, o.changes, o.dep))
    # keep only options that aren't beaten on both arrival and departure by an earlier one
    out: list[Option] = []
    for o in ranked:
        if any(p.arr <= o.arr and p.dep >= o.dep and p.changes <= o.changes for p in out):
            continue
        out.append(o)
        if len(out) >= limit:
            break
    return out
