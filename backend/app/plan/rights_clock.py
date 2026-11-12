"""The Rights Clock.

Shows, on a timeline, each money right the passenger has and when it ends,
and finds the DECISION DEADLINE: the first future moment when the best plan
changes or the money it keeps goes down, assuming nothing else changes.

Method: rights only change at a small set of breakpoints (refund-slab edges,
train departure, TDR deadlines, alternative booking cut-offs). Between them,
everything is constant, so we re-run the same rules + ranking just after each
breakpoint. No AI, no prediction.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from pydantic import BaseModel

from app.domain.models import Journey
from app.plan.models import Plan, PlanKind
from app.rules.engine import RuleRegistry, cancellation_refund
from app.rules.models import Outcome, TicketStatus

HORIZON_HOURS = 24


class Window(BaseModel):
    id: str
    kind: str                      # CANCEL_SLAB, TDR_LATE, TDR_MISSED_CONNECTION, BOOK_ALTERNATIVE
    start: datetime
    end: datetime
    amount_paise: int | None
    if_approved: bool = False
    verified: bool = True
    status: str                    # OPEN, UPCOMING, CLOSED


class RightsClock(BaseModel):
    now: datetime
    horizon_end: datetime
    windows: list[Window]
    next_drop: dict | None = None
    decision_deadline: datetime | None = None
    then_plan_kind: PlanKind | None = None
    assumption: str = "IF_NOTHING_ELSE_CHANGES"


def _status(now: datetime, start: datetime, end: datetime) -> str:
    if end <= now:
        return "CLOSED"
    return "OPEN" if start <= now else "UPCOMING"


def cancel_windows(journey: Journey, now: datetime, horizon_end: datetime, registry: RuleRegistry) -> list[Window]:
    """Cancellation-refund windows for the first leg, from now until departure."""
    t = journey.legs[0].ticket
    dep = t.scheduled_departure
    if now >= dep:
        return []
    rs = registry.rule_set_for(t, now)
    edges = [now]
    if t.status == TicketStatus.CONFIRMED:
        edges += [dep - timedelta(hours=s.min_hours) for s in rs.confirmed_slabs if s.min_hours is not None]
    elif rs.rac_wl_cancel_cutoff_minutes is not None:
        edges.append(dep - timedelta(minutes=rs.rac_wl_cancel_cutoff_minutes))
    edges.append(dep)
    edges = sorted({e for e in edges if now <= e <= dep})
    out = []
    for i, (a, b) in enumerate(zip(edges, edges[1:])):
        if a >= horizon_end or a == b:
            continue
        mid = a + (b - a) / 2
        d = cancellation_refund(t, mid, registry)
        amount = d.refund_paise if d.outcome == Outcome.REFUND_ON_CANCEL else 0
        out.append(Window(id=f"cancel-{i}", kind="CANCEL_SLAB", start=a, end=min(b, horizon_end),
                          amount_paise=amount, verified=d.last_verified is not None and d.legal_status.value == "NOTIFIED",
                          status=_status(now, a, b)))
    return out


def plan_windows(plans: list[Plan], now: datetime, horizon_end: datetime) -> list[Window]:
    out = []
    seen = set()
    for p in plans:
        if p.deadline is None or p.deadline <= now:
            continue
        if p.kind in (PlanKind.FILE_TDR_LATE, PlanKind.TDR_MISSED_CONNECTION_ONLY) and p.kind not in seen:
            seen.add(p.kind)
            start = now
            for d in p.decisions:
                if d.kind == "TDR_MISSED_CONNECTION" and d.deadline:
                    start = d.deadline - timedelta(minutes=180)   # can be filed once the first train arrives
            out.append(Window(id=f"w-{p.id}", kind="TDR_LATE" if p.kind == PlanKind.FILE_TDR_LATE else "TDR_MISSED_CONNECTION",
                              start=start, end=min(p.deadline, horizon_end), amount_paise=p.money_back_paise,
                              if_approved=True, verified=not p.deadline_unverified, status=_status(now, start, p.deadline)))
        if p.needs_new_ticket and p.rank == min((q.rank or 99) for q in plans if q.needs_new_ticket):
            out.append(Window(id=f"w-{p.id}", kind="BOOK_ALTERNATIVE", start=now, end=min(p.deadline, horizon_end),
                              amount_paise=None, verified=False, status=_status(now, now, p.deadline)))
    return out


TRAVEL_KINDS = {PlanKind.TRAVEL_AS_BOOKED, PlanKind.TRAVEL_DELAYED}


def _same(a: PlanKind, b: PlanKind) -> bool:
    return a == b or (a in TRAVEL_KINDS and b in TRAVEL_KINDS)


def build_rights_clock(journey: Journey, now: datetime, plans: list[Plan], registry: RuleRegistry,
                       rank_at: Callable[[datetime], list[Plan]], show_cancel_windows: bool = True) -> RightsClock:
    horizon_end = now + timedelta(hours=HORIZON_HOURS)
    windows = (cancel_windows(journey, now, horizon_end, registry) if show_cancel_windows else []) + \
        plan_windows(plans, now, horizon_end)

    # Next drop of the cancellation refund.
    next_drop = None
    cw = [w for w in windows if w.kind == "CANCEL_SLAB"]
    for a, b in zip(cw, cw[1:]):
        if (b.amount_paise or 0) < (a.amount_paise or 0):
            next_drop = {"at": a.end.isoformat(), "from_paise": a.amount_paise, "to_paise": b.amount_paise}
            break

    # Decision deadline: first breakpoint after which the top plan changes or keeps less money.
    top = plans[0] if plans else None
    deadline, then_kind = None, None
    if top is not None:
        breakpoints = sorted({w.end for w in windows if now < w.end <= horizon_end} |
                             {p.deadline for p in plans if p.deadline and now < p.deadline <= horizon_end})
        for bp in breakpoints:
            later = rank_at(bp + timedelta(minutes=1))
            if not later:
                continue
            new_top = later[0]
            if not _same(new_top.kind, top.kind) or new_top.money_back_paise < top.money_back_paise or \
                    (top.rides and new_top.rides != top.rides):
                deadline, then_kind = bp, new_top.kind
                break
    return RightsClock(now=now, horizon_end=horizon_end, windows=windows, next_drop=next_drop,
                       decision_deadline=deadline, then_plan_kind=then_kind)
