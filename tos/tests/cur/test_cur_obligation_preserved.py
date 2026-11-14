"""§1.3 커널 라운드 #1 — ``obligation_preserved`` 보존 의무 판정 (cur/predicates.py)."""

from __future__ import annotations

import pytest
from tos.cur import obligation_preserved
from tos.rcl import CapacityState

_LIVE_COMMITTED_STATE_VALUES = frozenset(
    state.value for state in CapacityState if state is not CapacityState.RELEASED
)


def test_no_obligation_asserted_is_trivially_preserved() -> None:
    """``obligation is None`` and the magnitude is known (not unknown) => ``True``."""
    assert (
        obligation_preserved(
            None,
            None,
            capacity_consuming_states=_LIVE_COMMITTED_STATE_VALUES,
            magnitude_unknown=False,
        )
        is True
    )
    assert (
        obligation_preserved(
            None,
            CapacityState.RELEASED.value,
            capacity_consuming_states=_LIVE_COMMITTED_STATE_VALUES,
            magnitude_unknown=False,
        )
        is True
    )


def test_concrete_obligation_with_unknown_state_is_not_preserved() -> None:
    """A concrete obligation cannot be confirmed preserved against an UNKNOWN state."""
    assert (
        obligation_preserved(
            1,
            None,
            capacity_consuming_states=_LIVE_COMMITTED_STATE_VALUES,
            magnitude_unknown=False,
        )
        is False
    )


@pytest.mark.parametrize("state", list(CapacityState))
def test_every_capacity_state_member(state: CapacityState) -> None:
    """(§1.3 — «상태 전수») preserved iff the state is still capacity-consuming (not RELEASED)."""
    expected = state is not CapacityState.RELEASED
    assert (
        obligation_preserved(
            7,
            state.value,
            capacity_consuming_states=_LIVE_COMMITTED_STATE_VALUES,
            magnitude_unknown=False,
        )
        is expected
    )


@pytest.mark.parametrize(
    ("obligation", "reservation_state"),
    [
        (None, None),
        (None, CapacityState.RELEASED.value),
        (None, CapacityState.COMMITTED_UNBOUND.value),
    ],
)
def test_magnitude_unknown_is_never_preserved_regardless_of_other_inputs(
    obligation: int | None, reservation_state: str | None
) -> None:
    """(§1.3 review #4) ``magnitude_unknown=True`` forces ``False`` — UNKNOWN is restrictive."""
    assert (
        obligation_preserved(
            obligation,
            reservation_state,
            capacity_consuming_states=_LIVE_COMMITTED_STATE_VALUES,
            magnitude_unknown=True,
        )
        is False
    )


@pytest.mark.parametrize("state", list(CapacityState))
def test_magnitude_unknown_overrides_an_otherwise_capacity_consuming_state(
    state: CapacityState,
) -> None:
    """(§1.3 review #4) Even a live capacity-consuming state does not rescue an unknown magnitude."""
    assert (
        obligation_preserved(
            None,
            state.value,
            capacity_consuming_states=_LIVE_COMMITTED_STATE_VALUES,
            magnitude_unknown=True,
        )
        is False
    )


def test_magnitude_unknown_keyword_is_required() -> None:
    """(§1.3 review #4) ``magnitude_unknown`` is keyword-only with no default — callers must decide."""
    with pytest.raises(TypeError):
        obligation_preserved(  # type: ignore[call-arg]
            None, None, capacity_consuming_states=_LIVE_COMMITTED_STATE_VALUES
        )
