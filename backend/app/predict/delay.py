"""Train Delay Propagation Engine.

Question: will this train win back some of its delay, or lose more, before it reaches a station that matters
(the change of train, or the destination)?

Evidence used (each one is shown to the passenger):
  A. The train's own delay, observation by observation (trend and slope).
  B. Trains AHEAD of it on the same route sections, in the same direction, close in time, that are
     themselves running late: a congestion-RISK indicator, never presented as a confirmed cause.
  C. Fog warnings valid on the sections ahead at the time the train will pass.
  D. Recovery allowances on the sections ahead (how much time the timetable lets a late train win back).

Model: BASELINE_HEURISTIC_V1, a transparent set of documented rules (docs/DELAY_PROPAGATION_INTELLIGENCE.md).
It gives an arrival RANGE and a risk band. It does NOT give probabilities: there is no historical running
data to train or calibrate a model, so `probability` is always None and `probability_status` says why.
A future ML model can implement the same `DelayModel` protocol and be evaluated with app/predict/evaluation.py.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.core.clock import ensure_aware
from app.data.timetable import Stop, train_schedule
from app.detect.detector import STALE_MINUTES
from app.domain.models import Event, EventType, Leg
from app.predict import network
from app.predict.weather import FogSeverity, WeatherProvider
from app.providers import ProviderNotConfigured

MODEL_NAME = "BASELINE_HEURISTIC_V1"

# ----- documented constants (see docs/DELAY_PROPAGATION_INTELLIGENCE.md) -----
TREND_WINDOW_MIN = 300          # observations older than this are not used for the trend
SLOPE_STEADY = 4.0              # |slope| below 4 min per hour = steady
TREND_WEIGHT = 0.5              # only half of the extrapolated trend is trusted ...
TREND_HORIZON_H = 2.0           # ... and only for the next 2 hours
MIN_TREND_SPAN_MIN = 30         # readings closer together than 30 min don't make a trend (a sudden jump is a new delay)
TREND_CAP_MIN = 60              # the trend can move the estimate by at most 60 min
CONGESTION_WINDOW_MIN = 30      # a delayed train counts if it enters the section 0-30 min before us
CONGESTION_MIN_DELAY = 10       # ... and is itself at least 10 min late
NETWORK_FRESH_MIN = 45          # ... and that observation is at most 45 min old
CONGESTION_ADD = {"NONE": 0, "LOW": 5, "MODERATE": 10, "HIGH": 20}      # extra minutes on the LATE end
FOG_ADD = {FogSeverity.MODERATE: 15, FogSeverity.DENSE: 30}             # extra minutes on the LATE end
BASE_UNCERTAINTY_MIN = 10       # late end always gets +10 min ...
UNCERTAINTY_PER_HOUR = 5        # ... plus 5 min per remaining hour, capped
UNCERTAINTY_CAP = 40


class Trend(str, Enum):
    RECOVERING = "RECOVERING"
    STEADY = "STEADY"
    GROWING = "GROWING"
    UNKNOWN = "UNKNOWN"


class Outlook(str, Enum):
    MAY_RECOVER = "MAY_RECOVER"
    LIKELY_STABLE = "LIKELY_STABLE"
    MAY_INCREASE = "MAY_INCREASE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class RiskBand(str, Enum):
    LOWER = "LOWER"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class Observation(BaseModel):
    station: str | None
    delay_minutes: int
    observed_at: datetime
    source: str
    age_minutes: int


class CongestionCheck(BaseModel):
    """One other train we looked at, and whether (and why) it counts."""
    train_no: str
    section: str
    counted: bool
    reason: str      # COUNTED | OPPOSITE_DIRECTION | BEHIND_US | TOO_FAR_AHEAD | NOT_DELAYED | NO_FRESH_OBSERVATION
    its_delay_minutes: int | None = None
    gap_minutes: int | None = None        # how many minutes before us it enters the section (expected)


class Congestion(BaseModel):
    level: str = "NONE"                   # NONE | LOW | MODERATE | HIGH | UNKNOWN
    counted: int = 0
    checks: list[CongestionCheck] = Field(default_factory=list)
    note: str = "CONGESTION_RISK_INDICATOR_NOT_CONFIRMED_CAUSE"


class WeatherContext(BaseModel):
    status: str = "OK"                    # OK | UNAVAILABLE | NOT_CONFIGURED
    provider: str = ""
    applied: list[dict] = Field(default_factory=list)       # warnings valid on a section ahead when we pass
    ignored: list[dict] = Field(default_factory=list)       # expired / not yet valid / other sections
    note: str = "WARNING_RAISES_RISK_NOT_PROOF_OF_CAUSE"


class Remaining(BaseModel):
    from_station: str | None
    to_station: str
    sections: list[str] = Field(default_factory=list)
    km: int = 0
    scheduled_minutes: int = 0
    halts: int = 0
    recovery_allowance_minutes: int = 0


class DelayPrediction(BaseModel):
    train_no: str
    target_station: str
    model: str = MODEL_NAME
    generated_at: datetime
    latest_data_at: datetime | None
    data_fresh: bool
    current_delay_minutes: int | None
    scheduled_arrival: datetime
    expected_arrival: datetime | None
    arrival_early: datetime | None
    arrival_late: datetime | None
    delay_low: int | None
    delay_mid: int | None
    delay_high: int | None
    outlook: Outlook
    growth_risk: RiskBand
    probability: float | None = None
    probability_status: str = "DISABLED_NOT_CALIBRATED"
    trend: Trend
    slope_min_per_hour: float | None
    observations: list[Observation]
    congestion: Congestion
    weather: WeatherContext
    remaining: Remaining
    quality: str                          # GOOD | LIMITED | POOR
    missing_inputs: list[str]
    evidence: list[dict]
    explanation: list[dict]               # codes + numbers; the UI turns them into sentences
    limitations: list[str]
    data_label: str = "SIMULATED"


class DelayModel(Protocol):
    name: str

    def predict(self, f: dict[str, Any]) -> tuple[int, int, int]: ...


class BaselineHeuristicModel:
    """Transparent rules. Input: feature dict. Output: (low, mid, high) delay in minutes at the target."""
    name = MODEL_NAME

    def predict(self, f: dict[str, Any]) -> tuple[int, int, int]:
        d = f["current_delay"]
        hours = max(0.0, f["remaining_minutes"] / 60)
        trend = (f["slope"] or 0.0) * min(hours, TREND_HORIZON_H) * TREND_WEIGHT
        trend = max(-TREND_CAP_MIN, min(TREND_CAP_MIN, trend))
        risk_add = CONGESTION_ADD[f["congestion_level"]] + f["fog_add"]
        mid = max(0, round(d + trend + risk_add / 2))
        recover = f["recovery_allowance"] + (5 if f["trend"] == Trend.RECOVERING else 0)
        low = max(0, min(mid, d) - recover) if hours > 0 else mid
        spread = min(UNCERTAINTY_CAP, BASE_UNCERTAINTY_MIN + round(UNCERTAINTY_PER_HOUR * hours))
        high = mid + risk_add - risk_add // 2 + spread if hours > 0 else mid
        return low, mid, high


def run_date_for(stops: list[Stop], leg: Leg) -> date:
    """The date the train started its run (a leg may board mid-route)."""
    s = next(s for s in stops if s.train_no == leg.train_no and s.stn == leg.from_stn)
    return leg.ticket.scheduled_departure.date() - timedelta(days=s.day)


def _observations(train_no: str, events: list[Event], now: datetime) -> list[Observation]:
    obs = [e for e in events if e.train_no == train_no and e.type == EventType.DELAY and e.observed_at <= now]
    obs.sort(key=lambda e: e.observed_at)
    return [Observation(station=e.station, delay_minutes=e.delay_minutes or 0, observed_at=e.observed_at,
                        source=e.source.value, age_minutes=int((now - e.observed_at).total_seconds() // 60))
            for e in obs]


def _trend(obs: list[Observation], now: datetime) -> tuple[Trend, float | None, list[dict]]:
    recent = [o for o in obs if (now - o.observed_at).total_seconds() / 60 <= TREND_WINDOW_MIN]
    steps = [{"from": a.station, "to": b.station, "change": b.delay_minutes - a.delay_minutes}
             for a, b in zip(recent, recent[1:])]
    if len(recent) < 2:
        return Trend.UNKNOWN, None, steps
    hours = (recent[-1].observed_at - recent[0].observed_at).total_seconds() / 3600
    if hours * 60 < MIN_TREND_SPAN_MIN:
        return Trend.UNKNOWN, None, steps
    slope = round((recent[-1].delay_minutes - recent[0].delay_minutes) / hours, 1)
    if slope >= SLOPE_STEADY:
        return Trend.GROWING, slope, steps
    if slope <= -SLOPE_STEADY:
        return Trend.RECOVERING, slope, steps
    return Trend.STEADY, slope, steps


def _latest_delay(train_no: str, events: list[Event], now: datetime) -> tuple[int, datetime] | None:
    obs = [e for e in events if e.train_no == train_no and e.type == EventType.DELAY and e.observed_at <= now]
    if not obs:
        return None
    e = max(obs, key=lambda e: e.observed_at)
    return e.delay_minutes or 0, e.observed_at


def congestion(stops: list[Stop], our_passes: list[network.SectionPass], our_delay: int,
               network_events: list[Event], now: datetime, our_train: str) -> Congestion:
    """Trains that will be just ahead of us on the SAME section in the SAME direction and are late."""
    ahead_ids = {p.section for p in our_passes}
    others = sorted({s.train_no for s in stops} - {our_train})
    checks: list[CongestionCheck] = []
    for t in others:
        for run in {p.sched_enter.date() for p in our_passes} | {p.sched_enter.date() - timedelta(days=1) for p in our_passes}:
            for op in network.passes(stops, t, run):
                if op.section not in ahead_ids:
                    continue                                  # different section: not relevant at all
                ours = next(p for p in our_passes if p.section == op.section)
                if abs((op.sched_enter - ours.sched_enter).total_seconds()) > 6 * 3600:
                    continue                                  # a different run of that train, far away in time
                if (op.a, op.b) != (ours.a, ours.b):
                    checks.append(CongestionCheck(train_no=t, section=op.section, counted=False,
                                                  reason="OPPOSITE_DIRECTION"))
                    continue
                ld = _latest_delay(t, network_events, now)
                if ld is None or (now - ld[1]).total_seconds() / 60 > NETWORK_FRESH_MIN:
                    checks.append(CongestionCheck(train_no=t, section=op.section, counted=False,
                                                  reason="NO_FRESH_OBSERVATION"))
                    continue
                its_delay = ld[0]
                its_enter = op.sched_enter + timedelta(minutes=its_delay)
                our_enter = ours.sched_enter + timedelta(minutes=our_delay)
                gap = int((our_enter - its_enter).total_seconds() // 60)
                if gap < 0:
                    reason = "BEHIND_US"
                elif gap > CONGESTION_WINDOW_MIN:
                    reason = "TOO_FAR_AHEAD"
                elif its_delay < CONGESTION_MIN_DELAY:
                    reason = "NOT_DELAYED"
                else:
                    reason = "COUNTED"
                checks.append(CongestionCheck(train_no=t, section=op.section, counted=reason == "COUNTED",
                                              reason=reason, its_delay_minutes=its_delay, gap_minutes=gap))
    seen, uniq = set(), []
    for c in checks:                                          # one entry per train and section
        if (c.train_no, c.section) not in seen:
            seen.add((c.train_no, c.section)); uniq.append(c)
    checks = uniq
    n = sum(c.counted for c in checks)
    worst = max((c.its_delay_minutes or 0 for c in checks if c.counted), default=0)
    level = "NONE" if n == 0 else "HIGH" if n >= 3 else "MODERATE" if n == 2 or worst >= 45 else "LOW"
    return Congestion(level=level, counted=n, checks=checks)


def weather_context(provider: WeatherProvider | None, our_passes: list[network.SectionPass], our_delay: int,
                    now: datetime) -> tuple[WeatherContext, int]:
    if provider is None:
        return WeatherContext(status="NOT_CONFIGURED"), 0
    try:
        warnings = provider.fog_warnings(now)
    except (ProviderNotConfigured, Exception) as e:    # provider down = "weather unavailable", never a crash
        return WeatherContext(status="UNAVAILABLE", provider=getattr(provider, "name", "?"),
                              ignored=[{"reason": type(e).__name__}]), 0
    ctx = WeatherContext(provider=provider.name)
    add = 0
    for w in warnings:
        hit = None
        for p in our_passes:
            if not w.covers_section(p.a, p.b):
                continue
            t = p.sched_enter + timedelta(minutes=our_delay)
            if w.valid_at(t):
                hit = p
                break
            ctx.ignored.append({"id": w.id, "section": p.section,
                                "reason": "EXPIRED" if t > w.valid_to else "NOT_YET_VALID"})
        if hit:
            ctx.applied.append({"id": w.id, "severity": w.severity.value, "section": hit.section,
                                "valid_from": w.valid_from.isoformat(), "valid_to": w.valid_to.isoformat(),
                                "issued_at": w.issued_at.isoformat(), "source": w.source})
            add = max(add, FOG_ADD[w.severity])
        elif not any(i.get("id") == w.id for i in ctx.ignored):
            ctx.ignored.append({"id": w.id, "reason": "NOT_ON_ROUTE_AHEAD"})
    return ctx, add


def predict_delay(stops: list[Stop], leg: Leg, events: list[Event], network_events: list[Event],
                  weather: WeatherProvider | None, now: datetime, target_station: str | None = None,
                  model: DelayModel | None = None) -> DelayPrediction:
    now = ensure_aware(now, "now")
    model = model or BaselineHeuristicModel()
    target = target_station or leg.to_stn
    run = run_date_for(stops, leg)
    sched = train_schedule(stops, leg.train_no, run)
    names = [s for s, _, _ in sched]
    sched_arr = next(a for s, a, _ in sched if s == target)
    obs = _observations(leg.train_no, events, now)
    trend, slope, steps = _trend(obs, now)
    missing: list[str] = []
    limitations = ["NO_HISTORICAL_DATA_NO_PROBABILITIES", "SIMULATED_NETWORK_MODEL", "NO_BLOCK_SECTION_OCCUPANCY_DATA"]

    latest = obs[-1] if obs else None
    fresh = latest is not None and latest.age_minutes <= STALE_MINUTES
    d = latest.delay_minutes if latest else None
    if latest is None:
        missing.append("NO_RUNNING_OBSERVATION")
    elif not fresh:
        missing.append("RUNNING_DATA_STALE")
    if trend == Trend.UNKNOWN:
        missing.append("ONLY_ONE_OBSERVATION" if len(obs) == 1 else "NO_TREND")
    if all(o.station is None for o in obs) and obs:
        missing.append("NO_STATION_LEVEL_OBSERVATIONS")

    # Where is the train now (by schedule + current delay), and what is still ahead?
    dd = d or 0
    idx_target = names.index(target)
    pos = 0
    for i, (s, a, dep) in enumerate(sched[: idx_target + 1]):
        t = dep or a
        if t and t + timedelta(minutes=dd) <= now:
            pos = i
    ahead = [p for p in network.passes(stops, leg.train_no, run)
             if names.index(p.a) >= pos and names.index(p.b) <= idx_target]
    secs = [network.section_between(p.a, p.b) for p in ahead]
    remaining_min = max(0, int((sched_arr + timedelta(minutes=dd) - now).total_seconds() // 60))
    rem = Remaining(from_station=names[pos], to_station=target, sections=[p.section for p in ahead],
                    km=sum(s.km for s in secs if s), scheduled_minutes=remaining_min,
                    halts=max(0, idx_target - pos - 1),
                    recovery_allowance_minutes=sum(s.recovery_allowance_min for s in secs if s))
    if not ahead and pos < idx_target:
        missing.append("NO_SECTION_DATA")

    cong = congestion(stops, ahead, dd, network_events, now, leg.train_no) if ahead else Congestion()
    wx, fog_add = weather_context(weather, ahead, dd, now)
    if wx.status != "OK":
        missing.append("WEATHER_UNAVAILABLE")

    evidence = [{"kind": "OWN_TRAIN", "observations": len(obs), "trend": trend.value, "slope": slope, "steps": steps},
                {"kind": "CONGESTION", "level": cong.level, "counted": cong.counted},
                {"kind": "WEATHER", "status": wx.status, "applied": len(wx.applied)},
                {"kind": "RECOVERY_ALLOWANCE", "minutes": rem.recovery_allowance_minutes}]

    base = dict(train_no=leg.train_no, target_station=target, generated_at=now,
                latest_data_at=latest.observed_at if latest else None, data_fresh=fresh,
                current_delay_minutes=d, scheduled_arrival=sched_arr, trend=trend, slope_min_per_hour=slope,
                observations=obs, congestion=cong, weather=wx, remaining=rem, missing_inputs=missing,
                evidence=evidence, limitations=limitations)

    if latest is None or not fresh:
        return DelayPrediction(**base, expected_arrival=None, arrival_early=None, arrival_late=None,
                               delay_low=None, delay_mid=None, delay_high=None,
                               outlook=Outlook.INSUFFICIENT_EVIDENCE, growth_risk=RiskBand.INSUFFICIENT_EVIDENCE,
                               quality="POOR",
                               explanation=[{"code": "NO_FRESH_DATA" if latest else "NO_DATA",
                                             "age": latest.age_minutes if latest else None}])

    low, mid, high = model.predict({"current_delay": d, "remaining_minutes": remaining_min, "slope": slope,
                                    "trend": trend, "congestion_level": cong.level, "fog_add": fog_add,
                                    "recovery_allowance": rem.recovery_allowance_minutes})
    score = {Trend.GROWING: 2, Trend.STEADY: 0, Trend.RECOVERING: -1, Trend.UNKNOWN: 0}[trend]
    score += {"NONE": 0, "LOW": 1, "MODERATE": 2, "HIGH": 3}[cong.level] + (2 if fog_add >= 30 else 1 if fog_add else 0)
    growth = RiskBand.LOWER if score <= 0 else RiskBand.MODERATE if score <= 2 else RiskBand.HIGH
    if trend == Trend.UNKNOWN and score <= 0:
        growth = RiskBand.MODERATE            # one observation is not enough to call the risk "lower"
    outlook = (Outlook.MAY_RECOVER if trend == Trend.RECOVERING and score <= 0 and low < d
               else Outlook.MAY_INCREASE if high - d >= 20 and score >= 1
               else Outlook.LIKELY_STABLE)
    quality = "GOOD" if len(obs) >= 3 and not [m for m in missing if m != "WEATHER_UNAVAILABLE"] else "LIMITED"

    expl = [{"code": "CURRENT_DELAY", "delay": d, "station": latest.station, "at": latest.observed_at.isoformat()},
            {"code": "TREND_" + trend.value, "slope": slope, "observations": len(obs)}]
    if cong.counted:
        expl.append({"code": "CONGESTION_" + cong.level, "trains": [c.train_no for c in cong.checks if c.counted],
                     "sections": sorted({c.section for c in cong.checks if c.counted})})
    if wx.applied:
        expl.append({"code": "FOG_WARNING", "severity": wx.applied[0]["severity"], "section": wx.applied[0]["section"],
                     "valid_to": wx.applied[0]["valid_to"]})
    if rem.recovery_allowance_minutes and remaining_min:
        expl.append({"code": "CAN_RECOVER_UP_TO", "minutes": rem.recovery_allowance_minutes, "sections": rem.sections})
    expl.append({"code": "RANGE", "low": low, "high": high, "target": target})

    return DelayPrediction(**base, expected_arrival=sched_arr + timedelta(minutes=mid),
                           arrival_early=sched_arr + timedelta(minutes=low),
                           arrival_late=sched_arr + timedelta(minutes=high),
                           delay_low=low, delay_mid=mid, delay_high=high, outlook=outlook, growth_risk=growth,
                           quality=quality, explanation=expl)
