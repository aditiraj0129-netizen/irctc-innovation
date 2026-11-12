"""Plan builder: turns a situation into concrete, rule-backed options.

Plans come ONLY from the rules engine and the timetable. Money figures are
always computed by the rules engine. Alternative trains are marked
CHECK_AVAILABILITY because we have no live seat data.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.data.timetable import Connection
from app.detect.detector import Assessment, SituationType
from app.domain.models import Journey, expected_arrival, expected_departure
from app.plan.csa import Option, alternatives
from app.plan.models import Certainty, Plan, PlanKind, RideOut
from app.plan.transfer import PassengerProfile, TransferClass, check_transfer, required_minutes, worst
from app.rules.engine import (
    RuleRegistry, cancellation_refund, late_running_tdr, missed_connection_tdr, train_cancelled,
    waitlisted_after_chart,
)
from app.rules.models import Outcome

BOOKING_BUFFER_MIN = 30   # our assumption: time needed to book and reach the platform


def _rides(o: Option) -> list[RideOut]:
    return [RideOut(**r.__dict__) for r in o.rides]


def transfer_rule(journey: Journey, profile: PassengerProfile | None):
    """Per-station minimum change time for this passenger (never below the journey's own minimum)."""
    return lambda stn: required_minutes(stn, profile, journey.min_transfer_minutes)


def _alt_plans(base_id: str, kind: PlanKind, opts: list[Option], journey: Journey | None = None,
               profile: PassengerProfile | None = None, **common) -> list[Plan]:
    plans = []
    floor = journey.min_transfer_minutes if journey else 30
    for i, o in enumerate(opts, start=1):
        book_by = o.dep - timedelta(minutes=BOOKING_BUFFER_MIN)
        deadline = min(d for d in [common.get("deadline"), book_by] if d is not None)
        checks = [check_transfer(a.to_stn, a.arr, b.dep, profile, floor) for a, b in zip(o.rides, o.rides[1:])]
        if any(c.cls == TransferClass.NOT_FEASIBLE for c in checks):
            continue                       # never offer a change the passenger can't make
        w = worst(checks)
        warnings = list(common.get("warnings", []))
        if w == TransferClass.HIGH_RISK:
            warnings.append("TRANSFER_HIGH_RISK")
        plans.append(Plan(id=f"{base_id}-{i}", kind=kind, travels=True, arrival=o.arr, rides=_rides(o),
                          needs_new_ticket=True, certainty=Certainty.CHECK_AVAILABILITY,
                          transfers=checks, worst_transfer=w, changes=o.changes,
                          **{**common, "deadline": deadline, "warnings": warnings}))
    return plans


def build_plans(journey: Journey, assessment: Assessment, conns: list[Connection],
                registry: RuleRegistry, profile: PassengerProfile | None = None) -> list[Plan]:
    now = assessment.now
    sit = assessment.primary
    live = assessment.live
    first, last = journey.legs[0], journey.legs[-1]
    plans: list[Plan] = []
    start_alt = now + timedelta(minutes=BOOKING_BUFFER_MIN)
    mt = transfer_rule(journey, profile)
    alt = dict(journey=journey, profile=profile)

    if sit.type in (SituationType.STALE_DATA, SituationType.JOURNEY_OVER):
        return [Plan(id="official", kind=PlanKind.USE_OFFICIAL_CHANNEL, travels=False,
                     certainty=Certainty.UNCERTAIN)]

    if sit.type in (SituationType.ALL_CLEAR, SituationType.NOT_WATCHING_YET, SituationType.NEAR_3H):
        arr = expected_arrival(last, live[last.train_no])
        kind = PlanKind.TRAVEL_DELAYED if sit.type == SituationType.NEAR_3H else PlanKind.TRAVEL_AS_BOOKED
        plans.append(Plan(id="travel", kind=kind, travels=True, arrival=arr, certainty=Certainty.BOOKED,
                          warnings=["MAY_BECOME_TDR_ELIGIBLE"] if sit.type == SituationType.NEAR_3H else []))
        plans.append(_cancel_plan(journey, now, registry))
        return plans

    if sit.type == SituationType.LATE_OVER_3H:
        st = live[first.train_no]
        exp_dep = expected_departure(first, st)
        plans.append(Plan(id="travel", kind=PlanKind.TRAVEL_DELAYED, travels=True,
                          arrival=expected_arrival(last, live[last.train_no]), certainty=Certainty.BOOKED))
        tdr = late_running_tdr(first.ticket, st.delay_minutes, exp_dep, now, registry)
        if tdr.outcome == Outcome.ELIGIBLE_TO_FILE_TDR:
            common = dict(money_back_paise=tdr.refund_paise, money_back_if_approved=True,
                          money_lost_paise=first.ticket.total_fare_paise - tdr.refund_paise,
                          deadline=tdr.deadline, decisions=[tdr])
            plans.append(Plan(id="tdr", kind=PlanKind.FILE_TDR_LATE, travels=False,
                              certainty=Certainty.IF_APPROVED, **common))
            delayed_arr = expected_arrival(last, live[last.train_no])
            opts = [o for o in alternatives(conns, journey.origin, journey.destination, start_alt,
                                            mt, {first.train_no})
                    if o.arr < delayed_arr]
            plans += _alt_plans("tdr-alt", PlanKind.TDR_LATE_PLUS_ALTERNATIVE, opts[:2], **alt, **common)
        elif tdr.outcome == Outcome.NEEDS_VERIFICATION:
            plans.append(Plan(id="official", kind=PlanKind.USE_OFFICIAL_CHANNEL, travels=False,
                              certainty=Certainty.UNCERTAIN, decisions=[tdr]))
        plans.append(_cancel_plan(journey, now, registry))
        return plans

    if sit.type in (SituationType.WAITLISTED_AFTER_CHART, SituationType.TRAIN_CANCELLED):
        leg = next(l for l in journey.legs if l.seq == sit.leg_seq)
        d = (waitlisted_after_chart(leg.ticket, now, registry) if sit.type == SituationType.WAITLISTED_AFTER_CHART
             else train_cancelled(leg.ticket, now, registry))
        common = dict(money_back_paise=d.refund_paise, money_lost_paise=leg.ticket.total_fare_paise - d.refund_paise,
                      decisions=[d], decision_leg=leg.seq)
        plans.append(Plan(id="auto", kind=PlanKind.AUTO_REFUND_WAIT, travels=False,
                          certainty=Certainty.AUTOMATIC, **common))
        opts = alternatives(conns, leg.from_stn, journey.destination, start_alt, mt, {leg.train_no})
        plans += _alt_plans("auto-alt", PlanKind.AUTO_REFUND_PLUS_ALTERNATIVE, opts[:3], **alt, **common)
        return plans

    if sit.type == SituationType.CONNECTION_AT_RISK:
        b = next(l for l in journey.legs if l.seq == sit.leg_seq)
        a = next(l for l in journey.legs if l.seq == sit.leg_seq - 1)
        arr_a = expected_arrival(a, live[a.train_no])
        opts = alternatives(conns, b.from_stn, journey.destination,
                            max(arr_a + timedelta(minutes=mt(b.from_stn)), start_alt), mt, {b.train_no})
        if journey.linked_pnr:
            d = missed_connection_tdr(b.ticket, True, arr_a, now, registry)
            common = dict(money_back_paise=d.refund_paise, money_back_if_approved=True,
                          money_lost_paise=b.ticket.total_fare_paise - d.refund_paise, deadline=d.deadline,
                          deadline_unverified=True, decisions=[d], warnings=list(d.warnings), decision_leg=b.seq)
            plans += _alt_plans("mc-alt", PlanKind.TDR_MISSED_CONNECTION_PLUS_ALTERNATIVE, opts[:3], **alt, **common)
            plans.append(Plan(id="mc-tdr", kind=PlanKind.TDR_MISSED_CONNECTION_ONLY, travels=False,
                              certainty=Certainty.IF_APPROVED, **common))
        else:
            d = cancellation_refund(b.ticket, now, registry)
            common = dict(money_back_paise=d.refund_paise, money_lost_paise=b.ticket.total_fare_paise - d.refund_paise,
                          decisions=[d], warnings=list(d.warnings), decision_leg=b.seq)
            plans += _alt_plans("cx-alt", PlanKind.CANCEL_NEXT_LEG_PLUS_ALTERNATIVE, opts[:3], **alt, **common)
        return plans

    return [Plan(id="official", kind=PlanKind.USE_OFFICIAL_CHANNEL, travels=False, certainty=Certainty.UNCERTAIN)]


def _cancel_plan(journey: Journey, now: datetime, registry: RuleRegistry) -> Plan:
    from app.rules.engine import next_slab_change
    t = journey.legs[0].ticket
    d = cancellation_refund(t, now, registry)
    total = sum(l.ticket.total_fare_paise for l in journey.legs)
    deadline = next_slab_change(t, now, registry) if d.outcome == Outcome.REFUND_ON_CANCEL else None
    return Plan(id="cancel", kind=PlanKind.CANCEL_NOW, travels=False, money_back_paise=d.refund_paise,
                money_lost_paise=total - d.refund_paise if len(journey.legs) == 1 else t.total_fare_paise - d.refund_paise,
                deadline=deadline, certainty=Certainty.AUTOMATIC if d.outcome == Outcome.REFUND_ON_CANCEL
                else Certainty.UNCERTAIN, decisions=[d], warnings=list(d.warnings))
