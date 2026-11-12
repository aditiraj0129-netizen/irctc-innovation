"""Simulated disruption tests for the detector."""
from datetime import datetime, timedelta

import pytest

from app.core.clock import IST
from app.data.source import load_scenarios
from app.detect.detector import SituationType, detect
from app.domain.models import Event, EventType
from app.rules.models import TicketStatus


@pytest.fixture(scope="module")
def sc():
    return load_scenarios()


def ev(train, kind, at, **kw):
    return Event(train_no=train, type=kind, observed_at=at, **kw)


def test_normal_journey_far_ahead_is_not_watched(sc):
    s = sc["normal_journey"]
    assert detect(s.journey, s.events, s.start_clock).primary.type == SituationType.NOT_WATCHING_YET


def test_all_clear_when_on_time_and_fresh(sc):
    s = sc["normal_journey"]
    now = s.journey.legs[0].scheduled_departure - timedelta(hours=2)
    events = [ev("90301", EventType.DELAY, now - timedelta(minutes=5), delay_minutes=0)]
    assert detect(s.journey, events, now).primary.type == SituationType.ALL_CLEAR


def test_stale_data_blocks_advice(sc):
    s = sc["edge_three_hours"]
    later = s.start_clock + timedelta(minutes=30)      # last update 12:25, now 13:00
    a = detect(s.journey, s.events, later)
    assert a.primary.type == SituationType.STALE_DATA


def test_no_events_at_all_while_watching_is_stale(sc):
    s = sc["edge_three_hours"]
    assert detect(s.journey, [], s.start_clock).primary.type == SituationType.STALE_DATA


@pytest.mark.parametrize("delay, expected", [
    (190, SituationType.LATE_OVER_3H),
    (181, SituationType.LATE_OVER_3H),
    (180, SituationType.NEAR_3H),
    (150, SituationType.NEAR_3H),
    (149, SituationType.ALL_CLEAR),
])
def test_three_hour_thresholds(sc, delay, expected):
    s = sc["edge_three_hours"]
    now = s.start_clock
    events = [ev("90501", EventType.DELAY, now - timedelta(minutes=1), delay_minutes=delay)]
    assert detect(s.journey, events, now).primary.type == expected


def test_future_events_are_ignored(sc):
    s = sc["edge_three_hours"]
    events = [ev("90501", EventType.DELAY, s.start_clock - timedelta(minutes=2), delay_minutes=0),
              ev("90501", EventType.DELAY, s.start_clock + timedelta(hours=1), delay_minutes=300)]
    assert detect(s.journey, events, s.start_clock).primary.type == SituationType.ALL_CLEAR


def test_waitlisted_after_chart(sc):
    s = sc["waitlisted_family"]
    assert detect(s.journey, s.events, s.start_clock).primary.type == SituationType.WAITLISTED_AFTER_CHART


def test_chart_confirms_ticket_no_alert(sc):
    s = sc["waitlisted_family"]
    events = [ev("90301", EventType.CHART_PREPARED, s.start_clock - timedelta(minutes=5),
                 chart_status=TicketStatus.CONFIRMED)]
    # The booked status stays WAITLISTED in our data, but the chart now says CONFIRMED: no alert.
    assert detect(s.journey, events, s.start_clock).primary.type == SituationType.ALL_CLEAR


def test_connection_buffer_maths(sc):
    s = sc["missed_connection"]
    a = detect(s.journey, s.events, s.start_clock)
    sit = a.primary
    assert sit.type == SituationType.CONNECTION_AT_RISK
    # expected arrival 05:00 + 130 = 07:10; next train 06:15; minus 30 min transfer = -85
    assert sit.buffer_minutes == -85
    assert sit.detail["station"] == "PRYJ"


@pytest.mark.parametrize("delay, at_risk", [(45, False), (46, True)])
def test_connection_boundary(sc, delay, at_risk):
    s = sc["missed_connection"]
    # 75 min scheduled gap, 30 min minimum transfer: a 45-min delay leaves exactly 0 margin.
    events = [ev("90101", EventType.DELAY, s.start_clock - timedelta(minutes=1), delay_minutes=delay)]
    types = [x.type for x in detect(s.journey, events, s.start_clock).situations]
    assert (SituationType.CONNECTION_AT_RISK in types) is at_risk


def test_train_cancelled(sc):
    s = sc["normal_journey"]
    now = s.journey.legs[0].scheduled_departure - timedelta(hours=3)
    events = [ev("90301", EventType.CANCELLED, now - timedelta(minutes=2))]
    assert detect(s.journey, events, now).primary.type == SituationType.TRAIN_CANCELLED


def test_journey_over(sc):
    s = sc["normal_journey"]
    now = s.journey.legs[-1].scheduled_arrival + timedelta(minutes=1)
    assert detect(s.journey, [], now).primary.type == SituationType.JOURNEY_OVER


def test_invalid_event_rejected():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Event(train_no="90301", type="DELAY", delay_minutes=-10, observed_at=datetime(2026, 12, 15, tzinfo=IST))
