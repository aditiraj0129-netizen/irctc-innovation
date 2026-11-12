"""What-If simulator, counterfactual recommendations, resilience score."""
from datetime import timedelta

import pytest

from app.data.source import load_scenarios
from app.domain.models import Event, EventType
from app.insights.resilience import score_journey
from app.plan.counterfactual import recommend
from app.plan.models import PlanKind
from app.plan.ranker import Priority
from app.plan.service import assess, connections_for
from app.twin.twin import build_twin
from app.whatif.simulator import ScenarioId, simulate


@pytest.fixture(scope="module")
def sc():
    return load_scenarios()


def by_id(res):
    return {o.id: o for o in res.outcomes}


def test_all_scenarios_present_and_deterministic(sc):
    s = sc["missed_connection"]
    a = simulate(s.journey, s.events, s.start_clock)
    b = simulate(s.journey, s.events, s.start_clock)
    assert [o.id for o in a.outcomes] == list(ScenarioId)
    assert a.model_dump() == b.model_dump()


def test_missed_connection_outcomes(sc):
    s = sc["missed_connection"]
    o = by_id(simulate(s.journey, s.events, s.start_clock))
    best = o[ScenarioId.BEST_NOW]
    assert best.arrival.strftime("%d %H:%M") == "16 20:30" and best.arrival_diff_minutes == 240
    assert best.money_back_paise == 45500 and best.money_back_if_approved
    assert best.confidence == "MEDIUM" and "SEATS_NOT_CHECKED" in best.confidence_reasons
    assert o[ScenarioId.CANCEL_NOW].money_back_paise == 0          # leg 2 within 8 h: nothing back
    assert o[ScenarioId.ONE_CHANGE_ROUTE].changes == 1


def test_waiting_long_loses_options(sc):
    s = sc["missed_connection"]
    o = by_id(simulate(s.journey, s.events, s.start_clock, wait_minutes=420))   # wait until 09:30
    w = o[ScenarioId.WAIT_30]
    assert any(k.startswith("90205@") for k in w.lost_options)                 # 09:45 train needs booking by 09:15
    assert "IF_NOTHING_ELSE_CHANGES" in w.assumptions and "SOME_OPTIONS_DISAPPEAR" in w.cons


def test_delay_grows_is_hypothetical(sc):
    s = sc["edge_three_hours"]
    o = by_id(simulate(s.journey, s.events, s.start_clock, delay_increase=120))
    d = o[ScenarioId.DELAY_GROWS]
    assert "HYPOTHETICAL_EVENT" in d.assumptions and "HYPOTHETICAL" in d.confidence_reasons
    assert len(s.events) == 1                                                  # nothing stored


def test_miss_connection_is_simulated_when_not_yet_missed(sc):
    s = sc["missed_connection"]
    small = [Event(train_no="90101", type=EventType.DELAY, delay_minutes=10, observed_at=s.start_clock)]
    m = by_id(simulate(s.journey, small, s.start_clock))[ScenarioId.MISS_CONNECTION]
    assert m.applicable and "FIRST_TRAIN_DELAY_46_MIN" in m.assumptions        # 10 + 35 margin + 1


def test_not_applicable_scenarios_say_why(sc):
    s = sc["waitlisted_family"]
    o = by_id(simulate(s.journey, s.events, s.start_clock))
    assert o[ScenarioId.CANCEL_NOW].not_applicable_reason == "AUTO_REFUND_ALREADY_DUE"
    assert o[ScenarioId.MISS_CONNECTION].not_applicable_reason == "NO_CONNECTION"


def test_invalid_whatif_parameters(sc):
    s = sc["normal_journey"]
    with pytest.raises(ValueError):
        simulate(s.journey, s.events, s.start_clock, delay_increase=0)
    with pytest.raises(ValueError):
        simulate(s.journey, s.events, s.start_clock, wait_minutes=1000)


def test_counterfactual_only_from_calculated_scenarios(sc):
    s = sc["missed_connection"]
    r = assess(s.journey, s.events, s.start_clock)
    rec = recommend(r.plans, Priority.TIME, simulate(s.journey, s.events, s.start_clock, wait_minutes=420))
    assert rec.plan_id == r.plans[0].id
    assert "ARRIVES_EARLIER" in rec.why and "CONNECTION_FEASIBLE" in rec.why
    assert rec.comparisons[0].arrival_diff_minutes == 200
    effects = {c.scenario: c.effect for c in rec.counterfactuals}
    assert effects[ScenarioId.WAIT_30] == "RECOMMENDED_NO_LONGER_FEASIBLE"
    assert recommend(r.plans, Priority.TIME, None).counterfactuals == []       # nothing claimed without the simulator


def test_resilience_is_transparent_and_experimental(sc):
    s = sc["missed_connection"]
    twin = build_twin(s.journey, s.events, s.start_clock)
    r = score_journey(s.journey, twin, connections_for(s.journey))
    assert r.label == "EXPERIMENTAL" and r.method_note == "WEIGHTED_RULES_NOT_VALIDATED"
    assert sum(f.weight for f in r.factors) == 100
    assert r.score == round(sum(f.score * f.weight for f in r.factors) / 100)
    assert "CONNECTION_BUFFER" in r.main_risks and "CHOOSE_LONGER_CONNECTION" in r.suggestions
    unlinked = s.journey.model_copy(update={"linked_pnr": False})
    assert score_journey(unlinked, twin, connections_for(s.journey)).score < r.score
