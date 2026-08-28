"""Bounded-evaluation property tests — DCE-EV-007 (design §6.1 / §3.4).

DCE-EV-007 (bounded ⇒ no-action): the pure symbolic state machine either
*completes* (work fits the injected budget) or degrades to a recorded **no-action**
— never a partial outcome and never an ``EVALUATING`` stall (RFC-008 §9). The bound
is symbolic (a step count), never an invented numeric wall-time/CPU value
(design §7 — VERIFICATION-PROFILE-002 carries no DSL-evaluation bound).

★ fail-open guard: **★2 producer-optimism** — a ``BoundOutcome`` cannot store a
``degraded_to_no_action`` flag that disagrees with the pure predicate, and cannot
record a non-terminal ``EVALUATING`` state.
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given
from pydantic import ValidationError
from tos.dsl import (
    ArtifactIntegrityError,
    BoundOutcome,
    BoundState,
    NoActionOutcome,
    Proposal,
    degrades_to_no_action,
    resolve_bound,
    select_outcome,
)

from ._dsl_strategies import (
    ENFORCEMENT_VERSION,
    SCHEME,
    issue_no_action,
    issue_proposal,
)

_COMPLETED_OUTCOME: Proposal = issue_proposal()
_DEGRADED_OUTCOME: NoActionOutcome = issue_no_action()


# ---------------------------------------------------------------------------
# resolve_bound + the transition (DCE-EV-007)
# ---------------------------------------------------------------------------


@given(
    work=st.integers(min_value=0, max_value=200),
    budget=st.integers(min_value=0, max_value=200),
)
def test_bounded_evaluation_completes_or_degrades_to_no_action(
    work: int, budget: int
) -> None:
    """Work within budget completes; over budget degrades to No-Action, never partial (DCE-EV-007)."""
    state = resolve_bound(work_steps=work, budget_steps=budget)
    outcome = select_outcome(
        state,
        completed_outcome=_COMPLETED_OUTCOME,
        on_exhaustion=lambda: _DEGRADED_OUTCOME,
    )
    if work <= budget:
        assert state is BoundState.COMPLETED
        assert degrades_to_no_action(state) is False
        assert outcome is _COMPLETED_OUTCOME
    else:
        assert state is BoundState.BOUND_EXHAUSTED
        assert degrades_to_no_action(state) is True
        # The degraded outcome is a first-class No-Action Outcome — not a partial
        # action and not the completed Proposal.
        assert isinstance(outcome, NoActionOutcome)
        assert outcome is _DEGRADED_OUTCOME


def test_degrades_to_no_action_only_on_exhaustion() -> None:
    """Only BOUND_EXHAUSTED degrades to no-action (positive + negative)."""
    assert degrades_to_no_action(BoundState.BOUND_EXHAUSTED) is True
    assert degrades_to_no_action(BoundState.COMPLETED) is False
    assert degrades_to_no_action(BoundState.EVALUATING) is False


@given(count=st.integers(min_value=-50, max_value=-1))
def test_negative_bound_counts_are_rejected(count: int) -> None:
    """A negative symbolic count is an ill-formed bound (design §3.4)."""
    with pytest.raises(ArtifactIntegrityError):
        resolve_bound(work_steps=count, budget_steps=0)
    with pytest.raises(ArtifactIntegrityError):
        resolve_bound(work_steps=0, budget_steps=count)


def test_select_outcome_rejects_evaluating_stall() -> None:
    """An unresolved (EVALUATING) evaluation is the stall DCE-INV-007 forbids."""
    with pytest.raises(ArtifactIntegrityError):
        select_outcome(
            BoundState.EVALUATING,
            completed_outcome=_COMPLETED_OUTCOME,
            on_exhaustion=lambda: _DEGRADED_OUTCOME,
        )


# ---------------------------------------------------------------------------
# ★2 producer-optimism — BoundOutcome flag must match the pure predicate
# ---------------------------------------------------------------------------


@given(
    state=st.sampled_from([BoundState.COMPLETED, BoundState.BOUND_EXHAUSTED]),
    flag=st.booleans(),
)
def test_bound_outcome_flag_must_match_terminal_state(
    state: BoundState, flag: bool
) -> None:
    """A BoundOutcome issues iff its degrade flag equals the predicate (★2 producer-optimism)."""
    expected = degrades_to_no_action(state)
    if flag == expected:
        bound = BoundOutcome.issue(
            scheme=SCHEME,
            bound_outcome_id="bound-p",
            terminal_state=state,
            degraded_to_no_action=flag,
            enforcement_mechanism_version=ENFORCEMENT_VERSION,
        )
        assert bound.terminal_state is state
        assert bound.degraded_to_no_action is expected
    else:
        with pytest.raises(ValidationError):
            BoundOutcome.issue(
                scheme=SCHEME,
                bound_outcome_id="bound-p",
                terminal_state=state,
                degraded_to_no_action=flag,
                enforcement_mechanism_version=ENFORCEMENT_VERSION,
            )


def test_bound_outcome_rejects_evaluating_state() -> None:
    """A recorded EVALUATING terminal state is unconstructable (DCE-INV-007 no stall)."""
    with pytest.raises(ValidationError):
        BoundOutcome.issue(
            scheme=SCHEME,
            bound_outcome_id="bound-stall",
            terminal_state=BoundState.EVALUATING,
            degraded_to_no_action=False,
            enforcement_mechanism_version=ENFORCEMENT_VERSION,
        )
