"""session_phase_admits — the central fail-closed predicate (design #19 §5.1; VTG-EV-001 substrate).

The VTG-EV-001 yolk: an unenumerated / unknown / calendar-only phase is never admissible;
an empty admitting set admits nothing; only a policy-declared admitting phase for the exact
action passes (both-ways). SessionPhase is an injected opaque token judged by membership, never
truthiness (§2.2(3)).

Regime tag: predicate / model substrate only; VTG-EV-001 NOT_IMPLEMENTED (`/3` + Broker
residue); EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.venue import ActionClass, OrderAdmissibilityResult, session_phase_admits

from ._venue_strategies import PHASE_TOKENS, clean_policy, clean_snapshot


def test_admitting_phase_for_exact_action_is_admissible_positive_side() -> None:
    """(§10 canary b) An observed phase in the policy admitting set for the exact action => ADMISSIBLE."""
    policy = clean_policy(
        action=ActionClass.NEW_LONG, admitting_phases=frozenset({"continuous_trading"})
    )
    snapshot = clean_snapshot()
    assert (
        session_phase_admits(
            "continuous_trading", ActionClass.NEW_LONG, snapshot, policy
        )
        is OrderAdmissibilityResult.ADMISSIBLE
    )


def test_unenumerated_phase_is_inadmissible() -> None:
    """(§10 line 269) An observed phase NOT in the admitting set is INADMISSIBLE."""
    policy = clean_policy(
        action=ActionClass.NEW_LONG, admitting_phases=frozenset({"continuous_trading"})
    )
    snapshot = clean_snapshot()
    assert (
        session_phase_admits("opening_auction", ActionClass.NEW_LONG, snapshot, policy)
        is OrderAdmissibilityResult.INADMISSIBLE
    )


def test_none_phase_is_unknown() -> None:
    """(§8 line 245) A None observed phase is UNKNOWN (restrictive, never permissive)."""
    policy = clean_policy()
    snapshot = clean_snapshot()
    assert (
        session_phase_admits(None, ActionClass.NEW_LONG, snapshot, policy)
        is OrderAdmissibilityResult.UNKNOWN
    )


def test_unenumerated_action_is_inadmissible() -> None:
    """(§8 line 245) An action with no declared admitting set is INADMISSIBLE (fail-closed)."""
    policy = clean_policy(action=ActionClass.NEW_LONG)
    snapshot = clean_snapshot()
    # NEW_SHORT was never declared in the policy.
    assert (
        session_phase_admits(
            "continuous_trading", ActionClass.NEW_SHORT, snapshot, policy
        )
        is OrderAdmissibilityResult.INADMISSIBLE
    )


def test_empty_admitting_set_admits_nothing_both_ways() -> None:
    """(§4.7 ∅ both-ways) An empty admitting set admits NO phase (vacuous admit is not an admit)."""
    policy = clean_policy(action=ActionClass.NEW_LONG, admitting_phases=frozenset())
    snapshot = clean_snapshot()
    # Even the "usual" continuous_trading phase is denied when the set is empty.
    assert (
        session_phase_admits(
            "continuous_trading", ActionClass.NEW_LONG, snapshot, policy
        )
        is OrderAdmissibilityResult.INADMISSIBLE
    )
    assert (
        session_phase_admits("anything", ActionClass.NEW_LONG, snapshot, policy)
        is OrderAdmissibilityResult.INADMISSIBLE
    )


def test_phase_a_decision_not_reusable_in_phase_b() -> None:
    """(§10 line 273) A phase approved for continuous trading is not reusable in an auction."""
    policy = clean_policy(
        action=ActionClass.NEW_LONG, admitting_phases=frozenset({"continuous_trading"})
    )
    snapshot = clean_snapshot()
    # continuous_trading admits; opening_auction (phase B) does not.
    assert (
        session_phase_admits(
            "continuous_trading", ActionClass.NEW_LONG, snapshot, policy
        )
        is OrderAdmissibilityResult.ADMISSIBLE
    )
    assert (
        session_phase_admits("opening_auction", ActionClass.NEW_LONG, snapshot, policy)
        is OrderAdmissibilityResult.INADMISSIBLE
    )


def test_none_snapshot_or_policy_is_unknown() -> None:
    """(∅) A None snapshot / policy is UNKNOWN (fail-closed)."""
    policy = clean_policy()
    snapshot = clean_snapshot()
    assert (
        session_phase_admits("continuous_trading", ActionClass.NEW_LONG, None, policy)
        is OrderAdmissibilityResult.UNKNOWN
    )
    assert (
        session_phase_admits("continuous_trading", ActionClass.NEW_LONG, snapshot, None)
        is OrderAdmissibilityResult.UNKNOWN
    )


@given(
    phase=st.sampled_from(sorted(PHASE_TOKENS)),
    admit=st.sampled_from(sorted(PHASE_TOKENS)),
)
def test_property_membership_decides_admissibility(phase: str, admit: str) -> None:
    """(property) The observed token admits iff it is in the policy admitting set for the action."""
    policy = clean_policy(
        action=ActionClass.NEW_LONG, admitting_phases=frozenset({admit})
    )
    snapshot = clean_snapshot()
    result = session_phase_admits(phase, ActionClass.NEW_LONG, snapshot, policy)
    if phase == admit:
        assert result is OrderAdmissibilityResult.ADMISSIBLE
    else:
        assert result is OrderAdmissibilityResult.INADMISSIBLE


@given(unknown_token=st.text(min_size=1, max_size=6))
def test_property_unknown_token_never_admits_empty_set(unknown_token: str) -> None:
    """(∅ property) With an empty admitting set, NO token ever admits (escape check)."""
    policy = clean_policy(action=ActionClass.NEW_LONG, admitting_phases=frozenset())
    snapshot = clean_snapshot()
    assert (
        session_phase_admits(unknown_token, ActionClass.NEW_LONG, snapshot, policy)
        is OrderAdmissibilityResult.INADMISSIBLE
    )
