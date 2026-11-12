"""API tests for the upgrade endpoints (validation + integration)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)
ALL = ["normal_journey", "edge_three_hours", "waitlisted_family", "missed_connection",
       "family_confirmed", "family_waitlisted"]


@pytest.fixture(autouse=True)
def reset():
    for j in ALL:
        c.post(f"/api/demo/{j}/reset")
        c.put(f"/api/journeys/{j}/preferences", json={})


def test_all_new_endpoints_respond():
    for path in ["twin", "whatif", "wallet", "resilience", "offline-card", "community/reports", "preferences"]:
        assert c.get(f"/api/journeys/missed_connection/{path}").status_code == 200, path
    assert c.get("/api/groups").json()[0]["id"] == "demo_family"
    assert c.get("/api/groups/demo_family").status_code == 200


def test_unknown_ids_404():
    assert c.get("/api/journeys/nope/twin").status_code == 404
    assert c.get("/api/groups/nope").status_code == 404


@pytest.mark.parametrize("q", ["delay_increase=0", "delay_increase=999", "wait_minutes=1", "priority=fast"])
def test_whatif_validation(q):
    assert c.get(f"/api/journeys/missed_connection/whatif?{q}").status_code == 422


def test_preferences_change_transfer_analysis():
    c.put("/api/journeys/missed_connection/preferences",
          json={"profile": {"senior": True, "step_free": True}, "priority": "risk"})
    t = c.get("/api/journeys/missed_connection/twin").json()
    assert t["transfers"][0]["check"]["required_minutes"] == 40
    assert c.put("/api/journeys/missed_connection/preferences",
                 json={"profile": {"walking_speed": "running"}}).status_code == 422


def test_claim_flow_and_validation():
    assert c.post("/api/journeys/edge_three_hours/wallet/claims",
                  json={"item_id": "TDR_LATE_RUNNING:1", "status": "RECEIVED"}).status_code == 422
    assert c.post("/api/journeys/edge_three_hours/wallet/claims",
                  json={"item_id": "TDR_LATE_RUNNING:1", "status": "FILED"}).status_code == 200
    w = c.get("/api/journeys/edge_three_hours/wallet").json()
    assert next(i for i in w["items"] if i["id"] == "TDR_LATE_RUNNING:1")["stage"] == "FILED"
    assert c.post("/api/journeys/edge_three_hours/wallet/claims",
                  json={"item_id": "x", "status": "MAYBE"}).status_code == 422


def test_export_is_downloadable_text():
    r = c.get("/api/journeys/edge_three_hours/wallet/export")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert "not guaranteed" in r.text


def test_assistant_validation_and_language():
    assert c.post("/api/journeys/edge_three_hours/assistant", json={"text": "", "lang": "en"}).status_code == 422
    assert c.post("/api/journeys/edge_three_hours/assistant", json={"text": "hi", "lang": "fr"}).status_code == 422
    r = c.post("/api/journeys/edge_three_hours/assistant", json={"text": "kitna paisa milega", "lang": "hi"}).json()
    assert r["intent"] == "REFUND" and "₹1,180" in r["answer"]


def test_assessment_has_recommendation_and_keeps_old_fields():
    a = c.get("/api/journeys/missed_connection/assessment").json()
    for k in ["journey", "now", "situation", "plans", "rights_clock", "actions", "data_label"]:
        assert k in a
    assert a["recommendation"]["plan_id"] == a["plans"][0]["id"]
    stale = c.post("/api/demo/edge_three_hours/clock", json={"advance_minutes": 40})
    assert c.get("/api/journeys/edge_three_hours/assessment").json()["recommendation"] is None


def test_seeded_reports_are_marked_simulated_and_unverified():
    r = c.get("/api/journeys/missed_connection/community/reports").json()
    assert r and all(x["simulated_seed"] and x["label"] == "UNVERIFIED_PASSENGER_REPORT" for x in r)
    plat = next(x for x in r if x["type"] == "PLATFORM_CHANGE")
    assert plat["reporters"] == 2 and plat["conflicting"]


def test_group_reset_and_cancelled_train_flow():
    assert c.post("/api/demo/groups/demo_family/reset").status_code == 200
    c.post("/api/demo/normal_journey/clock", json={"at": "2026-12-15T18:00:00+05:30"})   # 4 h before departure
    c.post("/api/demo/normal_journey/events", json={"train_no": "90301", "type": "CANCELLED"})
    a = c.get("/api/journeys/normal_journey/assessment").json()
    assert a["situation"]["type"] == "TRAIN_CANCELLED"
    assert a["plans"][0]["money_back_paise"] == 214000 or any(p["kind"] == "AUTO_REFUND_WAIT" for p in a["plans"])
    t = c.get("/api/journeys/normal_journey/twin").json()
    assert t["status"] == "BROKEN"


def test_cancellation_known_days_early_is_shown_immediately():
    """Found during upgrade testing: a cancellation 3 days ahead used to show 'not watching yet'."""
    c.post("/api/demo/normal_journey/events", json={"train_no": "90301", "type": "CANCELLED"})
    a = c.get("/api/journeys/normal_journey/assessment").json()
    assert a["situation"]["type"] == "TRAIN_CANCELLED"
