"""Late-running TDR and automatic refund tests."""
from datetime import timedelta

import pytest

from app.rules.engine import InvalidTicketError, late_running_tdr, train_cancelled, waitlisted_after_chart
from app.rules.models import APPROVAL_NOTE, Outcome, TicketStatus, TrainCategory
from tests.conftest import DEP

FARE = 214000


def expected(delay_min: int):
    return DEP + timedelta(minutes=delay_min)


@pytest.mark.parametrize(
    "delay, outcome",
    [(180, Outcome.NOT_ELIGIBLE),           # exactly 3h is NOT "more than 3 hours"
     (181, Outcome.ELIGIBLE_TO_FILE_TDR),
     (270, Outcome.ELIGIBLE_TO_FILE_TDR),
     (0, Outcome.NOT_ELIGIBLE)],
)
def test_three_hour_boundary(make_ticket, registry, delay, outcome):
    now = DEP + timedelta(minutes=10)       # passenger is waiting at the station
    d = late_running_tdr(make_ticket(), delay, expected(delay), now, registry)
    assert d.outcome == outcome


def test_eligible_tdr_never_promises_refund(make_ticket, registry):
    now = DEP - timedelta(hours=1)
    d = late_running_tdr(make_ticket(passengers=2), 270, expected(270), now, registry)
    assert d.outcome == Outcome.ELIGIBLE_TO_FILE_TDR
    assert d.refund_paise == FARE * 2                 # amount IF approved: full fare
    assert d.deadline == expected(270)                # file before the train actually leaves
    assert d.deadline_moves_with_live_status is True
    assert d.approval_note == APPROVAL_NOTE
    assert "guarantee" not in d.reason_key.lower()
    assert d.rule_ids == ["TDR-LATE-3H"]


def test_window_closes_when_train_departs(make_ticket, registry):
    d = late_running_tdr(make_ticket(), 270, expected(270), expected(270), registry)
    assert d.outcome == Outcome.NOT_ELIGIBLE
    assert d.reason_key == "TDR_WINDOW_CLOSED_TRAIN_DEPARTED"
    d2 = late_running_tdr(make_ticket(), 270, expected(270), DEP, registry, train_departed=True)
    assert d2.outcome == Outcome.NOT_ELIGIBLE


def test_delay_shrinking_below_3h_removes_eligibility(make_ticket, registry):
    now = DEP + timedelta(minutes=30)
    before = late_running_tdr(make_ticket(), 190, expected(190), now, registry)
    after = late_running_tdr(make_ticket(), 170, expected(170), now, registry)
    assert before.outcome == Outcome.ELIGIBLE_TO_FILE_TDR
    assert after.outcome == Outcome.NOT_ELIGIBLE


def test_vande_bharat_late_rule_is_marked_uncertain(make_ticket, registry):
    t = make_ticket(train_category=TrainCategory.VANDE_BHARAT_SLEEPER)
    d = late_running_tdr(t, 300, expected(300), DEP, registry)
    assert d.outcome == Outcome.NEEDS_VERIFICATION
    assert d.refund_paise == 0


def test_negative_delay_rejected(make_ticket, registry):
    with pytest.raises(ValueError):
        late_running_tdr(make_ticket(), -5, DEP, DEP, registry)


def test_train_cancelled_full_auto_refund(make_ticket, registry):
    d = train_cancelled(make_ticket(passengers=3), DEP - timedelta(hours=2), registry)
    assert d.outcome == Outcome.AUTO_REFUND
    assert d.refund_paise == FARE * 3


def test_waitlisted_after_chart_family_of_four(make_ticket, registry):
    t = make_ticket(status=TicketStatus.WAITLISTED, passengers=4)
    d = waitlisted_after_chart(t, DEP - timedelta(hours=9), registry)
    assert d.outcome == Outcome.AUTO_REFUND
    assert d.deduction_paise == 6000 * 4
    assert d.refund_paise == FARE * 4 - 24000


def test_waitlist_rule_rejects_confirmed_ticket(make_ticket, registry):
    with pytest.raises(InvalidTicketError):
        waitlisted_after_chart(make_ticket(), DEP, registry)
