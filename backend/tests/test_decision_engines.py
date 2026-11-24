"""PREDICT -> DECIDE -> RECOVER: delay propagation, connection risk, recovery search, decision comparison."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.data.source import load_scenarios
from app.decide.decision import CARD_KEYS, build_decision
from app.domain.models import Event, EventType
from app.plan.ranker import Priority
from app.plan.service import stops
from app.plan.transfer import PassengerProfile
from app.predict import evaluation as ev
from app.predict.connection import ConnRisk, connection_risk
from app.predict.delay import (BaselineHeuristicModel, Outlook, RiskBand, Trend, congestion, predict_delay,
                               run_date_for)
from app.predict import network
from app.predict.weather import IMDWeatherProvider, SimulatedWeatherProvider, UnavailableWeatherProvider
from app.recover.engine import (DemoSampleBusProvider, NoBusProvider, OptionKind, ResultType, connections_window,
                                pareto, recover)
from app.rules.models import Ticket

SC = load_scenarios()


def sc(name):
    return SC[name]


def pred_for(name, events=None, weather="sim", now=None, network_events=None):
    s = sc(name)
    w = SimulatedWeatherProvider(s.weather_warnings) if weather == "sim" else weather
    return predict_delay(stops(), s.journey.legs[0], s.events if events is None else events,
                         s.network_events if network_events is None else network_events, w, now or s.start_clock)


def decision(name, **kw):
    s = sc(name)
    return build_decision(s.journey, kw.pop("events", s.events), kw.pop("now", s.start_clock),
                          network_events=s.network_events, weather=SimulatedWeatherProvider(s.weather_warnings),
                          bus=kw.pop("bus", DemoSampleBusProvider()), **kw)


# ---------- A. own-train delay trend ----------

def test_trend_recovering_growing_and_steady():
    rec, worse, fog = pred_for("decide_recover"), pred_for("decide_worsening"), pred_for("decide_fog")
    assert rec.trend == Trend.RECOVERING and rec.slope_min_per_hour < 0
    assert worse.trend == Trend.GROWING and worse.slope_min_per_hour > 0
    assert fog.trend == Trend.STEADY
    assert [s["change"] for s in rec.evidence[0]["steps"]] == [-10, -10]
    assert rec.outlook == Outlook.MAY_RECOVER and rec.growth_risk == RiskBand.LOWER


def test_range_is_a_range_and_never_a_probability():
    for name in ["decide_recover", "decide_worsening", "decide_fog", "decide_missed"]:
        p = pred_for(name)
        assert p.delay_low <= p.delay_mid <= p.delay_high
        assert p.arrival_early <= p.expected_arrival <= p.arrival_late
        assert p.probability is None and p.probability_status == "DISABLED_NOT_CALIBRATED"
        assert p.generated_at and p.latest_data_at and p.explanation and p.limitations


def test_missing_observations_give_insufficient_evidence_not_a_guess():
    s = sc("decide_recover")
    p = pred_for("decide_recover", events=[e for e in s.events if e.type != EventType.DELAY])
    assert p.outlook == Outlook.INSUFFICIENT_EVIDENCE and p.growth_risk == RiskBand.INSUFFICIENT_EVIDENCE
    assert p.expected_arrival is None and "NO_RUNNING_OBSERVATION" in p.missing_inputs
    one = pred_for("decide_recover", events=[s.events[-1]])
    assert one.trend == Trend.UNKNOWN and "ONLY_ONE_OBSERVATION" in one.missing_inputs
    assert one.growth_risk == RiskBand.MODERATE         # one reading is not enough to call it "lower"


def test_stale_running_data_gives_no_range():
    s = sc("decide_recover")
    p = pred_for("decide_recover", now=s.start_clock + timedelta(minutes=40))
    assert not p.data_fresh and p.delay_mid is None and "RUNNING_DATA_STALE" in p.missing_inputs
    d = decision("decide_recover", now=s.start_clock + timedelta(minutes=40))
    assert d.recommendation["code"] == "CHECK_OFFICIAL_STATUS"


def test_baseline_model_rules_are_transparent():
    m = BaselineHeuristicModel()
    base = {"current_delay": 20, "remaining_minutes": 60, "slope": 0.0, "trend": Trend.STEADY,
            "congestion_level": "NONE", "fog_add": 0, "recovery_allowance": 10}
    assert m.predict(base) == (10, 20, 35)                # 20 - 10 allowance; +10 base +5/h uncertainty
    assert m.predict({**base, "fog_add": 30})[2] > m.predict(base)[2]
    assert m.predict({**base, "remaining_minutes": 0}) == (20, 20, 20)


# ---------- B. shared route sections ----------

def test_shared_section_matching_counts_only_trains_just_ahead():
    p = pred_for("decide_worsening")
    reasons = {c.train_no: c.reason for c in p.congestion.checks}
    assert reasons["90723"] == "COUNTED" and reasons["90725"] == "COUNTED"
    assert reasons["90729"] == "TOO_FAR_AHEAD"
    assert reasons["90724"] == "OPPOSITE_DIRECTION"           # delayed, same track, other direction: not counted
    assert p.congestion.level == "MODERATE" and p.congestion.note == "CONGESTION_RISK_INDICATOR_NOT_CONFIRMED_CAUSE"


def test_false_congestion_correlations_are_rejected():
    s = sc("decide_worsening")
    leg = s.journey.legs[0]
    passes = [x for x in network.passes(stops(), leg.train_no, run_date_for(stops(), leg)) if x.section == "AGC-NDLS"]
    t = s.start_clock

    def check(events):
        return {c.train_no: c.reason for c in congestion(stops(), passes, 20, events, t, leg.train_no).checks}

    # a delayed train that is BEHIND us
    late_behind = [Event(train_no="90723", type=EventType.DELAY, delay_minutes=80, observed_at=t)]
    assert check(late_behind)["90723"] == "BEHIND_US"
    # an on-time train ahead
    assert check([Event(train_no="90723", type=EventType.DELAY, delay_minutes=5, observed_at=t)])["90723"] == "NOT_DELAYED"
    # an old observation is not evidence
    old = [Event(train_no="90723", type=EventType.DELAY, delay_minutes=35, observed_at=t - timedelta(hours=2))]
    assert check(old)["90723"] == "NO_FRESH_OBSERVATION"
    # a delayed train on a DIFFERENT corridor is never even looked at
    other = [Event(train_no="90101", type=EventType.DELAY, delay_minutes=90, observed_at=t)]
    assert "90101" not in check(other)


# ---------- C. fog / weather ----------

def test_fog_warning_applies_only_on_route_ahead_and_while_valid():
    p = pred_for("decide_fog")
    assert [w["id"] for w in p.weather.applied] == ["FOG-SIM-AGC-NDLS"]
    assert {"id": "FOG-SIM-JHS-AGC-MORNING", "section": "JHS-AGC", "reason": "EXPIRED"} in p.weather.ignored
    no_fog = pred_for("decide_fog", weather=SimulatedWeatherProvider([]))
    assert p.delay_high > no_fog.delay_high and p.weather.note == "WARNING_RAISES_RISK_NOT_PROOF_OF_CAUSE"


def test_weather_provider_unavailable_is_reported_not_crashing():
    for prov in (IMDWeatherProvider(), UnavailableWeatherProvider()):
        p = pred_for("decide_fog", weather=prov)
        assert p.weather.status == "UNAVAILABLE" and "WEATHER_UNAVAILABLE" in p.missing_inputs
        assert p.expected_arrival is not None          # the prediction still works without weather

    class Broken:
        name = "BROKEN"

        def fog_warnings(self, now):
            raise TimeoutError("provider down")
    assert pred_for("decide_fog", weather=Broken()).weather.status == "UNAVAILABLE"


# ---------- connection risk ----------

@pytest.mark.parametrize("name,risk", [("decide_recover", ConnRisk.TIGHT), ("decide_worsening", ConnRisk.HIGH_RISK),
                                       ("decide_fog", ConnRisk.HIGH_RISK), ("decide_missed", ConnRisk.NOT_FEASIBLE),
                                       ("decide_nextday", ConnRisk.NOT_FEASIBLE)])
def test_connection_feasibility_uses_the_whole_range(name, risk):
    s = sc(name)
    c = connection_risk(s.journey, 1, pred_for(name), s.events, s.start_clock)
    assert c.risk == risk and c.probability is None
    assert c.slack_early >= c.slack_expected >= c.slack_late


def test_transfer_buffer_depends_on_passenger_needs():
    s = sc("decide_recover")
    p = pred_for("decide_recover")
    normal = connection_risk(s.journey, 1, p, s.events, s.start_clock)
    slow = connection_risk(s.journey, 1, p, s.events, s.start_clock, PassengerProfile(senior=True, step_free=True))
    assert slow.transfer_minutes_needed > normal.transfer_minutes_needed >= s.journey.min_transfer_minutes
    assert slow.risk != ConnRisk.COMFORTABLE and "STEP_FREE_ROUTE" in slow.transfer_basis
    # a 25-minute gap is NOT treated as proof: the same 20-min delay is TIGHT when recovering, HIGH_RISK when growing
    assert normal.risk == ConnRisk.TIGHT
    assert normal.max_tolerable_delay_minutes == 60 - normal.transfer_minutes_needed


# ---------- recovery engine ----------

def _rec(name, **kw):
    s = sc(name)
    st = stops()
    conns = connections_window(st, s.journey.legs[0].ticket.scheduled_departure.date() - timedelta(days=1), 4)
    leg2 = s.journey.legs[1]
    return recover(conns, "NDLS", "CDG", kw.pop("earliest", s.start_clock + timedelta(hours=2, minutes=40)),
                   s.start_clock, "CONNECTION_BROKEN", {(leg2.train_no, run_date_for(st, leg2))},
                   travel_class="CC", bus=kw.pop("bus", DemoSampleBusProvider()), **kw)


def test_recovery_finds_direct_one_change_nearby_and_next_day():
    r = _rec("decide_missed")
    kinds = {o.kind for o in r.options}
    assert {OptionKind.DIRECT, OptionKind.NEARBY_STATION} <= kinds
    assert all(o.legs[-1].to_stn == "CDG" for o in r.options + r.next_day)
    assert all(o.next_day and o.tatkal and o.tatkal["guaranteed"] is False for o in r.next_day)
    assert "90821" not in {l.train_no for o in r.options for l in o.legs}         # the missed booked train is excluded


def test_ranking_is_explained_and_follows_priority():
    r = _rec("decide_missed")
    for o in r.options:
        assert o.score == round(sum(p["points"] for p in o.score_parts), 2)
    assert [o.rank for o in r.options] == list(range(1, len(r.options) + 1))
    by_transfers = _rec("decide_missed", priority=Priority.TRANSFERS)
    assert by_transfers.options[0].transfers == 0


def test_no_duplicate_or_dominated_trains():
    r = _rec("decide_missed")
    ids = [o.id for o in r.options + r.next_day]
    assert len(ids) == len(set(ids))
    assert pareto(r.options) == r.options


def test_no_alternative_available_gives_a_clear_reason():
    r = _rec("decide_missed", earliest=sc("decide_missed").start_clock + timedelta(days=5), bus=NoBusProvider())
    assert r.options == [] and r.next_day == [] and r.empty_reason == "NO_ALTERNATIVE_FOUND"


def test_seat_availability_and_fares_are_never_invented():
    r = _rec("decide_missed")
    for o in r.options + r.next_day:
        assert o.seat_availability == "UNKNOWN_NOT_CONNECTED" and o.fare_paise is None
        assert o.result_type == ResultType.DEMO_SIMULATED          # exactly one status, never "confirmed"
    for b in r.buses:
        assert b.fare_status == "SAMPLE_NOT_REAL" and b.result_type == ResultType.DEMO_SIMULATED


def test_buses_only_from_a_configured_provider():
    assert _rec("decide_missed", bus=NoBusProvider()).bus_status == "NOT_CONFIGURED"
    assert _rec("decide_missed", bus=None).buses == []
    assert _rec("decide_missed").bus_status == "DEMO_SAMPLES"


def test_unreserved_eligibility_rules():
    r = _rec("decide_missed")
    assert r.unreserved
    for u in r.unreserved:
        assert u.unreserved["separate_ticket_required"] is True and u.unreserved["current_ticket_valid"] is False
        assert all(network.train_info(l.train_no).general_coaches for l in u.legs if l.mode == "TRAIN")
    # chair-car-only trains (no General coaches) are never offered as unreserved
    assert not any(l.train_no in ("90821", "90801") for u in r.unreserved for l in u.legs)


# ---------- decision comparison ----------

def test_every_card_is_filled_never_blank():
    for name in SC:
        d = decision(name)
        assert [c.key for c in d.cards] == CARD_KEYS
        for c in d.cards:
            assert c.meaning
            assert c.status == "AVAILABLE" or c.reason or c.missing, (name, c.key)
            assert c.next_action or c.status != "AVAILABLE", (name, c.key)


def test_refund_comparison_cancel_now_vs_later():
    d = decision("decide_refund")
    rows = {m.key: m for m in d.money}
    assert rows["CANCEL_NOW"].money_back_paise == 66000 and rows["CANCEL_NOW"].certainty == "RULE_ESTIMATE"
    assert rows["WAIT_UNTIL"].money_back_paise == 66000 and rows["WAIT_UNTIL"].at < rows["CANCEL_LATER"].at
    assert rows["CANCEL_LATER"].money_back_paise == 0
    assert d.claims.tdr_eligibility == "MAY_BECOME_ELIGIBLE"           # 2.5 h late: not yet over 3 h
    assert d.recommendation["if_not_travelling"]["decide_by"].startswith("2026-12-26T01:29")
    assert rows["CANCEL_NOW"].legal_status == "ANNOUNCED"


def test_dont_cancel_when_a_claim_is_worth_more():
    d = decision("decide_worsening")
    cancel = next(c for c in d.cards if c.key == "CANCEL")
    assert cancel.money["paise"] == 0 and cancel.next_action["code"] == "DO_NOT_CANCEL_TDR_BETTER"
    assert d.claims.tdr_eligibility == "ELIGIBLE_IF_MISSED" and d.claims.tdr_submission == "NOT_SUBMITTED_BY_AGLA_KADAM"
    assert d.recommendation["code"] == "STAY_BUT_PREPARE" and d.recommendation["dont_cancel"]["tdr_paise"] == 64500


def test_missed_connection_does_not_automatically_qualify():
    s = sc("decide_missed")
    j = s.journey.model_copy(update={"linked_pnr": False})
    d = build_decision(j, s.events, s.start_clock, bus=DemoSampleBusProvider())
    assert d.claims.tdr_eligibility == "NOT_ELIGIBLE" and d.claims.tdr_reason == "PNRS_NOT_LINKED"
    assert d.recommendation["claim"]["code"] == "TDR_NOT_ELIGIBLE"


def test_missing_ticket_information_is_explained():
    s = sc("decide_refund")
    leg = s.journey.legs[0]
    counter = leg.model_copy(update={"ticket": Ticket(**{**leg.ticket.model_dump(), "is_eticket": False})})
    j = s.journey.model_copy(update={"legs": [counter]})
    d = build_decision(j, s.events, s.start_clock)
    cancel = next(c for c in d.cards if c.key == "CANCEL")
    assert cancel.status == "DATA_MISSING" and cancel.reason == "COUNTER_TICKET_USE_COUNTER"


@pytest.mark.parametrize("name,code,card", [
    ("decide_recover", "STAY_AND_WATCH", "CONTINUE"), ("decide_worsening", "STAY_BUT_PREPARE", "CONTINUE"),
    ("decide_fog", "STAY_BUT_PREPARE", "CONTINUE"), ("decide_missed", "BOOK_ALTERNATIVE", "OTHER_TRAIN"),
    ("decide_refund", "TRAVEL_AS_BOOKED", "CONTINUE"), ("decide_nextday", "BOOK_ALTERNATIVE", "NEXT_SERVICE")])
def test_six_demo_scenarios_end_to_end(name, code, card):
    d = decision(name)
    assert d.recommendation["code"] == code and d.recommendation["card"] == card
    assert sum(c.recommended for c in d.cards) == 1


def test_next_day_tatkal_timing_is_one_day_before_and_not_guaranteed():
    d = decision("decide_nextday")
    tk = d.recommendation["tatkal"]
    assert tk["opens_at"] == "2026-12-27T10:00:00+05:30" and tk["guaranteed"] is False   # CC is an AC class: 10:00
    assert tk["availability"] == "UNKNOWN_NOT_CONNECTED"


def test_evaluation_maths_on_hand_made_numbers():
    assert ev.mae([10, 20], [12, 16]) == 3
    assert ev.rmse([10, 20], [12, 16]) == pytest.approx((10) ** 0.5)
    assert ev.brier([1.0, 0.0], [True, False]) == 0
    assert ev.interval_coverage([0, 0], [10, 5], [5, 7]) == 0.5
    assert ev.EVALUATION_STATUS.startswith("NOT_EVALUATED")
    with pytest.raises(ValueError):
        ev.brier([1.5], [True])


# ---------- API + Copilot ----------

c = TestClient(__import__("app.main", fromlist=["app"]).app)


def test_decision_api_for_every_journey_and_404():
    for jid in SC:
        r = c.get(f"/api/v1/journeys/{jid}/decision")
        assert r.status_code == 200 and len(r.json()["cards"]) == 6
    assert c.get("/api/v1/journeys/nope/decision").status_code == 404
    p = c.get("/api/v1/journeys/decide_fog/prediction").json()
    assert p["prediction"]["weather"]["applied"] and p["evaluation_status"].startswith("NOT_EVALUATED")
    assert c.get("/api/v1/journeys/decide_missed/recovery-options").json()["options"]


@pytest.mark.parametrize("q,intent,needle", [
    ("My train is 20 minutes late. Can I catch the next train?", "CATCH_CONNECTION", "at risk"),
    ("If I cancel now, how much money will I get?", "CANCEL_MONEY", "₹645"),
    ("Find another train to Chandigarh.", "FIND_TRAIN", "Seats and fares are not checked"),
    ("Can I use a general ticket?", "UNRESERVED", "separate unreserved ticket"),
    ("Can I travel by bus instead?", "BUS", "Demo sample only"),
    ("What if I wait until tomorrow?", "NEXT_DAY", "never guaranteed"),
    ("Explain the safest option in Hindi.", "SAFEST", "सबसे सुरक्षित"),
    ("What if it gets delayed another 15 minutes?", "WHAT_IF_DELAY", "15 min")])
def test_copilot_decision_questions(q, intent, needle):
    c.post("/api/demo/decide_worsening/reset")
    r = c.post("/api/v1/journeys/decide_worsening/copilot", json={"message": q, "lang": "en"}).json()
    assert r["intent"] == intent and needle in r["answer"]
    assert all(t["ok"] for t in r["tool_calls"])


def test_copilot_rejects_hallucinated_train_data():
    from app.copilot.copilot import run_copilot
    from app.copilot.tools import ToolContext

    class FakeLLM:
        def __init__(self):
            self.n = 0

        def complete_json(self, system, user):
            self.n += 1
            if self.n == 1:
                return {"intent": "FIND_TRAIN", "calls": [{"tool": "find_alternatives", "args": {}}]}
            return {"answer": "Take train 90999 at 18:05, seats available, guaranteed refund."}
    s = sc("decide_missed")
    ctx = ToolContext(journey=s.journey, events=s.events, now=s.start_clock, profile=PassengerProfile())
    r = run_copilot("find another train", ctx, llm=FakeLLM())
    assert "90999" not in r.answer and r.answer_source == "TEMPLATES"
    assert any(w.startswith("LLM_PHRASE_REJECTED") for w in r.warnings)


def test_invalid_tool_calls_are_refused():
    from app.copilot.tools import ToolCall, ToolContext, run_tool
    s = sc("decide_missed")
    ctx = ToolContext(journey=s.journey, events=s.events, now=s.start_clock, profile=PassengerProfile())
    assert run_tool(ctx, ToolCall(tool="find_alternatives", args={"priority": "cheapest_ever"})).error == "INVALID_ARGUMENTS"
    assert run_tool(ctx, ToolCall(tool="find_bus", args={"book": True})).error == "INVALID_ARGUMENTS"
    assert run_tool(ctx, ToolCall(tool="book_alternative_train")).error == "TOOL_NOT_ALLOWED"


def test_rag_cites_unreserved_and_tatkal_guidance_or_says_no_source():
    from app.knowledge.grounded import grounded_answer
    a = grounded_answer("can I travel in general coach with unreserved ticket")
    assert a.found and any(x.doc_id == "GUIDE-UNRESERVED" for x in a.citations)
    assert not grounded_answer("price of a flight to the moon").found


def test_a_sudden_jump_is_not_extrapolated_as_a_trend():
    # Two readings 5 minutes apart (25 -> 95 min) must not be read as "+840 min per hour".
    s = sc("bhopal_delhi_chandigarh")
    jump = [*s.events, Event(train_no="90701", type=EventType.DELAY, delay_minutes=95, observed_at=s.start_clock)]
    p = predict_delay(stops(), s.journey.legs[0], jump, [], None, s.start_clock)
    assert p.trend == Trend.UNKNOWN and p.current_delay_minutes == 95
    assert p.delay_high - p.delay_mid <= 40
    d = build_decision(s.journey, jump, s.start_clock, bus=DemoSampleBusProvider())
    assert d.recommendation["code"] == "BOOK_ALTERNATIVE" and d.recommendation["option"]["train"] == "90803"
