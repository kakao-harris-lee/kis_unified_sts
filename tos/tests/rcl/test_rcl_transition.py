"""Capacity-state conservatism lattice (RCL design §5.4; ADR-002-002 §10.2).

Less-conservative transitions require a strong cause; timeout / absence / operator
assumption may only increase conservatism. RELEASED is reachable only under the
final-quantity proof rule (INV-007) and is terminal.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.rcl import WEAK_CAUSES, CapacityState, TransitionCause, transition_allowed


def test_released_unreachable_without_final_quantity_proof() -> None:
    """(canary) RELEASED is reachable only under FINAL_QUANTITY_PROOF (INV-007)."""
    frm = CapacityState.POSITION_CONSUMED
    for cause in TransitionCause:
        allowed = transition_allowed(frm, CapacityState.RELEASED, cause)
        assert allowed is (cause is TransitionCause.FINAL_QUANTITY_PROOF)


def test_released_via_timeout_blocked() -> None:
    """(canary) A timeout alone cannot release capacity."""
    assert (
        transition_allowed(
            CapacityState.POSITION_CONSUMED,
            CapacityState.RELEASED,
            TransitionCause.TIMEOUT,
        )
        is False
    )


def test_released_is_terminal() -> None:
    """No transition may leave RELEASED (terminal for the reservation, §10.1 line 562)."""
    for to_state in CapacityState:
        for cause in TransitionCause:
            assert transition_allowed(CapacityState.RELEASED, to_state, cause) is False


def test_quarantined_to_less_conservative_via_timeout_blocked() -> None:
    """(canary) QUARANTINED_UNKNOWN -> less conservative is blocked by a weak cause."""
    for weak in WEAK_CAUSES:
        assert (
            transition_allowed(
                CapacityState.QUARANTINED_UNKNOWN, CapacityState.POTENTIALLY_LIVE, weak
            )
            is False
        )


def test_quarantined_to_less_conservative_allowed_with_strong_cause() -> None:
    """A less-conservative move IS allowed under a strong cause (not RELEASED)."""
    assert (
        transition_allowed(
            CapacityState.QUARANTINED_UNKNOWN,
            CapacityState.POTENTIALLY_LIVE,
            TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        )
        is True
    )


@given(weak=st.sampled_from(sorted(WEAK_CAUSES)))
def test_weak_causes_may_only_increase_conservatism(weak: TransitionCause) -> None:
    """Weak causes may increase conservatism but never decrease it (§10.2 line 574)."""
    # Increase (COMMITTED_UNBOUND -> QUARANTINED_UNKNOWN) is allowed under a weak cause.
    assert (
        transition_allowed(
            CapacityState.COMMITTED_UNBOUND, CapacityState.QUARANTINED_UNKNOWN, weak
        )
        is True
    )
    # Decrease (QUARANTINED_UNKNOWN -> COMMITTED_UNBOUND) is blocked under a weak cause.
    assert (
        transition_allowed(
            CapacityState.QUARANTINED_UNKNOWN, CapacityState.COMMITTED_UNBOUND, weak
        )
        is False
    )


@given(cause=st.sampled_from(list(TransitionCause)))
def test_increasing_conservatism_allowed_for_any_cause(cause: TransitionCause) -> None:
    """Increasing conservatism is allowed regardless of cause (never blocked)."""
    assert (
        transition_allowed(
            CapacityState.COMMITTED_UNBOUND, CapacityState.QUARANTINED_UNKNOWN, cause
        )
        is True
    )
