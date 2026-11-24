"""Station Route Engine: Dijkstra over the station graph, with passenger profiles.

Profiles
  FASTEST         - shortest expected time; may use stairs, escalators and lifts
  STEP_FREE       - never uses stairs or escalators (lifts and level paths only)
  FEWER_LEVELS    - like FASTEST, but each change of level costs 10 minutes extra, so it avoids overbridges
                    whenever a level path exists

Walking-time RANGE, not a single number (documented assumptions, docs/STATION_NAVIGATION_ARCHITECTURE.md):
  walking        : 1.3 m/s (quiet) to 0.8 m/s (crowded); slow walker 0.8 to 0.5 m/s
  stairs (1 level): +30 to +75 s (slow walker +60 to +150 s), plus about 15 m
  escalator      : +30 to +60 s (direction not verified)
  lift           : +45 to +240 s (waiting time unknown; the lift's working status is ALWAYS unknown)
"""
from __future__ import annotations

import heapq
from enum import Enum

from pydantic import BaseModel, Field

from app.station.graph import Edge, EdgeKind, NodeKind, Station, worst

SPEED = {"normal": (1.3, 0.8), "slow": (0.8, 0.5)}
FIXED = {EdgeKind.STAIRS: {"normal": (30, 75), "slow": (60, 150)}, EdgeKind.ESCALATOR: {"normal": (30, 60), "slow": (40, 80)},
         EdgeKind.LIFT: {"normal": (45, 240), "slow": (45, 240)}}
LEVEL_PENALTY_S = 600


class Profile(str, Enum):
    FASTEST = "fastest"
    STEP_FREE = "step_free"
    FEWER_LEVELS = "fewer_levels"


class RouteError(ValueError):
    pass


class Step(BaseModel):
    code: str                      # START | WALK_PLATFORM | WALK_CONCOURSE | WALK_LINK | UP | DOWN | CROSS_FOB | ARRIVE
    params: dict = Field(default_factory=dict)


class Route(BaseModel):
    station: str
    profile: Profile
    walking_speed: str
    found: bool
    reason: str | None = None
    start: str
    end: str
    start_label: dict | None = None
    end_label: dict | None = None
    path: list[str] = Field(default_factory=list)
    distance_m: int = 0
    minutes_low: int = 0
    minutes_high: int = 0
    stairs: int = 0
    lifts: int = 0
    escalators: int = 0
    level_changes: int = 0
    steps: list[Step] = Field(default_factory=list)
    verification: str = "ILLUSTRATIVE"
    confidence: str = "SCHEMATIC_DEMO"      # VERIFIED_ROUTE would need surveyed station data (none yet)
    warnings: list[str] = Field(default_factory=list)


def _usable(e: Edge, profile: Profile) -> bool:
    if profile == Profile.STEP_FREE and not e.step_free:
        return False
    return True


def _secs(e: Edge, speed: str) -> tuple[float, float]:
    fast, slow = SPEED[speed]
    lo, hi = e.distance_m / fast, e.distance_m / slow
    if e.kind in FIXED:
        a, b = FIXED[e.kind][speed]
        lo, hi = lo + a, hi + b
    return lo, hi


def _weight(e: Edge, profile: Profile, speed: str) -> float:
    lo, hi = _secs(e, speed)
    w = (lo + hi) / 2
    if profile == Profile.FEWER_LEVELS and e.level_change:
        w += LEVEL_PENALTY_S
    return w


def _adj(st: Station) -> dict[str, list[tuple[str, Edge, int]]]:
    adj: dict[str, list] = {n: [] for n in st.nodes}
    for e in st.edges:
        adj[e.a].append((e.b, e, e.level_change))
        adj[e.b].append((e.a, e, -e.level_change))
    return adj


def route(st: Station, start: str, end: str, profile: Profile = Profile.FASTEST, speed: str = "normal") -> Route:
    if start not in st.nodes or end not in st.nodes:
        raise RouteError("UNKNOWN_LOCATION")
    if speed not in SPEED:
        raise RouteError("BAD_SPEED")
    base = dict(station=st.code, profile=profile, walking_speed=speed, start=start, end=end,
                start_label=st.nodes[start].label, end_label=st.nodes[end].label)
    adj = _adj(st)
    dist, prev = {start: 0.0}, {}
    pq = [(0.0, start)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == end:
            break
        if d > dist.get(u, float("inf")):
            continue
        for v, e, lc in adj[u]:
            if not _usable(e, profile):
                continue
            nd = d + _weight(e, profile, speed)
            if nd < dist.get(v, float("inf")):
                dist[v], prev[v] = nd, (u, e, lc)
                heapq.heappush(pq, (nd, v))
    if end not in dist:
        return Route(**base, found=False, reason="NO_STEP_FREE_ROUTE" if profile == Profile.STEP_FREE else "NO_ROUTE",
                     warnings=["MAP_SCHEMATIC"])
    seq: list[tuple[str, str, Edge, int]] = []
    v = end
    while v != start:
        u, e, lc = prev[v]
        seq.append((u, v, e, lc))
        v = u
    seq.reverse()
    lo = hi = dist_m = 0.0
    ver = "VERIFIED_PUBLIC"
    r = Route(**base, found=True)
    for u, v, e, lc in seq:
        a, b = _secs(e, speed)
        lo, hi, dist_m = lo + a, hi + b, dist_m + e.distance_m
        ver = worst(ver, e.verification)
        r.stairs += e.kind == EdgeKind.STAIRS
        r.lifts += e.kind == EdgeKind.LIFT
        r.escalators += e.kind == EdgeKind.ESCALATOR
        r.level_changes += abs(lc)
    r.path = [start] + [v for _, v, _, _ in seq]
    r.distance_m, r.minutes_low, r.minutes_high = round(dist_m), max(1, round(lo / 60)), max(1, round(hi / 60 + 0.49))
    r.verification = ver
    r.confidence = "SCHEMATIC_DEMO" if st.map_kind == "SCHEMATIC" or ver == "ILLUSTRATIVE" else "REPORTED_ROUTE"
    r.warnings = ["MAP_SCHEMATIC"] + (["LIFT_STATUS_UNKNOWN"] if r.lifts else []) + \
        (["ESCALATOR_DIRECTION_NOT_VERIFIED"] if r.escalators else []) + ["CROWDS_CHANGE_WALKING_TIME"]
    r.steps = _steps(st, seq)
    return r


def _steps(st: Station, seq: list) -> list[Step]:
    N = st.nodes
    steps: list[Step] = [Step(code="START", params={"at": N[seq[0][0]].label})]

    def add(code: str, **p):
        if steps and steps[-1].code == code and code in ("WALK_PLATFORM", "WALK_CONCOURSE", "CROSS_FOB"):
            last = steps[-1].params
            last["m"] = last.get("m", 0) + p.get("m", 0)
            for k, val in p.items():
                if k != "m":
                    last[k] = val
            return
        steps.append(Step(code=code, params=p))

    for i, (u, v, e, lc) in enumerate(seq):
        nu, nv = N[u], N[v]
        if e.kind in (EdgeKind.STAIRS, EdgeKind.LIFT, EdgeKind.ESCALATOR):
            target = nv.label
            add("UP" if lc > 0 else "DOWN", via=e.kind.value, to=target, status=e.status)
        elif e.kind == EdgeKind.FOB:
            plats = [p for p in st.groups[nv.group]]
            add("CROSS_FOB", fob=nv.label, m=round(e.distance_m), last_platforms=plats)
        elif e.kind == EdgeKind.LINK:
            add("WALK_LINK", name=e.name or {}, m=round(e.distance_m))
        elif nu.kind == NodeKind.CONCOURSE and nv.kind == NodeKind.CONCOURSE:
            add("WALK_CONCOURSE", m=round(e.distance_m), name=nv.label)
        elif nv.kind in (NodeKind.PLATFORM_POINT, NodeKind.PLATFORM) and nu.kind in (NodeKind.PLATFORM_POINT, NodeKind.PLATFORM):
            if e.distance_m > 5:
                nxt = _landmark(st, seq, i)
                add("WALK_PLATFORM", platforms=st.groups[nv.group], m=round(e.distance_m), toward=nxt)
        elif nv.kind == NodeKind.CONCOURSE:
            add("TO_CONCOURSE", name=nv.label)
        elif nv.kind == NodeKind.SIDE:
            add("TO_SIDE", name=nv.label)
        elif nu.kind == NodeKind.SIDE and nv.kind == NodeKind.PLATFORM_POINT:
            add("ENTER_PLATFORM", platforms=st.groups[nv.group])
        elif nu.kind == NodeKind.CONCOURSE and nv.kind == NodeKind.PLATFORM_POINT:
            add("ENTER_PLATFORM", platforms=st.groups[nv.group])
    end = N[seq[-1][1]]
    steps.append(Step(code="ARRIVE", params={"at": end.label, "verification": end.verification,
                                              "facility_type": end.facility_type}))
    return steps


def _landmark(st: Station, seq: list, i: int) -> dict | None:
    """The next thing the passenger will see after walking along the platform."""
    for u, v, e, lc in seq[i + 1:]:
        n = st.nodes[v]
        if e.kind in (EdgeKind.STAIRS, EdgeKind.LIFT, EdgeKind.ESCALATOR, EdgeKind.FOB):
            return st.nodes[v].label if n.kind == NodeKind.FOB else None
        if n.kind in (NodeKind.CONCOURSE, NodeKind.SIDE, NodeKind.FACILITY):
            return n.label
        if n.kind == NodeKind.PLATFORM:
            return None                # the middle of the same platform: "towards Platform 16" on Platform 16 reads badly
    return None


def all_profiles(st: Station, start: str, end: str, speed: str = "normal") -> list[Route]:
    """Fastest, step-free and fewer-level-changes routes; identical paths are reported once."""
    out, seen = [], set()
    for p in Profile:
        r = route(st, start, end, p, speed)
        key = tuple(r.path) if r.found else ("none", p)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out
