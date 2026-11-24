"""Station graph: builds a walkable graph (nodes + edges) from a station's schematic data file.

Data files (app/station/data/<CODE>.yaml) hold only what public sources support plus clearly
ILLUSTRATIVE geometry. Every node and edge carries its own verification status and source, so a route
over illustrative paths can never be presented as verified.

Geometry (schematic metres, NOT to scale):
  x = position along the platforms (THROUGH stations: overbridges cross at some x; TERMINUS stations: the
      head concourse is at x = 0 and platforms run away from it)
  y = across the platforms (one platform surface per "group"; island platforms carry two numbers)
  level 0 = platforms / concourse, level 1 = foot overbridge deck
"""
from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

DATA = Path(__file__).parent / "data"
VERIFICATION_ORDER = {"VERIFIED_PUBLIC": 0, "REPORTED": 1, "ILLUSTRATIVE": 2}


class NodeKind(str, Enum):
    PLATFORM = "PLATFORM"            # "I am on Platform N" (middle of the platform)
    PLATFORM_POINT = "PLATFORM_POINT"
    FOB = "FOB"
    CONCOURSE = "CONCOURSE"
    SIDE = "SIDE"                    # entrance / exit
    FACILITY = "FACILITY"


class EdgeKind(str, Enum):
    WALK = "WALK"
    STAIRS = "STAIRS"
    LIFT = "LIFT"
    ESCALATOR = "ESCALATOR"
    FOB = "FOB"
    LINK = "LINK"


class Node(BaseModel):
    id: str
    kind: NodeKind
    label: dict                      # {en, hi}
    x: float
    y: float
    level: int = 0
    group: int | None = None
    platform: int | None = None
    facility_type: str | None = None
    verification: str = "ILLUSTRATIVE"
    source: str | None = None


class Edge(BaseModel):
    a: str
    b: str
    kind: EdgeKind
    distance_m: float
    level_change: int = 0            # +1 up from a to b, -1 down, 0 flat
    step_free: bool = True
    direction: str = "BOTH"
    status: str = "N/A"              # lifts/escalators: UNKNOWN (never assumed working)
    verification: str = "ILLUSTRATIVE"
    source: str | None = None
    name: dict | None = None


class Station(BaseModel):
    code: str
    name: dict
    kind: str
    map_kind: str
    platform_count: dict
    platforms: list[int]
    groups: list[list[int]]
    nodes: dict[str, Node]
    edges: list[Edge]
    facilities: list[str]
    sources: dict
    notes: str = "SCHEMATIC_NOT_OFFICIAL_NOT_TO_SCALE"


def worst(*v: str) -> str:
    return max(v, key=lambda s: VERIFICATION_ORDER.get(s, 2))


def _plabel(refs: list[int]) -> dict:
    if len(refs) == 1:
        return {"en": f"Platform {refs[0]}", "hi": f"प्लेटफॉर्म {refs[0]}"}
    return {"en": f"Platforms {refs[0]}–{refs[-1]}", "hi": f"प्लेटफॉर्म {refs[0]}–{refs[-1]}"}


def build(spec: dict) -> Station:
    L, dy = spec["platform_length_m"], spec["group_spacing_m"]
    groups: list[list[int]] = spec["platform_groups"]["groups"]
    gver = spec["platform_groups"]["verification"]
    terminus = spec["kind"] == "TERMINUS"
    complexes = spec.get("complexes") or [{"id": "ALL", "groups": list(range(len(groups)))}]
    comp_of = {g: c["id"] for c in complexes for g in c["groups"]}
    # y position per group (extra gap before a complex that asks for it)
    ys, y = [], 0.0
    for g in range(len(groups)):
        c = next(c for c in complexes if g in c["groups"])
        if g == c["groups"][0] and g > 0 and c.get("gap_m"):
            y += c["gap_m"]
        ys.append(y)
        y += dy
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []

    def pt(g: int, x: float) -> str:
        nid = f"G{g}_{int(x)}"
        if nid not in nodes:
            nodes[nid] = Node(id=nid, kind=NodeKind.PLATFORM_POINT, label=_plabel(groups[g]), x=x, y=ys[g], group=g,
                              verification=gver)
        return nid

    xs: dict[int, set[float]] = {g: {L / 2} for g in range(len(groups))}
    if terminus:
        for g in xs:
            xs[g].add(0.0)
    for f in spec.get("fobs", []):
        span = f.get("groups") or [0, len(groups) - 1]
        for g in range(span[0], span[1] + 1):
            xs[g].add(float(f["x_m"]))
    for fac in spec.get("facilities", []):
        if "group" in fac:
            xs[fac["group"]].add(float(fac["x_m"]))
    for s in spec.get("sides", []):
        if "group" in s:
            xs[s["group"]].add(float(s["x_m"]))
    # walking along each platform surface
    for g, xx in xs.items():
        order = sorted(xx)
        for a, b in zip(order, order[1:]):
            edges.append(Edge(a=pt(g, a), b=pt(g, b), kind=EdgeKind.WALK, distance_m=b - a, verification=gver))
        for ref in groups[g]:
            nid = f"PF{ref}"
            nodes[nid] = Node(id=nid, kind=NodeKind.PLATFORM, label={"en": f"Platform {ref}", "hi": f"प्लेटफॉर्म {ref}"},
                              x=L / 2, y=ys[g], group=g, platform=ref, verification="VERIFIED_PUBLIC",
                              source=spec["platform_count"].get("source"))
            edges.append(Edge(a=nid, b=pt(g, L / 2), kind=EdgeKind.WALK, distance_m=3, verification=gver))
    # head concourse (terminus stations)
    if terminus:
        for c in complexes:
            gs = c["groups"]
            for g in gs:
                cid = f"C_G{g}"
                nodes[cid] = Node(id=cid, kind=NodeKind.CONCOURSE, label=c.get("name", {"en": "Concourse", "hi": "कॉनकोर्स"}),
                                  x=-30, y=ys[g], group=g, verification="ILLUSTRATIVE")
                edges.append(Edge(a=cid, b=pt(g, 0.0), kind=EdgeKind.WALK, distance_m=30, verification="ILLUSTRATIVE"))
            for a, b in zip(gs, gs[1:]):
                edges.append(Edge(a=f"C_G{a}", b=f"C_G{b}", kind=EdgeKind.WALK, distance_m=ys[b] - ys[a],
                                  verification="ILLUSTRATIVE"))
        for lk in spec.get("complex_links", []):
            ca = next(c for c in complexes if c["id"] == lk["a"])
            cb = next(c for c in complexes if c["id"] == lk["b"])
            edges.append(Edge(a=f"C_G{ca['groups'][-1]}", b=f"C_G{cb['groups'][0]}", kind=EdgeKind.LINK,
                              distance_m=lk["distance_m"], verification=lk["verification"], name=lk["name"]))
    # foot overbridges: a deck node above every platform it crosses, stairs/lift/escalator down to it
    for f in spec.get("fobs", []):
        span = f.get("groups") or [0, len(groups) - 1]
        ver = worst(f["verification"], f.get("position_verification", "ILLUSTRATIVE"))
        prev = None
        for g in range(span[0], span[1] + 1):
            did = f"{f['id']}_G{g}"
            nodes[did] = Node(id=did, kind=NodeKind.FOB, label=f["name"], x=f["x_m"], y=ys[g], level=1, group=g,
                              verification=ver, source=f.get("source"))
            if prev:
                edges.append(Edge(a=prev, b=did, kind=EdgeKind.FOB, distance_m=ys[g] - nodes[prev].y,
                                  verification=ver, source=f.get("source"), name=f["name"]))
            prev = did
            p = pt(g, float(f["x_m"]))
            edges.append(Edge(a=p, b=did, kind=EdgeKind.STAIRS, distance_m=15, level_change=1, step_free=False,
                              verification=ver))
            if g in f.get("lifts_at", []):
                edges.append(Edge(a=p, b=did, kind=EdgeKind.LIFT, distance_m=5, level_change=1, status="UNKNOWN",
                                  verification="ILLUSTRATIVE"))
            if g in f.get("escalators_at", []):
                edges.append(Edge(a=p, b=did, kind=EdgeKind.ESCALATOR, distance_m=15, level_change=1, step_free=False,
                                  status="UNKNOWN", direction="NOT_VERIFIED", verification="ILLUSTRATIVE"))
    # entrances / exits
    for s in spec.get("sides", []):
        sid = f"SIDE_{s['id']}"
        if "group" in s:
            g = s["group"]
            off = -45 if g == 0 else 45
            nodes[sid] = Node(id=sid, kind=NodeKind.SIDE, label=s["name"], x=s["x_m"], y=ys[g] + off, group=g,
                              verification=s["verification"], source=s.get("source"))
            edges.append(Edge(a=sid, b=pt(g, float(s["x_m"])), kind=EdgeKind.WALK, distance_m=40,
                              verification=s["verification"]))
            if s.get("fob_link"):
                f = next(f for f in spec["fobs"] if f["id"] == s["fob_link"])
                edges.append(Edge(a=sid, b=f"{f['id']}_G{g}", kind=EdgeKind.STAIRS, distance_m=60, level_change=1,
                                  step_free=False, verification="ILLUSTRATIVE"))
        else:
            c = next(c for c in complexes if c["id"] == s["complex"])
            g0 = c["groups"][len(c["groups"]) // 2]
            nodes[sid] = Node(id=sid, kind=NodeKind.SIDE, label=s["name"], x=-110, y=ys[g0], group=g0,
                              verification=s["verification"], source=s.get("source"))
            edges.append(Edge(a=sid, b=f"C_G{g0}", kind=EdgeKind.WALK, distance_m=60, verification=s["verification"]))
    # facilities
    fids = []
    side_count: dict[str, int] = {}
    for fac in spec.get("facilities", []):
        fid = fac["id"]
        if "side" in fac:
            anchor = f"SIDE_{fac['side']}"
            n = nodes[anchor]
            k = side_count.get(anchor, 0)
            side_count[anchor] = k + 1
            # spread facilities next to their entrance so they don't overlap on the schematic
            x, yy, d = n.x - 60 + 28 * k, n.y + 22, 25
        elif "concourse_group" in fac:
            anchor = f"C_G{fac['concourse_group']}"
            n = nodes[anchor]
            x, yy, d = n.x - 45, n.y, 20
        else:
            anchor = pt(fac["group"], float(fac["x_m"]))
            n = nodes[anchor]
            x, yy, d = n.x, n.y + 8, 8
        nodes[fid] = Node(id=fid, kind=NodeKind.FACILITY, label=fac["name"], x=x, y=yy, group=n.group,
                          facility_type=fac["type"], verification=fac["verification"], source=fac.get("source"))
        edges.append(Edge(a=fid, b=anchor, kind=EdgeKind.WALK, distance_m=d, verification=fac["verification"]))
        fids.append(fid)
    plats = sorted(r for g in groups for r in g)
    return Station(code=spec["code"], name=spec["name"], kind=spec["kind"], map_kind=spec["map_kind"],
                   platform_count=spec["platform_count"], platforms=plats, groups=groups, nodes=nodes, edges=edges,
                   facilities=fids, sources=spec.get("sources", {}))


@lru_cache
def stations() -> dict[str, Station]:
    out = {}
    for f in sorted(DATA.glob("*.yaml")):
        st = build(yaml.safe_load(f.read_text(encoding="utf-8")))
        out[st.code] = st
    return out


def get(code: str) -> Station | None:
    return stations().get(code)
