"""Connecting Train Feasibility with the station walk.

  available transfer time = connecting train departure - first train arrival
  required transfer time  = station walking time (route engine range) + safety buffer (default 5 min)
  margin                  = available - required

Checked at three points of the first train's predicted arrival range, with the matching walking time:
  early arrival + quickest walk, likely arrival + middle walk, late arrival + slowest walk.

  COMFORTABLE  margin >= 10 min even in the late/slow case
  TIGHT        margin >= 0 in the late/slow case
  HIGH_RISK    works in the likely case only
  UNLIKELY     works only in the early/quick case
  NOT_FEASIBLE fails even in the early/quick case
  CANNOT_ASSESS a platform, the arrival time or the station map is missing (no route is invented)

Platform uncertainty: if either platform is only SCHEDULED or PREDICTED (or is stale), the result is capped at
TIGHT and says why. Nothing here is a guarantee.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from app.domain.models import Event, Journey, expected_departure, live_state
from app.plan.transfer import PassengerProfile
from app.predict.delay import DelayPrediction
from app.station import graph
from app.station.platforms import PlatformInfo, PlatformObservation, PStatus, platform_info
from app.station.route import Profile, Route, RouteError, route

DEFAULT_BUFFER = 5
ORDER = ["COMFORTABLE", "TIGHT", "HIGH_RISK", "UNLIKELY", "NOT_FEASIBLE"]


class StationConnection(BaseModel):
    station: str
    station_name: dict | None = None
    has_map: bool
    first_train: str
    first_train_name: str
    second_train: str
    second_train_name: str
    arrival_platform: PlatformInfo
    departure_platform: PlatformInfo
    arrival_early: datetime | None
    arrival_expected: datetime | None
    arrival_late: datetime | None
    scheduled_arrival: datetime
    departure: datetime
    departure_delay_minutes: int = 0
    buffer_minutes: int
    route: Route | None = None
    profile: Profile
    available_minutes: dict | None = None       # {early, likely, late}
    required_minutes: dict | None = None        # {low, likely, high}
    margin_minutes: dict | None = None          # {early, likely, late}
    result: str                                 # COMFORTABLE ... NOT_FEASIBLE | CANNOT_ASSESS
    capped_by: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    reasons: list[dict] = Field(default_factory=list)
    prepare_to_alight: bool = False
    minutes_to_arrival: int | None = None
    data_fresh: bool = False
    location: str | None = None                 # where the walk starts (passenger-chosen, or arrival platform)
    location_source: str = "ARRIVAL_PLATFORM"   # ARRIVAL_PLATFORM | MANUAL | LINK (QR-style) | NONE
    guarantee: bool = False


def _profile(p: PassengerProfile | None) -> tuple[Profile, str]:
    p = p or PassengerProfile()
    return (Profile.STEP_FREE if p.step_free else Profile.FASTEST), ("slow" if p.speed == "slow" else "normal")


def assess_connection(journey: Journey, first_seq: int, pred: DelayPrediction | None, events: list[Event], now: datetime,
                      observations: list[PlatformObservation], profile: PassengerProfile | None = None,
                      buffer: int = DEFAULT_BUFFER, route_profile: Profile | None = None,
                      at: str | None = None, at_source: str = "MANUAL") -> StationConnection:
    a, b = journey.legs[first_seq - 1], journey.legs[first_seq]
    stn = a.to_stn
    st = graph.get(stn)
    arr_p = platform_info(a.train_no, stn, "ARRIVAL", observations, now)
    dep_p = platform_info(b.train_no, stn, "DEPARTURE", observations, now)
    dep = expected_departure(b, live_state(b.train_no, events, now))
    rp, speed = _profile(profile)
    rp = route_profile or rp
    out = StationConnection(
        station=stn, station_name=st.name if st else None, has_map=st is not None, first_train=a.train_no,
        first_train_name=a.train_name, second_train=b.train_no, second_train_name=b.train_name,
        arrival_platform=arr_p, departure_platform=dep_p, arrival_early=pred.arrival_early if pred else None,
        arrival_expected=pred.expected_arrival if pred else None, arrival_late=pred.arrival_late if pred else None,
        scheduled_arrival=a.scheduled_arrival, departure=dep,
        departure_delay_minutes=int((dep - b.ticket.scheduled_departure).total_seconds() // 60),
        buffer_minutes=buffer, profile=rp, result="CANNOT_ASSESS", data_fresh=bool(pred and pred.data_fresh))
    if pred and pred.expected_arrival:
        out.minutes_to_arrival = int((pred.expected_arrival - now).total_seconds() // 60)
        out.prepare_to_alight = pred.data_fresh and 0 <= out.minutes_to_arrival <= 45 and arr_p.platform is not None
    # where does the walk start?
    start = None
    if at:
        if st is None or at not in st.nodes:
            out.missing.append("UNKNOWN_LOCATION")
        else:
            start, out.location, out.location_source = at, at, at_source
    elif arr_p.platform is not None:
        start, out.location, out.location_source = f"PF{arr_p.platform}", f"PF{arr_p.platform}", "ARRIVAL_PLATFORM"
    else:
        out.location_source = "NONE"
    if st is None:
        out.missing.append("NO_STATION_MAP")
    if arr_p.platform is None and not at:
        out.missing.append("ARRIVAL_PLATFORM_UNKNOWN")
    if dep_p.platform is None:
        out.missing.append("DEPARTURE_PLATFORM_UNKNOWN")
    if pred is None or pred.expected_arrival is None:
        out.missing.append("ARRIVAL_TIME_UNKNOWN")
    if out.missing or start is None:
        out.reasons.append({"code": "CANNOT_ASSESS", "missing": out.missing})
        return out
    try:
        r = route(st, start, f"PF{dep_p.platform}", rp, speed)
    except RouteError:
        out.missing.append("PLATFORM_NOT_ON_MAP")
        return out
    out.route = r
    if not r.found:
        out.missing.append(r.reason or "NO_ROUTE")
        out.reasons.append({"code": r.reason or "NO_ROUTE", "profile": rp.value})
        return out
    mid_walk = (r.minutes_low + r.minutes_high) / 2
    avail = {k: int((dep - t).total_seconds() // 60) for k, t in
             (("early", pred.arrival_early), ("likely", pred.expected_arrival), ("late", pred.arrival_late))}
    req = {"low": r.minutes_low + buffer, "likely": round(mid_walk + buffer), "high": r.minutes_high + buffer}
    marg = {"early": avail["early"] - req["low"], "likely": avail["likely"] - req["likely"], "late": avail["late"] - req["high"]}
    res = ("COMFORTABLE" if marg["late"] >= 10 else "TIGHT" if marg["late"] >= 0 else "HIGH_RISK" if marg["likely"] >= 0
           else "UNLIKELY" if marg["early"] >= 0 else "NOT_FEASIBLE")
    for p, code in ((arr_p, "ARRIVAL_PLATFORM_NOT_CONFIRMED"), (dep_p, "DEPARTURE_PLATFORM_NOT_CONFIRMED")):
        if not p.trusted:
            out.capped_by.append(code)
    if out.capped_by and res == "COMFORTABLE":
        res = "TIGHT"
    out.available_minutes, out.required_minutes, out.margin_minutes, out.result = avail, req, marg, res
    out.reasons += [{"code": "WALK", "low": r.minutes_low, "high": r.minutes_high, "m": r.distance_m,
                     "stairs": r.stairs, "lifts": r.lifts},
                    {"code": "AVAILABLE", **avail}, {"code": "BUFFER", "minutes": buffer}]
    if out.capped_by:
        out.reasons.append({"code": "PLATFORM_UNCERTAIN", "which": out.capped_by})
    if r.lifts:
        out.reasons.append({"code": "LIFT_STATUS_UNKNOWN"})
    return out


def trusted_transfer_need(journey: Journey, first_seq: int, observations: list[PlatformObservation], now: datetime,
                          profile: PassengerProfile | None = None, buffer: int = DEFAULT_BUFFER) -> tuple[int, list[str]] | None:
    """Transfer time from the station route, used by the Connection Risk Engine ONLY when both platforms are
    CONFIRMED/REPORTED and fresh. Otherwise None (the general station estimate is kept)."""
    a, b = journey.legs[first_seq - 1], journey.legs[first_seq]
    st = graph.get(a.to_stn)
    if st is None:
        return None
    ap = platform_info(a.train_no, a.to_stn, "ARRIVAL", observations, now)
    dp = platform_info(b.train_no, a.to_stn, "DEPARTURE", observations, now)
    if not (ap.trusted and dp.trusted):
        return None
    rp, speed = _profile(profile)
    try:
        r = route(st, f"PF{ap.platform}", f"PF{dp.platform}", rp, speed)
    except RouteError:
        return None
    if not r.found:
        return None
    return r.minutes_high + buffer, [f"STATION_ROUTE_PF{ap.platform}_TO_PF{dp.platform}", f"BUFFER_{buffer}"]
