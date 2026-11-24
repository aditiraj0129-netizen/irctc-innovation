"""JourneyRecoveryEngine: practical ways to still reach the destination.

Searches, from where the passenger will actually be (usually the change-of-train station):
  1. direct trains, 2. one-change trains, 3. two-change trains (only if nothing simpler exists),
  4. trains from a nearby station, 5. eligible unreserved (General) travel, 6. buses (demo samples only),
  7. next-day trains (with Tatkal timing, never a promise of a seat).

Every result carries exactly ONE `result_type`, a data source, an update time, seat availability (always
UNKNOWN until an authorised availability provider is connected) and a fare status (unknown for trains).
Ranking is a transparent weighted sum; every point is listed in `score_parts`. No AI is involved.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, Field

from app.core.clock import IST, ensure_aware
from app.data.timetable import Connection, build_connections
from app.plan.ranker import Priority
from app.plan.transfer import PassengerProfile, RISK_ORDER, TransferClass, check_transfer, station_info
from app.predict import network
from app.providers import ProviderNotConfigured


class ResultType(str, Enum):
    CONFIRMED_SCHEDULE = "CONFIRMED_SCHEDULE"            # from an authorised timetable provider
    LIVE_RUNNING = "LIVE_RUNNING"                        # from authorised live running status
    CONFIRMED_AVAILABILITY = "CONFIRMED_AVAILABILITY"    # seats confirmed by an authorised availability provider
    AVAILABILITY_UNAVAILABLE = "AVAILABILITY_UNAVAILABLE"  # real schedule, but no availability data
    ESTIMATED_ALTERNATIVE = "ESTIMATED_ALTERNATIVE"      # built from estimates (e.g. road times)
    DEMO_SIMULATED = "DEMO_SIMULATED"                    # simulated demo data only


class OptionKind(str, Enum):
    DIRECT = "DIRECT"
    ONE_CHANGE = "ONE_CHANGE"
    TWO_CHANGES = "TWO_CHANGES"
    NEARBY_STATION = "NEARBY_STATION"
    UNRESERVED = "UNRESERVED"
    BUS = "BUS"


class RLeg(BaseModel):
    mode: str                       # TRAIN | BUS | ACCESS
    train_no: str | None = None
    name: str
    from_stn: str
    to_stn: str
    dep: datetime
    arr: datetime
    general_coaches: bool | None = None
    reserved: bool | None = None


class RecoveryOption(BaseModel):
    id: str
    kind: OptionKind
    result_type: ResultType
    legs: list[RLeg]
    departure: datetime
    arrival: datetime
    duration_minutes: int
    transfers: int
    transfer_risk: TransferClass | None = None
    next_day: bool = False
    service: str                    # RESERVED | RESERVED_AND_GENERAL | UNRESERVED_ONLY | ROAD
    seat_availability: str = "UNKNOWN_NOT_CONNECTED"
    fare_paise: int | None = None
    fare_status: str = "NOT_AVAILABLE"          # NOT_AVAILABLE | SAMPLE_NOT_REAL | CONFIRMED
    data_source: str
    last_updated: datetime | None = None
    ticket_action: list[str] = Field(default_factory=list)
    unreserved: dict | None = None
    tatkal: dict | None = None
    score: float = 0.0
    rank: int = 0
    score_parts: list[dict] = Field(default_factory=list)


class RecoverySearch(BaseModel):
    origin: str
    destination: str
    earliest_start: datetime
    reason: str                     # CONNECTION_AT_RISK | CONNECTION_BROKEN | TRAIN_DISRUPTED | BACKUP_ONLY
    now: datetime
    window_hours: int
    options: list[RecoveryOption]
    next_day: list[RecoveryOption]
    unreserved: list[RecoveryOption]
    buses: list[RecoveryOption]
    bus_status: str                 # DEMO_SAMPLES | NOT_CONFIGURED | NONE_FOUND
    empty_reason: str | None = None
    weights: dict
    rules: dict
    data_label: str = "SIMULATED"


# ----- rule summaries shown with unreserved / Tatkal options (sources in the knowledge base) -----
UNRESERVED_RULES = {
    "id": "GUIDE-UNRESERVED",
    "points": ["SEPARATE_UNRESERVED_TICKET_NEEDED", "GENERAL_COACHES_ONLY", "RESERVED_TICKET_OF_OTHER_TRAIN_NOT_VALID",
               "BUY_BEFORE_BOARDING_UTS_RAILONE_COUNTER", "PENALTY_IN_RESERVED_COACH"],
    "status": "GENERAL_GUIDANCE",
}
TATKAL_RULES = {
    "id": "GUIDE-TATKAL",
    "ac_opens": "10:00", "non_ac_opens": "11:00", "days_before": 1,
    "points": ["OPENS_DAY_BEFORE_JOURNEY", "AADHAAR_OTP_REQUIRED", "NOT_GUARANTEED", "CONFIRMED_TATKAL_NO_REFUND"],
    "status": "SUMMARY_OF_ANNOUNCED_RULE",
}
AC_CLASSES = {"1A", "2A", "3A", "3E", "CC", "EC"}

WEIGHTS = {
    Priority.TIME: {"arrival_per_30min": 1.0, "transfer": 0.5, "risk": 1.0},
    Priority.MONEY: {"arrival_per_30min": 0.6, "transfer": 0.5, "risk": 1.0},
    Priority.RISK: {"arrival_per_30min": 0.6, "transfer": 0.8, "risk": 2.0},
    Priority.TRANSFERS: {"arrival_per_30min": 0.6, "transfer": 2.0, "risk": 1.0},
    Priority.FAMILY: {"arrival_per_30min": 0.6, "transfer": 1.0, "risk": 1.5},
}
RISK_POINTS = {TransferClass.COMFORTABLE: 0.0, TransferClass.TIGHT: 0.5, TransferClass.HIGH_RISK: 1.5}
MODE_POINTS = {OptionKind.NEARBY_STATION: 0.5, OptionKind.BUS: 1.0, OptionKind.UNRESERVED: 0.0}


# ----- bus providers -----
class BusProvider(Protocol):
    name: str

    def buses(self, origin: str, dest: str, after: datetime, until: datetime) -> list[RecoveryOption]: ...


class DemoSampleBusProvider:
    """Demo mode only. SAMPLE buses from network.yaml: not real timetables, fares or seats."""
    name = "DEMO_SAMPLE_BUSES"

    def buses(self, origin: str, dest: str, after: datetime, until: datetime) -> list[RecoveryOption]:
        out = []
        for b in network.bus_samples():
            if b["from_station"] != origin or b["to_station"] != dest:
                continue
            for day in {after.date(), after.date() + timedelta(days=1)}:
                for hhmm in b["departures"]:
                    dep = datetime.combine(day, time.fromisoformat(hhmm), IST)
                    start = dep - timedelta(minutes=b["access_minutes"])
                    if not (after <= start <= until):
                        continue
                    arr = dep + timedelta(minutes=b["duration_minutes"])
                    end = arr + timedelta(minutes=b["egress_minutes"])
                    legs = [RLeg(mode="ACCESS", name=f"{origin} → {b['from_terminal']}", from_stn=origin,
                                 to_stn="BUS", dep=start, arr=dep),
                            RLeg(mode="BUS", name=b["operator"], from_stn=b["from_terminal"], to_stn=b["to_terminal"],
                                 dep=dep, arr=arr),
                            RLeg(mode="ACCESS", name=f"{b['to_terminal']} → {dest}", from_stn="BUS", to_stn=dest,
                                 dep=arr, arr=end)]
                    out.append(RecoveryOption(
                        id=f"BUS-{dep:%Y%m%d%H%M}", kind=OptionKind.BUS, result_type=ResultType.DEMO_SIMULATED,
                        legs=legs, departure=start, arrival=end, duration_minutes=int((end - start).total_seconds() // 60),
                        transfers=0, service="ROAD", fare_paise=b["sample_fare_paise"], fare_status="SAMPLE_NOT_REAL",
                        data_source="DEMO_SAMPLE_NOT_REAL", ticket_action=["BUY_BUS_TICKET_FROM_OPERATOR"]))
        return out


class NoBusProvider:
    name = "NOT_CONFIGURED"

    def buses(self, origin: str, dest: str, after: datetime, until: datetime) -> list[RecoveryOption]:
        raise ProviderNotConfigured("No authorised bus timetable provider is connected")


# ----- search -----
def _runs(conns: list[Connection]) -> dict[tuple[str, date], list[Connection]]:
    r: dict[tuple[str, date], list[Connection]] = defaultdict(list)
    for c in conns:
        r[(c.train_no, c.run_date)].append(c)
    for v in r.values():
        v.sort(key=lambda c: c.dep)
    return r


def _hops(run: list[Connection], frm: str) -> list[tuple[str, datetime, datetime]]:
    """(station reached, departure from `frm`, arrival there) for every later stop of a run."""
    out, dep = [], None
    for c in run:
        if dep is None and c.from_stn == frm:
            dep = c.dep
        if dep is not None:
            out.append((c.to_stn, dep, c.arr))
    return out


def _train_leg(c0: Connection, to: str, dep: datetime, arr: datetime, frm: str) -> RLeg:
    info = network.train_info(c0.train_no)
    return RLeg(mode="TRAIN", train_no=c0.train_no, name=c0.train_name, from_stn=frm, to_stn=to, dep=dep, arr=arr,
                general_coaches=info.general_coaches, reserved=info.reserved)


def _service(legs: list[RLeg]) -> str:
    trains = [l for l in legs if l.mode == "TRAIN"]
    if trains and all(l.reserved is False for l in trains):
        return "UNRESERVED_ONLY"
    if trains and all(l.general_coaches for l in trains):
        return "RESERVED_AND_GENERAL"
    return "RESERVED"


def _make(kind: OptionKind, legs: list[RLeg], profile: PassengerProfile | None, floor: int) -> RecoveryOption | None:
    checks = []
    trains = [l for l in legs if l.mode == "TRAIN"]
    for a, b in zip(trains, trains[1:]):
        checks.append(check_transfer(a.to_stn, a.arr, b.dep, profile, floor))
    if any(c.cls == TransferClass.NOT_FEASIBLE for c in checks):
        return None
    risk = max((c.cls for c in checks), key=lambda c: RISK_ORDER[c], default=None)
    key = "+".join(f"{l.train_no or l.mode}@{l.dep:%m%d%H%M}" for l in legs)
    return RecoveryOption(id=key, kind=kind, result_type=ResultType.DEMO_SIMULATED, legs=legs, departure=legs[0].dep,
                          arrival=legs[-1].arr, duration_minutes=int((legs[-1].arr - legs[0].dep).total_seconds() // 60),
                          transfers=len(trains) - 1, transfer_risk=risk, service=_service(legs),
                          data_source="SIMULATED_TIMETABLE", ticket_action=["BOOK_NEW_TICKET_IRCTC_CHECK_SEATS"])


def search_trains(conns: list[Connection], origin: str, dest: str, start: datetime, until: datetime,
                  exclude: set[tuple[str, date]], profile: PassengerProfile | None, floor: int
                  ) -> list[RecoveryOption]:
    runs = _runs(conns)
    out: list[RecoveryOption] = []

    def from_station(frm: str, after: datetime, kind: OptionKind, prefix: list[RLeg]) -> list[RecoveryOption]:
        found = []
        for (tn, rd), run in runs.items():
            if (tn, rd) in exclude:
                continue
            hops = _hops(run, frm)
            if not hops or not (after <= hops[0][1] <= until):
                continue
            for stn, dep, arr in hops:
                if stn == dest:
                    o = _make(kind, [*prefix, _train_leg(run[0], dest, dep, arr, frm)], profile, floor)
                    if o:
                        found.append(o)
        return found

    direct = from_station(origin, start, OptionKind.DIRECT, [])
    out += direct
    # one change at any intermediate station
    for (tn, rd), run in runs.items():
        if (tn, rd) in exclude:
            continue
        hops = _hops(run, origin)
        if not hops or not (start <= hops[0][1] <= until):
            continue
        for stn, dep, arr in hops:
            if stn == dest:
                break
            first = _train_leg(run[0], stn, dep, arr, origin)
            for (tn2, rd2), run2 in runs.items():
                if tn2 == tn or (tn2, rd2) in exclude:
                    continue
                hops2 = _hops(run2, stn)
                if not hops2 or not (arr < hops2[0][1] <= arr + timedelta(hours=6)):
                    continue
                for stn2, dep2, arr2 in hops2:
                    if stn2 == dest:
                        o = _make(OptionKind.ONE_CHANGE, [first, _train_leg(run2[0], dest, dep2, arr2, stn)],
                                  profile, floor)
                        if o:
                            out.append(o)
    # nearby stations (getting there is an ESTIMATE)
    for nb in network.nearby(origin):
        reach = start + timedelta(minutes=nb["minutes"])
        access = RLeg(mode="ACCESS", name=nb["mode"], from_stn=origin, to_stn=nb["code"], dep=start, arr=reach)
        for o in from_station(nb["code"], reach + timedelta(minutes=10), OptionKind.NEARBY_STATION, []):
            o.legs = [access.model_copy(update={"dep": o.departure - timedelta(minutes=nb["minutes"] + 10),
                                                "arr": o.departure - timedelta(minutes=10)}), *o.legs]
            o.departure = o.legs[0].dep
            o.duration_minutes = int((o.arrival - o.departure).total_seconds() // 60)
            o.result_type = ResultType.DEMO_SIMULATED
            o.ticket_action = ["TRAVEL_TO_NEARBY_STATION", *o.ticket_action]
            out.append(o)
    # deduplicate (same trains, same departures)
    seen, uniq = set(), []
    for o in sorted(out, key=lambda o: (o.arrival, o.transfers)):
        if o.id not in seen:
            seen.add(o.id)
            uniq.append(o)
    return pareto(uniq)


def pareto(opts: list[RecoveryOption]) -> list[RecoveryOption]:
    """Drop an option if another one leaves no earlier, arrives no later, with no more changes
    (and is strictly better in one of them). Example: 'train A then change to train B' is dropped
    when you could simply wait and take train B all the way."""
    def dominates(y: RecoveryOption, x: RecoveryOption) -> bool:
        if y.kind == OptionKind.NEARBY_STATION and x.kind != OptionKind.NEARBY_STATION:
            return False                      # different kind of effort; keep both
        better_eq = y.departure >= x.departure and y.arrival <= x.arrival and y.transfers <= x.transfers
        strict = y.departure > x.departure or y.arrival < x.arrival or y.transfers < x.transfers
        return better_eq and strict
    return [x for x in opts if not any(dominates(y, x) for y in opts if y is not x)]


def _score(opts: list[RecoveryOption], priority: Priority, profile: PassengerProfile | None) -> None:
    if not opts:
        return
    w = WEIGHTS[priority]
    best = min(o.arrival for o in opts)
    for o in opts:
        late = int((o.arrival - best).total_seconds() // 60)
        parts = [{"code": "ARRIVAL_LATER_THAN_BEST", "minutes": late, "points": round(late / 30 * w["arrival_per_30min"], 2)},
                 {"code": "TRANSFERS", "count": o.transfers, "points": round(o.transfers * w["transfer"], 2)}]
        if o.transfer_risk:
            parts.append({"code": "TRANSFER_RISK", "risk": o.transfer_risk.value,
                          "points": round(RISK_POINTS.get(o.transfer_risk, 0) * w["risk"], 2)})
        if MODE_POINTS.get(o.kind):
            parts.append({"code": "MODE_" + o.kind.value, "points": MODE_POINTS[o.kind]})
        if profile and profile.step_free:
            hard = [l.to_stn for l in o.legs[:-1] if l.mode == "TRAIN" and station_info(l.to_stn)["complexity"] == "HIGH"]
            if hard:
                parts.append({"code": "STEP_FREE_HARD_STATION", "stations": hard, "points": 1.0})
        parts.append({"code": "SEATS_UNKNOWN", "points": 0.0})     # same for all: not used to reorder
        parts.append({"code": "FARE_UNKNOWN", "points": 0.0})
        o.score_parts = parts
        o.score = round(sum(p["points"] for p in parts), 2)
    opts.sort(key=lambda o: (o.score, o.arrival))
    for i, o in enumerate(opts, start=1):
        o.rank = i


def _tatkal(o: RecoveryOption, travel_class: str, now: datetime) -> dict:
    opens_t = TATKAL_RULES["ac_opens"] if travel_class in AC_CLASSES else TATKAL_RULES["non_ac_opens"]
    opens = datetime.combine(o.departure.date() - timedelta(days=1), time.fromisoformat(opens_t), IST)
    return {"opens_at": opens.isoformat(), "state": "OPEN_NOW" if now >= opens else "OPENS_LATER",
            "class": travel_class, "availability": "UNKNOWN_NOT_CONNECTED", "guaranteed": False,
            "rule": TATKAL_RULES["id"]}


def recover(conns: list[Connection], origin: str, dest: str, earliest: datetime, now: datetime, reason: str,
            exclude: set[tuple[str, date]], profile: PassengerProfile | None = None,
            priority: Priority = Priority.TIME, travel_class: str = "3A", floor: int = 30,
            bus: BusProvider | None = None, window_hours: int = 12) -> RecoverySearch:
    earliest, now = ensure_aware(earliest, "earliest"), ensure_aware(now, "now")
    same_day_end = earliest + timedelta(hours=window_hours)
    horizon = earliest + timedelta(hours=36)
    allr = search_trains(conns, origin, dest, earliest, horizon, exclude, profile, floor)
    for o in allr:
        # "Next day" = a service on a later calendar day from 04:00 on. A train leaving at 00:30 tonight
        # is still a "tonight" option.
        o.next_day = o.departure.date() > earliest.date() and o.departure.hour >= 4
        o.last_updated = now
    today = [o for o in allr if not o.next_day]
    nextd = [o for o in allr if o.next_day]
    for o in nextd:
        o.tatkal = _tatkal(o, travel_class, now)
        o.ticket_action = [*o.ticket_action, "TATKAL_IF_NEEDED_NOT_GUARANTEED"]
    # unreserved: same-day trains whose every train has General coaches
    unres = []
    for o in today:
        if all(l.general_coaches for l in o.legs if l.mode == "TRAIN"):
            u = o.model_copy(deep=True)
            u.id, u.kind = "UR-" + o.id, OptionKind.UNRESERVED
            u.ticket_action = ["BUY_UNRESERVED_TICKET_BEFORE_BOARDING", "TRAVEL_IN_GENERAL_COACH_ONLY"]
            u.unreserved = {"permits_unreserved": True, "separate_ticket_required": True,
                            "current_ticket_valid": False, "coach": "GENERAL_ONLY",
                            "train_attribute_verified": False, "rule": UNRESERVED_RULES["id"]}
            u.seat_availability = "NO_SEAT_RESERVATION_CROWDING_POSSIBLE"
            unres.append(u)
    buses, bus_status = [], "NOT_CONFIGURED"
    if bus is not None:
        try:
            buses = bus.buses(origin, dest, earliest, same_day_end)
            bus_status = "DEMO_SAMPLES" if buses else "NONE_FOUND"
            for b in buses:
                b.last_updated = now
        except ProviderNotConfigured:
            buses, bus_status = [], "NOT_CONFIGURED"
    _score(today, priority, profile)
    _score(nextd, priority, profile)
    _score(unres, priority, profile)
    _score(buses, priority, profile)
    empty = None if (today or nextd or buses) else "NO_ALTERNATIVE_FOUND"
    return RecoverySearch(origin=origin, destination=dest, earliest_start=earliest, reason=reason, now=now,
                          window_hours=window_hours, options=today[:6], next_day=nextd[:4], unreserved=unres[:4],
                          buses=buses[:3], bus_status=bus_status, empty_reason=empty,
                          weights={k.value: v for k, v in WEIGHTS.items()} | {"risk_points": {k.value: v for k, v in RISK_POINTS.items()},
                                                                               "mode_points": {k.value: v for k, v in MODE_POINTS.items()}},
                          rules={"unreserved": UNRESERVED_RULES, "tatkal": TATKAL_RULES})


def connections_window(stops, start: date, days: int = 3) -> list[Connection]:
    return build_connections(stops, start, days=days)
