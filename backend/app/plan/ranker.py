"""Explainable ranking.

The passenger picks a priority. We sort with simple, visible rules (no hidden
weights), then attach a reason comparing each plan with the next one down.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from app.plan.models import Plan

FAR_FUTURE = datetime.max


class Priority(str, Enum):
    TIME = "time"      # reach soonest
    MONEY = "money"    # keep the most money already paid
    RISK = "risk"      # most certain outcome


def _arr(p: Plan) -> float:
    return p.arrival.timestamp() if (p.travels and p.arrival) else float("inf")


def sort_key(p: Plan, priority: Priority) -> tuple:
    if priority == Priority.TIME:
        return (0 if p.travels else 1, _arr(p), -p.certainty, p.money_lost_paise)
    if priority == Priority.MONEY:
        return (p.money_lost_paise, p.needs_new_ticket, -p.certainty, _arr(p))
    return (-p.certainty, p.money_lost_paise, _arr(p))


def rank(plans: list[Plan], priority: Priority) -> list[Plan]:
    ordered = sorted(plans, key=lambda p: sort_key(p, priority))
    for i, p in enumerate(ordered):
        p.rank = i + 1
        p.reasons = []
        nxt = ordered[i + 1] if i + 1 < len(ordered) else None
        if nxt is None:
            continue
        if p.travels and nxt.travels and p.arrival and nxt.arrival and p.arrival < nxt.arrival:
            p.reasons.append({"key": "ARRIVES_EARLIER", "minutes": int((nxt.arrival - p.arrival).total_seconds() // 60)})
        if p.travels and not nxt.travels:
            p.reasons.append({"key": "STILL_REACHES"})
        if p.money_lost_paise < nxt.money_lost_paise:
            p.reasons.append({"key": "KEEPS_MORE_MONEY", "paise": nxt.money_lost_paise - p.money_lost_paise})
        if p.certainty > nxt.certainty:
            p.reasons.append({"key": "MORE_CERTAIN"})
    return ordered
