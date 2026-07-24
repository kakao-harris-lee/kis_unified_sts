"""Restrictive dominance + precedence lattice (§5.3; SA-EV-009 — strong substrate).

HALT / restrictive dominates any outstanding permissive capability regardless of issue
order (the both-order property); safer-state transitions are broad while permissive
transitions require a current epoch; a stale but authentic restrictive message may apply
only when it cannot enlarge authority; and HALT's effect classifier denies new risk /
re-arm / limit activation while preserving protective controls.
"""

from __future__ import annotations

from tos.authority import (
    AuthorityState,
    CapabilityType,
    Ordering,
    OrderingEvent,
    compare_order,
    halt_denies,
    is_restrictive_dominating_type,
    permissive_transition_allowed,
    restrictive_dominates,
    restrictive_may_apply_when_stale,
    safer_transition_allowed,
)

from ._authority_strategies import issue_capability


def _halt() -> object:
    return issue_capability(
        capability_id="halt-1", capability_type=CapabilityType.HALT, issue_sequence=1
    )


def _permissive(issue_sequence: int) -> object:
    return issue_capability(
        capability_id="perm-1",
        capability_type=CapabilityType.NORMAL_RISK_INCREASING,
        issue_sequence=issue_sequence,
    )


def test_halt_dominates_permissive_both_orders() -> None:
    """(canary SA-EV-009) HALT dominates a permissive grant in BOTH issue orders.

    The two orderings are genuinely distinct (``compare_order`` reports BEFORE vs AFTER
    from the issue sequences), yet ``restrictive_dominates`` returns True in both — proving
    dominance is order-independent (§7 line 239-242; §20 line 746; SA-INV-010).
    """
    halt = _halt()

    # (a) HALT issued first (seq 1), permissive second (seq 2).
    perm_after = _permissive(issue_sequence=2)
    halt_first = OrderingEvent(
        event_id="halt", source_continuity_id="c", source_native_sequence=1
    )
    perm_second = OrderingEvent(
        event_id="perm", source_continuity_id="c", source_native_sequence=2
    )
    assert compare_order(halt_first, perm_second) is Ordering.BEFORE
    assert restrictive_dominates(AuthorityState.LIVE_NORMAL, [halt, perm_after]) is True

    # (b) permissive issued first (seq 1), HALT second (seq 2) — reversed order.
    perm_before = _permissive(issue_sequence=1)
    perm_first = OrderingEvent(
        event_id="perm", source_continuity_id="c", source_native_sequence=1
    )
    halt_second = OrderingEvent(
        event_id="halt", source_continuity_id="c", source_native_sequence=2
    )
    assert compare_order(perm_first, halt_second) is Ordering.BEFORE
    # Same outstanding set, reversed list order — dominance is unchanged (True).
    assert (
        restrictive_dominates(AuthorityState.LIVE_NORMAL, [perm_before, halt]) is True
    )


def test_contain_also_dominates() -> None:
    """A CONTAIN capability outstanding also dominates a permissive grant."""
    contain = issue_capability(
        capability_id="con-1", capability_type=CapabilityType.CONTAIN
    )
    assert restrictive_dominates(AuthorityState.LIVE_NORMAL, [contain]) is True


def test_no_restriction_no_dominance() -> None:
    """(guard fires) With no restrictive state / capability, a permissive grant is NOT dominated."""
    perm = _permissive(issue_sequence=1)
    assert restrictive_dominates(AuthorityState.LIVE_NORMAL, [perm]) is False
    assert restrictive_dominates(AuthorityState.LIVE_NORMAL, []) is False


def test_degraded_or_safer_state_dominates() -> None:
    """A state at DEGRADED_PROTECTIVE or safer dominates any permissive grant (rank >= 2)."""
    for state in (
        AuthorityState.DEGRADED_PROTECTIVE,
        AuthorityState.CONTAINED,
        AuthorityState.HALTED,
    ):
        assert restrictive_dominates(state, []) is True
    for state in (AuthorityState.LIVE_RESTRICTED, AuthorityState.LIVE_NORMAL):
        assert restrictive_dominates(state, []) is False


def test_restrictive_type_classifier() -> None:
    """HALT / CONTAIN are restrictive-dominating; permissive types are not."""
    assert is_restrictive_dominating_type(CapabilityType.HALT) is True
    assert is_restrictive_dominating_type(CapabilityType.CONTAIN) is True
    assert (
        is_restrictive_dominating_type(CapabilityType.NORMAL_RISK_INCREASING) is False
    )
    assert is_restrictive_dominating_type(None) is False


def test_safer_transition_always_allowed() -> None:
    """A transition toward an equal or safer state is always allowed (§7 line 237-239)."""
    assert safer_transition_allowed(AuthorityState.LIVE_NORMAL, AuthorityState.HALTED)
    assert safer_transition_allowed(
        AuthorityState.LIVE_NORMAL, AuthorityState.LIVE_NORMAL
    )
    # A less-safe direction is NOT a safer transition.
    assert (
        safer_transition_allowed(AuthorityState.HALTED, AuthorityState.LIVE_NORMAL)
        is False
    )


def test_permissive_transition_requires_current_epoch() -> None:
    """(canary) A less-safe transition needs epoch_current=True; None/False forbids it (§7 line 239)."""
    # HALTED -> LIVE_NORMAL is a permissive direction.
    assert (
        permissive_transition_allowed(
            AuthorityState.HALTED, AuthorityState.LIVE_NORMAL, epoch_current=True
        )
        is True
    )
    for epoch_current in (False, None):
        assert (
            permissive_transition_allowed(
                AuthorityState.HALTED,
                AuthorityState.LIVE_NORMAL,
                epoch_current=epoch_current,
            )
            is False
        )


def test_permissive_transition_allows_safer_direction_regardless() -> None:
    """A safer-or-equal direction is allowed even without a current epoch."""
    assert (
        permissive_transition_allowed(
            AuthorityState.LIVE_NORMAL, AuthorityState.HALTED, epoch_current=None
        )
        is True
    )


def test_restrictive_may_apply_when_stale_requires_authentic_and_cannot_enlarge() -> (
    None
):
    """(canary) A stale restrictive message applies only when authentic AND cannot-enlarge (§16.2)."""
    assert restrictive_may_apply_when_stale(authentic=True, cannot_enlarge=True) is True
    # Any None / False on either coordinate => not applicable (fail-closed).
    assert (
        restrictive_may_apply_when_stale(authentic=None, cannot_enlarge=True) is False
    )
    assert (
        restrictive_may_apply_when_stale(authentic=True, cannot_enlarge=None) is False
    )
    assert (
        restrictive_may_apply_when_stale(authentic=False, cannot_enlarge=True) is False
    )
    assert (
        restrictive_may_apply_when_stale(authentic=True, cannot_enlarge=False) is False
    )


def test_halt_denies_risk_increasing_rearm_and_limit_activation() -> None:
    """(canary §16.3) HALT denies new risk-increasing, re-arm, and limit activation."""
    assert halt_denies(CapabilityType.NORMAL_RISK_INCREASING) is True
    assert halt_denies(CapabilityType.REARM) is True
    assert halt_denies(CapabilityType.LIMIT_ACTIVATION) is True


def test_halt_preserves_protective_types() -> None:
    """HALT preserves protective / cancel / reconciliation / risk-reducing controls (§16.3)."""
    for captype in (
        CapabilityType.DEGRADED_PROTECTIVE,
        CapabilityType.CANCEL_REQUEST,
        CapabilityType.PROTECTIVE_CANCEL_OR_REPLACE,
        CapabilityType.NORMAL_RISK_REDUCING,
        CapabilityType.RECONCILIATION_ONLY,
    ):
        assert halt_denies(captype) is False
