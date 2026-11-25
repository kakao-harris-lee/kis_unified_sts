"""Bounded-evaluation state machine — DCE-INV-007 (design §3.4)."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from tos.dsl._base import ArtifactIntegrityError
from tos.dsl.outcome import NoActionOutcome, Outcome


class BoundState(StrEnum):
    """The terminal (or in-progress) state of a bounded evaluation (design §3.4)."""

    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    BOUND_EXHAUSTED = "BOUND_EXHAUSTED"


def resolve_bound(*, work_steps: int, budget_steps: int) -> BoundState:
    """Resolve a symbolic bounded evaluation to a terminal state (design §3.4)."""
    if work_steps < 0 or budget_steps < 0:
        raise ArtifactIntegrityError(
            "work_steps and budget_steps must be non-negative symbolic counts "
            f"(work_steps={work_steps}, budget_steps={budget_steps})"
        )
    return (
        BoundState.COMPLETED
        if work_steps <= budget_steps
        else BoundState.BOUND_EXHAUSTED
    )


def degrades_to_no_action(state: BoundState) -> bool:
    """Whether a terminal state degrades to no-action (DCE-INV-007)."""
    return state is BoundState.BOUND_EXHAUSTED


def select_outcome(
    state: BoundState,
    *,
    completed_outcome: Outcome,
    on_exhaustion: Callable[[], NoActionOutcome],
) -> Outcome:
    """Map a terminal bound state to the recorded Outcome (DCE-INV-007; design §3.4)."""
    if state is BoundState.COMPLETED:
        return completed_outcome
    if state is BoundState.BOUND_EXHAUSTED:
        return on_exhaustion()
    raise ArtifactIntegrityError(
        "a bounded evaluation must terminate (COMPLETED or BOUND_EXHAUSTED); an "
        "EVALUATING state is the unbounded stall DCE-INV-007 forbids"
    )
