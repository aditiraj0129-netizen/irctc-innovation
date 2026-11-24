"""Journey Recovery Graph, recovery view and dashboard (next round)."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.data.source import load_scenarios
from app.domain.models import Event, EventType, Journey, Leg
from app.graph.journey_graph import build_graph
from app.graph.recovery import build_recovery
from app.main import app
from app.plan.transfer import PassengerProfile
from app.rules.models import Ticket

c = TestClient(app)


@pytest.fixture(scope="module")
def sc():
    return load_scenarios()


def delay(train, mins, at):
    return Event(train_no=train, type=EventType.DELAY, delay_minutes=mins, observed_at=at)


def codes(g):
    return [t.code for t in g.trace]


def test_bhopal_delhi_chandigarh_at_risk_then_broken(sc):
    s = sc["bhopal_delhi_chandigarh"]
    g = build_graph(s.journey, s.events, s.start_clock)
    assert codes(g) == ["TRAIN_DELAYED", "CONNECTION_AT_RISK"]
    t = next(e for e in g.edges if e.kind.value == "TRANSFER")
    assert (t.gap_minutes, t.required_minutes, t.margin_minutes, t.state.value) == (35, 30, 5, "AT_RISK")
    # the graph updates the moment the delay grows
    g2 = build_graph(s.journey, [*s.events, delay("90701", 95, s.start_clock)], s.start_clock)
    assert codes(g2) == ["TRAIN_DELAYED", "CONNECTION_BROKEN", "LEG_LIKELY_MISSED", "RECOVERY_NEEDED"]
    assert g2.broken_from_leg == 2
    assert {n.id: n.state.value for n in g2.nodes} == {"L1:DEP": "DONE", "L1:ARR": "DELAYED",
                                                      "L2:DEP": "BROKEN", "L2:ARR": "BROKEN"}
    # and back again when the delay recovers
    g3 = build_graph(s.journey, [*s.events, delay("90701", 5, s.start_clock)], s.start_clock)
    assert "CONNECTION_STILL_OK" in codes(g3) and g3.broken_from_leg is None


def test_passenger_profile_changes_the_graph(sc):
    s = sc["bhopal_delhi_chandigarh"]
    g = build_graph(s.journey, [*s.events, delay("90701", 10, s.start_clock)], s.start_clock)
    assert codes(g)[-1] == "CONNECTION_TIGHT"                 # 50 min gap, 30 needed
    slow = build_graph(s.journey, [*s.events, delay("90701", 10, s.start_clock)], s.start_clock,
                       PassengerProfile(senior=True, step_free=True))
    t = next(e for e in slow.edges if e.kind.value == "TRANSFER")
    assert t.required_minutes == 53 and "CONNECTION_BROKEN" in codes(slow)   # NDLS: 25*1.5+15


def test_three_connected_trains_propagate(sc):
    """Multiple connected trains: a broken first change makes every later leg unreachable."""
    base = sc["missed_connection"].journey
    t0 = base.legs[0]
    mk = lambda seq, no, a, b, dep, arr: Leg(seq=seq, train_name=f"Sim {no}", from_stn=a, to_stn=b, scheduled_arrival=arr,
                                            ticket=t0.ticket.model_copy(update={"train_no": no, "scheduled_departure": dep}))
    d = t0.scheduled_departure
    j = Journey(id="three", pnr_label="x", title="three legs", legs=[
        mk(1, "91001", "NDLS", "CNB", d, d + timedelta(hours=5)),
        mk(2, "91002", "CNB", "PRYJ", d + timedelta(hours=6), d + timedelta(hours=9)),
        mk(3, "91003", "PRYJ", "PNBE", d + timedelta(hours=10), d + timedelta(hours=15))])
    now = d + timedelta(hours=2)
    g = build_graph(j, [delay("91001", 90, now)], now)
    assert codes(g)[:4] == ["TRAIN_DELAYED", "CONNECTION_BROKEN", "LEG_LIKELY_MISSED", "DOWNSTREAM_LEG_UNREACHABLE"]
    assert g.broken_from_leg == 2 and len(g.nodes) == 6 and len(g.edges) == 5


def test_cancelled_and_stale_and_conflicting_events(sc):
    s = sc["bhopal_delhi_chandigarh"]
    now = s.start_clock
    cx = build_graph(s.journey, [*s.events, Event(train_no="90801", type=EventType.CANCELLED, observed_at=now)], now)
    assert "TRAIN_CANCELLED" in codes(cx) and cx.broken_from_leg == 2
    stale = build_graph(s.journey, s.events, now + timedelta(minutes=40))
    assert codes(stale)[0] == "DATA_STALE"
    # conflicting delay reports: the latest observation wins, deterministically
    mixed = [*s.events, delay("90701", 95, now - timedelta(minutes=3)), delay("90701", 20, now)]
    assert "CONNECTION_BROKEN" not in codes(build_graph(s.journey, mixed, now))


def test_recovery_rights_and_urgency(sc):
    s = sc["bhopal_delhi_chandigarh"]
    watch = build_recovery(s.journey, s.events, s.start_clock)
    assert watch.urgency.level == "WATCH" and watch.consequence["connection_margin_minutes"] == 5
    r = build_recovery(s.journey, [*s.events, delay("90701", 95, s.start_clock)], s.start_clock)
    assert r.situation == "CONNECTION_AT_RISK" and r.affected_legs == [1, 2]
    assert r.consequence["fare_of_unusable_legs_paise"] == 64500
    top = r.next_steps[0]
    assert top.plan_kind == "TDR_MISSED_CONNECTION_PLUS_ALTERNATIVE" and top.trains == ["90803"]
    assert top.money_back_if_approved and top.deadline_unverified
    assert {x.kind for x in r.rights} >= {"TDR_MISSED_CONNECTION"}
    assert r.recommendation and r.recommendation.plan_id == top.plan_id
    assert r.what_happened[0].delay_minutes == 95 and r.what_happened[0].source == "SIMULATED"


def test_recovery_stale_gives_no_advice(sc):
    s = sc["edge_three_hours"]
    r = build_recovery(s.journey, s.events, s.start_clock + timedelta(minutes=40))
    assert not r.data_fresh and r.urgency.level == "UNKNOWN" and r.recommendation is None
    assert [x.plan_kind for x in r.next_steps] == ["USE_OFFICIAL_CHANNEL"]


def test_api_graph_recovery_dashboard_and_v1():
    c.post("/api/demo/bhopal_delhi_chandigarh/reset")
    assert c.get("/api/v1/health").status_code == 200
    assert c.get("/api/v1/journeys/bhopal_delhi_chandigarh/graph").json()["trace"][1]["code"] == "CONNECTION_AT_RISK"
    c.post("/api/demo/bhopal_delhi_chandigarh/events", json={"train_no": "90701", "type": "DELAY", "delay_minutes": 95})
    rec = c.get("/api/journeys/bhopal_delhi_chandigarh/recovery").json()
    assert rec["graph"]["broken_from_leg"] == 2 and rec["journey"]["legs"][1]["to"]["en"] == "Chandigarh"
    d = c.get("/api/dashboard?ids=normal_journey,bhopal_delhi_chandigarh,unknown_one").json()["journeys"]
    assert [x["journey"]["id"] for x in d] == ["bhopal_delhi_chandigarh", "normal_journey"]   # most urgent first
    assert c.get("/api/dashboard?ids=../../etc").status_code == 422
    assert c.get("/api/dashboard").json()["journeys"] == []
    c.post("/api/demo/bhopal_delhi_chandigarh/reset")
