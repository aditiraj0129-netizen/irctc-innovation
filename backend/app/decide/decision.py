"""Passenger Decision Model: PREDICT -> DECIDE -> RECOVER, in one answer.

Builds, for one journey at one moment:
  * header      - what is happening (first train, arrival range, next departure, time available, risk, freshness)
  * prediction  - Delay Propagation Engine output (range + risk band, never a fake probability)
  * connection  - Connection Risk Engine output
  * cards       - six options, always filled: CONTINUE, CANCEL, OTHER_TRAIN, UNRESERVED, BUS, NEXT_SERVICE.
                  If something cannot be calculated, the card says WHAT is missing (never a blank box).
  * money       - side-by-side: cancel now / wait 15 min / wait until the decision point / cancel later /
                  keep ticket and claim (TDR) / alternative. Amounts only from the deterministic rules engine.
  * recommendation - one plain next step, chosen by documented rules (docs/PASSENGER_DECISION_MODEL.md).

Every money figure is an ESTIMATE from versioned rules; a TDR is a request the Zonal Railway decides.
Nothing here books, cancels or files anything.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from app.core.clock import ensure_aware
from app.detect.detector import SituationType
from app.domain.models import Event, Journey, Leg, expected_departure, live_state
from app.plan.models import PlanKind
from app.plan.ranker import Priority
from app.plan.service import assess, registry, stops
from app.plan.transfer import PassengerProfile, required_minutes
from app.predict.connection import ConnectionRisk, ConnRisk, connection_risk
from app.predict.delay import DelayPrediction, predict_delay, run_date_for
from app.predict.weather import WeatherProvider
from app.recover.engine import BusProvider, RecoverySearch, connections_window, recover
from app.rules.engine import cancellation_refund, late_running_tdr, missed_connection_tdr, next_slab_change
from app.rules.models import Decision as RuleDecision
from app.rules.models import Outcome
from app.twin.twin import LegState, build_twin

CARD_KEYS = ["CONTINUE", "CANCEL", "OTHER_TRAIN", "UNRESERVED", "BUS", "NEXT_SERVICE"]
BAD = {ConnRisk.HIGH_RISK, ConnRisk.UNLIKELY, ConnRisk.NOT_FEASIBLE}
BROKEN = {ConnRisk.UNLIKELY, ConnRisk.NOT_FEASIBLE}


class Card(BaseModel):
    key: str
    status: str                       # AVAILABLE | NOT_APPLICABLE | DATA_MISSING | NONE_FOUND | NOT_CONFIGURED
    recommended: bool = False
    meaning: str                      # code: what this option means
    outcome: dict = Field(default_factory=dict)       # what happens if chosen (codes + numbers)
    money: dict = Field(default_factory=dict)         # {kind, paise, certainty, rule_ids, legal_status}
    risk: str | None = None
    deadline: datetime | None = None
    deadline_kind: str | None = None
    deadline_unverified: bool = False
    next_action: dict = Field(default_factory=dict)   # {code, ...numbers}
    items: list[dict] = Field(default_factory=list)   # trains / buses / rules shown on the card
    missing: list[str] = Field(default_factory=list)
    reason: str | None = None         # why NOT_APPLICABLE / NONE_FOUND / DATA_MISSING


class MoneyRow(BaseModel):
    key: str                          # CANCEL_NOW | WAIT_15 | WAIT_UNTIL | CANCEL_LATER | KEEP_AND_CLAIM | ALTERNATIVE
    at: datetime | None
    applicable: bool = True
    reason: str | None = None
    money_back_paise: int | None
    charge_paise: int | None
    certainty: str                    # RULE_ESTIMATE | IF_APPROVED | AUTOMATIC | NONE | UNKNOWN
    deadline: datetime | None = None
    travel_outcome: str               # NO_TRAVEL | TRAVEL_BOOKED | TRAVEL_NEW_TICKET | DEPENDS
    risk: str | None = None
    next_step: str
    rule_ids: list[str] = Field(default_factory=list)
    legal_status: str | None = None


class Claims(BaseModel):
    """Kept apart on purpose: an estimate is not an eligibility, which is not a submission, which is not money."""
    cancellation_refund_estimate_paise: int | None = None
    tdr_eligibility: str = "NOT_ASSESSED"         # ELIGIBLE_IF_MISSED | ELIGIBLE_NOW | NOT_ELIGIBLE | MAY_BECOME_ELIGIBLE | NOT_RELEVANT
    tdr_reason: str | None = None
    tdr_submission: str = "NOT_SUBMITTED_BY_AGLA_KADAM"
    railway_approval: str = "UNKNOWN"
    refund_received: str = "UNKNOWN"


class DecisionView(BaseModel):
    journey_id: str
    now: datetime
    priority: Priority
    header: dict
    prediction: DelayPrediction | None
    connection: ConnectionRisk | None
    recovery: RecoverySearch
    cards: list[Card]
    money: list[MoneyRow]
    claims: Claims
    recommendation: dict
    data_label: str = "SIMULATED"
    disclaimer: str = "ESTIMATES_NOT_GUARANTEED_RAILWAY_DECIDES_TDR"


def _active_leg(journey: Journey, twin) -> Leg | None:
    for leg, tl in zip(journey.legs, twin.legs):
        if tl.state != LegState.ARRIVED:
            return leg
    return None


def _cancel_target(journey: Journey, twin, events: list[Event], now: datetime) -> Leg | None:
    """The first booked ticket whose train has not left yet: the only one that can still be cancelled."""
    for leg, tl in zip(journey.legs, twin.legs):
        if tl.state in (LegState.ARRIVED, LegState.IN_TRANSIT, LegState.CANCELLED, LegState.WAITLISTED):
            continue
        lv = live_state(leg.train_no, events, now)
        if lv.departed or now >= expected_departure(leg, lv):
            continue
        return leg
    return None


def _money(d: RuleDecision) -> dict:
    return {"paise": d.refund_paise, "charge_paise": d.deduction_paise, "outcome": d.outcome.value,
            "rule_ids": d.rule_ids, "legal_status": d.legal_status.value if d.legal_status else None,
            "unresolved": d.unresolved, "reason": d.reason_key}


def build_decision(journey: Journey, events: list[Event], now: datetime, *, network_events: list[Event] | None = None,
                   weather: WeatherProvider | None = None, bus: BusProvider | None = None,
                   profile: PassengerProfile | None = None, priority: Priority = Priority.TIME,
                   station_need=None) -> DecisionView:
    now = ensure_aware(now, "now")
    st = stops()
    reg = registry()
    base = assess(journey, events, now, priority, profile)
    sit = base.assessment.primary.type
    twin = build_twin(journey, events, now, profile)
    active = _active_leg(journey, twin)
    idx = journey.legs.index(active) if active else len(journey.legs) - 1
    has_next = active is not None and idx + 1 < len(journey.legs)

    pred = None
    if active is not None and twin.legs[idx].state not in (LegState.CANCELLED,):
        pred = predict_delay(st, active, events, network_events or [], weather, now, active.to_stn)
    override = station_need(journey, idx + 1) if (station_need and has_next) else None
    conn = connection_risk(journey, idx + 1, pred, events, now, profile, override) if (has_next and pred) else None

    # ---------- recovery search: from where the passenger will be ----------
    final = journey.legs[-1].to_stn
    if conn is not None:
        nxt = journey.legs[idx + 1]
        arr = (pred.expected_arrival or twin.legs[idx].expected_arrival)
        earliest = max(now, arr + timedelta(minutes=conn.transfer_minutes_needed))
        origin, excl_leg = conn.station, nxt
        reason = ("CONNECTION_BROKEN" if conn.risk in BROKEN else "CONNECTION_AT_RISK" if conn.risk == ConnRisk.HIGH_RISK
                  else "BACKUP_ONLY")
        tclass = nxt.ticket.travel_class
    else:
        leg0 = active or journey.legs[-1]
        origin, excl_leg, tclass = leg0.from_stn, leg0, leg0.ticket.travel_class
        earliest = now + timedelta(minutes=15)
        reason = "TRAIN_DISRUPTED" if sit not in (SituationType.ALL_CLEAR, SituationType.NOT_WATCHING_YET) else "BACKUP_ONLY"
    conns = connections_window(st, journey.legs[0].ticket.scheduled_departure.date() - timedelta(days=1), 4)
    rec = recover(conns, origin, final, earliest, now, reason, {(excl_leg.train_no, run_date_for(st, excl_leg))},
                  profile, priority, tclass, journey.min_transfer_minutes, bus)

    # ---------- money: cancellation now vs later, and claims ----------
    target = _cancel_target(journey, twin, events, now)
    claims = Claims()
    money_rows: list[MoneyRow] = []
    cancel_now = None
    if target is not None:
        cancel_now = cancellation_refund(target.ticket, now, reg)
        claims.cancellation_refund_estimate_paise = cancel_now.refund_paise
    tdr: RuleDecision | None = None
    if conn is not None and conn.risk in BAD:
        nxt = journey.legs[idx + 1]
        arr = pred.expected_arrival or twin.legs[idx].expected_arrival
        tdr = missed_connection_tdr(nxt.ticket, journey.linked_pnr, arr, now, reg)
        claims.tdr_eligibility = "ELIGIBLE_IF_MISSED" if tdr.outcome == Outcome.ELIGIBLE_TO_FILE_TDR else "NOT_ELIGIBLE"
        claims.tdr_reason = tdr.reason_key
    elif conn is None and active is not None and sit in (SituationType.NEAR_3H, SituationType.LATE_OVER_3H):
        lv = live_state(active.train_no, events, now)
        tdr = late_running_tdr(active.ticket, lv.delay_minutes, expected_departure(active, lv), now, reg, lv.departed)
        claims.tdr_eligibility = ("ELIGIBLE_NOW" if tdr.outcome == Outcome.ELIGIBLE_TO_FILE_TDR
                                  else "MAY_BECOME_ELIGIBLE" if tdr.reason_key == "DELAY_NOT_OVER_3H" else "NOT_ELIGIBLE")
        claims.tdr_reason = tdr.reason_key
    else:
        claims.tdr_eligibility = "NOT_RELEVANT"

    change_at = next_slab_change(target.ticket, now, reg) if target else None
    if target is not None and change_at and change_at >= target.ticket.scheduled_departure:
        change_at = None
    best_alt = (rec.options or rec.next_day or rec.buses or [None])[0]

    def row_cancel(key: str, at: datetime) -> MoneyRow:
        if target is None:
            return MoneyRow(key=key, at=at, applicable=False, reason="NOTHING_LEFT_TO_CANCEL", money_back_paise=None,
                            charge_paise=None, certainty="NONE", travel_outcome="TRAVEL_BOOKED", next_step="NONE")
        if at >= target.ticket.scheduled_departure:
            return MoneyRow(key=key, at=at, applicable=False, reason="AFTER_SCHEDULED_DEPARTURE", money_back_paise=0,
                            charge_paise=None, certainty="NONE", travel_outcome="NO_TRAVEL", next_step="NONE")
        d = cancellation_refund(target.ticket, at, reg)
        if d.outcome == Outcome.NOT_MODELLED:
            return MoneyRow(key=key, at=at, applicable=False, reason=d.reason_key, money_back_paise=None,
                            charge_paise=None, certainty="UNKNOWN", travel_outcome="NO_TRAVEL", next_step="ASK_COUNTER")
        nxt_step = "CANCEL_ON_IRCTC" if d.refund_paise > 0 else "CANCELLING_RETURNS_NOTHING"
        return MoneyRow(key=key, at=at, money_back_paise=d.refund_paise, charge_paise=d.deduction_paise,
                        certainty="RULE_ESTIMATE", travel_outcome="NO_TRAVEL", next_step=nxt_step,
                        rule_ids=d.rule_ids, legal_status=d.legal_status.value if d.legal_status else None,
                        deadline=change_at)

    if target is not None:
        money_rows.append(row_cancel("CANCEL_NOW", now))
        money_rows.append(row_cancel("WAIT_15", now + timedelta(minutes=15)))
        wait_until = (change_at - timedelta(minutes=1)) if change_at else None
        if conn is not None and conn.watch and pred and pred.remaining.sections:
            watch_t = _scheduled_at(st, active, conn.watch["station"], pred)
            if watch_t and (wait_until is None or watch_t < wait_until):
                wait_until = watch_t
        if wait_until and wait_until >= target.ticket.scheduled_departure:
            wait_until = target.ticket.scheduled_departure - timedelta(minutes=1)
        if wait_until and wait_until > now:
            r = row_cancel("WAIT_UNTIL", wait_until)
            money_rows.append(r)
        if change_at:
            money_rows.append(row_cancel("CANCEL_LATER", change_at + timedelta(minutes=1)))
        else:
            money_rows.append(MoneyRow(key="CANCEL_LATER", at=None, applicable=False,
                                       reason="NO_FURTHER_CHANGE_BEFORE_DEPARTURE", money_back_paise=None,
                                       charge_paise=None, certainty="NONE", travel_outcome="NO_TRAVEL", next_step="NONE"))
    if tdr is not None:
        ok = tdr.outcome == Outcome.ELIGIBLE_TO_FILE_TDR
        money_rows.append(MoneyRow(
            key="KEEP_AND_CLAIM", at=now, applicable=ok or claims.tdr_eligibility == "MAY_BECOME_ELIGIBLE",
            reason=None if ok else tdr.reason_key, money_back_paise=tdr.refund_paise if ok else 0,
            charge_paise=None, certainty="IF_APPROVED" if ok else "NONE", deadline=tdr.deadline,
            travel_outcome="DEPENDS", risk=conn.risk.value if conn else None,
            next_step="FILE_TDR_AFTER_MISSING" if conn is not None else "FILE_TDR_BEFORE_DEPARTURE" if ok else "WATCH_3H",
            rule_ids=tdr.rule_ids, legal_status=tdr.legal_status.value if tdr.legal_status else None))
    if best_alt is not None:
        money_rows.append(MoneyRow(key="ALTERNATIVE", at=best_alt.departure, money_back_paise=None, charge_paise=None,
                                   certainty="UNKNOWN", travel_outcome="TRAVEL_NEW_TICKET",
                                   risk=best_alt.transfer_risk.value if best_alt.transfer_risk else None,
                                   next_step="BOOK_ON_IRCTC_CHECK_SEATS_AND_FARE"))

    cards = _cards(journey, twin, idx, active, pred, conn, rec, target, cancel_now, change_at, tdr, claims, now)
    recommendation = _recommend(sit, pred, conn, rec, cards, cancel_now, tdr, claims, base, now, active, st)
    for c in cards:
        c.recommended = c.key == recommendation.get("card")
    header = _header(journey, idx, active, pred, conn, sit, twin, now)
    return DecisionView(journey_id=journey.id, now=now, priority=priority, header=header, prediction=pred,
                        connection=conn, recovery=rec, cards=cards, money=money_rows, claims=claims,
                        recommendation=recommendation)


def _scheduled_at(st, leg: Leg, station: str, pred: DelayPrediction) -> datetime | None:
    from app.data.timetable import train_schedule
    for s, a, d in train_schedule(st, leg.train_no, run_date_for(st, leg)):
        if s == station:
            t = a or d
            return t + timedelta(minutes=pred.current_delay_minutes or 0) if t else None
    return None


def _header(journey, idx, active, pred, conn, sit, twin, now) -> dict:
    h = {"situation": sit.value, "status": "STALE" if sit == SituationType.STALE_DATA else None}
    if active is not None:
        h |= {"first_train": active.train_no, "first_train_name": active.train_name, "arrival_station": active.to_stn,
              "scheduled_arrival": active.scheduled_arrival.isoformat(),
              "current_delay_minutes": pred.current_delay_minutes if pred else None,
              "expected_arrival": pred.expected_arrival.isoformat() if pred and pred.expected_arrival else None,
              "arrival_early": pred.arrival_early.isoformat() if pred and pred.arrival_early else None,
              "arrival_late": pred.arrival_late.isoformat() if pred and pred.arrival_late else None,
              "latest_data_at": pred.latest_data_at.isoformat() if pred and pred.latest_data_at else None,
              "data_age_minutes": pred.observations[-1].age_minutes if pred and pred.observations else None,
              "data_fresh": bool(pred and pred.data_fresh)}
    if conn is not None:
        avail = int((conn.next_departure - conn.arrival_expected).total_seconds() // 60) if conn.arrival_expected else None
        h |= {"second_train": conn.to_train, "second_train_name": journey.legs[idx + 1].train_name,
              "next_departure": conn.next_departure.isoformat(), "time_available_minutes": avail,
              "transfer_needed_minutes": conn.transfer_minutes_needed, "risk": conn.risk.value}
        h["status"] = h["status"] or ("CONNECTION_BROKEN" if conn.risk in BROKEN else "CONNECTION_AT_RISK"
                                      if conn.risk == ConnRisk.HIGH_RISK else "CONNECTION_TIGHT"
                                      if conn.risk == ConnRisk.TIGHT else "CONNECTION_UNKNOWN"
                                      if conn.risk == ConnRisk.INSUFFICIENT_INFORMATION else "CONNECTION_OK")
    else:
        h["status"] = h["status"] or {"TRAIN_CANCELLED": "TRAIN_CANCELLED", "WAITLISTED_AFTER_CHART": "NOT_CONFIRMED",
                                      "LATE_OVER_3H": "TRAIN_LATE", "NEAR_3H": "TRAIN_LATE",
                                      "JOURNEY_OVER": "JOURNEY_OVER"}.get(sit.value, "ON_TRACK")
    return h


def _cards(journey, twin, idx, active, pred, conn, rec, target, cancel_now, change_at, tdr, claims, now) -> list[Card]:
    cards: list[Card] = []
    # 1. CONTINUE
    if active is None:
        cards.append(Card(key="CONTINUE", status="NOT_APPLICABLE", meaning="CONTINUE_AS_BOOKED", reason="JOURNEY_OVER"))
    elif twin.legs[idx].state in (LegState.CANCELLED, LegState.WAITLISTED):
        cards.append(Card(key="CONTINUE", status="NOT_APPLICABLE", meaning="CONTINUE_AS_BOOKED",
                          reason="TRAIN_CANCELLED" if twin.legs[idx].state == LegState.CANCELLED else "TICKET_NOT_CONFIRMED"))
    else:
        c = Card(key="CONTINUE", status="AVAILABLE", meaning="CONTINUE_AS_BOOKED",
                 money={"kind": "NOTHING_LOST_NOW", "paise": 0, "certainty": "RULE_ESTIMATE"})
        if (pred is None or not pred.observations) and now < active.ticket.scheduled_departure:
            # The train has not started yet, so there is no running data to predict from. Not a problem.
            c.outcome = {"code": "NOT_RUNNING_YET", "departure": active.ticket.scheduled_departure.isoformat(),
                         "arrival": active.scheduled_arrival.isoformat()}
            c.risk = "NO_LIVE_DATA_YET"
            c.next_action = {"code": "CHECK_AGAIN_BEFORE_DEPARTURE"}
        elif pred is None or pred.expected_arrival is None:
            c.status, c.missing = "DATA_MISSING", list(pred.missing_inputs if pred else ["NO_RUNNING_OBSERVATION"])
            c.next_action = {"code": "CHECK_OFFICIAL_STATUS"}
        else:
            c.outcome = {"code": "ARRIVE_AT", "station": active.to_stn, "early": pred.arrival_early.isoformat(),
                         "expected": pred.expected_arrival.isoformat(), "late": pred.arrival_late.isoformat(),
                         "outlook": pred.outlook.value, "growth_risk": pred.growth_risk.value}
            c.risk = conn.risk.value if conn else pred.growth_risk.value
            if conn is not None:
                c.outcome |= {"slack_early": conn.slack_early, "slack_expected": conn.slack_expected,
                              "slack_late": conn.slack_late, "need": conn.transfer_minutes_needed,
                              "next_departure": conn.next_departure.isoformat()}
                if conn.risk in BROKEN:
                    c.next_action = {"code": "CONNECTION_WILL_LIKELY_FAIL"}
                elif conn.watch:
                    c.next_action = {"code": "WATCH_AT_STATION", "station": conn.watch["station"],
                                     "max_delay": conn.watch["max_delay_minutes"]}
                c.items = [{"code": r["code"], **{k: v for k, v in r.items() if k != "code"}} for r in conn.reasons]
            else:
                c.next_action = {"code": "TRAVEL_AND_MONITOR"}
        cards.append(c)

    # 2. CANCEL
    if target is None:
        cards.append(Card(key="CANCEL", status="NOT_APPLICABLE", meaning="CANCEL_TICKET",
                          reason="BOOKED_TRAINS_ALREADY_LEFT",
                          next_action={"code": "SEE_CLAIM_INSTEAD"} if claims.tdr_eligibility.startswith("ELIGIBLE")
                          else {"code": "NOTHING_TO_CANCEL"},
                          items=[{"code": "TDR_STATUS", "eligibility": claims.tdr_eligibility, "reason": claims.tdr_reason,
                                  "tdr_paise": tdr.refund_paise if tdr else None,
                                  "deadline": tdr.deadline.isoformat() if tdr and tdr.deadline else None}]))
    elif cancel_now.outcome == Outcome.NOT_MODELLED:
        cards.append(Card(key="CANCEL", status="DATA_MISSING", meaning="CANCEL_TICKET", reason=cancel_now.reason_key,
                          missing=["TICKET_DETAILS_FOR_RULE"], next_action={"code": "ASK_COUNTER_OR_139"}))
    else:
        c = Card(key="CANCEL", status="AVAILABLE", meaning="CANCEL_TICKET", risk="NO_TRAVEL_ON_THIS_TICKET",
                 money={"kind": "CANCELLATION_REFUND", "certainty": "RULE_ESTIMATE", **_money(cancel_now),
                        "fare_paise": target.ticket.total_fare_paise},
                 outcome={"code": "CANCEL_LEG", "train": target.train_no, "from": target.from_stn, "to": target.to_stn,
                          "class": target.ticket.travel_class, "status": target.ticket.status.value,
                          "quota": target.ticket.quota.value, "eticket": target.ticket.is_eticket})
        if change_at:
            later = cancellation_refund(target.ticket, change_at + timedelta(minutes=1), registry())
            c.deadline, c.deadline_kind = change_at, "REFUND_DROPS"
            c.outcome |= {"refund_after_change_paise": later.refund_paise,
                          "minutes_left": int((change_at - now).total_seconds() // 60)}
        if tdr is not None and tdr.outcome == Outcome.ELIGIBLE_TO_FILE_TDR and tdr.refund_paise > cancel_now.refund_paise:
            c.next_action = {"code": "DO_NOT_CANCEL_TDR_BETTER", "tdr_paise": tdr.refund_paise,
                             "cancel_paise": cancel_now.refund_paise, "rule": tdr.rule_ids[0] if tdr.rule_ids else None}
        elif cancel_now.refund_paise == 0:
            c.next_action = {"code": "CANCELLING_RETURNS_NOTHING"}
        else:
            c.next_action = {"code": "CANCEL_ON_IRCTC_IF_NOT_TRAVELLING"}
        c.items = [{"code": "TDR_STATUS", "eligibility": claims.tdr_eligibility, "reason": claims.tdr_reason,
                    "tdr_paise": tdr.refund_paise if tdr else None,
                    "deadline": tdr.deadline.isoformat() if tdr and tdr.deadline else None}]
        cards.append(c)

    # 3. OTHER_TRAIN
    if rec.options:
        o = rec.options[0]
        cards.append(Card(key="OTHER_TRAIN", status="AVAILABLE", meaning="FIND_ANOTHER_TRAIN",
                          outcome={"code": "ARRIVE_AT", "expected": o.arrival.isoformat(), "from": rec.origin},
                          money={"kind": "NEW_TICKET_FARE_UNKNOWN", "paise": None, "certainty": "UNKNOWN"},
                          risk=o.transfer_risk.value if o.transfer_risk else "NO_CHANGE",
                          deadline=o.departure, deadline_kind="TRAIN_DEPARTS",
                          next_action={"code": "BOOK_ON_IRCTC_CHECK_SEATS", "train": o.legs[-1].train_no},
                          items=[x.model_dump(mode="json") for x in rec.options[:4]]))
    else:
        cards.append(Card(key="OTHER_TRAIN", status="NONE_FOUND", meaning="FIND_ANOTHER_TRAIN",
                          reason="NO_SAME_DAY_TRAIN_FOUND", next_action={"code": "SEE_NEXT_DAY_OR_BUS"}))
    # 4. UNRESERVED
    if rec.unreserved:
        u = rec.unreserved[0]
        cards.append(Card(key="UNRESERVED", status="AVAILABLE", meaning="UNRESERVED_TRAVEL",
                          outcome={"code": "ARRIVE_AT", "expected": u.arrival.isoformat()},
                          money={"kind": "UNRESERVED_FARE_UNKNOWN", "paise": None, "certainty": "UNKNOWN"},
                          risk="NO_SEAT_GUARANTEE", deadline=u.departure, deadline_kind="TRAIN_DEPARTS",
                          next_action={"code": "BUY_UNRESERVED_TICKET", "train": u.legs[-1].train_no},
                          items=[x.model_dump(mode="json") for x in rec.unreserved[:3]] +
                                [{"code": "RULES", **rec.rules["unreserved"]}]))
    else:
        cards.append(Card(key="UNRESERVED", status="NONE_FOUND", meaning="UNRESERVED_TRAVEL",
                          reason="NO_SAME_DAY_TRAIN_WITH_GENERAL_COACHES",
                          items=[{"code": "RULES", **rec.rules["unreserved"]}],
                          next_action={"code": "DO_NOT_BOARD_RESERVED_COACH_WITHOUT_VALID_TICKET"}))
    # 5. BUS
    if rec.buses:
        b = rec.buses[0]
        cards.append(Card(key="BUS", status="AVAILABLE", meaning="BUS_INSTEAD",
                          outcome={"code": "ARRIVE_AT", "expected": b.arrival.isoformat()},
                          money={"kind": "SAMPLE_FARE_NOT_REAL", "paise": b.fare_paise, "certainty": "SAMPLE"},
                          risk="DEMO_SAMPLE_ONLY", deadline=b.departure, deadline_kind="LEAVE_FOR_TERMINAL",
                          next_action={"code": "CHECK_OPERATOR_TIMETABLE"},
                          items=[x.model_dump(mode="json") for x in rec.buses[:3]]))
    else:
        cards.append(Card(key="BUS", status="NOT_CONFIGURED" if rec.bus_status == "NOT_CONFIGURED" else "NONE_FOUND",
                          meaning="BUS_INSTEAD", reason="BUS_DATA_NOT_CONNECTED" if rec.bus_status == "NOT_CONFIGURED"
                          else "NO_BUS_IN_WINDOW", next_action={"code": "CHECK_STATE_TRANSPORT_SITE"}))
    # 6. NEXT_SERVICE
    if rec.next_day:
        n = rec.next_day[0]
        cards.append(Card(key="NEXT_SERVICE", status="AVAILABLE", meaning="WAIT_NEXT_SERVICE",
                          outcome={"code": "ARRIVE_AT", "expected": n.arrival.isoformat()},
                          money={"kind": "NEW_TICKET_FARE_UNKNOWN", "paise": None, "certainty": "UNKNOWN"},
                          risk=n.transfer_risk.value if n.transfer_risk else "NO_CHANGE",
                          deadline=datetime.fromisoformat(n.tatkal["opens_at"]) if n.tatkal else None,
                          deadline_kind="TATKAL_OPENS",
                          next_action={"code": "BOOK_NEXT_DAY_TATKAL_NOT_GUARANTEED", "train": n.legs[-1].train_no},
                          items=[x.model_dump(mode="json") for x in rec.next_day[:3]] +
                                [{"code": "RULES", **rec.rules["tatkal"]}]))
    else:
        cards.append(Card(key="NEXT_SERVICE", status="NONE_FOUND", meaning="WAIT_NEXT_SERVICE",
                          reason="NO_NEXT_DAY_TRAIN_IN_DATA", next_action={"code": "CHECK_IRCTC"}))
    return cards


def _pick(o, origin: str) -> dict:
    """Short description of one recovery option for the recommendation (first train leg, not the walk)."""
    first = next((l for l in o.legs if l.mode in ("TRAIN", "BUS")), o.legs[0])
    access = o.legs[0] if o.legs[0].mode == "ACCESS" and o.kind.value == "NEARBY_STATION" else None
    return {"train": "+".join(l.train_no for l in o.legs if l.mode == "TRAIN") or first.name,
            "dep": first.dep.isoformat(), "arr": o.arrival.isoformat(), "from": first.from_stn,
            "leave_at": o.departure.isoformat(), "next_day": o.next_day,
            "access_minutes": int((access.arr - access.dep).total_seconds() // 60) if access else None}


def _recommend(sit, pred, conn, rec, cards, cancel_now, tdr, claims, base, now, active, st) -> dict:
    """Deterministic decision rules (docs/PASSENGER_DECISION_MODEL.md). Returns codes + numbers."""
    if sit == SituationType.STALE_DATA or (pred is not None and not pred.data_fresh and pred.observations):
        return {"card": None, "code": "CHECK_OFFICIAL_STATUS", "why": ["DATA_STALE"], "call": "139"}
    if sit == SituationType.JOURNEY_OVER or active is None:
        return {"card": None, "code": "JOURNEY_OVER", "why": []}
    top = base.plans[0] if base.plans else None
    alt = rec.options[0] if rec.options else None
    nd = rec.next_day[0] if rec.next_day else None
    if conn is not None:
        if conn.risk in (ConnRisk.COMFORTABLE, ConnRisk.TIGHT):
            return {"card": "CONTINUE", "code": "STAY_AND_WATCH", "why": ["CONNECTION_" + conn.risk.value],
                    "watch": conn.watch, "slack_late": conn.slack_late}
        if conn.risk == ConnRisk.HIGH_RISK:
            r = {"card": "CONTINUE", "code": "STAY_BUT_PREPARE", "why": ["CONNECTION_HIGH_RISK"], "watch": conn.watch}
            if alt:
                r["backup"] = _pick(alt, rec.origin)
            if tdr is not None and tdr.outcome == Outcome.ELIGIBLE_TO_FILE_TDR and cancel_now is not None \
                    and tdr.refund_paise > cancel_now.refund_paise:
                r["dont_cancel"] = {"cancel_paise": cancel_now.refund_paise, "tdr_paise": tdr.refund_paise}
                r["why"].append("TDR_BETTER_THAN_CANCELLING")
            return r
        if conn.risk in BROKEN:
            card = "OTHER_TRAIN" if alt else "NEXT_SERVICE" if nd else "BUS" if rec.buses else None
            pick = alt or nd
            r = {"card": card, "code": "BOOK_ALTERNATIVE" if pick else "NO_ALTERNATIVE_CALL_139",
                 "why": ["CONNECTION_" + conn.risk.value]}
            if pick:
                r["option"] = _pick(pick, rec.origin)
                if pick.next_day and pick.tatkal:
                    r["tatkal"] = pick.tatkal
            if tdr is not None and tdr.outcome == Outcome.ELIGIBLE_TO_FILE_TDR:
                r["claim"] = {"code": "FILE_TDR_MISSED_CONNECTION", "paise": tdr.refund_paise,
                              "deadline": tdr.deadline.isoformat() if tdr.deadline else None, "if_approved": True}
            elif tdr is not None:
                r["claim"] = {"code": "TDR_NOT_ELIGIBLE", "reason": tdr.reason_key}
                if cancel_now is not None and cancel_now.refund_paise > 0:
                    r["claim"] |= {"cancel_paise": cancel_now.refund_paise}
            return r
        return {"card": None, "code": "CHECK_OFFICIAL_STATUS", "why": ["INSUFFICIENT_INFORMATION"], "call": "139"}
    # single train (or last leg): follow the rules-engine plan, and say what to do if not travelling
    clock = base.rights_clock
    kind = top.kind if top else None
    if kind in (PlanKind.FILE_TDR_LATE, PlanKind.TDR_LATE_PLUS_ALTERNATIVE):
        return {"card": "CANCEL", "code": "FILE_TDR_BEFORE_DEPARTURE", "why": ["LATE_OVER_3H"],
                "claim": {"paise": tdr.refund_paise if tdr else top.money_back_paise,
                          "deadline": (tdr.deadline if tdr else top.deadline).isoformat() if (tdr or top).deadline else None}}
    if kind in (PlanKind.AUTO_REFUND_WAIT, PlanKind.AUTO_REFUND_PLUS_ALTERNATIVE):
        return {"card": "OTHER_TRAIN" if alt else "NEXT_SERVICE", "code": "AUTO_REFUND_FIND_TRAIN",
                "why": [sit.value], "refund_paise": top.money_back_paise}
    r = {"card": "CONTINUE", "code": "TRAVEL_AS_BOOKED", "why": [sit.value]}
    if pred is not None and pred.expected_arrival:
        r["arrive"] = {"early": pred.arrival_early.isoformat(), "late": pred.arrival_late.isoformat()}
    if cancel_now is not None:
        drop = next_slab_change(active.ticket, now, registry()) if active is not None else None
        if drop is not None and drop >= active.ticket.scheduled_departure:
            drop = None
        r["if_not_travelling"] = {"cancel_paise": cancel_now.refund_paise,
                                  "decide_by": (drop - timedelta(minutes=1)).isoformat() if drop
                                  else clock.decision_deadline.isoformat() if clock.decision_deadline else None}
        if claims.tdr_eligibility == "MAY_BECOME_ELIGIBLE":
            r["if_not_travelling"]["tdr_if_over_3h"] = True
    return r
