"""Counterfactual Decision Intelligence.

Explains WHY the recommended plan beats each alternative (computed differences,
not AI text), and what would happen under other decisions, but ONLY when the
What-If simulator actually calculated that scenario.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.plan.models import Plan
from app.plan.ranker import Priority
from app.whatif.simulator import ScenarioId, WhatIfResult


class Comparison(BaseModel):
    plan_id: str
    plan_kind: str
    arrival_diff_minutes: int | None      # positive = the recommended plan arrives earlier by this much
    money_diff_paise: int                 # positive = the recommended plan keeps this much more money
    certainty_diff: int                   # positive = the recommended plan is more certain
    changes_diff: int                     # positive = the recommended plan has fewer changes
    transfer_risk_diff: int               # positive = the recommended plan has a safer change of train
    points: list[str] = Field(default_factory=list)


class Counterfactual(BaseModel):
    scenario: ScenarioId
    effect: str                            # e.g. RECOMMENDED_NO_LONGER_FEASIBLE, LESS_MONEY, NO_CHANGE
    detail: dict = Field(default_factory=dict)


class Recommendation(BaseModel):
    plan_id: str
    plan_kind: str
    priority: Priority
    why: list[str]
    comparisons: list[Comparison]
    counterfactuals: list[Counterfactual]


def _ride_key(p: Plan) -> str:
    return " + ".join(f"{r.train_no}@{r.dep.isoformat()}" for r in p.rides)


def compare(top: Plan, other: Plan) -> Comparison:
    arr = None
    if top.travels and other.travels and top.arrival and other.arrival:
        arr = int((other.arrival - top.arrival).total_seconds() // 60)
    c = Comparison(plan_id=other.id, plan_kind=other.kind.value, arrival_diff_minutes=arr,
                   money_diff_paise=other.money_lost_paise - top.money_lost_paise,
                   certainty_diff=int(top.certainty) - int(other.certainty),
                   changes_diff=other.changes - top.changes,
                   transfer_risk_diff=other.transfer_risk - top.transfer_risk)
    if top.travels and not other.travels:
        c.points.append("YOU_STILL_TRAVEL")
    if arr is not None and arr > 0:
        c.points.append("ARRIVES_EARLIER")
    if c.money_diff_paise > 0:
        c.points.append("KEEPS_MORE_MONEY")
    if c.certainty_diff > 0:
        c.points.append("MORE_CERTAIN")
    if c.changes_diff > 0:
        c.points.append("FEWER_CHANGES")
    if c.transfer_risk_diff > 0:
        c.points.append("SAFER_TRANSFER")
    if other.needs_new_ticket and not top.needs_new_ticket:
        c.points.append("NO_NEW_TICKET_NEEDED")
    return c


PRIORITY_POINT = {Priority.TIME: "MATCHES_PRIORITY_TIME", Priority.MONEY: "MATCHES_PRIORITY_MONEY",
                  Priority.RISK: "MATCHES_PRIORITY_RISK", Priority.TRANSFERS: "MATCHES_PRIORITY_TRANSFERS",
                  Priority.FAMILY: "MATCHES_PRIORITY_RISK"}


def recommend(plans: list[Plan], priority: Priority, whatif: WhatIfResult | None = None) -> Recommendation | None:
    if not plans:
        return None
    top = plans[0]
    comps = [compare(top, p) for p in plans[1:]]
    why = [PRIORITY_POINT[priority]]
    for point in ["YOU_STILL_TRAVEL", "ARRIVES_EARLIER", "KEEPS_MORE_MONEY", "MORE_CERTAIN", "FEWER_CHANGES",
                  "SAFER_TRANSFER", "NO_NEW_TICKET_NEEDED"]:
        if comps and point in comps[0].points:
            why.append(point)
    if top.transfers and all(t.cls.value != "NOT_FEASIBLE" for t in top.transfers):
        why.append("CONNECTION_FEASIBLE")

    cfs: list[Counterfactual] = []
    if whatif:
        by = {o.id: o for o in whatif.outcomes}
        w = by.get(ScenarioId.WAIT_30)
        if w and w.applicable:
            key = _ride_key(top)
            if key and key in w.lost_options:
                cfs.append(Counterfactual(scenario=ScenarioId.WAIT_30, effect="RECOMMENDED_NO_LONGER_FEASIBLE",
                                          detail={"wait_minutes": whatif.wait_minutes}))
            elif w.money_back_paise < top.money_back_paise:
                cfs.append(Counterfactual(scenario=ScenarioId.WAIT_30, effect="LESS_MONEY",
                                          detail={"from_paise": top.money_back_paise, "to_paise": w.money_back_paise,
                                                  "wait_minutes": whatif.wait_minutes}))
            elif w.lost_options:
                cfs.append(Counterfactual(scenario=ScenarioId.WAIT_30, effect="SOME_OPTIONS_DISAPPEAR",
                                          detail={"count": len(w.lost_options), "wait_minutes": whatif.wait_minutes}))
            else:
                cfs.append(Counterfactual(scenario=ScenarioId.WAIT_30, effect="NO_CHANGE",
                                          detail={"wait_minutes": whatif.wait_minutes}))
        d = by.get(ScenarioId.DELAY_GROWS)
        if d and d.applicable:
            if d.plan_kind != top.kind:
                cfs.append(Counterfactual(scenario=ScenarioId.DELAY_GROWS, effect="BEST_OPTION_CHANGES",
                                          detail={"to_kind": d.plan_kind.value if d.plan_kind else None,
                                                  "extra_delay_minutes": whatif.delay_increase_minutes}))
            else:
                cfs.append(Counterfactual(scenario=ScenarioId.DELAY_GROWS, effect="SAME_BEST_OPTION",
                                          detail={"extra_delay_minutes": whatif.delay_increase_minutes}))
    return Recommendation(plan_id=top.id, plan_kind=top.kind.value, priority=priority, why=why,
                          comparisons=comps, counterfactuals=cfs)
