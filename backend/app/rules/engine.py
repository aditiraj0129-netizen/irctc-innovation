"""Deterministic refund and TDR rules engine.

No AI is used here. Every answer:
  * comes from a rule in rulesets.yaml,
  * names the rule and its source,
  * uses whole paise (no floats),
  * never promises that a TDR will be approved.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from app.core.clock import ensure_aware
from app.rules.models import (
    AC_CLASSES, APPROVAL_NOTE, Decision, LegalStatus, Outcome, Quota, RuleRegistryData,
    RuleSet, Slab, SlabType, SpecialRule, Ticket, TicketStatus,
)

DEFAULT_RULES_FILE = Path(__file__).parent / "data" / "rulesets.yaml"


class RuleNotFoundError(LookupError):
    """No rule covers this train category on this date."""


class InvalidTicketError(ValueError):
    """The ticket can't exist under the rules (e.g. RAC on Vande Bharat Sleeper)."""


# ---------- Loading ----------

class RuleRegistry:
    def __init__(self, data: RuleRegistryData):
        self.data = data

    @classmethod
    def from_yaml(cls, path: Path = DEFAULT_RULES_FILE) -> "RuleRegistry":
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return cls(RuleRegistryData.model_validate(raw))

    @staticmethod
    def _in_force(item, on: datetime) -> bool:
        d = on.date()
        return item.effective_from <= d and (item.effective_to is None or d <= item.effective_to)

    def rule_set_for(self, ticket: Ticket, on: datetime) -> RuleSet:
        for rs in self.data.rule_sets:
            if ticket.train_category in rs.train_categories and self._in_force(rs, on):
                return rs
        raise RuleNotFoundError(f"No refund rule set for {ticket.train_category.value} on {on.date()}")

    def special(self, rule_id: str, ticket: Ticket, on: datetime) -> SpecialRule | None:
        for r in self.data.special_rules:
            if r.id == rule_id and ticket.train_category in r.train_categories and self._in_force(r, on):
                return r
        return None


# ---------- Helpers ----------

def hours_before(departure: datetime, at: datetime) -> float:
    return (departure - at).total_seconds() / 3600


def pick_slab(slabs: list[Slab], hours_left: float) -> Slab:
    for slab in slabs:
        if slab.min_hours is None:
            return slab
        if hours_left > slab.min_hours or (slab.min_inclusive and hours_left == slab.min_hours):
            return slab
    return slabs[-1]


def percent_of(amount_paise: int, percent: int) -> int:
    """Percentage in whole paise, rounded half up."""
    return (amount_paise * percent + 50) // 100


def unresolved_conditions(rs_or_rule) -> list[str]:
    """Everything about this rule that we have NOT verified yet. Shown to the passenger."""
    out = []
    if rs_or_rule.legal_status == LegalStatus.ANNOUNCED:
        out.append("RULE_NOT_YET_NOTIFIED")
    if rs_or_rule.source.last_verified is None:
        out.append("SOURCE_NOT_YET_CHECKED")
    if getattr(rs_or_rule, "needs_verification", False):
        out.append("INTERPRETATION_NEEDS_VERIFICATION")
    return out


def _base(kind: str, rs_or_rule, **kw) -> Decision:
    src = rs_or_rule.source
    return Decision(
        kind=kind,
        rule_set_id=getattr(rs_or_rule, "id", None),
        rule_version=rs_or_rule.version,
        rule_name=rs_or_rule.name,
        applies_to_categories=list(rs_or_rule.train_categories),
        effective_from=rs_or_rule.effective_from,
        legal_status=rs_or_rule.legal_status,
        source_title=src.title,
        source_url=src.url,
        last_verified=src.last_verified,
        unresolved=unresolved_conditions(rs_or_rule),
        **kw,
    )


def _common_warnings(ticket: Ticket, legal_status: LegalStatus) -> list[str]:
    w = []
    if legal_status == LegalStatus.ANNOUNCED:
        w.append("RULE_ANNOUNCED_NOT_NOTIFIED")
    if ticket.travel_class in AC_CLASSES:
        w.append("GST_ON_CHARGES_NOT_INCLUDED")
    w.append("RAILWAY_ROUNDING_NOT_MODELLED")
    return w


def _validate(ticket: Ticket, rs: RuleSet) -> None:
    if ticket.status not in rs.allowed_statuses:
        raise InvalidTicketError(f"{ticket.status.value} tickets are not issued on {ticket.train_category.value}")
    if ticket.quota not in rs.allowed_quotas:
        raise InvalidTicketError(f"{ticket.quota.value} quota is not available on {ticket.train_category.value}")
    if ticket.travel_class not in rs.flat_charge_paise:
        raise InvalidTicketError(f"Class {ticket.travel_class.value} is not on {ticket.train_category.value}")


# ---------- 1. Cancellation refund ----------

def cancellation_refund(ticket: Ticket, at: datetime, registry: RuleRegistry) -> Decision:
    """What the passenger gets back if they cancel online at time `at`."""
    at = ensure_aware(at, "at")
    rs = registry.rule_set_for(ticket, at)
    _validate(ticket, rs)
    warnings = _common_warnings(ticket, rs.legal_status)
    kind = "CANCELLATION"
    hrs = hours_before(ticket.scheduled_departure, at)

    if not ticket.is_eticket:
        return _base(kind, rs, outcome=Outcome.NOT_MODELLED, reason_key="COUNTER_TICKET_USE_COUNTER",
                     warnings=warnings)

    # RAC and waitlisted: refund minus clerkage, until the cut-off before departure.
    if ticket.status in (TicketStatus.RAC, TicketStatus.WAITLISTED):
        cutoff_min = rs.rac_wl_cancel_cutoff_minutes
        if cutoff_min is None or rs.clerkage_paise_per_passenger is None:
            return _base(kind, rs, outcome=Outcome.NOT_MODELLED, reason_key="RAC_WL_RULE_MISSING",
                         warnings=warnings)
        if hrs * 60 >= cutoff_min:
            clerkage = min(rs.clerkage_paise_per_passenger * ticket.passengers, ticket.total_fare_paise)
            return _base(kind, rs, outcome=Outcome.REFUND_ON_CANCEL,
                         refund_paise=ticket.total_fare_paise - clerkage, deduction_paise=clerkage,
                         rule_ids=[f"{rs.id}:RAC_WL_CLERKAGE"], reason_key="RAC_WL_CLERKAGE",
                         warnings=warnings)
        return _base(kind, rs, outcome=Outcome.NO_REFUND, deduction_paise=ticket.total_fare_paise,
                     rule_ids=[f"{rs.id}:RAC_WL_CUTOFF"], reason_key="RAC_WL_PAST_CUTOFF",
                     warnings=warnings)

    # Confirmed Tatkal: no refund on cancellation.
    if ticket.quota == Quota.TATKAL and not rs.tatkal_confirmed_refund:
        return _base(kind, rs, outcome=Outcome.NO_REFUND, deduction_paise=ticket.total_fare_paise,
                     rule_ids=[f"{rs.id}:TATKAL_CNF"], reason_key="TATKAL_CONFIRMED_NO_REFUND",
                     warnings=warnings)

    # Confirmed: time slabs.
    slab = pick_slab(rs.confirmed_slabs, hrs)
    slab_id = f"{rs.id}:CNF_{slab.type.value}" + (f"_{slab.percent}" if slab.percent else "")
    fare_pp = ticket.fare_per_passenger_paise
    flat = rs.flat_charge_paise[ticket.travel_class]

    if slab.type == SlabType.NO_REFUND:
        return _base(kind, rs, outcome=Outcome.NO_REFUND, deduction_paise=ticket.total_fare_paise,
                     rule_ids=[slab_id], reason_key="CNF_NO_REFUND_WINDOW", warnings=warnings)
    if slab.type == SlabType.FLAT:
        charge_pp = flat
    else:
        charge_pp = percent_of(fare_pp, slab.percent)
        if slab.min_flat:
            charge_pp = max(charge_pp, flat)
    charge_pp = min(charge_pp, fare_pp)
    deduction = charge_pp * ticket.passengers
    return _base(kind, rs, outcome=Outcome.REFUND_ON_CANCEL,
                 refund_paise=ticket.total_fare_paise - deduction, deduction_paise=deduction,
                 rule_ids=[slab_id], reason_key=f"CNF_{slab.type.value}", warnings=warnings)


def next_slab_change(ticket: Ticket, at: datetime, registry: RuleRegistry) -> datetime | None:
    """The next moment the cancellation refund gets worse (used by the Rights Clock later)."""
    from datetime import timedelta
    at = ensure_aware(at, "at")
    rs = registry.rule_set_for(ticket, at)
    hrs = hours_before(ticket.scheduled_departure, at)
    for slab in rs.confirmed_slabs:
        if slab.min_hours is not None and slab.min_hours < hrs:
            return ticket.scheduled_departure - timedelta(hours=slab.min_hours)
    return None


# ---------- 2. Late running: TDR ----------

def late_running_tdr(ticket: Ticket, delay_minutes: int, expected_departure: datetime,
                     at: datetime, registry: RuleRegistry, train_departed: bool = False) -> Decision:
    """Train running late from the boarding station and the passenger does NOT travel."""
    at = ensure_aware(at, "at")
    expected_departure = ensure_aware(expected_departure, "expected_departure")
    if delay_minutes < 0:
        raise ValueError("delay_minutes cannot be negative")
    kind = "TDR_LATE_RUNNING"

    vbs = registry.special("TDR-LATE-3H-VBS", ticket, at)
    if vbs:
        return _base(kind, vbs, outcome=Outcome.NEEDS_VERIFICATION, rule_ids=[vbs.id],
                     reason_key="VBS_LATE_RULE_UNCLEAR", approval_note=APPROVAL_NOTE)

    rule = registry.special("TDR-LATE-3H", ticket, at)
    if rule is None:
        raise RuleNotFoundError("No late-running rule for this train/date")
    threshold = int(rule.params["delay_threshold_minutes"])
    common = dict(rule_ids=[rule.id], approval_note=APPROVAL_NOTE)

    if not ticket.is_eticket:
        return _base(kind, rule, outcome=Outcome.NOT_MODELLED, reason_key="COUNTER_TICKET_USE_COUNTER", **common)
    if delay_minutes <= threshold:   # rule says MORE than 3 hours
        return _base(kind, rule, outcome=Outcome.NOT_ELIGIBLE, reason_key="DELAY_NOT_OVER_3H", **common)
    if train_departed or at >= expected_departure:
        return _base(kind, rule, outcome=Outcome.NOT_ELIGIBLE, deadline=expected_departure,
                     reason_key="TDR_WINDOW_CLOSED_TRAIN_DEPARTED", **common)
    return _base(kind, rule, outcome=Outcome.ELIGIBLE_TO_FILE_TDR,
                 refund_paise=ticket.total_fare_paise, deadline=expected_departure,
                 deadline_moves_with_live_status=True, reason_key="TDR_LATE_FULL_FARE", **common)


# ---------- 3. Automatic refunds ----------

def train_cancelled(ticket: Ticket, at: datetime, registry: RuleRegistry) -> Decision:
    at = ensure_aware(at, "at")
    rule = registry.special("AUTO-TRAIN-CANCELLED", ticket, at)
    if rule is None:
        raise RuleNotFoundError("No train-cancelled rule")
    if not ticket.is_eticket:
        return _base("TRAIN_CANCELLED", rule, outcome=Outcome.NOT_MODELLED, rule_ids=[rule.id],
                     reason_key="COUNTER_TICKET_USE_COUNTER")
    return _base("TRAIN_CANCELLED", rule, outcome=Outcome.AUTO_REFUND,
                 refund_paise=ticket.total_fare_paise, rule_ids=[rule.id],
                 reason_key="TRAIN_CANCELLED_AUTO_FULL")


def waitlisted_after_chart(ticket: Ticket, at: datetime, registry: RuleRegistry) -> Decision:
    """Fully waitlisted e-ticket after the chart: dropped, refund minus clerkage."""
    at = ensure_aware(at, "at")
    if ticket.status != TicketStatus.WAITLISTED:
        raise InvalidTicketError("Only fully waitlisted tickets are dropped at charting")
    rule = registry.special("AUTO-WL-DROPPED", ticket, at)
    if rule is None:
        raise RuleNotFoundError("No waitlist-dropped rule for this train")
    rs = registry.rule_set_for(ticket, at)
    clerkage = min((rs.clerkage_paise_per_passenger or 0) * ticket.passengers, ticket.total_fare_paise)
    return _base("WL_AFTER_CHART", rule, outcome=Outcome.AUTO_REFUND,
                 refund_paise=ticket.total_fare_paise - clerkage, deduction_paise=clerkage,
                 rule_ids=[rule.id, f"{rs.id}:RAC_WL_CLERKAGE"], reason_key="WL_DROPPED_CLERKAGE",
                 warnings=_common_warnings(ticket, rs.legal_status))


# ---------- 4. Missed connection (linked PNRs) ----------

def missed_connection_tdr(second_leg: Ticket, linked_pnr: bool, first_train_actual_arrival: datetime,
                          at: datetime, registry: RuleRegistry) -> Decision:
    """Second train missed because the first was late. Only linked PNRs qualify."""
    from datetime import timedelta
    at = ensure_aware(at, "at")
    first_train_actual_arrival = ensure_aware(first_train_actual_arrival, "first_train_actual_arrival")
    rule = registry.special("TDR-MISSED-CONNECTION", second_leg, at)
    kind = "TDR_MISSED_CONNECTION"
    if rule is None:
        raise RuleNotFoundError("No missed-connection rule for this train")
    common = dict(rule_ids=[rule.id], approval_note=APPROVAL_NOTE)
    if not linked_pnr:
        return _base(kind, rule, outcome=Outcome.NOT_ELIGIBLE, reason_key="PNRS_NOT_LINKED", **common)
    if second_leg.status == TicketStatus.WAITLISTED:
        return _base(kind, rule, outcome=Outcome.NOT_ELIGIBLE, reason_key="LINKED_NEEDS_CONFIRMED", **common)
    deadline = first_train_actual_arrival + timedelta(minutes=int(rule.params["deadline_minutes_after_arrival"]))
    if at >= deadline:
        return _base(kind, rule, outcome=Outcome.NOT_ELIGIBLE, deadline=deadline,
                     reason_key="TDR_WINDOW_CLOSED", **common)
    return _base(kind, rule, outcome=Outcome.ELIGIBLE_TO_FILE_TDR, refund_paise=second_leg.total_fare_paise,
                 deadline=deadline, deadline_moves_with_live_status=True,
                 warnings=["DEADLINE_FROM_PARTNER_SOURCE_UNVERIFIED"],
                 reason_key="TDR_MISSED_CONNECTION_FULL_FARE", **common)
