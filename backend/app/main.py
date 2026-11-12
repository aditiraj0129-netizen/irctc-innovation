"""FastAPI app for Agla Kadam.

Run:  uvicorn app.main:app --reload
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import hmac
import logging
import os
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.core.clock import FixedClock, ensure_aware
from app.data.source import SimulatedSource, UnknownPNRError, load_scenarios
from app.data.timetable import STATIONS, TIMETABLE_LABEL
from app.domain.models import Event, EventSource, EventType
from app.explain.explainer import explain, llm_from_env
from app.assistant.assistant import answer as assistant_answer
from app.community.reports import CommunityService, ReportIn, seed as seed_reports
from app.detect.detector import SituationType
from app.family.family import group_view, load_groups
from app.insights.resilience import score_journey
from app.offline.card import build_card
from app.plan.counterfactual import recommend
from app.plan.ranker import Priority
from app.plan.service import assess, connections_for, registry
from app.plan.transfer import PassengerProfile
from app.rules.models import TicketStatus
from app.store import Store
from app.twin.twin import build_twin
from app.wallet.wallet import build_wallet, export_text, valid_transition
from app.whatif.simulator import simulate

logging.basicConfig(level=logging.INFO, format='{"t":"%(asctime)s","lvl":"%(levelname)s","msg":%(message)s}')
log = logging.getLogger("agla")

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "240"))
# Optional: when set, presenter/demo endpoints need the header X-Demo-Token with this value,
# so nobody else can change the demo on a public link. Never put the value in source code.
DEMO_TOKEN = os.getenv("DEMO_TOKEN", "")
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "microphone=(self), camera=(), geolocation=()",
}

app = FastAPI(title="Agla Kadam API", version="1.0.0",
              description="Disruption helper for booked train journeys. ALL railway data here is SIMULATED.")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
                   allow_methods=["*"], allow_headers=["*"])


# ---------- state (in memory; the demo needs no database) ----------

class State:
    def __init__(self):
        self.scenarios = load_scenarios()
        self.source = SimulatedSource(self.scenarios)
        self.clocks = {k: FixedClock(s.start_clock) for k, s in self.scenarios.items()}
        self.store = Store()
        self.community = CommunityService(self.store)
        self.groups = load_groups()
        self.llm = llm_from_env()
        for k, sc in self.scenarios.items():
            seed_reports(self.community, k, sc.start_clock)


S = State()
_hits: dict[str, deque] = defaultdict(deque)


def client_ip(request: Request) -> str:
    """The caller's address. Behind Render's proxy, uvicorn runs with --proxy-headers
    (see Dockerfile), so this is the real user's address, not the proxy's."""
    return request.client.host if request.client else "?"


@app.middleware("http")
async def log_and_limit(request: Request, call_next):
    rid = uuid.uuid4().hex[:8]
    ip = client_ip(request)
    now = time.monotonic()
    if len(_hits) > 5000:                      # forget addresses that have been quiet for a minute
        for k in [k for k, v in _hits.items() if not v or now - v[-1] > 60]:
            del _hits[k]
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if request.url.path.startswith("/api/") and len(q) >= RATE_LIMIT_PER_MIN:
        return JSONResponse({"detail": "Too many requests"}, status_code=429, headers=SECURITY_HEADERS)
    q.append(now)
    if request.url.path.startswith("/api/demo/") and DEMO_TOKEN and not hmac.compare_digest(
            request.headers.get("X-Demo-Token", ""), DEMO_TOKEN):
        return JSONResponse({"detail": "Presenter token required"}, status_code=403, headers=SECURITY_HEADERS)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception('"unhandled error rid=%s"', rid)
        return JSONResponse({"detail": "Something went wrong. Please use the official channel (RailOne / 139).",
                             "request_id": rid}, status_code=500)
    log.info('"%s %s %s %.0fms rid=%s"', request.method, request.url.path, response.status_code,
             (time.perf_counter() - start) * 1000, rid)
    response.headers["X-Request-ID"] = rid
    for k, v in SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    return response


def _scenario(jid: str):
    if jid not in S.scenarios:
        raise HTTPException(404, "Journey not found")
    return S.scenarios[jid]


def _stn(code: str) -> dict:
    return {"code": code, **STATIONS.get(code, {"en": code, "hi": code})}


def journey_out(jid: str) -> dict:
    sc = _scenario(jid)
    j = sc.journey
    return {
        "id": j.id, "pnr_label": j.pnr_label, "title": sc.title, "linked_pnr": j.linked_pnr, "group": sc.group,
        "min_transfer_minutes": j.min_transfer_minutes,
        "legs": [{"seq": l.seq, "train_no": l.train_no, "train_name": l.train_name,
                  "from": _stn(l.from_stn), "to": _stn(l.to_stn),
                  "scheduled_departure": l.scheduled_departure, "scheduled_arrival": l.scheduled_arrival,
                  "class": l.ticket.travel_class.value, "status": l.ticket.status.value,
                  "quota": l.ticket.quota.value, "category": l.ticket.train_category.value,
                  "passengers": l.ticket.passengers, "fare_paise": l.ticket.total_fare_paise}
                 for l in j.legs],
    }


class Preferences(BaseModel):
    profile: PassengerProfile = Field(default_factory=PassengerProfile)
    priority: Priority = Priority.TIME


def prefs(jid: str) -> Preferences:
    d = S.store.get_prefs(jid)
    return Preferences(**d) if d else Preferences()


def ctx(jid: str):
    """Everything every feature needs for one journey, from ONE place (no duplicated logic)."""
    sc = _scenario(jid)
    return sc.journey, S.source.events_for(jid), S.clocks[jid].now(), prefs(jid).profile


# ---------- passenger API ----------

class AddJourney(BaseModel):
    pnr: str = Field(pattern=r"^\d{10}$")


@app.get("/api/health")
def health():
    return {"ok": True, "data": "SIMULATED", "llm": S.llm is not None, "rules_version": registry().data.version}


@app.get("/api/scenarios")
def scenarios():
    return [{"id": s.id, "pnr": s.pnr, "title": s.title, "group": s.group} for s in S.scenarios.values()]


@app.post("/api/journeys")
def add_journey(body: AddJourney):
    try:
        sc = S.source.scenario_for_pnr(body.pnr)
    except UnknownPNRError:
        raise HTTPException(404, "PNR_NOT_IN_DEMO_DATA")
    return journey_out(sc.id)


@app.get("/api/journeys/{jid}")
def get_journey(jid: str):
    return journey_out(jid)


@app.get("/api/journeys/{jid}/assessment")
def get_assessment(jid: str, priority: Priority = Priority.TIME, lang: str = Query("en", pattern="^(en|hi)$")):
    journey, events, now, profile = ctx(jid)
    r = assess(journey, events, now, priority, profile)
    rec = None
    if r.assessment.primary.type not in (SituationType.STALE_DATA, SituationType.JOURNEY_OVER):
        rec = recommend(r.plans, priority, simulate(journey, events, now, priority, profile))
    plans = []
    for p in r.plans:
        e = explain(p, lang, S.llm)
        plans.append({**p.model_dump(mode="json"), "explanation": e.model_dump()})
    return {
        "journey": journey_out(jid), "now": now, "priority": priority.value, "lang": lang,
        "data_label": "SIMULATED", "timetable_label": TIMETABLE_LABEL,
        "situation": r.assessment.primary.model_dump(mode="json"),
        "situations": [s.model_dump(mode="json") for s in r.assessment.situations],
        "live": {k: v.model_dump(mode="json") for k, v in r.assessment.live.items()},
        "plans": plans, "rights_clock": r.rights_clock.model_dump(mode="json"),
        "recommendation": rec.model_dump(mode="json") if rec else None,
        "profile": profile.model_dump(),
        "actions": S.store.actions(jid),
    }


class ActionIn(BaseModel):
    plan_id: str = Field(min_length=1, max_length=64)
    plan_kind: str = Field(min_length=1, max_length=64)


@app.post("/api/journeys/{jid}/actions")
def record_action(jid: str, body: ActionIn):
    _scenario(jid)
    return S.store.add_action(jid, body.plan_id, body.plan_kind, S.clocks[jid].now().isoformat())


@app.get("/api/rules")
def rules():
    d = registry().data
    return {"version": d.version,
            "rule_sets": [r.model_dump(mode="json", include={"id", "name", "legal_status", "effective_from",
                                                              "effective_to", "source", "train_categories"})
                          for r in d.rule_sets],
            "special_rules": [r.model_dump(mode="json", include={"id", "name", "legal_status", "source",
                                                                  "needs_verification"}) for r in d.special_rules]}


# ---------- upgrade: digital twin, what-if, wallet, resilience, offline, assistant, community ----------

@app.get("/api/journeys/{jid}/twin")
def get_twin(jid: str):
    journey, events, now, profile = ctx(jid)
    return build_twin(journey, events, now, profile).model_dump(mode="json")


@app.get("/api/journeys/{jid}/whatif")
def get_whatif(jid: str, priority: Priority = Priority.TIME, delay_increase: int = Query(60, ge=1, le=600),
               wait_minutes: int = Query(30, ge=5, le=720)):
    journey, events, now, profile = ctx(jid)
    return simulate(journey, events, now, priority, profile, delay_increase, wait_minutes).model_dump(mode="json")


def _wallet(jid: str):
    journey, events, now, profile = ctx(jid)
    plans = assess(journey, events, now, Priority.TIME, profile).plans
    return build_wallet(journey, events, now, plans, S.store.claims(jid), S.store.actions(jid))


@app.get("/api/journeys/{jid}/wallet")
def get_wallet(jid: str):
    return _wallet(jid).model_dump(mode="json")


class ClaimIn(BaseModel):
    item_id: str = Field(min_length=3, max_length=64)
    status: str = Field(pattern="^(FILED|APPROVED|RECEIVED|REJECTED)$")


@app.post("/api/journeys/{jid}/wallet/claims")
def post_claim(jid: str, body: ClaimIn):
    w = _wallet(jid)
    if not valid_transition(w, body.item_id, body.status):
        raise HTTPException(422, "INVALID_CLAIM_STEP")
    return S.store.add_claim(jid, body.item_id, body.status, S.clocks[jid].now().isoformat())


@app.get("/api/journeys/{jid}/wallet/export", response_class=PlainTextResponse)
def export_wallet(jid: str):
    return PlainTextResponse(export_text(_wallet(jid)),
                             headers={"Content-Disposition": f'attachment; filename="agla-kadam-{jid}-rights.txt"'})


@app.get("/api/journeys/{jid}/preferences")
def get_prefs(jid: str):
    _scenario(jid)
    return prefs(jid).model_dump()


@app.put("/api/journeys/{jid}/preferences")
def put_prefs(jid: str, body: Preferences):
    _scenario(jid)
    S.store.set_prefs(jid, body.model_dump())
    return body.model_dump()


@app.get("/api/journeys/{jid}/resilience")
def get_resilience(jid: str):
    journey, events, now, profile = ctx(jid)
    twin = build_twin(journey, events, now, profile)
    return score_journey(journey, twin, connections_for(journey), profile).model_dump(mode="json")


@app.get("/api/journeys/{jid}/offline-card")
def get_offline_card(jid: str):
    journey, events, now, profile = ctx(jid)
    plans = assess(journey, events, now, Priority.TIME, profile).plans
    twin = build_twin(journey, events, now, profile)
    wallet = build_wallet(journey, events, now, plans, S.store.claims(jid), S.store.actions(jid))
    return build_card(journey, twin, plans, wallet).model_dump(mode="json")


class AskIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    lang: str = Field("en", pattern="^(en|hi)$")


@app.post("/api/journeys/{jid}/assistant")
def ask(jid: str, body: AskIn):
    journey, events, now, profile = ctx(jid)
    r = assess(journey, events, now, Priority.TIME, profile)
    wallet = build_wallet(journey, events, now, r.plans, S.store.claims(jid), S.store.actions(jid))
    twin = build_twin(journey, events, now, profile)
    stale = r.assessment.primary.type == SituationType.STALE_DATA
    return assistant_answer(body.text, body.lang, r.plans, wallet, twin, stale, S.llm).model_dump(mode="json")


@app.get("/api/journeys/{jid}/community/reports")
def list_reports(jid: str):
    _scenario(jid)
    return [r.model_dump(mode="json") for r in S.community.active(jid, S.clocks[jid].now())]


@app.post("/api/journeys/{jid}/community/reports")
def add_report(jid: str, body: ReportIn, request: Request):
    _scenario(jid)
    # One caller (network address) = one reporter. We don't trust any client-chosen header for this,
    # because it could be changed on every request to fake "many reporters".
    who = client_ip(request)
    return S.community.submit(jid, body, who, S.clocks[jid].now()).model_dump(mode="json")


@app.get("/api/groups")
def list_groups():
    return [{"id": g.id, "name": g.name, "members": len(g.members)} for g in S.groups.values()]


@app.get("/api/groups/{gid}")
def get_group(gid: str, priority: Priority = Priority.FAMILY):
    if gid not in S.groups:
        raise HTTPException(404, "Group not found")
    g = S.groups[gid]
    jids = list(dict.fromkeys(m.journey for m in g.members))
    now = S.clocks[jids[0]].now()
    return group_view(g, {j: S.scenarios[j].journey for j in jids}, {j: S.source.events_for(j) for j in jids},
                      now, priority).model_dump(mode="json")


# ---------- presenter (demo only) ----------

class ClockIn(BaseModel):
    at: datetime | None = None
    advance_minutes: int | None = Field(default=None, ge=-24 * 60, le=24 * 60)


class EventIn(BaseModel):
    train_no: str = Field(pattern=r"^\d{5}$")
    type: EventType
    delay_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    chart_status: TicketStatus | None = None


def _demo_only():
    if not DEMO_MODE:
        raise HTTPException(403, "Demo endpoints are disabled")


@app.post("/api/demo/{jid}/reset")
def demo_reset(jid: str):
    _demo_only()
    sc = _scenario(jid)
    S.source.reset(jid)
    S.clocks[jid].set(sc.start_clock)
    S.store.clear_journey(jid)
    seed_reports(S.community, jid, sc.start_clock)
    return {"ok": True, "now": S.clocks[jid].now()}


@app.post("/api/demo/groups/{gid}/reset")
def demo_group_reset(gid: str):
    _demo_only()
    if gid not in S.groups:
        raise HTTPException(404, "Group not found")
    for j in dict.fromkeys(m.journey for m in S.groups[gid].members):
        demo_reset(j)
    return {"ok": True}


@app.post("/api/demo/{jid}/clock")
def demo_clock(jid: str, body: ClockIn):
    _demo_only()
    _scenario(jid)
    if body.at is not None:
        S.clocks[jid].set(ensure_aware(body.at, "at"))
    elif body.advance_minutes is not None:
        S.clocks[jid].advance(minutes=body.advance_minutes)
    return {"now": S.clocks[jid].now()}


@app.post("/api/demo/{jid}/events")
def demo_event(jid: str, body: EventIn):
    _demo_only()
    sc = _scenario(jid)
    if body.train_no not in {l.train_no for l in sc.journey.legs}:
        raise HTTPException(422, "Train is not part of this journey")
    if body.type == EventType.DELAY and body.delay_minutes is None:
        raise HTTPException(422, "delay_minutes is required for DELAY")
    ev = Event(train_no=body.train_no, type=body.type, delay_minutes=body.delay_minutes,
               chart_status=body.chart_status, observed_at=S.clocks[jid].now(), source=EventSource.SIMULATED)
    S.source.add_event(jid, ev)
    return ev.model_dump(mode="json")


# ---------- serve the built frontend (single deployment) ----------

DIST = Path(os.getenv("FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist"))
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    DIST_ROOT = DIST.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        # Only serve files that really live inside the built frontend folder.
        # Anything else (including "../" tricks) gets the app's index page, never another file.
        f = (DIST_ROOT / path).resolve()
        inside = f == DIST_ROOT or DIST_ROOT in f.parents
        return FileResponse(f if path and inside and f.is_file() else DIST_ROOT / "index.html")
