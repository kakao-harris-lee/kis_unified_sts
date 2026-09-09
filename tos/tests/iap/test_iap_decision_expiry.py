"""§1.2 커널 라운드 #1 — ``decision_unexpired`` 결정 만료 술어 (iap/predicates.py).

ADR-002-023 §12 항목 2 "unexpired" 는 Consumption Fencing 이 증명해야 하는 두 긍정 사실 중
하나이며, §18 은 "expiry prevents future consumption or send, releases nothing" 라 명시한다.
``tos.iap`` 는 여전히 clock-free — age bound 는 ``tos.time`` 이 만든 주입값이다. 동형 모델은
``tos.time.snapshot_age_admissible``: 어느 한쪽이라도 ``None`` ⇒ ``False`` (fail-closed), 음수
bound ⇒ ``False``, ``bound <= max`` 일 때만 ``True``.

``IndependentApprovalDecision`` 레코드는 이 아크에서 무편집 — covered 집합 변경은 기존 digest
픽스처를 전부 붕괴시키고, 발행시각은 소비 시점의 런타임 사실이라 §12 "receipt time" 대로
Consumption 증거 소관이다(design #40 §1.2).

Regime tag: authoring evidence only; closes no IAP-EV item (design #15 §1).
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.iap import decision_unexpired


def test_both_none_is_expired() -> None:
    """Neither the max nor the bound established => fail-closed expired."""
    assert (
        decision_unexpired(max_decision_age_ms=None, decision_age_bound_ms=None)
        is False
    )


def test_max_none_bound_concrete_is_expired() -> None:
    """No injected policy maximum => fail-closed expired, regardless of the bound."""
    assert (
        decision_unexpired(max_decision_age_ms=None, decision_age_bound_ms=5) is False
    )


def test_bound_none_max_concrete_is_expired() -> None:
    """An UNKNOWN age bound => fail-closed expired, regardless of the injected maximum."""
    assert (
        decision_unexpired(max_decision_age_ms=100, decision_age_bound_ms=None) is False
    )


def test_negative_bound_is_expired() -> None:
    """A negative age bound is a defect, never proof of freshness => fail-closed expired."""
    assert (
        decision_unexpired(max_decision_age_ms=100, decision_age_bound_ms=-1) is False
    )


def test_bound_equal_to_max_is_unexpired() -> None:
    """The boundary itself is admissible (``bound <= max``, not strictly less)."""
    assert (
        decision_unexpired(max_decision_age_ms=100, decision_age_bound_ms=100) is True
    )


def test_bound_exceeding_max_is_expired() -> None:
    """A bound strictly greater than the injected maximum is expired."""
    assert (
        decision_unexpired(max_decision_age_ms=100, decision_age_bound_ms=101) is False
    )


@given(bound=st.integers(0, 10**6), max_age=st.integers(0, 10**6))
def test_admissible_iff_within_max(bound: int, max_age: int) -> None:
    """A non-negative, concrete bound is unexpired iff it does not exceed the injected max."""
    assert decision_unexpired(
        max_decision_age_ms=max_age, decision_age_bound_ms=bound
    ) is (bound <= max_age)
