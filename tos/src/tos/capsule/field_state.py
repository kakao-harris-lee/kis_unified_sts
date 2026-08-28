"""Five-valued field-state lattice and conservative aggregation (design §2.1).

ADR-002-018 §11 (line 302) fixes a five-valued lattice used to evaluate every
critical-input element. Design §2.1 additionally fixes the *restrictiveness*
ordering used by the conservative aggregations in §5:

    INVALID  >  CONFLICTED  >  STALE  >  UNKNOWN  >  VALID

``VALID`` is the single admitting state, reached only when every blocking
predicate passes (CII-INV-005, ADR line 166-168). All aggregation here is
monotone toward *more* restrictive: no operation in this module can move a set
of states toward ``VALID``.

This module is pure and has no third-party or ``shared.*`` dependency (design
§0.3 firewall closure minimisation).
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum


class FieldState(StrEnum):
    """The five-valued critical-input field state (ADR-002-018 §11 line 302)."""

    VALID = "VALID"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    INVALID = "INVALID"


# Restrictiveness rank: higher is more restrictive (design §2.1 lattice). Only
# ``VALID`` has rank 0, so any non-VALID state dominates it in ``worst``.
_RESTRICTIVENESS: dict[FieldState, int] = {
    FieldState.VALID: 0,
    FieldState.UNKNOWN: 1,
    FieldState.STALE: 2,
    FieldState.CONFLICTED: 3,
    FieldState.INVALID: 4,
}


def restrictiveness(state: FieldState) -> int:
    """Return the restrictiveness rank of ``state`` (higher is more restrictive).

    Args:
        state: The field state to rank.

    Returns:
        The integer rank per the design §2.1 lattice.
    """
    return _RESTRICTIVENESS[state]


def more_restrictive(left: FieldState, right: FieldState) -> FieldState:
    """Return the more restrictive of two states (design §2.1).

    Args:
        left: A field state.
        right: A field state.

    Returns:
        Whichever of ``left``/``right`` is more restrictive; ``left`` on a tie.
    """
    return left if _RESTRICTIVENESS[left] >= _RESTRICTIVENESS[right] else right


def worst(states: Iterable[FieldState]) -> FieldState:
    """Return the most restrictive state in ``states`` (design §2.1, §5.1).

    An empty iterable aggregates to ``VALID`` (the lattice identity / least
    restrictive element). Callers that must *not* treat "no evidence" as valid
    (fail-closed gates, §5.1/§6.2) supply an explicit ``UNKNOWN`` floor.

    Args:
        states: The field states to aggregate.

    Returns:
        The most restrictive ``FieldState`` observed, or ``VALID`` if empty.
    """
    result = FieldState.VALID
    for state in states:
        if _RESTRICTIVENESS[state] > _RESTRICTIVENESS[result]:
            result = state
    return result
