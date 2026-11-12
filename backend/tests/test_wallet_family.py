"""Passenger Rights Wallet + Family Journey Guardian."""
import pytest

from app.data.source import load_scenarios
from app.family.family import group_view, load_groups, merged_profile
from app.plan.ranker import Priority
from app.plan.service import assess
from app.wallet.wallet import Stage, build_wallet, export_text, valid_transition


@pytest.fixture(scope="module")
def sc():
    return load_scenarios()


def wallet(s, claims=()):
    r = assess(s.journey, s.events, s.start_clock)
    return build_wallet(s.journey, s.events, s.start_clock, r.plans, list(claims), [])


def test_wallet_edge_case_items_and_rule_metadata(sc):
    w = wallet(sc["edge_three_hours"])
    tdr = next(i for i in w.items if i.kind == "TDR_LATE_RUNNING")
    assert tdr.stage == Stage.ELIGIBLE_TO_FILE and tdr.if_approved and tdr.estimate_only
    assert tdr.estimated_refund_paise == 118000 and tdr.minutes_left == 280
    assert tdr.rule.rule_set_id == "TDR-LATE-3H" and tdr.rule.rule_version and tdr.rule.effective_from
    cancel = next(i for i in w.items if i.kind == "CANCELLATION")
    assert cancel.stage == Stage.NOT_ELIGIBLE and "RULE_NOT_YET_NOTIFIED" in cancel.rule.unresolved
    assert w.best_estimate_paise == 118000 and w.best_estimate_needs_approval
    assert w.disclaimer == "ESTIMATES_NOT_GUARANTEED"


def test_wallet_waitlisted_is_automatic_and_has_no_cancel_estimate(sc):
    w = wallet(sc["waitlisted_family"])
    assert [i.kind for i in w.items] == ["WL_AFTER_CHART"]
    assert w.items[0].stage == Stage.AUTOMATIC_DUE and w.items[0].estimated_refund_paise == 214000


def test_claim_lifecycle_only_moves_forward(sc):
    s = sc["edge_three_hours"]
    w = wallet(s)
    item = "TDR_LATE_RUNNING:1"
    assert valid_transition(w, item, "FILED")
    assert not valid_transition(w, item, "RECEIVED")            # can't skip filing and approval
    assert not valid_transition(w, item, "ESTIMATE")             # system stages can't be set by users
    assert not valid_transition(w, "CANCELLATION:1", "FILED")    # nothing to file there
    w2 = wallet(s, [{"item_id": item, "status": "FILED", "at": s.start_clock.isoformat()},
                    {"item_id": item, "status": "APPROVED", "at": s.start_clock.isoformat()}])
    it = next(i for i in w2.items if i.id == item)
    assert it.stage == Stage.APPROVED and it.rule_stage == Stage.ELIGIBLE_TO_FILE
    assert [h.kind for h in w2.history].count("CLAIM_UPDATE") == 2


def test_export_never_guarantees(sc):
    txt = export_text(wallet(sc["missed_connection"]))
    assert "not guaranteed" in txt and "SIMULATED" in txt and "deadline unverified" in txt
    assert "guaranteed refund" not in txt.lower()


def test_family_group_detects_split_and_keeps_together_first(sc):
    g = load_groups()["demo_family"]
    js = {k: s.journey for k, s in sc.items()}
    ev = {k: s.events for k, s in sc.items()}
    v = group_view(g, js, ev, sc["family_confirmed"].start_clock, Priority.FAMILY)
    assert "DIFFERENT_STATUS" in v.divergence and "PART_OF_GROUP_CANNOT_TRAVEL_AS_BOOKED" in v.divergence
    assert v.group_profile.senior and v.group_profile.step_free
    top = v.options[0]
    assert top.keeps_together and top.suitability == "GROUP" and top.kind == "SWITCH_ALL_TOGETHER"
    # money from the rules engine: WL refund 2 x (1650-60) + confirmed cancel 50% of 2 x 1650
    assert top.money_back_paise == 318000 + 165000 and top.new_tickets_needed == 4
    assert "CONFIRMED_MEMBERS_WOULD_CANCEL" in top.warnings
    split = next(o for o in v.options if o.kind == "SPLIT_ALTERNATIVE")
    assert not split.keeps_together and split.suitability == "INDIVIDUAL" and "SPLITS_THE_GROUP" in split.warnings
    money_first = group_view(g, js, ev, sc["family_confirmed"].start_clock, Priority.MONEY).options[0]
    assert money_first.money_lost_paise == 12000                  # cheapest option splits the group (warned)


def test_group_profile_and_no_personal_data():
    g = load_groups()["demo_family"]
    p = merged_profile(g.members)
    assert p.speed == "slow"
    dumped = g.model_dump_json()
    assert "name" not in [k for m in g.model_dump()["members"] for k in m]
