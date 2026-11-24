"""The Copilot's tool ALLOWLIST.

Every tool:
- is READ-ONLY. There is deliberately no tool that books, cancels, files a TDR or changes any data.
- has a strict argument schema (`extra="forbid"`, ranges) that is validated before it runs.
- works only on the journey the server bound to the conversation. The model never chooses the journey id,
  so it cannot read another passenger's journey.
- returns structured data from the deterministic engines. Hypothetical what-ifs are computed on a copy of the
  events and never stored.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import Event, EventType, Journey
from app.graph.journey_graph import build_graph
from app.knowledge.grounded import grounded_answer
from app.offline.card import build_card
from app.plan.ranker import Priority
from app.plan.service import assess
from app.plan.transfer import PassengerProfile
from app.twin.twin import build_twin
from app.wallet.wallet import build_wallet
from app.whatif.simulator import simulate


@dataclass
class ToolContext:
    journey: Journey
    events: list[Event]
    now: datetime
    profile: PassengerProfile
    lang: str = "en"
    family: Callable[[], dict | None] | None = None      # bound by the server when the journey is in a group
    cache: dict = field(default_factory=dict)            # per-request memo so tools don't recompute
    # Bound by the server: builds the decision view (prediction, connection, recovery, money) for this journey.
    decide: Callable[[Priority], Any] | None = None


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LegArg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    leg: int | None = Field(default=None, ge=1, le=4)


class ExtraDelay(BaseModel):
    model_config = ConfigDict(extra="forbid")
    extra_delay_minutes: int = Field(default=0, ge=0, le=600)


class SimArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wait_minutes: int = Field(default=30, ge=5, le=720)
    delay_increase: int = Field(default=60, ge=1, le=600)
    priority: Priority = Priority.TIME


class RankArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    priority: Priority = Priority.TIME


class KnowledgeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=300)


def _assess(ctx: ToolContext, priority: Priority = Priority.TIME):
    key = ("assess", priority)
    if key not in ctx.cache:
        ctx.cache[key] = assess(ctx.journey, ctx.events, ctx.now, priority, ctx.profile)
    return ctx.cache[key]


def get_journey(ctx: ToolContext, a: NoArgs) -> dict:
    j = ctx.journey
    return {"journey_id": j.id, "pnr": j.pnr_label, "linked_pnr": j.linked_pnr,
            "legs": [{"leg": l.seq, "train_no": l.train_no, "train_name": l.train_name, "from": l.from_stn,
                      "to": l.to_stn, "scheduled_departure": l.scheduled_departure.isoformat(),
                      "scheduled_arrival": l.scheduled_arrival.isoformat(), "class": l.ticket.travel_class.value,
                      "status": l.ticket.status.value, "passengers": l.ticket.passengers} for l in j.legs]}


def get_train_status(ctx: ToolContext, a: LegArg) -> dict:
    twin = build_twin(ctx.journey, ctx.events, ctx.now, ctx.profile)
    legs = [l for l in twin.legs if a.leg is None or l.seq == a.leg]
    return {"status": twin.status.value, "legs": [
        {"leg": l.seq, "train_no": l.train_no, "state": l.state.value, "delay_minutes": l.delay_minutes,
         "expected_arrival": l.expected_arrival.isoformat(), "freshness": l.info.freshness.value,
         "last_update": l.info.last_update.isoformat() if l.info.last_update else None, "source": l.info.source}
        for l in legs]}


def detect_connection_risk(ctx: ToolContext, a: NoArgs) -> dict:
    g = build_graph(ctx.journey, ctx.events, ctx.now, ctx.profile)
    return {"status": g.status.value, "broken_from_leg": g.broken_from_leg,
            "trace": [t.model_dump() for t in g.trace],
            "transfers": [e.model_dump(mode="json") for e in g.edges if e.kind.value == "TRANSFER"]}


def calculate_transfer_buffer(ctx: ToolContext, a: ExtraDelay) -> dict:
    events = list(ctx.events)
    if a.extra_delay_minutes and len(ctx.journey.legs) > 1:
        from app.domain.models import live_state
        first = ctx.journey.legs[0]
        cur = live_state(first.train_no, events, ctx.now).delay_minutes
        events.append(Event(train_no=first.train_no, type=EventType.DELAY,
                            delay_minutes=cur + a.extra_delay_minutes, observed_at=ctx.now))   # hypothetical copy
    g = build_graph(ctx.journey, events, ctx.now, ctx.profile)
    return {"hypothetical": bool(a.extra_delay_minutes), "extra_delay_minutes": a.extra_delay_minutes,
            "transfers": [{"station": g.nodes[2 * i + 1].station, "gap_minutes": e.gap_minutes,
                           "required_minutes": e.required_minutes, "margin_minutes": e.margin_minutes,
                           "class": e.transfer_class.value if e.transfer_class else None}
                          for i, e in enumerate(x for x in g.edges if x.kind.value == "TRANSFER")]}


def evaluate_railway_rules(ctx: ToolContext, a: NoArgs) -> dict:
    r = _assess(ctx)
    w = build_wallet(ctx.journey, ctx.events, ctx.now, r.plans, [], [])
    return {"disclaimer": w.disclaimer, "items": [
        {"kind": i.kind, "leg": i.leg_seq, "stage": i.stage.value, "estimated_refund_paise": i.estimated_refund_paise,
         "if_approved": i.if_approved, "deadline": i.deadline.isoformat() if i.deadline else None,
         "deadline_unverified": i.deadline_unverified, "rule_ids": i.rule.rule_ids, "rule_set_id": i.rule.rule_set_id,
         "legal_status": i.rule.legal_status, "unresolved": i.rule.unresolved} for i in w.items]}


def get_applicable_deadlines(ctx: ToolContext, a: NoArgs) -> dict:
    r = _assess(ctx)
    rc = r.rights_clock
    return {"decide_by": rc.decision_deadline.isoformat() if rc.decision_deadline else None,
            "then": rc.then_plan_kind.value if rc.then_plan_kind else None,
            "plan_deadlines": [{"plan_kind": p.kind.value, "deadline": p.deadline.isoformat(),
                                "unverified": p.deadline_unverified} for p in r.plans if p.deadline]}


def simulate_journey_options(ctx: ToolContext, a: SimArgs) -> dict:
    res = simulate(ctx.journey, ctx.events, ctx.now, a.priority, ctx.profile, a.delay_increase, a.wait_minutes)
    return res.model_dump(mode="json")


def rank_recovery_plans(ctx: ToolContext, a: RankArgs) -> dict:
    r = _assess(ctx, a.priority)
    return {"situation": r.assessment.primary.type.value, "plans": [
        {"rank": p.rank, "plan_kind": p.kind.value, "travels": p.travels,
         "arrival": p.arrival.isoformat() if p.arrival else None, "money_back_paise": p.money_back_paise,
         "if_approved": p.money_back_if_approved, "deadline": p.deadline.isoformat() if p.deadline else None,
         "trains": [x.train_no for x in p.rides], "rule_ids": [i for d in p.decisions for i in d.rule_ids],
         "reasons": [x["key"] if isinstance(x, dict) else x.key for x in p.reasons]} for p in r.plans[:3]]}


def get_cached_journey_state(ctx: ToolContext, a: NoArgs) -> dict:
    r = _assess(ctx)
    twin = build_twin(ctx.journey, ctx.events, ctx.now, ctx.profile)
    w = build_wallet(ctx.journey, ctx.events, ctx.now, r.plans, [], [])
    return build_card(ctx.journey, twin, r.plans, w).model_dump(mode="json")


def search_railway_knowledge(ctx: ToolContext, a: KnowledgeArgs) -> dict:
    ans = grounded_answer(a.query, ctx.lang, as_of=ctx.now.date().isoformat())
    return ans.model_dump()


def get_family_options(ctx: ToolContext, a: NoArgs) -> dict:
    data = ctx.family() if ctx.family else None
    return data or {"available": False}


# ---------- PREDICT -> DECIDE -> RECOVER tools (read-only) ----------

def _decision(ctx: ToolContext, priority: Priority = Priority.TIME):
    key = ("decision", priority)
    if key not in ctx.cache:
        if ctx.decide is not None:
            ctx.cache[key] = ctx.decide(priority)
        else:
            from app.decide.decision import build_decision
            ctx.cache[key] = build_decision(ctx.journey, ctx.events, ctx.now, profile=ctx.profile, priority=priority)
    return ctx.cache[key]


def _opt(o) -> dict:
    first = next((l for l in o.legs if l.mode in ("TRAIN", "BUS")), o.legs[0])
    access = next((l for l in o.legs if l.mode == "ACCESS"), None)
    return {"trains": [l.train_no for l in o.legs if l.mode == "TRAIN"], "kind": o.kind.value,
            "from": first.from_stn, "departure": first.dep.isoformat(), "arrival": o.arrival.isoformat(),
            "leave_at": o.departure.isoformat(),
            "access_minutes": int((access.arr - access.dep).total_seconds() // 60) if access and o.legs[0] is access else None,
            "transfers": o.transfers, "result_type": o.result_type.value, "seat_availability": o.seat_availability,
            "fare_paise": o.fare_paise, "fare_status": o.fare_status, "rank": o.rank, "tatkal": o.tatkal,
            "unreserved": o.unreserved, "service": o.service}


def predict_delay_tool(ctx: ToolContext, a: NoArgs) -> dict:
    d = _decision(ctx)
    return {"prediction": d.prediction.model_dump(mode="json") if d.prediction else None,
            "connection": d.connection.model_dump(mode="json") if d.connection else None,
            "header": d.header}


def compare_decisions(ctx: ToolContext, a: RankArgs) -> dict:
    d = _decision(ctx, a.priority)
    return {"money": [m.model_dump(mode="json") for m in d.money], "claims": d.claims.model_dump(mode="json"),
            "cards": [{"key": c.key, "status": c.status, "reason": c.reason, "money": c.money,
                       "next_action": c.next_action, "outcome": c.outcome} for c in d.cards],
            "recommendation": d.recommendation, "header": d.header}


def find_alternatives(ctx: ToolContext, a: RankArgs) -> dict:
    r = _decision(ctx, a.priority).recovery
    return {"origin": r.origin, "destination": r.destination, "earliest": r.earliest_start.isoformat(),
            "options": [_opt(o) for o in r.options], "next_day": [_opt(o) for o in r.next_day],
            "empty_reason": r.empty_reason}


def check_unreserved(ctx: ToolContext, a: NoArgs) -> dict:
    r = _decision(ctx).recovery
    return {"options": [_opt(o) for o in r.unreserved], "rules": r.rules["unreserved"],
            "booked_train": ctx.journey.legs[-1].train_no}


def find_bus(ctx: ToolContext, a: NoArgs) -> dict:
    r = _decision(ctx).recovery
    return {"status": r.bus_status, "options": [_opt(o) | {"terminal": o.legs[1].from_stn} for o in r.buses]}


def next_day_options(ctx: ToolContext, a: NoArgs) -> dict:
    r = _decision(ctx).recovery
    return {"options": [_opt(o) for o in r.next_day], "rules": r.rules["tatkal"]}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args: type[BaseModel]
    fn: Callable[[ToolContext, Any], dict]


TOOLS: dict[str, ToolSpec] = {t.name: t for t in [
    ToolSpec("get_journey", "Booked legs of the current journey (masked PNR).", NoArgs, get_journey),
    ToolSpec("get_train_status", "Live (simulated) state, delay and data freshness of each leg.", LegArg, get_train_status),
    ToolSpec("detect_connection_risk", "Journey graph trace: delays, transfer margins, broken legs.", NoArgs,
             detect_connection_risk),
    ToolSpec("calculate_transfer_buffer", "Transfer margins, optionally with a hypothetical extra delay.", ExtraDelay,
             calculate_transfer_buffer),
    ToolSpec("evaluate_railway_rules", "Rights Wallet: refunds, stages, rule ids, legal status.", NoArgs,
             evaluate_railway_rules),
    ToolSpec("get_applicable_deadlines", "Decision deadline and plan deadlines.", NoArgs, get_applicable_deadlines),
    ToolSpec("simulate_journey_options", "What-if scenarios (wait, delay grows, cancel, alternatives).", SimArgs,
             simulate_journey_options),
    ToolSpec("rank_recovery_plans", "Top recovery plans ranked by a priority.", RankArgs, rank_recovery_plans),
    ToolSpec("get_cached_journey_state", "The offline snapshot card for this journey.", NoArgs, get_cached_journey_state),
    ToolSpec("search_railway_knowledge", "Cited passages from the railway rules knowledge base.", KnowledgeArgs,
             search_railway_knowledge),
    ToolSpec("get_family_options", "Together vs split options when the journey belongs to a family group.", NoArgs,
             get_family_options),
    ToolSpec("predict_delay", "Delay outlook (arrival range, trend, congestion, fog) and connection risk.", NoArgs,
             predict_delay_tool),
    ToolSpec("compare_decisions", "Cancel now vs wait vs claim vs alternative, money from the rules engine.", RankArgs,
             compare_decisions),
    ToolSpec("find_alternatives", "Other trains (direct, one change, nearby station) and next-day trains.", RankArgs,
             find_alternatives),
    ToolSpec("check_unreserved", "Trains with General coaches and the unreserved-ticket rules.", NoArgs, check_unreserved),
    ToolSpec("find_bus", "Bus options (demo samples only; none when no provider is connected).", NoArgs, find_bus),
    ToolSpec("next_day_options", "Next-day trains with Tatkal opening time (never guaranteed).", NoArgs, next_day_options),
]}


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str = Field(max_length=40)
    args: dict = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool: str
    args: dict
    ok: bool
    error: str | None = None
    data: dict | None = None


def run_tool(ctx: ToolContext, call: ToolCall) -> ToolResult:
    spec = TOOLS.get(call.tool)
    if spec is None:
        return ToolResult(tool=call.tool, args=call.args, ok=False, error="TOOL_NOT_ALLOWED")
    try:
        args = spec.args(**call.args)
    except Exception:
        return ToolResult(tool=call.tool, args=call.args, ok=False, error="INVALID_ARGUMENTS")
    try:
        return ToolResult(tool=call.tool, args=args.model_dump(mode="json"), ok=True, data=spec.fn(ctx, args))
    except ValueError as e:
        return ToolResult(tool=call.tool, args=args.model_dump(mode="json"), ok=False, error=f"TOOL_ERROR:{e}")


def tool_catalog() -> list[dict]:
    """What the LLM planner is shown: names, descriptions and argument schemas only."""
    return [{"name": t.name, "description": t.description, "args": t.args.model_json_schema()} for t in TOOLS.values()]
