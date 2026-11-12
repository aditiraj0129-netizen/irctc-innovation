"""Offline card, assistant and community reports."""
from datetime import timedelta

import pytest

from app.assistant.assistant import Intent, answer, detect_intent
from app.community.reports import CommunityService, ReportIn, ReportType
from app.data.source import load_scenarios
from app.offline.card import build_card
from app.plan.ranker import Priority
from app.plan.service import assess
from app.store import Store
from app.twin.twin import build_twin
from app.wallet.wallet import build_wallet


@pytest.fixture(scope="module")
def sc():
    return load_scenarios()


def parts(s, now=None):
    now = now or s.start_clock
    r = assess(s.journey, s.events, now)
    return r, build_wallet(s.journey, s.events, now, r.plans, [], []), build_twin(s.journey, s.events, now)


# ---------- offline card ----------

def test_offline_card_is_a_labelled_snapshot_without_personal_data(sc):
    s = sc["missed_connection"]
    r, w, t = parts(s)
    card = build_card(s.journey, t, r.plans, w)
    assert card.data_label == "SIMULATED_SNAPSHOT_NOT_LIVE"
    assert card.pnr_label.startswith("81xxxxxx") and "8100000004" not in card.model_dump_json()
    assert card.stale_after == s.start_clock + timedelta(minutes=30)
    assert {e["number"] for e in card.emergency} >= {"139", "182", "1930"}
    assert card.plans[0]["rides"][0]["train_no"] == "90205"
    assert any(x["unresolved"] for x in card.rules)
    assert "CARD_IS_A_SNAPSHOT" in card.instructions


# ---------- assistant ----------

@pytest.mark.parametrize("text, intent", [
    ("Meri train teen ghante late hai, ab kya karun?", Intent.WHAT_TO_DO),
    ("मेरी ट्रेन लेट है, अब क्या करूँ?", Intent.WHAT_TO_DO),
    ("Should I wait or take another train?", Intent.WAIT_OR_ALTERNATIVE),
    ("What happens if I miss my connecting train?", Intent.MISS_CONNECTION),
    ("When is my refund filing deadline?", Intent.DEADLINE),
    ("kitna paisa milega", Intent.REFUND),
    ("Is my train late?", Intent.STATUS),
    ("tell me a joke", Intent.UNKNOWN),
])
def test_intents(text, intent):
    assert detect_intent(text) == intent


def test_assistant_answers_only_from_backend_facts(sc):
    s = sc["edge_three_hours"]
    r, w, t = parts(s)
    a = answer("When is my refund filing deadline?", "en", r.plans, w, t, stale=False)
    assert "17:10" in a.answer and a.rule_ids == ["TDR-LATE-3H"] and a.answer_source == "RULES_ENGINE"
    h = answer("Meri train teen ghante late hai, ab kya karun?", "hi", r.plans, w, t, stale=False)
    assert "₹1,180" in h.answer and "मंज़ूरी" in h.answer


def test_assistant_refuses_when_data_is_stale(sc):
    s = sc["edge_three_hours"]
    r, w, t = parts(s)
    a = answer("what should I do", "en", r.plans, w, t, stale=True)
    assert "139" in a.answer and "₹" not in a.answer


class EvilLLM:
    def complete_json(self, system, user):
        return {"intent": "REFUND", "answer": "You will get ₹99,999 guaranteed"}


class BrokenLLM:
    def complete_json(self, system, user):
        raise TimeoutError()


def test_llm_can_only_pick_an_intent_never_facts(sc):
    s = sc["edge_three_hours"]
    r, w, t = parts(s)
    a = answer("bhai scene batao zara", "en", r.plans, w, t, False, EvilLLM())
    assert a.intent == Intent.REFUND and a.intent_source == "llm"
    assert "99,999" not in a.answer and "₹1,180" in a.answer
    b = answer("blah blah", "en", r.plans, w, t, False, BrokenLLM())
    assert b.intent == Intent.UNKNOWN and "I can answer" in b.answer


# ---------- community reports ----------

@pytest.fixture
def svc():
    return CommunityService(Store(":memory:"))


def test_duplicate_and_confidence(svc, sc):
    now = sc["missed_connection"].start_clock
    r = ReportIn(station="PRYJ", type=ReportType.CONGESTION)
    svc.submit("missed_connection", r, "ip-1", now)
    again = svc.submit("missed_connection", r, "ip-1", now + timedelta(minutes=2))       # same person again
    assert again.reporters == 1 and again.confidence == "LOW"
    svc.submit("missed_connection", r, "ip-2", now + timedelta(minutes=3))
    third = svc.submit("missed_connection", r, "ip-3", now + timedelta(minutes=4))
    assert third.reporters == 3 and third.confidence == "MEDIUM"
    assert third.label == "UNVERIFIED_PASSENGER_REPORT" and not third.affects_recommendations
    assert len(svc.active("missed_connection", now + timedelta(minutes=5))) == 1


def test_conflict_and_expiry(svc, sc):
    now = sc["missed_connection"].start_clock
    svc.submit("j", ReportIn(station="PRYJ", type=ReportType.PLATFORM_CHANGE, note="far side"), "a", now)
    c = svc.submit("j", ReportIn(station="PRYJ", type=ReportType.PLATFORM_CHANGE, note="near side"), "b",
                   now + timedelta(minutes=5))
    assert c.conflicting
    assert svc.active("j", now + timedelta(minutes=64)) and not svc.active("j", now + timedelta(minutes=66))


def test_personal_data_rejected():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ReportIn(station="PRYJ", type="CONGESTION", note="call me 98765 43210")
    with pytest.raises(ValidationError):
        ReportIn(station="PRYJ", type="CONGESTION", note="mail x@y.com")
    with pytest.raises(ValidationError):
        ReportIn(station="Patna!", type="CONGESTION")


def test_reports_never_change_recommendations(sc):
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    c.post("/api/demo/missed_connection/reset")
    before = c.get("/api/journeys/missed_connection/assessment").json()
    for i in range(5):
        c.post("/api/journeys/missed_connection/community/reports", headers={"X-Reporter": f"user{i}"},
               json={"station": "PRYJ", "type": "TRAIN_STOPPED", "train_no": "90205"})
    after = c.get("/api/journeys/missed_connection/assessment").json()
    strip = lambda a: [(p["id"], p["money_back_paise"], p["deadline"], p["rank"]) for p in a["plans"]]
    assert strip(before) == strip(after)
    assert before["rights_clock"] == after["rights_clock"]
