"""Journey Digital Twin + Station Transfer Intelligence."""
from datetime import timedelta

import pytest

from app.data.source import load_scenarios
from app.domain.models import Event, EventType
from app.plan.ranker import Priority
from app.plan.service import assess
from app.plan.transfer import PassengerProfile, TransferClass, check_transfer, classify, required_minutes
from app.twin.twin import Freshness, JourneyStatus, LegState, build_twin


@pytest.fixture(scope="module")
def sc():
    return load_scenarios()


def delay(train, minutes, at):
    return Event(train_no=train, type=EventType.DELAY, delay_minutes=minutes, observed_at=at)


# ---------- transfer intelligence ----------

@pytest.mark.parametrize("margin, cls", [(-1, TransferClass.NOT_FEASIBLE), (0, TransferClass.HIGH_RISK),
                                         (9, TransferClass.HIGH_RISK), (10, TransferClass.TIGHT),
                                         (24, TransferClass.TIGHT), (25, TransferClass.COMFORTABLE)])
def test_transfer_classes(margin, cls):
    assert classify(margin) == cls


def test_required_time_depends_on_passenger():
    assert required_minutes("PRYJ") == 30                                  # floor wins (20 min walk estimate)
    assert required_minutes("PRYJ", PassengerProfile(walking_speed="slow")) == 30
    assert required_minutes("PRYJ", PassengerProfile(senior=True, step_free=True)) == 40   # 20*1.5 + 10
    assert required_minutes("NDLS", PassengerProfile(senior=True, step_free=True)) == 53   # 25*1.5 + 15
    assert required_minutes("UNKNOWN", floor=30) == 30                     # default estimate, never invented


def test_check_transfer_labels_estimates_as_simulated(sc):
    leg = sc["missed_connection"].journey.legs
    c = check_transfer("PRYJ", leg[0].scheduled_arrival, leg[1].scheduled_departure)
    assert c.gap_minutes == 75 and c.margin_minutes == 45 and c.cls == TransferClass.COMFORTABLE
    assert "Simulated" in c.estimate_label


def test_infeasible_alternative_is_never_offered(sc):
    """Scenario 6: an alternative whose change of train is impossible for this passenger is dropped."""
    s = sc["missed_connection"]
    normal = assess(s.journey, s.events, s.start_clock, Priority.TIME)
    assert normal.plans[0].rides[0].train_no == "90205"                    # 90205 -> PNBE 16:00 -> 90601 17:00
    # A passenger who needs 61+ minutes at Patna cannot make the 60-minute change.
    slow = PassengerProfile(senior=True, step_free=True)                   # PNBE needs 40 min -> still feasible
    r = assess(s.journey, s.events, s.start_clock, Priority.TIME, slow)
    assert r.plans[0].transfers[0].cls in (TransferClass.TIGHT, TransferClass.COMFORTABLE)
    j = s.journey.model_copy(update={"min_transfer_minutes": 65})
    r2 = assess(j, s.events, s.start_clock, Priority.TIME)
    assert all([x.train_no for x in p.rides] != ["90205", "90601"] for p in r2.plans)


def test_transfers_priority_prefers_direct_trains(sc):
    s = sc["missed_connection"]
    r = assess(s.journey, s.events, s.start_clock, Priority.TRANSFERS)
    assert r.plans[0].changes == 0 and r.plans[0].travels


# ---------- digital twin ----------

def test_twin_missed_connection(sc):
    s = sc["missed_connection"]
    t = build_twin(s.journey, s.events, s.start_clock)
    assert t.status == JourneyStatus.BROKEN
    assert [l.state for l in t.legs] == [LegState.IN_TRANSIT, LegState.LIKELY_MISSED]
    assert t.transfers[0].check.margin_minutes == -85
    assert t.affected_segments == [1, 2] and t.expected_final_arrival is None
    assert t.legs[0].info.freshness == Freshness.FRESH and t.legs[0].info.source == "SIMULATED"
    assert t.legs[1].info.freshness == Freshness.NONE


def test_twin_recalculates_when_events_change(sc):
    s = sc["missed_connection"]
    now = s.start_clock
    small = build_twin(s.journey, [delay("90101", 20, now)], now)
    assert small.status == JourneyStatus.DISRUPTED
    assert small.legs[1].state == LegState.SCHEDULED and small.unaffected_segments == [2]
    assert small.delay_at_destination_minutes == 0
    risky = build_twin(s.journey, [delay("90101", 40, now)], now)          # margin 5 -> high risk
    assert risky.legs[1].state == LegState.AT_RISK
    senior = build_twin(s.journey, [delay("90101", 30, now)], now, PassengerProfile(senior=True, step_free=True))
    assert senior.transfers[0].check.cls == TransferClass.HIGH_RISK      # 45 - 40 = 5 min to spare


def test_twin_normal_and_cancelled(sc):
    s = sc["normal_journey"]
    t = build_twin(s.journey, s.events, s.start_clock)
    assert t.status == JourneyStatus.ON_TRACK and t.unaffected_segments == [1]
    now = s.journey.legs[0].scheduled_departure - timedelta(hours=3)
    c = build_twin(s.journey, [Event(train_no="90301", type=EventType.CANCELLED, observed_at=now)], now)
    assert c.status == JourneyStatus.BROKEN and c.legs[0].state == LegState.CANCELLED


def test_twin_stale_info_is_marked(sc):
    s = sc["edge_three_hours"]
    t = build_twin(s.journey, s.events, s.start_clock + timedelta(minutes=40))
    assert t.legs[0].info.freshness == Freshness.STALE and t.legs[0].info.age_minutes == 45
