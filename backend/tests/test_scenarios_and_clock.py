"""End-to-end backend tests for the demo scenarios and the Rights Clock.
These are the exact inputs and expected outputs used in the live demo."""
from datetime import timedelta

import pytest

from app.data.source import load_scenarios
from app.domain.models import Event, EventType
from app.plan.models import Certainty, PlanKind
from app.plan.ranker import Priority
from app.plan.service import assess


@pytest.fixture(scope="module")
def sc():
    return load_scenarios()


def test_demo_1_normal_journey(sc):
    s = sc["normal_journey"]
    r = assess(s.journey, s.events, s.start_clock, Priority.MONEY)
    assert r.plans[0].kind == PlanKind.TRAVEL_AS_BOOKED
    cancel = next(p for p in r.plans if p.kind == PlanKind.CANCEL_NOW)
    assert cancel.money_back_paise == 196000            # ₹2,140 - ₹180 flat
    assert r.rights_clock.next_drop["to_paise"] == 160500
    assert r.rights_clock.next_drop["at"].startswith("2026-12-12T22:00")


def test_demo_2_edge_case_rights_appear_and_vanish(sc):
    s = sc["edge_three_hours"]
    r = assess(s.journey, s.events, s.start_clock, Priority.MONEY)
    tdr = next(p for p in r.plans if p.kind == PlanKind.FILE_TDR_LATE)
    assert tdr.money_back_paise == 118000 and tdr.money_back_if_approved
    assert tdr.deadline.strftime("%H:%M") == "17:10"
    assert any(w.kind == "TDR_LATE" and w.status == "OPEN" for w in r.rights_clock.windows)

    # Presenter drags the delay down to 170 min: the right disappears.
    events = [*s.events, Event(train_no="90501", type=EventType.DELAY, delay_minutes=170,
                               observed_at=s.start_clock)]
    r2 = assess(s.journey, events, s.start_clock, Priority.MONEY)
    assert not any(p.kind == PlanKind.FILE_TDR_LATE for p in r2.plans)
    assert not any(w.kind == "TDR_LATE" for w in r2.rights_clock.windows)
    assert "MAY_BECOME_TDR_ELIGIBLE" in r2.plans[0].warnings


def test_demo_2_vande_bharat_never_guesses(sc):
    s = sc["edge_three_hours"]
    j = s.journey.model_copy(deep=True)
    j.legs[0].ticket.train_category = "VANDE_BHARAT_SLEEPER"
    r = assess(j, s.events, s.start_clock, Priority.MONEY)
    assert any(p.kind == PlanKind.USE_OFFICIAL_CHANNEL for p in r.plans)
    assert not any(p.kind == PlanKind.FILE_TDR_LATE for p in r.plans)


def test_demo_3_waitlisted_family(sc):
    s = sc["waitlisted_family"]
    r = assess(s.journey, s.events, s.start_clock, Priority.TIME)
    auto = next(p for p in r.plans if p.kind == PlanKind.AUTO_REFUND_WAIT)
    assert auto.money_back_paise == 214000              # 4 x ₹595 - 4 x ₹60
    assert auto.certainty == Certainty.AUTOMATIC
    top = r.plans[0]
    assert top.kind == PlanKind.AUTO_REFUND_PLUS_ALTERNATIVE
    assert top.rides[0].train_no == "90305"
    assert top.certainty == Certainty.CHECK_AVAILABILITY   # never shown as a confirmed seat
    assert not any(w.kind == "CANCEL_SLAB" for w in r.rights_clock.windows)
    assert r.rights_clock.decision_deadline.strftime("%H:%M") == "16:30"


def test_demo_4_missed_connection_linked(sc):
    s = sc["missed_connection"]
    r = assess(s.journey, s.events, s.start_clock, Priority.TIME)
    top = r.plans[0]
    assert top.kind == PlanKind.TDR_MISSED_CONNECTION_PLUS_ALTERNATIVE
    assert [x.train_no for x in top.rides] == ["90205", "90601"]
    assert top.money_back_paise == 45500 and top.money_back_if_approved
    assert top.deadline_unverified
    w = next(w for w in r.rights_clock.windows if w.kind == "TDR_MISSED_CONNECTION")
    assert w.status == "UPCOMING" and not w.verified


def test_demo_4_not_linked_uses_cancellation_rules(sc):
    s = sc["missed_connection"]
    j = s.journey.model_copy(update={"linked_pnr": False})
    r = assess(j, s.events, s.start_clock, Priority.TIME)
    assert all(p.kind == PlanKind.CANCEL_NEXT_LEG_PLUS_ALTERNATIVE for p in r.plans)
    # Leg 2 leaves 06:15, now 02:30: under 8 h, so cancelling returns nothing.
    assert r.plans[0].money_back_paise == 0


def test_stale_data_gives_no_advice(sc):
    s = sc["edge_three_hours"]
    r = assess(s.journey, s.events, s.start_clock + timedelta(minutes=40))
    assert [p.kind for p in r.plans] == [PlanKind.USE_OFFICIAL_CHANNEL]
