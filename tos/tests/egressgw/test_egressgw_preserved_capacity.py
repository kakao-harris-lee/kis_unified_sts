"""§1.3 커널 라운드 #1 — item 16 worst-credible-capacity 보존 의무 타입화.

``cur.unknown_preserves_capacity`` 의 반환값이 지금까지는 사유 문자열에만 접혀 있었다
(design #40 §0 서베이: gateway.py:1165-1178). 이 아크는 그 값을 ``VerifyItemVerdict`` 와
``GatewayEvidenceRecord`` 의 **필드**에 싣는다 — item 16(CURRENTNESS)이 non-ADMIT 일 때, item 16
이 halt 를 유발했는지와 **무관하게** ``SEND_REFUSED`` 증거까지 전달한다(CUR-INV-011:183).

독립 리뷰 라운드 #1 finding #1(HIGH): 이전 구현은 ``verification.halt_item is CURRENTNESS`` 일
때만 값을 옮겼다 — item 16 이 non-ADMIT 이어도 더 이른 항목이 먼저 halt 를 유발하면 의무가 조용히
사라졌다(``CapacityObligationRecorder`` 는 ``None`` 에 no-op — 완전한 fail-silent). 17개 항목은
항상 전부 평가되므로(design #34 §4.1) item 16 자신의 verdict 는 어느 항목이 halt 를 유발했는지와
무관하게 항상 존재한다 — 이 아크는 그 verdict 를 무조건 스캔해 전달한다.

Regime tag: authoring evidence only; closes no EV (design #34 §1.1 / design #40 §1.3).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.cur import ProofResult
from tos.egressgw import (
    SendHaltReason,
    SendVerifyItem,
    VerifyDisposition,
    VerifyItemVerdict,
    VerifyOutcome,
    verify_send_boundary,
)

from ._egressgw_fixtures import build_gateway, full_fill_transport, happy_context


def test_preserved_capacity_only_constructable_for_item_16() -> None:
    """(§1.3) A non-None preserved obligation on any item but CURRENTNESS is unconstructable."""
    with pytest.raises(ValidationError, match="preserved worst-credible capacity"):
        VerifyItemVerdict(
            item=SendVerifyItem.ORDER_CONSTRUCTION,
            disposition=VerifyDisposition.REALIZED_STRUCTURAL,
            outcome=VerifyOutcome.SATISFIED,
            preserved_worst_credible_capacity=5,
        )


def test_preserved_capacity_constructable_for_currentness() -> None:
    """(§1.3, both ways) Item 16 may carry the obligation."""
    verdict = VerifyItemVerdict(
        item=SendVerifyItem.CURRENTNESS,
        disposition=VerifyDisposition.REALIZED_STRUCTURAL,
        outcome=VerifyOutcome.DENIED,
        preserved_worst_credible_capacity=3,
    )
    assert verdict.preserved_worst_credible_capacity == 3


def test_unknown_currentness_carries_the_preserved_obligation_on_the_verdict() -> None:
    """(§1.3) An UNKNOWN item-16 outcome records the worst-credible capacity on the verdict."""
    attempt, context = happy_context(egress_currentness_result=None)
    verification = verify_send_boundary(attempt=attempt, context=context)
    currentness_verdicts = [
        v for v in verification.verdicts if v.item is SendVerifyItem.CURRENTNESS
    ]
    assert len(currentness_verdicts) == 1
    verdict = currentness_verdicts[0]
    assert verdict.outcome is VerifyOutcome.UNKNOWN
    assert verdict.preserved_worst_credible_capacity == context.worst_credible_capacity


def test_denied_currentness_carries_the_preserved_obligation_on_the_verdict() -> None:
    """(§1.3) A DENIED item-16 outcome records the worst-credible capacity on the verdict."""
    attempt, context = happy_context(egress_currentness_result=ProofResult.RESTRICTED)
    verification = verify_send_boundary(attempt=attempt, context=context)
    currentness_verdicts = [
        v for v in verification.verdicts if v.item is SendVerifyItem.CURRENTNESS
    ]
    assert len(currentness_verdicts) == 1
    verdict = currentness_verdicts[0]
    assert verdict.outcome is VerifyOutcome.DENIED
    assert verdict.preserved_worst_credible_capacity == context.worst_credible_capacity


def test_satisfied_currentness_carries_no_obligation() -> None:
    """(§1.3, both ways) A SATISFIED item 16 records no preserved-capacity obligation."""
    attempt, context = happy_context()
    verification = verify_send_boundary(attempt=attempt, context=context)
    currentness_verdicts = [
        v for v in verification.verdicts if v.item is SendVerifyItem.CURRENTNESS
    ]
    assert len(currentness_verdicts) == 1
    assert currentness_verdicts[0].outcome is VerifyOutcome.SATISFIED
    assert currentness_verdicts[0].preserved_worst_credible_capacity is None


@pytest.mark.parametrize(
    "override",
    [
        {"egress_currentness_result": None},
        {"egress_currentness_result": ProofResult.RESTRICTED},
    ],
    ids=["unknown", "denied"],
)
def test_send_refused_evidence_carries_the_preserved_obligation(
    override: dict[str, object],
) -> None:
    """(§1.3) ``_halt`` transfers item 16's preserved obligation onto the SEND_REFUSED evidence."""
    attempt, context = happy_context(**override)
    transport = full_fill_transport()
    gateway, sink = build_gateway(attempt=attempt, context=context, transport=transport)
    handoff = gateway(attempt)
    assert handoff.accepted_for_transmission is None
    refusal = sink.records[-1]
    assert refusal.kind == "SEND_REFUSED"
    assert refusal.item is SendVerifyItem.CURRENTNESS
    assert refusal.halt_reason in {
        SendHaltReason.VERIFY_ITEM_DENIED,
        SendHaltReason.VERIFY_ITEM_UNKNOWN,
    }
    assert refusal.preserved_worst_credible_capacity == context.worst_credible_capacity


def test_send_refused_evidence_carries_no_obligation_when_item_16_is_satisfied() -> (
    None
):
    """(§1.3, both ways) A halt on a different item, with item 16 SATISFIED, carries no obligation.

    The obligation is ``None`` here **only** because item 16's own outcome is SATISFIED
    (currentness positively ``ADMIT`` — nothing to preserve), not because a different item
    halted first. See ``test_send_refused_evidence_carries_the_obligation_from_a_non_halting_item_16``
    for the co-occurring-failure case, where item 16 *does* author an obligation while a
    different item halts, and the obligation IS carried (review round #1 finding #1).
    """
    attempt, context = happy_context(construction=None)
    transport = full_fill_transport()
    gateway, sink = build_gateway(attempt=attempt, context=context, transport=transport)
    handoff = gateway(attempt)
    assert handoff.accepted_for_transmission is None
    refusal = sink.records[-1]
    assert refusal.kind == "SEND_REFUSED"
    assert refusal.item is SendVerifyItem.ORDER_CONSTRUCTION
    currentness_verdicts = [
        v
        for verification in gateway.verifications
        for v in verification.verdicts
        if v.item is SendVerifyItem.CURRENTNESS
    ]
    assert len(currentness_verdicts) == 1
    assert currentness_verdicts[0].outcome is VerifyOutcome.SATISFIED
    assert refusal.preserved_worst_credible_capacity is None


def test_send_refused_evidence_carries_the_obligation_from_a_non_halting_item_16() -> (
    None
):
    """(§1.3, review round #1 finding #1 — HIGH) Item 16's obligation survives a co-occurring halt.

    All 17 verify items are always evaluated, and only then does the loop pick the first
    non-admitting one as ``halt_item`` (``gateway.py:548-579``). Before this fix, ``_halt``
    transferred the obligation only under ``if verification.halt_item is
    SendVerifyItem.CURRENTNESS`` — so when ``ORDER_CONSTRUCTION`` fails alongside a non-ADMIT
    item 16, item 16 still computed and stored the obligation on its own verdict, but the
    ``SEND_REFUSED`` evidence recorded ``None``. Downstream, ``CapacityObligationRecorder``
    no-ops on ``None`` (``tos_runtime/rcl/obligation.py``): no evidence row, no kernel verdict,
    no halt — exactly the fail-silent class the lane exists to close.
    """
    attempt, context = happy_context(construction=None, egress_currentness_result=None)
    transport = full_fill_transport()
    gateway, sink = build_gateway(attempt=attempt, context=context, transport=transport)
    handoff = gateway(attempt)
    assert handoff.accepted_for_transmission is None
    verification = gateway.verifications[-1]
    assert verification.halt_item is SendVerifyItem.ORDER_CONSTRUCTION
    currentness_verdicts = [
        v for v in verification.verdicts if v.item is SendVerifyItem.CURRENTNESS
    ]
    assert len(currentness_verdicts) == 1
    assert currentness_verdicts[0].outcome is VerifyOutcome.UNKNOWN
    assert currentness_verdicts[0].preserved_worst_credible_capacity == 1
    refusal = sink.records[-1]
    assert refusal.kind == "SEND_REFUSED"
    assert refusal.item is SendVerifyItem.ORDER_CONSTRUCTION
    assert (
        refusal.preserved_worst_credible_capacity
        == context.worst_credible_capacity
        == 1
    )


def test_magnitude_unknown_only_constructable_for_item_16() -> None:
    """(§1.3 review #4) A magnitude-unknown flag on any item but CURRENTNESS is unconstructable."""
    with pytest.raises(ValidationError, match="magnitude-unknown"):
        VerifyItemVerdict(
            item=SendVerifyItem.ORDER_CONSTRUCTION,
            disposition=VerifyDisposition.REALIZED_STRUCTURAL,
            outcome=VerifyOutcome.SATISFIED,
            preserved_obligation_magnitude_unknown=True,
        )


def test_magnitude_unknown_rejected_alongside_a_concrete_obligation() -> None:
    """(§1.3 review #4) A magnitude-unknown flag contradicts a concrete preserved capacity."""
    with pytest.raises(ValidationError, match="magnitude-unknown"):
        VerifyItemVerdict(
            item=SendVerifyItem.CURRENTNESS,
            disposition=VerifyDisposition.REALIZED_STRUCTURAL,
            outcome=VerifyOutcome.DENIED,
            preserved_worst_credible_capacity=5,
            preserved_obligation_magnitude_unknown=True,
        )


def test_magnitude_unknown_constructable_for_currentness_with_no_concrete_obligation() -> (
    None
):
    """(§1.3 review #4) Item 16 may flag magnitude-unknown when it carries no concrete number."""
    verdict = VerifyItemVerdict(
        item=SendVerifyItem.CURRENTNESS,
        disposition=VerifyDisposition.REALIZED_STRUCTURAL,
        outcome=VerifyOutcome.UNKNOWN,
        preserved_obligation_magnitude_unknown=True,
    )
    assert verdict.preserved_obligation_magnitude_unknown is True
    assert verdict.preserved_worst_credible_capacity is None


@pytest.mark.parametrize(
    "override",
    [
        {"egress_currentness_result": None},
        {"egress_currentness_result": ProofResult.RESTRICTED},
    ],
    ids=["unknown", "denied"],
)
def test_item_16_non_admit_with_unknown_worst_credible_capacity_flags_magnitude_unknown(
    override: dict[str, object],
) -> None:
    """(§1.3 review #4) A non-admit item 16 with no observed worst-credible capacity flags it.

    ``context.worst_credible_capacity is None`` means the obligation's own **magnitude** was
    never observed — distinct from "no obligation asserted". The recorder must be able to tell
    the two apart (independent review round #1 finding #4).
    """
    attempt, context = happy_context(worst_credible_capacity=None, **override)
    verification = verify_send_boundary(attempt=attempt, context=context)
    currentness_verdicts = [
        v for v in verification.verdicts if v.item is SendVerifyItem.CURRENTNESS
    ]
    assert len(currentness_verdicts) == 1
    verdict = currentness_verdicts[0]
    assert verdict.preserved_worst_credible_capacity is None
    assert verdict.preserved_obligation_magnitude_unknown is True


def test_satisfied_currentness_never_flags_magnitude_unknown_even_with_no_observed_capacity() -> (
    None
):
    """(§1.3 review #4) A SATISFIED item 16 never flags magnitude-unknown, obligation or not."""
    attempt, context = happy_context(worst_credible_capacity=None)
    verification = verify_send_boundary(attempt=attempt, context=context)
    currentness_verdicts = [
        v for v in verification.verdicts if v.item is SendVerifyItem.CURRENTNESS
    ]
    assert len(currentness_verdicts) == 1
    assert currentness_verdicts[0].outcome is VerifyOutcome.SATISFIED
    assert currentness_verdicts[0].preserved_obligation_magnitude_unknown is False


def test_send_refused_evidence_carries_the_magnitude_unknown_flag() -> None:
    """(§1.3 review #4) ``_halt`` transfers the magnitude-unknown flag onto SEND_REFUSED too."""
    attempt, context = happy_context(
        construction=None, egress_currentness_result=None, worst_credible_capacity=None
    )
    transport = full_fill_transport()
    gateway, sink = build_gateway(attempt=attempt, context=context, transport=transport)
    handoff = gateway(attempt)
    assert handoff.accepted_for_transmission is None
    refusal = sink.records[-1]
    assert refusal.kind == "SEND_REFUSED"
    assert refusal.item is SendVerifyItem.ORDER_CONSTRUCTION
    assert refusal.preserved_worst_credible_capacity is None
    assert refusal.preserved_obligation_magnitude_unknown is True


def test_gateway_evidence_record_rejects_the_field_only_via_the_model_default() -> None:
    """(§1.3) The field exists on ``GatewayEvidenceRecord`` and defaults to ``None``."""
    from tos.egressgw import GatewayEvidenceRecord

    record = GatewayEvidenceRecord(kind="SEND_REFUSED", attempt_id="a1")
    assert record.preserved_worst_credible_capacity is None
    assert record.preserved_obligation_magnitude_unknown is False
    record2 = GatewayEvidenceRecord(
        kind="SEND_REFUSED",
        attempt_id="a1",
        item=SendVerifyItem.CURRENTNESS,
        preserved_worst_credible_capacity=9,
    )
    assert record2.preserved_worst_credible_capacity == 9
    record3 = GatewayEvidenceRecord(
        kind="SEND_REFUSED",
        attempt_id="a1",
        item=SendVerifyItem.CURRENTNESS,
        preserved_obligation_magnitude_unknown=True,
    )
    assert record3.preserved_obligation_magnitude_unknown is True
