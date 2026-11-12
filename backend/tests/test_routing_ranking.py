"""Route search and ranking tests."""
from datetime import date, datetime, timedelta

import pytest

from app.core.clock import IST
from app.data.timetable import build_connections, load_stops
from app.plan.csa import alternatives, earliest_arrival
from app.plan.models import Certainty, Plan, PlanKind
from app.plan.ranker import Priority, rank


@pytest.fixture(scope="module")
def conns():
    return build_connections(load_stops(), date(2026, 12, 14), days=4)


def t(day, hh, mm=0):
    return datetime(2026, 12, day, hh, mm, tzinfo=IST)


def test_direct_and_one_change_options(conns):
    opts = alternatives(conns, "PRYJ", "DBG", t(16, 7, 40), 30, {"90203"})
    assert [o.arr for o in opts][:3] == [t(16, 20, 30), t(16, 23, 50), t(17, 1, 0)]
    first = opts[0]
    assert [r.train_no for r in first.rides] == ["90205", "90601"]
    assert first.changes == 1


def test_best_option_matches_connection_scan(conns):
    start = t(16, 7, 40)
    opts = alternatives(conns, "PRYJ", "DBG", start, 30, {"90203"})
    assert earliest_arrival(conns, "PRYJ", "DBG", start, 30, {"90203"}) == opts[0].arr


def test_transfer_time_is_respected(conns):
    # 90205 reaches PNBE 16:00; 90601 leaves 17:00. With a 61-min minimum, that change is impossible.
    opts = alternatives(conns, "PRYJ", "DBG", t(16, 7, 40), 61, {"90203"})
    assert all([r.train_no for r in o.rides] != ["90205", "90601"] for o in opts)


def test_overnight_train_dates(conns):
    opts = alternatives(conns, "NDLS", "PNBE", t(15, 13, 35), 30, {"90301"})
    o = opts[0]
    assert o.rides[0].train_no == "90305"
    assert o.dep == t(15, 17, 0) and o.arr == t(16, 6, 30)


def test_no_route_returns_empty(conns):
    assert alternatives(conns, "DBG", "LKO", t(15, 10), 30) == []


def test_departed_trains_are_not_offered(conns):
    opts = alternatives(conns, "PRYJ", "DBG", t(16, 14, 5), 30)
    assert all(o.dep >= t(16, 14, 5) for o in opts)


def _plan(id, travels, arrival, lost, cert, new_ticket=False):
    return Plan(id=id, kind=PlanKind.TRAVEL_AS_BOOKED, travels=travels, arrival=arrival,
                money_lost_paise=lost, certainty=cert, needs_new_ticket=new_ticket)


def test_ranking_priorities_and_reasons():
    a = _plan("fast", True, t(16, 20), 5000, Certainty.CHECK_AVAILABILITY, True)
    b = _plan("slow", True, t(17, 1), 0, Certainty.BOOKED)
    c = _plan("stay", False, None, 0, Certainty.IF_APPROVED)
    assert [p.id for p in rank([a, b, c], Priority.TIME)] == ["fast", "slow", "stay"]
    assert [p.id for p in rank([a, b, c], Priority.MONEY)] == ["slow", "stay", "fast"]
    assert [p.id for p in rank([a, b, c], Priority.RISK)] == ["slow", "stay", "fast"]
    top = rank([a, b, c], Priority.TIME)[0]
    assert {"key": "ARRIVES_EARLIER", "minutes": 300} in top.reasons


def test_ranking_is_deterministic():
    plans = [_plan(str(i), True, t(16, 10 + i), 0, Certainty.CHECK_AVAILABILITY) for i in range(5)]
    assert [p.id for p in rank(list(reversed(plans)), Priority.TIME)] == ["0", "1", "2", "3", "4"]
