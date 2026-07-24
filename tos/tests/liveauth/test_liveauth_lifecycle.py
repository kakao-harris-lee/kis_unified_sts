"""Lifecycle transition legality + non-revival (§5.4; §8; REARM-AC-004).

Only the exact ADR §8 arrows are allowed; terminal states have no outgoing transition
(none returns to ACTIVE — non-revival); None on either side fails closed. An exhaustive
sweep over all ordered state pairs confirms the arrow table is neither too permissive nor
too restrictive. [REARM-EV-004]
"""

from __future__ import annotations

import itertools

import pytest
from tos.liveauth import LiveAuthorizationState, live_authorization_transition_allowed
from tos.liveauth.predicates import _LIVE_AUTHORIZATION_TRANSITIONS

_S = LiveAuthorizationState
_TERMINAL = (_S.DENIED, _S.SUSPENDED, _S.REVOKED, _S.EXPIRED, _S.SUPERSEDED)
_PROGRESSION = [
    (_S.REQUESTED, _S.VALIDATED),
    (_S.VALIDATED, _S.APPROVED),
    (_S.APPROVED, _S.ISSUED),
    (_S.ISSUED, _S.ACTIVE),
]


@pytest.mark.parametrize("from_state,to_state", _PROGRESSION)
def test_progression_arrows_allowed(
    from_state: LiveAuthorizationState, to_state: LiveAuthorizationState
) -> None:
    """(guard fires True) Each forward progression arrow is allowed."""
    assert live_authorization_transition_allowed(from_state, to_state) is True


@pytest.mark.parametrize("from_state", [_S.REQUESTED, _S.VALIDATED, _S.APPROVED])
def test_pre_issue_states_may_be_denied(from_state: LiveAuthorizationState) -> None:
    """(guard fires True) REQUESTED / VALIDATED / APPROVED may transition to DENIED."""
    assert live_authorization_transition_allowed(from_state, _S.DENIED) is True


@pytest.mark.parametrize("from_state", [_S.ISSUED, _S.ACTIVE])
@pytest.mark.parametrize(
    "to_state", [_S.SUSPENDED, _S.REVOKED, _S.EXPIRED, _S.SUPERSEDED]
)
def test_issued_active_may_be_invalidated(
    from_state: LiveAuthorizationState, to_state: LiveAuthorizationState
) -> None:
    """(guard fires True) ISSUED / ACTIVE may transition to each terminal invalidation."""
    assert live_authorization_transition_allowed(from_state, to_state) is True


@pytest.mark.parametrize("terminal", _TERMINAL)
def test_terminal_to_active_is_rejected(terminal: LiveAuthorizationState) -> None:
    """(canary non-revival §8.3) No terminal state may return to ACTIVE."""
    assert live_authorization_transition_allowed(terminal, _S.ACTIVE) is False


@pytest.mark.parametrize("terminal", _TERMINAL)
def test_terminal_has_no_outgoing_transition(terminal: LiveAuthorizationState) -> None:
    """(canary non-revival) A terminal state has NO outgoing transition to any state."""
    for to_state in _S:
        assert live_authorization_transition_allowed(terminal, to_state) is False


def test_none_either_side_is_rejected() -> None:
    """(canary) None on either side fails closed."""
    assert live_authorization_transition_allowed(None, _S.ACTIVE) is False
    assert live_authorization_transition_allowed(_S.ISSUED, None) is False
    assert live_authorization_transition_allowed(None, None) is False


def test_exhaustive_pair_sweep_matches_arrow_table() -> None:
    """(canary, exhaustive) Every ordered state pair is allowed iff it is a §8 arrow."""
    for from_state, to_state in itertools.product(_S, _S):
        expected = (from_state, to_state) in _LIVE_AUTHORIZATION_TRANSITIONS
        assert (
            live_authorization_transition_allowed(from_state, to_state) is expected
        ), f"({from_state}, {to_state}) mismatch"


def test_arrow_table_has_expected_cardinality() -> None:
    """The §8 arrow table has exactly 15 arrows (4 progression + 3 deny + 8 invalidation)."""
    assert len(_LIVE_AUTHORIZATION_TRANSITIONS) == 15


def test_no_self_loops() -> None:
    """(canary) No state transitions to itself (a lifecycle advance is never a no-op)."""
    for state in _S:
        assert live_authorization_transition_allowed(state, state) is False
