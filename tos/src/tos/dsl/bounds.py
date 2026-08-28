"""Bounded-evaluation state machine — DCE-INV-007 (design §3.4).

A pure state machine realizing DCE-INV-007 (ADR-DEV-001 §6 L170-172): exhausting a
time/resource bound degrades to **no-action** for the strategy's scope, never to an
unbounded stall or a partial, unrecorded action (RFC-008 §9; RFC-003 §13).

The bound is **symbolic and injected** (design §3.4/§7): a step counter, never a
numeric wall-time/CPU/memory value — VERIFICATION-PROFILE-002 carries **no**
DSL-evaluation bound, so inventing one is out of scope (numeric-bound approval is a
Phase-0 profile concern, design §7). Real metering + enforcement is layer 3
runtime (deferred, design §3.5). Phase 1 realizes only the transition:

    EVALUATING --(work_steps ≤ budget_steps)--> COMPLETED(outcome)
    EVALUATING --(work_steps >  budget_steps)--> BOUND_EXHAUSTED --> NoActionOutcome

There is no transition to a partial outcome and no non-terminating state, so a
bounded evaluation is total: it either completes or degrades to a recorded
no-action (never a stall).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design §firewall).
"""

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
    """Resolve a symbolic bounded evaluation to a terminal state (design §3.4).

    The bound is injected — ``budget_steps`` is a caller-supplied symbolic budget,
    never a hard-coded numeric (design §7). The evaluation *completes* iff the work
    fits the budget; otherwise it is *bound-exhausted*. It never returns a partial
    result and never leaves the machine ``EVALUATING`` (no unbounded stall).

    Args:
        work_steps: The symbolic amount of work the evaluation needs (``>= 0``).
        budget_steps: The injected symbolic budget (``>= 0``).

    Returns:
        ``COMPLETED`` if ``work_steps <= budget_steps``, else ``BOUND_EXHAUSTED``.

    Raises:
        ArtifactIntegrityError: If either count is negative (an ill-formed bound).
    """
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
    """Whether a terminal state degrades to no-action (DCE-INV-007).

    Args:
        state: The terminal bound state.

    Returns:
        ``True`` iff ``state`` is ``BOUND_EXHAUSTED``.
    """
    return state is BoundState.BOUND_EXHAUSTED


def select_outcome(
    state: BoundState,
    *,
    completed_outcome: Outcome,
    on_exhaustion: Callable[[], NoActionOutcome],
) -> Outcome:
    """Map a terminal bound state to the recorded Outcome (DCE-INV-007; design §3.4).

    A ``COMPLETED`` evaluation yields its computed outcome; a ``BOUND_EXHAUSTED`` one
    yields a recorded No-Action Outcome (built by ``on_exhaustion``). An
    ``EVALUATING`` state is rejected: an unresolved evaluation is exactly the
    unbounded stall / partial unrecorded action DCE-INV-007 forbids.

    Args:
        state: The terminal bound state.
        completed_outcome: The outcome to use when the evaluation completed.
        on_exhaustion: A zero-arg factory that builds the degraded No-Action
            Outcome (so this module needs no Capsule/version context).

    Returns:
        ``completed_outcome`` when ``COMPLETED``; a fresh No-Action Outcome when
        ``BOUND_EXHAUSTED``.

    Raises:
        ArtifactIntegrityError: If ``state`` is still ``EVALUATING``.
    """
    if state is BoundState.COMPLETED:
        return completed_outcome
    if state is BoundState.BOUND_EXHAUSTED:
        return on_exhaustion()
    raise ArtifactIntegrityError(
        "a bounded evaluation must terminate (COMPLETED or BOUND_EXHAUSTED); an "
        "EVALUATING state is the unbounded stall DCE-INV-007 forbids"
    )
