from datetime import datetime

import pytest

from app.core.clock import IST
from app.rules.engine import RuleRegistry
from app.rules.models import Quota, Ticket, TicketStatus, TrainCategory, TravelClass


@pytest.fixture(scope="session")
def registry() -> RuleRegistry:
    return RuleRegistry.from_yaml()


# Scheduled departure used by most tests: 10 Dec 2026, 22:00 IST.
DEP = datetime(2026, 12, 10, 22, 0, tzinfo=IST)


@pytest.fixture
def make_ticket():
    def _make(**overrides) -> Ticket:
        data = dict(
            train_no="12555",
            train_category=TrainCategory.REGULAR,
            travel_class=TravelClass.THIRD_AC,
            quota=Quota.GENERAL,
            status=TicketStatus.CONFIRMED,
            is_eticket=True,
            scheduled_departure=DEP,
            fare_per_passenger_paise=214000,   # ₹2,140
            passengers=1,
        )
        data.update(overrides)
        return Ticket(**data)
    return _make
