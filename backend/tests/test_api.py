"""API tests with FastAPI's test client."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_all():
    for jid in ["normal_journey", "edge_three_hours", "waitlisted_family", "missed_connection"]:
        client.post(f"/api/demo/{jid}/reset")


def test_health_says_simulated():
    r = client.get("/api/health").json()
    assert r["ok"] and r["data"] == "SIMULATED"


def test_add_journey_by_pnr():
    r = client.post("/api/journeys", json={"pnr": "8100000004"})
    assert r.status_code == 200
    j = r.json()
    assert j["id"] == "missed_connection" and len(j["legs"]) == 2
    assert j["pnr_label"].endswith("(simulated)")


@pytest.mark.parametrize("pnr, code", [("123", 422), ("abcdefghij", 422), ("9999999999", 404)])
def test_bad_pnr(pnr, code):
    assert client.post("/api/journeys", json={"pnr": pnr}).status_code == code


def test_assessment_has_plans_clock_and_explanations():
    r = client.get("/api/journeys/edge_three_hours/assessment?priority=money&lang=hi").json()
    assert r["data_label"] == "SIMULATED"
    assert r["situation"]["type"] == "LATE_OVER_3H"
    tdr = next(p for p in r["plans"] if p["kind"] == "FILE_TDR_LATE")
    assert tdr["money_back_paise"] == 118000
    assert tdr["explanation"]["source"] == "template"
    assert "₹1,180" in tdr["explanation"]["body"]
    assert any(w["kind"] == "TDR_LATE" for w in r["rights_clock"]["windows"])


def test_presenter_flow_delay_change_removes_right():
    client.post("/api/demo/edge_three_hours/events", json={"train_no": "90501", "type": "DELAY", "delay_minutes": 170})
    r = client.get("/api/journeys/edge_three_hours/assessment").json()
    assert r["situation"]["type"] == "NEAR_3H"
    assert not any(p["kind"] == "FILE_TDR_LATE" for p in r["plans"])


def test_clock_advance_makes_data_stale():
    client.post("/api/demo/edge_three_hours/clock", json={"advance_minutes": 40})
    r = client.get("/api/journeys/edge_three_hours/assessment").json()
    assert r["situation"]["type"] == "STALE_DATA"
    assert [p["kind"] for p in r["plans"]] == ["USE_OFFICIAL_CHANNEL"]


def test_event_validation():
    assert client.post("/api/demo/edge_three_hours/events",
                       json={"train_no": "12345", "type": "DELAY", "delay_minutes": 10}).status_code == 422
    assert client.post("/api/demo/edge_three_hours/events",
                       json={"train_no": "90501", "type": "DELAY"}).status_code == 422
    assert client.post("/api/demo/edge_three_hours/events",
                       json={"train_no": "90501", "type": "DELAY", "delay_minutes": -5}).status_code == 422


def test_unknown_journey_and_bad_lang():
    assert client.get("/api/journeys/nope/assessment").status_code == 404
    assert client.get("/api/journeys/normal_journey/assessment?lang=fr").status_code == 422


def test_record_action():
    r = client.post("/api/journeys/waitlisted_family/actions", json={"plan_id": "auto", "plan_kind": "AUTO_REFUND_WAIT"})
    assert r.status_code == 200
    a = client.get("/api/journeys/waitlisted_family/assessment").json()["actions"]
    assert a[0]["plan_id"] == "auto"


def test_rules_endpoint_lists_sources():
    r = client.get("/api/rules").json()
    assert all(rs["source"]["title"] for rs in r["rule_sets"])
    assert any(rs["legal_status"] == "ANNOUNCED" for rs in r["rule_sets"])
