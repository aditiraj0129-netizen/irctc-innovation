"""Journey Resilience Score (EXPERIMENTAL).

How well could this journey recover if something goes wrong? A transparent,
rule-based score: each factor has a visible formula and a fixed weight. It is
NOT a validated prediction, has NOT been tested against real historical data,
and must always be shown with the "experimental" label.
"""
from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel

from app.data.timetable import Connection
from app.domain.models import Journey
from app.plan.builder import transfer_rule
from app.plan.csa import alternatives
from app.plan.transfer import PassengerProfile, station_info
from app.twin.twin import JourneyTwin

WEIGHTS = {"CONNECTION_BUFFER": 25, "ALTERNATIVES": 20, "TRANSFER_COMPLEXITY": 15,
           "JOURNEY_DURATION": 10, "SINGLE_TRAIN_DEPENDENCE": 15, "RECOVERY_OPTIONS": 15}


class Factor(BaseModel):
    id: str
    weight: int
    score: int                 # 0-100
    value: str                 # the measured input, shown to the user
    explanation: str           # key for the UI


class Resilience(BaseModel):
    score: int
    label: str = "EXPERIMENTAL"
    factors: list[Factor]
    main_risks: list[str]
    suggestions: list[str]
    method_note: str = "WEIGHTED_RULES_NOT_VALIDATED"


def _step(value: float, steps: list[tuple[float, int]], default: int) -> int:
    for limit, score in steps:
        if value <= limit:
            return score
    return default


def score_journey(journey: Journey, twin: JourneyTwin, conns: list[Connection],
                  profile: PassengerProfile | None = None) -> Resilience:
    f: list[Factor] = []

    # 1. Connection buffer: smallest margin across changes of train (after the passenger's needed time).
    if twin.transfers:
        m = min(t.check.margin_minutes for t in twin.transfers)
        s = 0 if m < 0 else _step(m, [(9, 30), (24, 60), (44, 80)], 100)
        f.append(Factor(id="CONNECTION_BUFFER", weight=WEIGHTS["CONNECTION_BUFFER"], score=s,
                        value=f"{m} min", explanation="MARGIN_AFTER_NEEDED_TRANSFER_TIME"))
    else:
        f.append(Factor(id="CONNECTION_BUFFER", weight=WEIGHTS["CONNECTION_BUFFER"], score=100,
                        value="no change of train", explanation="DIRECT_JOURNEY"))

    # 2. Alternatives: other ways to finish the journey in the next 12 h from the riskiest point.
    point = twin.transfers[0].check.station if twin.transfers else journey.origin
    start = (twin.legs[0].expected_arrival if twin.transfers else journey.legs[0].scheduled_departure)
    booked = {l.train_no for l in journey.legs}
    opts = [o for o in alternatives(conns, point, journey.destination, start, transfer_rule(journey, profile),
                                    booked, limit=10) if o.dep <= start + timedelta(hours=12)]
    n = len(opts)
    f.append(Factor(id="ALTERNATIVES", weight=WEIGHTS["ALTERNATIVES"], score=[0, 40, 70][n] if n < 3 else 100,
                    value=f"{n} within 12 h from {point}", explanation="COUNT_OF_TIMETABLE_ALTERNATIVES"))

    # 3. Transfer complexity of the stations where you change (simulated estimates).
    if twin.transfers:
        worst_c = max((station_info(t.check.station)["complexity"] for t in twin.transfers),
                      key=["LOW", "MEDIUM", "HIGH"].index)
        s = {"LOW": 100, "MEDIUM": 70, "HIGH": 40}[worst_c]
        f.append(Factor(id="TRANSFER_COMPLEXITY", weight=WEIGHTS["TRANSFER_COMPLEXITY"], score=s,
                        value=f"{worst_c} (simulated estimate)", explanation="STATION_COMPLEXITY_SIMULATED"))
    else:
        f.append(Factor(id="TRANSFER_COMPLEXITY", weight=WEIGHTS["TRANSFER_COMPLEXITY"], score=100,
                        value="no change of train", explanation="DIRECT_JOURNEY"))

    # 4. Journey duration: longer journeys have more time for things to go wrong.
    hours = (journey.legs[-1].scheduled_arrival - journey.legs[0].scheduled_departure).total_seconds() / 3600
    f.append(Factor(id="JOURNEY_DURATION", weight=WEIGHTS["JOURNEY_DURATION"],
                    score=_step(hours, [(8, 100), (16, 75), (24, 50)], 30),
                    value=f"{hours:.1f} h", explanation="LONGER_JOURNEY_MORE_EXPOSURE"))

    # 5. Dependence on one train: a single train with no same-day alternative is fragile.
    if len(journey.legs) == 1:
        s = 40 if n == 0 else 70
        val = "one train" + ("" if n else ", no alternative found")
    else:
        s = 80
        val = f"{len(journey.legs)} trains"
    f.append(Factor(id="SINGLE_TRAIN_DEPENDENCE", weight=WEIGHTS["SINGLE_TRAIN_DEPENDENCE"], score=s,
                    value=val, explanation="RELIANCE_ON_ONE_TRAIN"))

    # 6. Recovery options built into the booking (linked PNRs protect a missed connection).
    if len(journey.legs) > 1:
        s = 100 if journey.linked_pnr else 30
        val = "PNRs linked" if journey.linked_pnr else "PNRs not linked"
    else:
        s, val = 70, "single ticket"
    f.append(Factor(id="RECOVERY_OPTIONS", weight=WEIGHTS["RECOVERY_OPTIONS"], score=s, value=val,
                    explanation="LINKED_PNR_PROTECTION"))

    total = round(sum(x.score * x.weight for x in f) / sum(x.weight for x in f))
    risks = [x.id for x in sorted(f, key=lambda x: x.score) if x.score < 60]
    tips = []
    if "CONNECTION_BUFFER" in risks:
        tips.append("CHOOSE_LONGER_CONNECTION")
    if "RECOVERY_OPTIONS" in risks:
        tips.append("LINK_PNRS_WHEN_BOOKING")
    if "ALTERNATIVES" in risks:
        tips.append("NOTE_BACKUP_TRAIN_BEFORE_TRAVEL")
    if "TRANSFER_COMPLEXITY" in risks:
        tips.append("ALLOW_EXTRA_TIME_AT_BIG_STATIONS")
    if "SINGLE_TRAIN_DEPENDENCE" in risks:
        tips.append("KEEP_A_BACKUP_PLAN")
    return Resilience(score=total, factors=f, main_risks=risks, suggestions=tips)
