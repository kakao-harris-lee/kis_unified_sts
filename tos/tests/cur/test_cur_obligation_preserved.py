"""§1.3 커널 라운드 #1 — ``obligation_preserved`` 보존 의무 판정 (cur/predicates.py).

``cur.unknown_preserves_capacity`` 가 반환한 worst-credible-capacity 의무가 rcl 예약의 현재
capacity 상태 아래에서 여전히 지켜지는지 판정한다(design #40 §1.3; CUR-INV-011:183). cur 는
sibling edge 0(design #23 §0.3) — ``tos.rcl.CapacityState`` 를 import 하지 않으므로
"capacity-consuming" 상태 집합은 **주입**된다(호출측이 ``tos.rcl`` 을 import 해 채운다).

**계획 대비 편차**: 계획 §1.3 은 시그니처를
``obligation_preserved(obligation: int | None, reservation_state: CapacityState | None) -> bool``
로 제시했으나, ``tos/tests/cur/test_cur_import_closure.py`` 의 §7.1 allowlist(``{tos, tos.canonical,
tos.ordering, tos.cur}``)는 ``tos.rcl`` 을 명시적으로 금지 대상(``_FORBIDDEN_SIBLINGS``)에 올린다 —
타입 힌트를 위한 import 조차 위반이다. 따라서 ``reservation_state`` 는 (``CapacityState`` 가
``StrEnum`` 이라 문자열과 동등 비교되는 점을 이용해) 문자열로 받고, "capacity-consuming" 집합은
``capacity_consuming_states: frozenset[str]`` 로 주입한다.

Regime tag: authoring evidence only; closes no CUR-EV item (design #23 §1).
"""

from __future__ import annotations

import pytest
from tos.cur import obligation_preserved
from tos.rcl import CapacityState

#: Mirrors rcl's own ``_LIVE_COMMITTED_STATES`` (rcl/predicates.py:172-174) — every state except
#: ``RELEASED`` still consumes capacity (``_CONSERVATISM_RANK`` ranks ``RELEASED`` lowest/terminal
#: and every other state, including ``POSITION_CONSUMED``, strictly more conservative).
_LIVE_COMMITTED_STATE_VALUES = frozenset(
    state.value for state in CapacityState if state is not CapacityState.RELEASED
)


def test_no_obligation_asserted_is_trivially_preserved() -> None:
    """``obligation is None`` => no obligation was ever asserted => ``True``."""
    assert (
        obligation_preserved(
            None, None, capacity_consuming_states=_LIVE_COMMITTED_STATE_VALUES
        )
        is True
    )
    assert (
        obligation_preserved(
            None,
            CapacityState.RELEASED.value,
            capacity_consuming_states=_LIVE_COMMITTED_STATE_VALUES,
        )
        is True
    )


def test_concrete_obligation_with_unknown_state_is_not_preserved() -> None:
    """A concrete obligation cannot be confirmed preserved against an UNKNOWN state."""
    assert (
        obligation_preserved(
            1, None, capacity_consuming_states=_LIVE_COMMITTED_STATE_VALUES
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
        )
        is expected
    )
