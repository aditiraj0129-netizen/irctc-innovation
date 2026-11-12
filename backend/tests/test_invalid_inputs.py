"""Bad input must be rejected loudly, never guessed."""
from datetime import date, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.core.clock import IST, FixedClock, NaiveDatetimeError
from app.rules.engine import RuleNotFoundError, RuleRegistry, cancellation_refund
from app.rules.models import RuleRegistryData
from tests.conftest import DEP


@pytest.mark.parametrize(
    "overrides",
    [
        {"train_no": "1255"},                     # 4 digits
        {"train_no": "12A55"},
        {"fare_per_passenger_paise": 0},
        {"fare_per_passenger_paise": -100},
        {"passengers": 0},
        {"passengers": 7},
        {"travel_class": "XX"},
        {"scheduled_departure": datetime(2026, 12, 10, 22, 0)},   # no timezone
    ],
)
def test_bad_ticket_rejected(make_ticket, overrides):
    with pytest.raises((ValidationError, NaiveDatetimeError)):
        make_ticket(**overrides)


def test_naive_cancellation_time_rejected(make_ticket, registry):
    with pytest.raises(NaiveDatetimeError):
        cancellation_refund(make_ticket(), datetime(2026, 12, 9, 10, 0), registry)


def test_date_with_no_rule_raises(make_ticket, registry):
    old = datetime(2014, 1, 1, 10, 0, tzinfo=IST)
    t = make_ticket(scheduled_departure=old + timedelta(days=3))
    with pytest.raises(RuleNotFoundError):
        cancellation_refund(t, old, registry)


def test_rules_file_rejects_badly_ordered_slabs(registry):
    raw = registry.data.model_dump(mode="json")
    raw["rule_sets"][0]["confirmed_slabs"].reverse()
    with pytest.raises(ValidationError):
        RuleRegistryData.model_validate(raw)


def test_every_rule_has_a_source(registry):
    for item in [*registry.data.rule_sets, *registry.data.special_rules]:
        assert item.source.title
        assert item.source.strength


def test_utc_input_is_converted_to_ist(make_ticket, registry):
    from zoneinfo import ZoneInfo
    utc_time = (DEP - timedelta(hours=30)).astimezone(ZoneInfo("UTC"))
    d = cancellation_refund(make_ticket(), utc_time, registry)
    assert d.rule_ids[0].endswith("CNF_PERCENT_25")


def test_fixed_clock():
    c = FixedClock(datetime(2026, 12, 10, 9, 0, tzinfo=IST))
    c.advance(minutes=90)
    assert c.now() == datetime(2026, 12, 10, 10, 30, tzinfo=IST)
    with pytest.raises(NaiveDatetimeError):
        c.set(datetime(2026, 12, 10, 9, 0))
