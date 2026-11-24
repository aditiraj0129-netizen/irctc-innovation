"""Journey Recovery Graph.

An explicit, testable model of a connected journey:

    BPL --[ride 90701]--> NDLS --[transfer, needs 30 min]--> NDLS --[ride 90801]--> CDG
     |                     |                                   |
   events              deadlines / rules                   events

Nodes are timed stops (a departure or an arrival of one leg). Edges are RIDES (inside one train) and
TRANSFERS (between two trains, with the time this passenger needs). Every node carries its scheduled time,
its expected time from the latest events, and how fresh that information is.

`propagate()` walks the edges in order and records a human-readable causal TRACE:
"90701 is 95 min late -> arrives NDLS 08:15 -> the 07:40 departure needs arrival by 07:10 -> connection
broken -> leg 2 likely missed". The graph is rebuilt from events every time (no hidden state), so it always
agrees with the twin, the detector and the planner, and it updates the moment an event changes.

No graph database is needed: a journey has a handful of nodes, and the edges come from the itinerary.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field

from app.core.clock import ensure_aware
from app.domain.models import Event, Journey
from app.plan.transfer import PassengerProfile, TransferClass
from app.twin.twin import Freshness, JourneyStatus, LegState, build_twin


class NodeKind(str, Enum):
    DEPART = "DEPART"
    ARRIVE = "ARRIVE"


class EdgeKind(str, Enum):
    RIDE = "RIDE"
    TRANSFER = "TRANSFER"


class NodeState(str, Enum):
    OK = "OK"
    DELAYED = "DELAYED"
    AT_RISK = "AT_RISK"
    BROKEN = "BROKEN"          # cannot happen as booked
    DONE = "DONE"              # already happened


class GraphNode(BaseModel):
    id: str                    # e.g. "L1:DEP"
    kind: NodeKind
    leg_seq: int
    station: str
    train_no: str
    scheduled: datetime
    expected: datetime
    delay_minutes: int
    state: NodeState
    freshness: Freshness
    last_update: datetime | None


class GraphEdge(BaseModel):
    id: str
    kind: EdgeKind
    source: str
    target: str
    # transfers only
    required_minutes: int | None = None
    gap_minutes: int | None = None
    margin_minutes: int | None = None
    transfer_class: TransferClass | None = None
    state: NodeState = NodeState.OK


class TraceStep(BaseModel):
    """One step of cause and effect, as codes + numbers (the UI turns these into words)."""
    code: str
    node: str | None = None
    edge: str | None = None
    data: dict = Field(default_factory=dict)


class JourneyGraph(BaseModel):
    journey_id: str
    now: datetime
    status: JourneyStatus
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    trace: list[TraceStep]
    broken_from_leg: int | None            # first leg that can't run as booked
    data_label: str = "SIMULATED"


def _node_state(leg_state: LegState, delay: int, is_arrival_done: bool) -> NodeState:
    if is_arrival_done:
        return NodeState.DONE
    if leg_state in (LegState.CANCELLED, LegState.LIKELY_MISSED, LegState.WAITLISTED):
        return NodeState.BROKEN
    if leg_state == LegState.AT_RISK:
        return NodeState.AT_RISK
    return NodeState.DELAYED if delay > 0 else NodeState.OK


def build_graph(journey: Journey, events: list[Event], now: datetime,
                profile: PassengerProfile | None = None) -> JourneyGraph:
    now = ensure_aware(now, "now")
    twin = build_twin(journey, events, now, profile)
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    for leg in twin.legs:
        dep_done = now >= leg.expected_departure and leg.state in (LegState.IN_TRANSIT, LegState.ARRIVED)
        arr_done = leg.state == LegState.ARRIVED
        common = dict(leg_seq=leg.seq, train_no=leg.train_no, delay_minutes=leg.delay_minutes,
                      freshness=leg.info.freshness, last_update=leg.info.last_update)
        nodes.append(GraphNode(id=f"L{leg.seq}:DEP", kind=NodeKind.DEPART, station=leg.from_stn,
                               scheduled=leg.scheduled_departure, expected=leg.expected_departure,
                               state=_node_state(leg.state, leg.delay_minutes, dep_done), **common))
        nodes.append(GraphNode(id=f"L{leg.seq}:ARR", kind=NodeKind.ARRIVE, station=leg.to_stn,
                               scheduled=leg.scheduled_arrival, expected=leg.expected_arrival,
                               state=_node_state(leg.state, leg.delay_minutes, arr_done), **common))
        edges.append(GraphEdge(id=f"L{leg.seq}:RIDE", kind=EdgeKind.RIDE, source=f"L{leg.seq}:DEP",
                               target=f"L{leg.seq}:ARR", state=nodes[-1].state))
    for tr in twin.transfers:
        c = tr.check
        st = {TransferClass.NOT_FEASIBLE: NodeState.BROKEN, TransferClass.HIGH_RISK: NodeState.AT_RISK}.get(
            c.cls, NodeState.OK)
        edges.append(GraphEdge(id=f"T{tr.from_seq}-{tr.to_seq}", kind=EdgeKind.TRANSFER,
                               source=f"L{tr.from_seq}:ARR", target=f"L{tr.to_seq}:DEP",
                               required_minutes=c.required_minutes, gap_minutes=c.gap_minutes,
                               margin_minutes=c.margin_minutes, transfer_class=c.cls, state=st))
    trace, broken_from = propagate(twin)
    return JourneyGraph(journey_id=journey.id, now=now, status=twin.status, nodes=nodes, edges=edges,
                        trace=trace, broken_from_leg=broken_from)


def propagate(twin) -> tuple[list[TraceStep], int | None]:
    """Explain, step by step and in order, how events move through the journey."""
    trace: list[TraceStep] = []
    broken_from: int | None = None
    upstream_broken = False
    for i, leg in enumerate(twin.legs):
        if leg.info.freshness == Freshness.STALE:
            trace.append(TraceStep(code="DATA_STALE", node=f"L{leg.seq}:ARR",
                                   data={"train": leg.train_no, "age_minutes": leg.info.age_minutes}))
        if leg.state == LegState.CANCELLED:
            trace.append(TraceStep(code="TRAIN_CANCELLED", node=f"L{leg.seq}:DEP", data={"train": leg.train_no}))
            broken_from = broken_from or leg.seq
            upstream_broken = True
        elif leg.state == LegState.WAITLISTED:
            trace.append(TraceStep(code="TICKET_NOT_CONFIRMED", node=f"L{leg.seq}:DEP", data={"train": leg.train_no}))
            broken_from = broken_from or leg.seq
            upstream_broken = True
        elif leg.delay_minutes > 0:
            trace.append(TraceStep(code="TRAIN_DELAYED", node=f"L{leg.seq}:ARR",
                                   data={"train": leg.train_no, "delay_minutes": leg.delay_minutes,
                                         "station": leg.to_stn, "expected_arrival": leg.expected_arrival.isoformat()}))
        if i + 1 < len(twin.legs):
            tr = twin.transfers[i]
            c = tr.check
            edge = f"T{tr.from_seq}-{tr.to_seq}"
            nxt = twin.legs[i + 1]
            if upstream_broken:
                trace.append(TraceStep(code="DOWNSTREAM_LEG_UNREACHABLE", edge=edge,
                                       data={"train": nxt.train_no, "leg": nxt.seq}))
                continue
            if nxt.state in (LegState.ARRIVED, LegState.IN_TRANSIT):
                continue
            base = {"station": c.station, "gap_minutes": c.gap_minutes, "required_minutes": c.required_minutes,
                    "margin_minutes": c.margin_minutes, "must_arrive_by": tr.latest_safe_arrival.isoformat(),
                    "next_train": nxt.train_no, "next_departure": nxt.expected_departure.isoformat()}
            if c.cls == TransferClass.NOT_FEASIBLE:
                trace.append(TraceStep(code="CONNECTION_BROKEN", edge=edge, data=base))
                trace.append(TraceStep(code="LEG_LIKELY_MISSED", node=f"L{nxt.seq}:DEP",
                                       data={"train": nxt.train_no, "leg": nxt.seq}))
                broken_from = broken_from or nxt.seq
                upstream_broken = True
            elif c.cls == TransferClass.HIGH_RISK:
                trace.append(TraceStep(code="CONNECTION_AT_RISK", edge=edge, data=base))
            elif c.cls == TransferClass.TIGHT:
                trace.append(TraceStep(code="CONNECTION_TIGHT", edge=edge, data=base))
            elif any(l.delay_minutes > 0 for l in twin.legs[: i + 1]):
                trace.append(TraceStep(code="CONNECTION_STILL_OK", edge=edge, data=base))
    if not trace:
        trace.append(TraceStep(code="ALL_ON_SCHEDULE"))
    elif twin.status == JourneyStatus.BROKEN or broken_from:
        trace.append(TraceStep(code="RECOVERY_NEEDED", data={"from_leg": broken_from}))
    return trace, broken_from


def minutes_between(a: datetime, b: datetime) -> int:
    return int((b - a) / timedelta(minutes=1))
