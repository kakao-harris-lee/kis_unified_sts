"""Session state machine — terminal non-revival property (design #17 §4.2/§10; SBR-INV-013).

Regime tag: predicate / model substrate only; SBR-EV substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.sbr import SessionState, is_terminal_state, session_transition_allowed

# test-only imports of the private tables (design #17 §7 — test import ∉ package closure).
from tos.sbr.state import _SESSION_TRANSITIONS, _TERMINAL_STATES

_SESSION_STATES = st.sampled_from(list(SessionState))
_READY_STATES = frozenset({SessionState.READY, SessionState.READY_RESTRICTED})


def test_linear_progression_path_is_allowed() -> None:
    """(§10 line 281-283) The TRIGGERED -> … -> DECISION_CANDIDATE -> READY path is allowed."""
    path = [
        SessionState.TRIGGERED,
        SessionState.FENCING,
        SessionState.INVENTORYING,
        SessionState.RECONCILING,
        SessionState.VALIDATING,
        SessionState.DECISION_CANDIDATE,
        SessionState.READY,
    ]
    for frm, to in zip(path, path[1:]):
        assert session_transition_allowed(frm, to) is True


def test_terminal_set_matches_the_adr() -> None:
    """(§10 line 293) The terminal set is exactly {NOT_READY, INVALIDATED, ABORTED, EXPIRED, SUPERSEDED}."""
    assert (
        frozenset(
            {
                SessionState.NOT_READY,
                SessionState.INVALIDATED,
                SessionState.ABORTED,
                SessionState.EXPIRED,
                SessionState.SUPERSEDED,
            }
        )
        == _TERMINAL_STATES
    )


@given(_SESSION_STATES)
def test_terminal_states_have_no_outgoing_arrow(state: SessionState) -> None:
    """(§10 line 293 property) A terminal state cannot transition to ANY state (non-revival)."""
    if not is_terminal_state(state):
        return
    for target in SessionState:
        assert session_transition_allowed(state, target) is False


@given(_SESSION_STATES, _SESSION_STATES)
def test_no_terminal_reaches_a_ready_state(frm: SessionState, to: SessionState) -> None:
    """(§10 line 293) No terminal state ever reaches READY / READY_RESTRICTED."""
    if is_terminal_state(frm) and to in _READY_STATES:
        assert session_transition_allowed(frm, to) is False


@given(_SESSION_STATES, _SESSION_STATES)
def test_allowed_iff_in_the_transition_table(
    frm: SessionState, to: SessionState
) -> None:
    """(property) session_transition_allowed is exactly membership in the §10 arrow table."""
    assert session_transition_allowed(frm, to) is ((frm, to) in _SESSION_TRANSITIONS)


def test_ready_states_may_only_be_invalidated_expired_superseded() -> None:
    """(§10 line 285) A ready state may only move to INVALIDATED / EXPIRED / SUPERSEDED."""
    for ready in _READY_STATES:
        allowed = {to for (frm, to) in _SESSION_TRANSITIONS if frm is ready}
        assert allowed == frozenset(
            {SessionState.INVALIDATED, SessionState.EXPIRED, SessionState.SUPERSEDED}
        )


def test_no_arrow_re_enters_candidacy_from_a_ready_state() -> None:
    """(§10) A ready state never re-enters DECISION_CANDIDATE / an earlier progress state."""
    for ready in _READY_STATES:
        assert (
            session_transition_allowed(ready, SessionState.DECISION_CANDIDATE) is False
        )
        assert session_transition_allowed(ready, SessionState.VALIDATING) is False
