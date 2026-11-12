"""LLM failure tests: the app must work, and never show an invented number."""
import httpx
import pytest

from app.data.source import load_scenarios
from app.explain import explainer
from app.explain.explainer import explain, rupees, validate
from app.plan.models import PlanKind
from app.plan.service import assess


@pytest.fixture(autouse=True)
def clear_cache():
    explainer._cache.clear()


@pytest.fixture(scope="module")
def tdr_plan():
    s = load_scenarios()["edge_three_hours"]
    r = assess(s.journey, s.events, s.start_clock)
    return next(p for p in r.plans if p.kind == PlanKind.FILE_TDR_LATE)


class FakeLLM:
    def __init__(self, reply=None, exc=None):
        self.reply, self.exc, self.calls = reply, exc, 0

    def complete_json(self, system, user):
        self.calls += 1
        if self.exc:
            raise self.exc
        return self.reply


def test_rupee_format():
    assert rupees(118000) == "₹1,180"
    assert rupees(12345678) == "₹1,23,456.78"
    assert rupees(0) == "₹0"


def test_no_llm_uses_template_in_both_languages(tdr_plan):
    en = explain(tdr_plan, "en", None)
    hi = explain(tdr_plan, "hi", None)
    assert en.source == hi.source == "template"
    assert "₹1,180" in en.body and "17:10" in en.body
    assert "₹1,180" in hi.body


def test_good_llm_reply_is_used_and_slots_filled(tdr_plan):
    llm = FakeLLM({"headline": "Skip this train, claim a refund",
                   "body": "File the TDR before {deadline}. If approved, {refund} comes back."})
    e = explain(tdr_plan, "en", llm)
    assert e.source == "llm"
    assert "₹1,180" in e.body and "17:10" in e.body


@pytest.mark.parametrize("reply, error", [
    ({"headline": "Refund", "body": "You will get ₹2,000 back."}, "DIGIT_OUTSIDE_SLOT"),
    ({"headline": "Refund", "body": "Refund of {bonus} is guaranteed."}, "UNKNOWN_SLOT:bonus"),
    ({"headline": "Refund", "body": "Your {refund} is guaranteed."}, "PROMISE_WORDING"),
    ({"headline": "", "body": "x"}, "EMPTY"),
    ({"headline": "रिफंड", "body": "आपको ₹२००० मिलेंगे"}, "DIGIT_OUTSIDE_SLOT"),
])
def test_bad_llm_reply_falls_back(tdr_plan, reply, error):
    e = explain(tdr_plan, "en", FakeLLM(reply))
    assert e.source == "template"
    assert error in e.validator_errors


@pytest.mark.parametrize("exc", [httpx.ReadTimeout("slow"), httpx.ConnectError("down"), ValueError("bad json")])
def test_llm_errors_fall_back(tdr_plan, exc):
    e = explain(tdr_plan, "en", FakeLLM(exc=exc))
    assert e.source == "template"
    assert e.validator_errors[0].startswith("LLM_ERROR")


def test_llm_reply_is_cached(tdr_plan):
    llm = FakeLLM({"headline": "Skip this train", "body": "If approved, {refund} comes back."})
    explain(tdr_plan, "en", llm)
    explain(tdr_plan, "en", llm)
    assert llm.calls == 1


def test_validator_allows_helpline_number():
    assert validate("Call", "Call 139 for help.", {"refund"}) == []


def test_every_template_uses_known_slots_and_no_promises():
    # Templates are written by us and may state fixed rule facts such as "3 hours";
    # the digit rule applies only to LLM output.
    from app.explain.templates import T
    from app.plan.models import PlanKind
    for lang, kinds in T.items():
        assert set(kinds) == set(PlanKind), lang
        for kind, (h, b) in kinds.items():
            errors = [e for e in validate(h, b, {"refund", "deadline", "arrival", "trains", "station"})
                      if e != "DIGIT_OUTSIDE_SLOT"]
            assert errors == [], (lang, kind)


def test_llm_disabled_by_default(monkeypatch):
    monkeypatch.delenv("LLM_ENABLED", raising=False)
    assert explainer.llm_from_env() is None
