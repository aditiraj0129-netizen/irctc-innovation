"""Connection Risk Engine: can the passenger make the change of train?

Not a single subtraction. We test the WHOLE predicted arrival range of the first train against the
second train's departure and the time THIS passenger needs at THIS station (walking speed, step-free).

  slack(x) = next departure - (first-train arrival x + transfer time needed)

  COMFORTABLE  : slack >= 10 min even if the first train arrives at the LATE end of its range
  TIGHT        : slack >= 0 at the late end (works, but little room)
  HIGH_RISK    : works at the middle estimate, fails at the late end
  UNLIKELY     : works only if the train recovers to the EARLY end of its range
  NOT_FEASIBLE : fails even at the early end
  INSUFFICIENT_INFORMATION : no fresh running data, so no range

No probability is given: the arrival range is a heuristic, not a calibrated distribution.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field

from app.domain.models import Event, Journey
from app.plan.transfer import PassengerProfile, required_minutes, station_info
from app.predict.delay import DelayPrediction
from app.domain.models import expected_departure, live_state

COMFORT_SLACK = 10


class ConnRisk(str, Enum):
    COMFORTABLE = "COMFORTABLE"
    TIGHT = "TIGHT"
    HIGH_RISK = "HIGH_RISK"
    UNLIKELY = "UNLIKELY"
    NOT_FEASIBLE = "NOT_FEASIBLE"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class ConnectionRisk(BaseModel):
    station: str
    from_train: str
    to_train: str
    next_departure: datetime
    next_departure_delay_minutes: int = 0
    transfer_minutes_needed: int
    transfer_basis: list[str] = Field(default_factory=list)
    station_complexity: str
    arrival_early: datetime | None
    arrival_expected: datetime | None
    arrival_late: datetime | None
    slack_early: int | None
    slack_expected: int | None
    slack_late: int | None
    risk: ConnRisk
    probability: float | None = None
    probability_status: str = "DISABLED_NOT_CALIBRATED"
    max_tolerable_delay_minutes: int          # if the first train is later than this, the change fails
    watch: dict | None = None                 # next station to check, and the delay that breaks the change
    reasons: list[dict] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


def _slack(dep: datetime, arr: datetime | None, need: int) -> int | None:
    return None if arr is None else int((dep - arr).total_seconds() // 60) - need


def connection_risk(journey: Journey, first_seq: int, pred: DelayPrediction, events: list[Event], now: datetime,
                    profile: PassengerProfile | None = None) -> ConnectionRisk:
    a = journey.legs[first_seq - 1]
    b = journey.legs[first_seq]
    stn = a.to_stn
    need = required_minutes(stn, profile, floor=journey.min_transfer_minutes)
    basis = [f"STATION_{stn}_{station_info(stn)['complexity']}", f"MIN_TRANSFER_{journey.min_transfer_minutes}"]
    p = profile or PassengerProfile()
    if p.speed == "slow":
        basis.append("SLOW_WALKING")
    if p.step_free:
        basis.append("STEP_FREE_ROUTE")
    lb = live_state(b.train_no, events, now)
    dep = expected_departure(b, lb)                 # if the second train is itself late, that helps
    dep_delay = int((dep - b.ticket.scheduled_departure).total_seconds() // 60)
    max_tol = int((dep - a.scheduled_arrival).total_seconds() // 60) - need
    s_e, s_m, s_l = (_slack(dep, pred.arrival_early, need), _slack(dep, pred.expected_arrival, need),
                     _slack(dep, pred.arrival_late, need))
    assumptions = ["BOARDING_CUTOFF_NOT_VERIFIED", "TRANSFER_TIME_SIMULATED_ESTIMATE"]
    if dep_delay:
        assumptions.append("SECOND_TRAIN_DELAY_MAY_CHANGE")

    if pred.expected_arrival is None:
        risk = ConnRisk.INSUFFICIENT_INFORMATION
    elif s_l >= COMFORT_SLACK:
        risk = ConnRisk.COMFORTABLE
    elif s_l >= 0:
        risk = ConnRisk.TIGHT
    elif s_m >= 0:
        risk = ConnRisk.HIGH_RISK
    elif s_e >= 0:
        risk = ConnRisk.UNLIKELY
    else:
        risk = ConnRisk.NOT_FEASIBLE

    reasons = [{"code": "NEED", "minutes": need, "station": stn}]
    if pred.expected_arrival is not None:
        reasons.append({"code": "SLACK_RANGE", "early": s_e, "expected": s_m, "late": s_l})
        if pred.congestion.counted:
            reasons.append({"code": "CONGESTION_AHEAD", "level": pred.congestion.level})
        if pred.weather.applied:
            reasons.append({"code": "FOG_AHEAD", "severity": pred.weather.applied[0]["severity"]})
        if pred.trend.value in ("GROWING", "RECOVERING"):
            reasons.append({"code": "TREND_" + pred.trend.value, "slope": pred.slope_min_per_hour})
    else:
        reasons.append({"code": "NO_FRESH_RUNNING_DATA"})

    # What to monitor next: the next scheduled stop before the change, and the delay that would break it.
    watch = None
    if pred.remaining.sections and len(pred.remaining.sections) > 1:
        nxt = pred.remaining.sections[0].split("-")[1]
        watch = {"station": nxt, "max_delay_minutes": max_tol}
    elif pred.remaining.sections:
        watch = {"station": stn, "max_delay_minutes": max_tol}

    return ConnectionRisk(station=stn, from_train=a.train_no, to_train=b.train_no, next_departure=dep,
                          next_departure_delay_minutes=dep_delay, transfer_minutes_needed=need,
                          transfer_basis=basis, station_complexity=station_info(stn)["complexity"],
                          arrival_early=pred.arrival_early, arrival_expected=pred.expected_arrival,
                          arrival_late=pred.arrival_late, slack_early=s_e, slack_expected=s_m, slack_late=s_l,
                          risk=risk, max_tolerable_delay_minutes=max_tol, watch=watch, reasons=reasons,
                          assumptions=assumptions)
