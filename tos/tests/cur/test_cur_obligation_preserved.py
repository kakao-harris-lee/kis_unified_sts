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

**독립 리뷰 라운드 #1 finding #4 (MEDIUM)**: ``obligation is None`` 은 두 가지 다른 사실을 뭉갠다 —
"의무가 애초에 없었다"와 "의무는 있는데 그 **크기**를 모른다"(``worst_credible_capacity`` 자체가
관측되지 않음). 후자는 CUR-INV-011 상 UNKNOWN 이 restrictive 하다는 원칙에 따라 **보존되지
않는다고 판정**해야 한다. 이제 ``magnitude_unknown: bool`` 을 키워드 전용·기본값 없이 받아, 호출측이
이 둘을 명시적으로 구분하도록 강제한다.

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
    """(§1.3 review #4) ``magnitude_unknown=True`` forces ``False`` — UNKNOWN is restrictive.

    CUR-INV-011:183 treats an unknown obligation as more restrictive than a known one, and
    capacity-consuming — a magnitude that cannot be confirmed cannot be confirmed preserved
    either, even when every other input (a ``None`` obligation, a capacity-consuming state)
    would otherwise say "trivially preserved" or "preserved".
    """
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
