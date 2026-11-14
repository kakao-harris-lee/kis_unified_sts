"""Five-valued field-state lattice and conservative aggregation (design §2.1)."""

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


_RESTRICTIVENESS: dict[FieldState, int] = {
    FieldState.VALID: 0,
    FieldState.UNKNOWN: 1,
    FieldState.STALE: 2,
    FieldState.CONFLICTED: 3,
    FieldState.INVALID: 4,
}


def restrictiveness(state: FieldState) -> int:
    """Return the restrictiveness rank of ``state`` (higher is more restrictive)."""
    return _RESTRICTIVENESS[state]


def more_restrictive(left: FieldState, right: FieldState) -> FieldState:
    """Return the more restrictive of two states (design §2.1)."""
    return left if _RESTRICTIVENESS[left] >= _RESTRICTIVENESS[right] else right


def worst(states: Iterable[FieldState]) -> FieldState:
    """Return the most restrictive state in ``states`` (design §2.1, §5.1)."""
    result = FieldState.VALID
    for state in states:
        if _RESTRICTIVENESS[state] > _RESTRICTIVENESS[result]:
            result = state
    return result
