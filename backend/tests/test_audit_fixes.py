"""Regression tests for the final audit fixes (security, trust, labelling)."""
import importlib

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app

c = TestClient(app)


@pytest.mark.parametrize("path", ["/..%2f..%2fbackend%2fapp%2fmain.py", "/..%2F..%2FREADME.md",
                                  "/%2e%2e/%2e%2e/README.md", "/assets/..%2f..%2f..%2fREADME.md"])
def test_no_file_outside_the_frontend_can_be_read(path):
    if not main.DIST.exists():
        pytest.skip("frontend not built")
    r = c.get(path)
    assert "FastAPI app for Agla Kadam" not in r.text and "Know your next step" not in r.text


def test_security_headers_on_every_response():
    r = c.get("/api/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "microphone=(self)" in r.headers["Permissions-Policy"]


def test_demo_token_protects_presenter_endpoints(monkeypatch):
    monkeypatch.setattr(main, "DEMO_TOKEN", "s3cret")
    assert c.post("/api/demo/normal_journey/reset").status_code == 403
    assert c.post("/api/demo/normal_journey/reset", headers={"X-Demo-Token": "wrong"}).status_code == 403
    assert c.post("/api/demo/normal_journey/reset", headers={"X-Demo-Token": "s3cret"}).status_code == 200
    assert c.get("/api/journeys/normal_journey/assessment").status_code == 200      # passenger API unaffected


def test_one_caller_cannot_pretend_to_be_many_reporters():
    c.post("/api/demo/missed_connection/reset")
    for i in range(5):
        r = c.post("/api/journeys/missed_connection/community/reports", headers={"X-Reporter": f"fake{i}"},
                   json={"station": "DBG", "type": "CONGESTION"})
    assert r.json()["reporters"] == 1 and r.json()["confidence"] == "LOW"


def test_rate_limiter_forgets_quiet_addresses(monkeypatch):
    main._hits.clear()
    for i in range(5001):
        main._hits[f"10.0.{i // 250}.{i % 250}"]          # empty = quiet
    c.get("/api/health")
    assert len(main._hits) < 10


def _ask(jid, text, lang="en"):
    c.post(f"/api/demo/{jid}/reset")
    return c.post(f"/api/journeys/{jid}/assistant", json={"text": text, "lang": lang}).json()["answer"]


def test_assistant_flags_announced_rule_and_uses_plain_words():
    a = _ask("normal_journey", "how much refund if I cancel")
    assert "₹1,960" in a and "not yet officially confirmed" in a
    assert "CANCELLATION" not in a and "ESTIMATE" not in a
    assert "Zonal Railway" not in a                       # no TDR involved in a cancellation


def test_assistant_tdr_note_only_for_tdr_and_notified_rule_not_flagged():
    a = _ask("edge_three_hours", "how much refund")
    assert "₹1,180" in a and "Zonal Railway" in a and "not yet officially confirmed" not in a
    s = _ask("missed_connection", "is my train late?")
    assert "IN_TRANSIT" not in s and "on the move" in s


def test_rule_sources_are_not_file_sharing_sites_for_core_rules():
    from app.rules.engine import RuleRegistry
    reg = RuleRegistry.from_yaml()
    tdr = next(r for r in reg.data.special_rules if r.id == "TDR-LATE-3H")
    assert "scribd" not in tdr.source.url and "Rule 13(1)" in tdr.source.title
    apr = next(r for r in reg.data.rule_sets if r.id == "RS-REG-2026-APR")
    assert apr.legal_status.value == "ANNOUNCED" and "pib.gov.in" in apr.source.url
