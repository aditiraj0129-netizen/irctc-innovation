"""Family Journey Guardian.

Looks at several PNRs that belong to one travelling group and answers: is the
group still travelling together, and which options keep it together? Uses the
same twin, rules engine and route search as single journeys; it adds no new
money logic. Members are labels only ("Adult 1", "Senior"): no names or IDs.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from app.domain.models import Event, Journey
from app.plan.models import Plan
from app.plan.ranker import Priority
from app.plan.service import assess, registry
from app.plan.transfer import PassengerProfile, TransferClass, station_info
from app.rules.engine import cancellation_refund
from app.rules.models import Outcome
from app.twin.twin import JourneyStatus, build_twin

GROUPS_FILE = Path(__file__).resolve().parents[1] / "data" / "groups.json"


class Member(BaseModel):
    id: str
    label: dict
    journey: str
    profile: PassengerProfile = Field(default_factory=PassengerProfile)


class Group(BaseModel):
    id: str
    name: dict
    note: str = ""
    members: list[Member]


def load_groups() -> dict[str, Group]:
    return {g["id"]: Group(**g) for g in json.loads(GROUPS_FILE.read_text(encoding="utf-8"))}


class MemberLine(BaseModel):
    member_id: str
    label: dict
    journey_id: str
    travels: bool
    trains: list[str]
    arrival: datetime | None
    status: str


class GroupOption(BaseModel):
    id: str
    kind: str                 # KEEP_BOOKED, SWITCH_ALL_TOGETHER, SPLIT_ALTERNATIVE, SPLIT_SOME_STAY
    keeps_together: bool
    suitability: str          # GROUP or INDIVIDUAL
    members: list[MemberLine]
    money_back_paise: int     # estimates from the rules engine, summed across PNRs
    money_lost_paise: int
    money_needs_approval: bool = False
    new_tickets_needed: int
    arrival_last: datetime | None
    arrival_spread_minutes: int
    changes: int
    senior_friendly: bool
    step_free_ok: bool
    warnings: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)
    rank: int | None = None


class GroupView(BaseModel):
    group_id: str
    name: dict
    now: datetime
    group_profile: PassengerProfile
    divergence: list[str]
    timeline: list[MemberLine]
    options: list[GroupOption]
    data_label: str = "SIMULATED"
    note: str


def merged_profile(members: list[Member]) -> PassengerProfile:
    """Plan for the most demanding member: the group moves at its slowest pace."""
    return PassengerProfile(
        walking_speed="slow" if any(m.profile.speed == "slow" for m in members) else "normal",
        step_free=any(m.profile.step_free for m in members),
        senior=any(m.profile.senior for m in members))


def _accessibility(plan: Plan | None, profile: PassengerProfile) -> tuple[bool, bool]:
    if plan is None or not plan.rides:
        return True, True
    senior_ok = plan.changes == 0 or (plan.worst_transfer in (TransferClass.COMFORTABLE,))
    step_ok = all(station_info(t.station)["complexity"] != "HIGH" for t in plan.transfers)
    return (senior_ok if profile.senior else True), (step_ok if profile.step_free else True)


def group_view(group: Group, journeys: dict[str, Journey], events: dict[str, list[Event]], now: datetime,
               priority: Priority = Priority.FAMILY) -> GroupView:
    prof = merged_profile(group.members)
    jids = list(dict.fromkeys(m.journey for m in group.members))
    twins = {j: build_twin(journeys[j], events[j], now, prof) for j in jids}
    results = {j: assess(journeys[j], events[j], now, Priority.TIME, prof) for j in jids}
    broken = [j for j in jids if twins[j].status == JourneyStatus.BROKEN]
    fine = [j for j in jids if j not in broken]

    def line(m: Member, travels: bool, trains: list[str], arrival, status: str) -> MemberLine:
        return MemberLine(member_id=m.id, label=m.label, journey_id=m.journey, travels=travels, trains=trains,
                          arrival=arrival, status=status)

    def booked_line(m: Member) -> MemberLine:
        t = twins[m.journey]
        return line(m, t.status != JourneyStatus.BROKEN, [l.train_no for l in t.legs], t.expected_final_arrival,
                    t.legs[0].state.value)

    timeline = [booked_line(m) for m in group.members]
    divergence = []
    if len({tl.status for tl in timeline}) > 1:
        divergence.append("DIFFERENT_STATUS")
    if len({tuple(tl.trains) for tl in timeline}) > 1:
        divergence.append("DIFFERENT_TRAINS")
    if broken and fine:
        divergence.append("PART_OF_GROUP_CANNOT_TRAVEL_AS_BOOKED")

    fares = {j: sum(l.ticket.total_fare_paise for l in journeys[j].legs) for j in jids}

    def cancel_back(j: str) -> tuple[int, list[str]]:
        d = cancellation_refund(journeys[j].legs[0].ticket, now, registry())
        return (d.refund_paise if d.outcome == Outcome.REFUND_ON_CANCEL else 0), d.rule_ids

    def auto_back(j: str) -> tuple[int, list[str], bool]:
        p = next((p for p in results[j].plans if p.decisions), None)
        if p is None:
            return 0, [], False
        return p.money_back_paise, [r for d in p.decisions for r in d.rule_ids], p.money_back_if_approved

    opts: list[GroupOption] = []
    if not broken:
        last = max((twins[j].expected_final_arrival for j in jids if twins[j].expected_final_arrival), default=None)
        same_train = len({tuple(l.train_no for l in twins[j].legs) for j in jids}) == 1
        opts.append(GroupOption(id="keep", kind="KEEP_BOOKED", keeps_together=same_train,
                                suitability="GROUP" if same_train else "INDIVIDUAL",
                                members=timeline, money_back_paise=0, money_lost_paise=0, new_tickets_needed=0,
                                arrival_last=last, arrival_spread_minutes=0, changes=0,
                                senior_friendly=True, step_free_ok=True))
    else:
        alt_plans: list[Plan] = []
        for j in broken:
            alt_plans += [p for p in results[j].plans if p.needs_new_ticket]
        alt_plans = sorted({tuple((r.train_no, r.dep) for r in p.rides): p for p in alt_plans}.values(),
                           key=lambda p: p.arrival)[:2]
        auto = {j: auto_back(j) for j in broken}
        canc = {j: cancel_back(j) for j in fine}
        pax_total = sum(l.ticket.passengers for j in jids for l in journeys[j].legs[:1])
        for i, p in enumerate(alt_plans, start=1):
            sen, step = _accessibility(p, prof)
            trains = [r.train_no for r in p.rides]
            back = sum(a[0] for a in auto.values()) + sum(c[0] for c in canc.values())
            warn = ["SEATS_NOT_CHECKED_FOR_WHOLE_GROUP"]
            if fine:
                warn.append("CONFIRMED_MEMBERS_WOULD_CANCEL")
            opts.append(GroupOption(
                id=f"together-{i}", kind="SWITCH_ALL_TOGETHER", keeps_together=True, suitability="GROUP",
                members=[line(m, True, trains, p.arrival, "SWITCHES") for m in group.members],
                money_back_paise=back, money_lost_paise=sum(fares.values()) - back,
                money_needs_approval=any(a[2] for a in auto.values()), new_tickets_needed=pax_total,
                arrival_last=p.arrival, arrival_spread_minutes=0, changes=p.changes, senior_friendly=sen,
                step_free_ok=step, warnings=warn,
                rule_ids=[r for a in auto.values() for r in a[1]] + [r for c in canc.values() for r in c[1]]))
            members = [booked_line(m) if m.journey in fine else line(m, True, trains, p.arrival, "SWITCHES")
                       for m in group.members]
            arrs = [x.arrival for x in members if x.arrival]
            broken_pax = sum(journeys[j].legs[0].ticket.passengers for j in broken)
            back2 = sum(a[0] for a in auto.values())
            opts.append(GroupOption(
                id=f"split-{i}", kind="SPLIT_ALTERNATIVE", keeps_together=False, suitability="INDIVIDUAL",
                members=members, money_back_paise=back2,
                money_lost_paise=sum(fares[j] for j in broken) - back2,
                money_needs_approval=any(a[2] for a in auto.values()), new_tickets_needed=broken_pax,
                arrival_last=max(arrs) if arrs else None,
                arrival_spread_minutes=int((max(arrs) - min(arrs)).total_seconds() // 60) if arrs else 0,
                changes=p.changes, senior_friendly=sen, step_free_ok=step,
                warnings=["SPLITS_THE_GROUP", "SEATS_NOT_CHECKED"],
                rule_ids=[r for a in auto.values() for r in a[1]]))
        if fine:
            members = [booked_line(m) if m.journey in fine else line(m, False, [], None, "DOES_NOT_TRAVEL")
                       for m in group.members]
            back3 = sum(a[0] for a in auto.values())
            opts.append(GroupOption(
                id="split-stay", kind="SPLIT_SOME_STAY", keeps_together=False, suitability="INDIVIDUAL",
                members=members, money_back_paise=back3, money_lost_paise=sum(fares[j] for j in broken) - back3,
                new_tickets_needed=0, arrival_last=max((x.arrival for x in members if x.arrival), default=None),
                arrival_spread_minutes=0, changes=0, senior_friendly=True, step_free_ok=True,
                warnings=["SPLITS_THE_GROUP", "SOME_MEMBERS_DO_NOT_TRAVEL"],
                rule_ids=[r for a in auto.values() for r in a[1]]))

    far = datetime.max.replace(tzinfo=now.tzinfo)
    if priority == Priority.TIME:
        key = lambda o: (o.arrival_last or far, not o.keeps_together)
    elif priority == Priority.MONEY:
        key = lambda o: (o.money_lost_paise, o.new_tickets_needed, not o.keeps_together)
    else:   # FAMILY / RISK / TRANSFERS: keep together, then accessible, then fewest changes, then soonest
        key = lambda o: (not o.keeps_together, not (o.senior_friendly and o.step_free_ok), o.changes,
                         o.arrival_last or far, o.money_lost_paise)
    opts.sort(key=key)
    for i, o in enumerate(opts, start=1):
        o.rank = i
    return GroupView(group_id=group.id, name=group.name, now=now, group_profile=prof, divergence=divergence,
                     timeline=timeline, options=opts, note=group.note)
