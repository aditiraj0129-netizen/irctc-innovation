"""FastAPI app for Agla Kadam.

Run:  uvicorn app.main:app --reload
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.core.clock import FixedClock, ensure_aware
from app.data.source import SimulatedSource, UnknownPNRError, load_scenarios
from app.data.timetable import STATIONS, TIMETABLE_LABEL
from app.domain.models import Event, EventSource, EventType
from app.explain.explainer import explain, llm_from_env
from app.plan.ranker import Priority
from app.plan.service import assess, registry
from app.rules.models import TicketStatus

logging.basicConfig(level=logging.INFO, format='{"t":"%(asctime)s","lvl":"%(levelname)s","msg":%(message)s}')
log = logging.getLogger("agla")

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "240"))

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
        self.actions: dict[str, list[dict]] = defaultdict(list)
        self.llm = llm_from_env()


S = State()
_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def log_and_limit(request: Request, call_next):
    rid = uuid.uuid4().hex[:8]
    ip = request.client.host if request.client else "?"
    q = _hits[ip]
    now = time.monotonic()
    while q and now - q[0] > 60:
        q.popleft()
    if request.url.path.startswith("/api/") and len(q) >= RATE_LIMIT_PER_MIN:
        return JSONResponse({"detail": "Too many requests"}, status_code=429)
    q.append(now)
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
        "id": j.id, "pnr_label": j.pnr_label, "title": sc.title, "linked_pnr": j.linked_pnr,
        "min_transfer_minutes": j.min_transfer_minutes,
        "legs": [{"seq": l.seq, "train_no": l.train_no, "train_name": l.train_name,
                  "from": _stn(l.from_stn), "to": _stn(l.to_stn),
                  "scheduled_departure": l.scheduled_departure, "scheduled_arrival": l.scheduled_arrival,
                  "class": l.ticket.travel_class.value, "status": l.ticket.status.value,
                  "quota": l.ticket.quota.value, "category": l.ticket.train_category.value,
                  "passengers": l.ticket.passengers, "fare_paise": l.ticket.total_fare_paise}
                 for l in j.legs],
    }


# ---------- passenger API ----------

class AddJourney(BaseModel):
    pnr: str = Field(pattern=r"^\d{10}$")


@app.get("/api/health")
def health():
    return {"ok": True, "data": "SIMULATED", "llm": S.llm is not None, "rules_version": registry().data.version}


@app.get("/api/scenarios")
def scenarios():
    return [{"id": s.id, "pnr": s.pnr, "title": s.title} for s in S.scenarios.values()]


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
    sc = _scenario(jid)
    now = S.clocks[jid].now()
    r = assess(sc.journey, S.source.events_for(jid), now, priority)
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
        "actions": S.actions[jid],
    }


class ActionIn(BaseModel):
    plan_id: str = Field(min_length=1, max_length=64)
    plan_kind: str = Field(min_length=1, max_length=64)


@app.post("/api/journeys/{jid}/actions")
def record_action(jid: str, body: ActionIn):
    _scenario(jid)
    entry = {"plan_id": body.plan_id, "plan_kind": body.plan_kind, "at": S.clocks[jid].now().isoformat()}
    S.actions[jid].append(entry)
    return entry


@app.get("/api/rules")
def rules():
    d = registry().data
    return {"version": d.version,
            "rule_sets": [r.model_dump(mode="json", include={"id", "name", "legal_status", "effective_from",
                                                              "effective_to", "source", "train_categories"})
                          for r in d.rule_sets],
            "special_rules": [r.model_dump(mode="json", include={"id", "name", "legal_status", "source",
                                                                  "needs_verification"}) for r in d.special_rules]}


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
    S.actions[jid].clear()
    return {"ok": True, "now": S.clocks[jid].now()}


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

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
