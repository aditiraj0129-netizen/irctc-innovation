"""Station Intelligence: graph, routes, platform confidence, connection feasibility, API and Copilot."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.clock import IST
from app.data.source import load_scenarios
from app.main import app
from app.plan.transfer import PassengerProfile
from app.predict.delay import predict_delay
from app.plan.service import stops
from app.station import graph
from app.station.feasibility import assess_connection, trusted_transfer_need
from app.station.graph import EdgeKind
from app.station.platforms import PlatformObservation, PStatus, platform_info
from app.station.route import Profile, RouteError, all_profiles, route
from app.station.service import nearest_facility

c = TestClient(app)
SC = load_scenarios()
NOW = datetime(2026, 12, 29, 18, 30, tzinfo=IST)


def obs(train, kind, p, status="CONFIRMED", mins_ago=5, stn="NDLS"):
    return PlatformObservation(train_no=train, station=stn, kind=kind, platform=p, status=status,
                               observed_at=NOW - timedelta(minutes=mins_ago), source="TEST")


# ---------- station data ----------

def test_three_stations_load_with_sources_and_honest_labels():
    s = graph.stations()
    assert set(s) == {"NDLS", "HWH", "CSMT"}
    for st in s.values():
        assert st.map_kind == "SCHEMATIC" and st.sources
        for n in st.nodes.values():
            assert n.verification in ("VERIFIED_PUBLIC", "REPORTED", "ILLUSTRATIVE")
        for e in st.edges:
            assert e.verification and (e.kind != EdgeKind.LIFT or e.status == "UNKNOWN")   # lifts never assumed working
    assert s["NDLS"].platforms == list(range(1, 17))
    assert 16 not in s["HWH"].platforms and 23 in s["HWH"].platforms                   # PF16 reported non-functional
    assert s["CSMT"].platforms == list(range(1, 19))


# ---------- station graph / route engine ----------

def test_valid_route_with_readable_steps_and_a_time_range():
    r = route(graph.get("NDLS"), "PF4", "PF12")
    assert r.found and r.path[0] == "PF4" and r.path[-1] == "PF12"
    assert 0 < r.minutes_low < r.minutes_high and r.distance_m > 0
    assert [s.code for s in r.steps] == ["START", "WALK_PLATFORM", "UP", "CROSS_FOB", "DOWN", "WALK_PLATFORM", "ARRIVE"]
    assert r.confidence == "SCHEMATIC_DEMO" and "MAP_SCHEMATIC" in r.warnings     # never shown as verified
    assert not any("node" in str(s.params).lower() for s in r.steps)


def test_fastest_route_is_no_slower_than_alternatives():
    st = graph.get("NDLS")
    fast = route(st, "PF4", "PF12", Profile.FASTEST)
    for r in all_profiles(st, "PF4", "PF12"):
        if r.found:
            assert (fast.minutes_low + fast.minutes_high) <= (r.minutes_low + r.minutes_high)


def test_accessible_route_avoids_stairs_and_uses_lifts_with_unknown_status():
    r = route(graph.get("NDLS"), "PF4", "PF12", Profile.STEP_FREE)
    assert r.found and r.stairs == 0 and r.escalators == 0 and r.lifts == 2
    assert "LIFT_STATUS_UNKNOWN" in r.warnings
    assert all(s.params.get("status") == "UNKNOWN" for s in r.steps if s.code in ("UP", "DOWN"))


def test_no_route_exists_when_no_lift_reaches_the_platform():
    r = route(graph.get("NDLS"), "PF7", "PF9", Profile.STEP_FREE)     # no lift mapped at Platforms 6–7
    assert not r.found and r.reason == "NO_STEP_FREE_ROUTE"


def test_multiple_routes_exist_at_a_terminus():
    st = graph.get("HWH")
    fast, level = route(st, "PF2", "PF8", Profile.FASTEST), route(st, "PF2", "PF8", Profile.FEWER_LEVELS)
    assert fast.found and level.found and level.level_changes == 0          # concourse walk, no bridge
    assert len(all_profiles(st, "PF2", "PF8")) >= 1


def test_between_complexes_and_sections():
    hwh = route(graph.get("HWH"), "PF9", "PF21")
    assert hwh.found and any(s.code == "WALK_LINK" for s in hwh.steps)
    csmt = route(graph.get("CSMT"), "PF3", "PF14", Profile.STEP_FREE)
    assert csmt.found and csmt.stairs == 0


def test_invalid_platform_and_missing_facility():
    with pytest.raises(RouteError):
        route(graph.get("NDLS"), "PF99", "PF1")
    r, targets = nearest_facility("CSMT", "PF1", "METRO")                  # no metro mapped at CSMT
    assert r is None and targets == []
    assert c.get("/api/v1/stations/NDLS/route?from=PF99&to=PF1").status_code == 422
    assert c.get("/api/v1/stations/ZZZ/route?from=PF1&to=PF2").status_code == 404
    assert c.get("/api/v1/stations/NDLS/route?from=PF1;drop&to=PF2").status_code == 422


def test_route_to_exit_and_facility_search():
    r, _ = nearest_facility("NDLS", "PF8", "EXIT")
    assert r.found and r.end.startswith("SIDE_")
    res = c.get("/api/v1/stations/NDLS/facilities?q=luggage").json()
    assert res["count"] == 1 and res["results"][0]["facility_type"] == "CLOAKROOM"
    assert c.get("/api/v1/stations/HWH/facilities?type=WAITING_ROOM").json()["count"] == 2
    assert c.get("/api/v1/stations/NDLS/facilities?q=helipad").json()["count"] == 0


def test_slow_walking_takes_longer():
    st = graph.get("NDLS")
    assert route(st, "PF4", "PF12", speed="slow").minutes_high > route(st, "PF4", "PF12").minutes_high


# ---------- platform information ----------

def test_platform_statuses():
    assert platform_info("90821", "NDLS", "DEPARTURE", [obs("90821", "DEPARTURE", 12)], NOW).status == PStatus.CONFIRMED
    rep = platform_info("90721", "NDLS", "ARRIVAL", [obs("90721", "ARRIVAL", 4, "REPORTED")], NOW)
    assert rep.status == PStatus.REPORTED and rep.trusted
    sch = platform_info("90821", "NDLS", "DEPARTURE", [], NOW)
    assert sch.status == PStatus.SCHEDULED and sch.platform == 12 and not sch.trusted
    pred = platform_info("90825", "NDLS", "DEPARTURE", [], NOW)
    assert pred.status == PStatus.PREDICTED and pred.platform == 15        # 6 of the last 7 runs
    unk = platform_info("90101", "NDLS", "DEPARTURE", [], NOW)             # history too mixed to predict
    assert unk.status == PStatus.UNKNOWN and unk.platform is None
    assert unk.message == "LIVE_PLATFORM_UNAVAILABLE_CHECK_BOARDS"


def test_stale_platform_is_kept_but_labelled_and_not_trusted():
    p = platform_info("90821", "NDLS", "DEPARTURE", [obs("90821", "DEPARTURE", 12, mins_ago=90)], NOW)
    assert p.platform == 12 and p.stale and not p.trusted and p.age_minutes == 90


def test_platform_change_is_detected():
    p = platform_info("90821", "NDLS", "DEPARTURE",
                      [obs("90821", "DEPARTURE", 12, mins_ago=20), obs("90821", "DEPARTURE", 16, mins_ago=2)], NOW)
    assert p.platform == 16 and p.changed_from == 12


# ---------- connection feasibility ----------

def _conn(events=None, observations=None, profile=None, now=None):
    s = SC["station_connection"]
    now = now or s.start_clock
    ev = s.events if events is None else events
    pred = predict_delay(stops(), s.journey.legs[0], ev, [], None, now)
    o = s.platform_events if observations is None else observations
    return assess_connection(s.journey, 1, pred, ev, now, o, profile)


def test_feasibility_formula_and_classes():
    c1 = _conn()
    assert c1.result == "TIGHT" and c1.route.found
    assert c1.margin_minutes["late"] == c1.available_minutes["late"] - c1.required_minutes["high"]
    assert c1.required_minutes["high"] == c1.route.minutes_high + c1.buffer_minutes and not c1.guarantee
    s = SC["station_connection"]
    early = [*s.events[:-1], s.events[-1].model_copy(update={"delay_minutes": 5})]
    assert _conn(events=early).result == "COMFORTABLE"
    late = [*s.events[:-1], s.events[-1].model_copy(update={"delay_minutes": 70})]
    assert _conn(events=late).result in ("UNLIKELY", "NOT_FEASIBLE")


def test_unknown_platforms_mean_no_invented_route():
    s = SC["station_connection"]
    no_dep = [o for o in s.platform_events if o.kind == "ARRIVAL"]
    j = s.journey
    leg2 = j.legs[1].model_copy(update={"ticket": j.legs[1].ticket.model_copy(update={"train_no": "90101"})})
    unknown = j.model_copy(update={"legs": [j.legs[0], leg2]})
    pred = predict_delay(stops(), j.legs[0], s.events, [], None, s.start_clock)
    r = assess_connection(unknown, 1, pred, s.events, s.start_clock, no_dep)
    assert r.result == "CANNOT_ASSESS" and "DEPARTURE_PLATFORM_UNKNOWN" in r.missing and r.route is None


def test_unknown_arrival_platform_cannot_be_assessed():
    s = SC["decide_missed"]                    # 90721 has a scheduled arrival platform; remove all platform data
    import app.station.platforms as P
    orig = P.scheduled
    P.scheduled = lambda *a: None
    try:
        pred = predict_delay(stops(), s.journey.legs[0], s.events, [], None, s.start_clock)
        r = assess_connection(s.journey, 1, pred, s.events, s.start_clock, [])
    finally:
        P.scheduled = orig
    assert r.result == "CANNOT_ASSESS" and "ARRIVAL_PLATFORM_UNKNOWN" in r.missing


def test_scheduled_platforms_cap_the_result():
    r = _conn(observations=[])                 # only scheduled platforms (4 and 12)
    assert r.capped_by == ["ARRIVAL_PLATFORM_NOT_CONFIRMED", "DEPARTURE_PLATFORM_NOT_CONFIRMED"]
    assert r.result != "COMFORTABLE"


def test_platform_change_increases_walk_and_step_free_needs_increase_time():
    s = SC["station_connection"]
    base = _conn()
    moved = _conn(observations=[*s.platform_events, PlatformObservation(
        train_no="90821", station="NDLS", kind="DEPARTURE", platform=16, status="CONFIRMED",
        observed_at=s.start_clock - timedelta(minutes=1), source="TEST")])
    assert moved.route.distance_m > base.route.distance_m and moved.departure_platform.changed_from == 12
    acc = _conn(profile=PassengerProfile(step_free=True, senior=True))
    assert acc.route.stairs == 0 and acc.required_minutes["high"] > base.required_minutes["high"]
    assert acc.result in ("HIGH_RISK", "UNLIKELY", "NOT_FEASIBLE")


def test_delay_change_moves_the_result():
    s = SC["station_connection"]
    worse = [*s.events, s.events[-1].model_copy(update={"delay_minutes": 45, "observed_at": s.start_clock})]
    assert ["COMFORTABLE", "TIGHT", "HIGH_RISK", "UNLIKELY", "NOT_FEASIBLE"].index(_conn(events=worse).result) > \
        ["COMFORTABLE", "TIGHT", "HIGH_RISK", "UNLIKELY", "NOT_FEASIBLE"].index(_conn().result)


def test_connection_engine_uses_station_route_only_with_trusted_platforms():
    s = SC["station_connection"]
    need = trusted_transfer_need(s.journey, 1, s.platform_events, s.start_clock)
    assert need is not None and need[0] == _conn().required_minutes["high"]
    assert trusted_transfer_need(s.journey, 1, [], s.start_clock) is None
    d = c.get("/api/v1/journeys/station_connection/decision").json()
    assert d["header"]["transfer_needed_minutes"] == need[0]


# ---------- API: journey navigator, manual platform, demo platform change ----------

def test_journey_station_api_manual_location_and_platform_change():
    c.post("/api/demo/station_connection/reset")
    j = c.get("/api/v1/journeys/station_connection/station").json()
    cn = j["connection"]
    assert j["station"] == "NDLS" and cn["arrival_platform"]["platform"] == 4 and cn["departure_platform"]["platform"] == 12
    assert cn["location_source"] == "ARRIVAL_PLATFORM" and cn["prepare_to_alight"] is True
    manual = c.get("/api/v1/journeys/station_connection/station?at=SIDE_PAHARGANJ").json()["connection"]
    assert manual["location"] == "SIDE_PAHARGANJ" and manual["location_source"] == "MANUAL"
    assert c.get("/api/v1/journeys/station_connection/station?at=NOWHERE").json()["connection"]["result"] == "CANNOT_ASSESS"
    r = c.post("/api/demo/station_connection/platform", json={"train_no": "90821", "station": "NDLS", "kind": "DEPARTURE", "platform": 16})
    assert r.status_code == 200
    after = c.get("/api/v1/journeys/station_connection/station").json()["connection"]
    assert after["departure_platform"]["platform"] == 16 and after["departure_platform"]["changed_from"] == 12
    c.post("/api/demo/station_connection/reset")
    assert c.get("/api/v1/journeys/station_connection/station").json()["connection"]["departure_platform"]["platform"] == 12


def test_passenger_entered_platform_is_labelled_and_validated():
    c.post("/api/demo/bhopal_delhi_chandigarh/reset")
    ok = c.post("/api/v1/journeys/bhopal_delhi_chandigarh/station/platform", json={"train_no": "90801", "kind": "DEPARTURE", "platform": 9})
    assert ok.json()["source"] == "PASSENGER_FROM_STATION_BOARD"
    v = c.get("/api/v1/journeys/bhopal_delhi_chandigarh/station").json()["connection"]["departure_platform"]
    assert v["platform"] == 9 and v["status"] == "REPORTED" and v["changed_from"] == 1
    assert c.post("/api/v1/journeys/bhopal_delhi_chandigarh/station/platform", json={"train_no": "90801", "kind": "DEPARTURE", "platform": 25}).status_code == 422
    assert c.post("/api/v1/journeys/bhopal_delhi_chandigarh/station/platform", json={"train_no": "12345", "kind": "DEPARTURE", "platform": 3}).status_code == 422
    c.post("/api/demo/bhopal_delhi_chandigarh/reset")


def test_live_platform_unavailable_message_when_nothing_is_known():
    j = c.get("/api/v1/journeys/normal_journey/station").json()
    assert j["arrival_platform"]["status"] == "UNKNOWN" and j["station_summary"] is None
    assert j["arrival_platform"]["message"] == "LIVE_PLATFORM_UNAVAILABLE_CHECK_BOARDS"


# ---------- Copilot ----------

@pytest.mark.parametrize("q,intent,needle", [
    ("Which platform will my train arrive on?", "PLATFORM_ARRIVAL", "Platform 4 (reported, not confirmed"),
    ("Which platform is my next train departing from?", "PLATFORM_DEPARTURE", "Platform 12"),
    ("How do I reach Platform 12 from Platform 4?", "STATION_ROUTE", "min on foot"),
    ("Where is the nearest exit?", "STATION_FACILITY", "Nearest exit"),
    ("Where can I buy a ticket?", "STATION_FACILITY", "ticket counter"),
    ("Where is the luggage room?", "STATION_FACILITY", "Cloakroom"),
    ("Is there a lift on my route?", "STATION_ROUTE", "Lift working status is unknown"),
    ("Give me a route without stairs.", "STATION_ROUTE", "0 stair"),
    ("Which route is fastest?", "STATION_ROUTE", "Schematic map")])
def test_copilot_station_questions(q, intent, needle):
    c.post("/api/demo/station_connection/reset")
    r = c.post("/api/v1/journeys/station_connection/copilot", json={"message": q, "lang": "en"}).json()
    assert r["intent"] == intent and needle in r["answer"], r["answer"]
    assert all(t["ok"] for t in r["tool_calls"])


def test_copilot_hindi_and_unknown_platform():
    r = c.post("/api/v1/journeys/station_connection/copilot", json={"message": "मेरी अगली ट्रेन किस प्लेटफॉर्म से जाएगी?", "lang": "en"}).json()
    assert "प्लेटफॉर्म 12" in r["answer"]
    u = c.post("/api/v1/journeys/normal_journey/copilot", json={"message": "Which platform will my train arrive on?", "lang": "en"}).json()
    assert "Live platform information is currently unavailable" in u["answer"]
    loc = c.post("/api/v1/journeys/normal_journey/copilot", json={"message": "Where is the nearest exit?", "lang": "en"}).json()
    assert "map" in loc["answer"].lower()                       # no station map for Darbhanga: says so, no invented exit


def test_copilot_cannot_invent_a_platform():
    from app.copilot.copilot import run_copilot
    from app.copilot.tools import ToolContext, ToolCall, run_tool
    from app.station.service import journey_station_view
    s = SC["normal_journey"]
    ctx = ToolContext(journey=s.journey, events=s.events, now=s.start_clock, profile=PassengerProfile(),
                      station=lambda: journey_station_view(s.journey, s.events, s.start_clock, None, [], None))

    class FakeLLM:
        n = 0

        def complete_json(self, system, user):
            self.n += 1
            if self.n == 1:
                return {"intent": "PLATFORM_ARRIVAL", "calls": [{"tool": "get_platforms", "args": {}}]}
            return {"answer": "Your train arrives on Platform 7, confirmed."}
    r = run_copilot("which platform will my train arrive on", ctx, llm=FakeLLM())
    assert "Platform 7" not in r.answer and "unavailable" in r.answer
    assert run_tool(ctx, ToolCall(tool="station_route", args={"to_platform": 99})).error == "INVALID_ARGUMENTS"
    assert run_tool(ctx, ToolCall(tool="find_facility", args={"type": "HELIPAD"})).error == "INVALID_ARGUMENTS"


def test_platform_walk_never_says_towards_the_same_platform():
    from app.station import graph as g
    from app.station.route import route
    st = g.get("NDLS")
    r = route(st, "PF4", "PF16")
    for s in r.steps:
        if s.code == "WALK_PLATFORM":
            assert s.params.get("toward") is None or "16" not in str(s.params["toward"]) or 16 not in s.params["platforms"]
