"""Cancellation refund tests, including exact boundary times."""
from datetime import datetime, timedelta

import pytest

from app.core.clock import IST
from app.rules.engine import InvalidTicketError, cancellation_refund, next_slab_change
from app.rules.models import LegalStatus, Outcome, Quota, TicketStatus, TrainCategory, TravelClass
from tests.conftest import DEP

FARE = 214000  # ₹2,140 per passenger


def at(hours_before: float, minutes_extra: int = 0):
    return DEP - timedelta(hours=hours_before) - timedelta(minutes=minutes_extra)


# ---------- Regular trains, April 2026 rules (announced) ----------

@pytest.mark.parametrize(
    "when, outcome, deduction, slab",
    [
        (at(72, 1), Outcome.REFUND_ON_CANCEL, 18000, "CNF_FLAT"),            # 72h01m: flat ₹180
        (at(72), Outcome.REFUND_ON_CANCEL, 53500, "CNF_PERCENT_25"),        # exactly 72h: 25%
        (at(24), Outcome.REFUND_ON_CANCEL, 53500, "CNF_PERCENT_25"),        # exactly 24h: 25%
        (at(24) + timedelta(minutes=1), Outcome.REFUND_ON_CANCEL, 107000, "CNF_PERCENT_50"),
        (at(8), Outcome.REFUND_ON_CANCEL, 107000, "CNF_PERCENT_50"),        # exactly 8h: 50%
        (at(8) + timedelta(minutes=1), Outcome.NO_REFUND, FARE, "CNF_NO_REFUND"),  # 7h59m
        (DEP + timedelta(minutes=5), Outcome.NO_REFUND, FARE, "CNF_NO_REFUND"),    # after departure
    ],
)
def test_regular_2026_boundaries(make_ticket, registry, when, outcome, deduction, slab):
    d = cancellation_refund(make_ticket(), when, registry)
    assert d.outcome == outcome
    assert d.deduction_paise == deduction
    assert d.refund_paise == FARE - deduction
    assert d.rule_set_id == "RS-REG-2026-APR"
    assert d.rule_ids[0].endswith(slab)


def test_announced_rule_is_flagged(make_ticket, registry):
    d = cancellation_refund(make_ticket(), at(30), registry)
    assert d.legal_status == LegalStatus.ANNOUNCED
    assert "RULE_ANNOUNCED_NOT_NOTIFIED" in d.warnings
    assert d.source_url and d.last_verified is not None


def test_minimum_flat_charge_applies(make_ticket, registry):
    # Sleeper ₹300: 25% = ₹75, but the minimum is the flat ₹120.
    t = make_ticket(travel_class=TravelClass.SLEEPER, fare_per_passenger_paise=30000)
    d = cancellation_refund(t, at(30), registry)
    assert d.deduction_paise == 12000
    assert d.refund_paise == 18000


def test_charge_never_exceeds_fare(make_ticket, registry):
    # Second sitting ₹50, flat charge ₹60: deduction is capped at ₹50.
    t = make_ticket(travel_class=TravelClass.SECOND_SITTING, fare_per_passenger_paise=5000)
    d = cancellation_refund(t, at(100), registry)
    assert d.deduction_paise == 5000
    assert d.refund_paise == 0


def test_multiple_passengers(make_ticket, registry):
    d = cancellation_refund(make_ticket(passengers=4), at(30), registry)
    assert d.deduction_paise == 53500 * 4
    assert d.refund_paise == (FARE - 53500) * 4


def test_ac_class_warns_gst_not_included(make_ticket, registry):
    assert "GST_ON_CHARGES_NOT_INCLUDED" in cancellation_refund(make_ticket(), at(30), registry).warnings
    sl = make_ticket(travel_class=TravelClass.SLEEPER, fare_per_passenger_paise=60000)
    assert "GST_ON_CHARGES_NOT_INCLUDED" not in cancellation_refund(sl, at(30), registry).warnings


# ---------- Rule version selection: 2015 rules before April 2026 ----------

DEP_FEB = datetime(2026, 2, 20, 22, 0, tzinfo=IST)


@pytest.mark.parametrize(
    "hours, deduction",
    [(48.02, 18000), (48, 53500), (12, 53500), (11.99, 107000), (4, 107000), (3.99, FARE)],
)
def test_regular_2015_rules_before_april_2026(make_ticket, registry, hours, deduction):
    t = make_ticket(scheduled_departure=DEP_FEB)
    d = cancellation_refund(t, DEP_FEB - timedelta(hours=hours), registry)
    assert d.rule_set_id == "RS-REG-2015"
    assert d.legal_status == LegalStatus.NOTIFIED
    assert d.deduction_paise == deduction


# ---------- Vande Bharat Sleeper / Amrit Bharat II (notified Jan 2026) ----------

@pytest.mark.parametrize(
    "when, deduction",
    [(at(72, 1), 53500), (at(72), 107000), (at(8), 107000), (at(8) + timedelta(minutes=1), FARE)],
)
def test_vande_bharat_sleeper(make_ticket, registry, when, deduction):
    t = make_ticket(train_category=TrainCategory.VANDE_BHARAT_SLEEPER)
    d = cancellation_refund(t, when, registry)
    assert d.rule_set_id == "RS-VBS-AB2-2026"
    assert d.legal_status == LegalStatus.NOTIFIED
    assert d.deduction_paise == deduction


def test_same_ticket_different_category_gives_different_answer(make_ticket, registry):
    reg = cancellation_refund(make_ticket(), at(100), registry)
    vbs = cancellation_refund(make_ticket(train_category=TrainCategory.AMRIT_BHARAT_II), at(100), registry)
    assert reg.refund_paise == FARE - 18000      # flat charge only
    assert vbs.refund_paise == FARE - 53500      # 25% deducted


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": TicketStatus.RAC},
        {"status": TicketStatus.WAITLISTED},
        {"quota": Quota.TATKAL},
        {"travel_class": TravelClass.SLEEPER},
    ],
)
def test_impossible_vbs_tickets_are_rejected(make_ticket, registry, overrides):
    t = make_ticket(train_category=TrainCategory.VANDE_BHARAT_SLEEPER, **overrides)
    with pytest.raises(InvalidTicketError):
        cancellation_refund(t, at(30), registry)


# ---------- Tatkal, RAC, waitlisted, counter tickets ----------

def test_confirmed_tatkal_no_refund(make_ticket, registry):
    d = cancellation_refund(make_ticket(quota=Quota.TATKAL), at(20), registry)
    assert d.outcome == Outcome.NO_REFUND
    assert d.reason_key == "TATKAL_CONFIRMED_NO_REFUND"


@pytest.mark.parametrize(
    "minutes_before, outcome, refund",
    [(60, Outcome.REFUND_ON_CANCEL, (FARE - 6000) * 2),
     (30, Outcome.REFUND_ON_CANCEL, (FARE - 6000) * 2),   # exactly 30 min: still allowed
     (29, Outcome.NO_REFUND, 0)],
)
def test_rac_clerkage_and_cutoff(make_ticket, registry, minutes_before, outcome, refund):
    t = make_ticket(status=TicketStatus.RAC, passengers=2)
    d = cancellation_refund(t, DEP - timedelta(minutes=minutes_before), registry)
    assert d.outcome == outcome
    assert d.refund_paise == refund


def test_counter_ticket_is_not_guessed(make_ticket, registry):
    d = cancellation_refund(make_ticket(is_eticket=False), at(30), registry)
    assert d.outcome == Outcome.NOT_MODELLED
    assert d.refund_paise == 0


# ---------- Next slab change (feeds the Rights Clock) ----------

def test_next_slab_change(make_ticket, registry):
    t = make_ticket()
    assert next_slab_change(t, at(100), registry) == DEP - timedelta(hours=72)
    assert next_slab_change(t, at(30), registry) == DEP - timedelta(hours=24)
    assert next_slab_change(t, at(5), registry) is None
