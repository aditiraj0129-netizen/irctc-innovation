"""Providers, cache, idempotency (next round)."""
import pytest
from fastapi.testclient import TestClient

from app.core.cache import TTLCache
from app.data.source import SimulatedSource, load_scenarios
from app.main import app
from app.providers import OfficialJourneys, OfficialTrainStatus, ProviderNotConfigured, build_providers

c = TestClient(app)


def test_simulated_providers_and_official_stubs_refuse():
    p = build_providers(SimulatedSource(load_scenarios()), "simulated")
    d = p.describe()
    assert d["train_status"] == "SIMULATED" and d["ai_model"].startswith("OFF")
    assert p.stations.name("CDG") == "Chandigarh" and p.stations.transfer_estimate("NDLS")
    with pytest.raises(ProviderNotConfigured):
        build_providers(SimulatedSource(load_scenarios()), "official")
    with pytest.raises(ProviderNotConfigured):
        OfficialTrainStatus().events_for("x")
    with pytest.raises(ProviderNotConfigured):
        OfficialJourneys().journey_for_pnr("1234567890")


def test_ttl_cache_expires_and_caps():
    t = [0.0]
    cache = TTLCache(ttl_seconds=5, max_items=2, clock=lambda: t[0])
    cache.put("a", 1)
    assert cache.get("a") == 1
    t[0] = 6
    assert cache.get("a") is None
    cache.put("x", 1); cache.put("y", 2); cache.put("z", 3)
    assert cache.get("x") is None and cache.get("z") == 3


def test_idempotent_claims():
    c.post("/api/demo/edge_three_hours/reset")
    h = {"Idempotency-Key": "abc12345-retry"}
    body = {"item_id": "TDR_LATE_RUNNING:1", "status": "FILED"}
    r1 = c.post("/api/journeys/edge_three_hours/wallet/claims", json=body, headers=h)
    r2 = c.post("/api/journeys/edge_three_hours/wallet/claims", json=body, headers=h)   # network retry
    assert r1.status_code == r2.status_code == 200 and r1.json() == r2.json()
    hist = c.get("/api/journeys/edge_three_hours/wallet").json()["history"]
    assert [x["kind"] for x in hist].count("CLAIM_UPDATE") == 1
    assert c.post("/api/journeys/edge_three_hours/wallet/claims", json=body,
                  headers={"Idempotency-Key": "bad key!"}).status_code == 422
    c.post("/api/demo/edge_three_hours/reset")


def test_health_reports_providers_and_versions():
    h = c.get("/api/v1/health").json()
    assert h["providers"]["mode"] == "simulated" and h["api_versions"] == ["v1"]
