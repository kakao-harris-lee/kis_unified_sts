"""§1.3 커널 라운드 #1 — item 16 worst-credible-capacity 보존 의무 타입화.

``cur.unknown_preserves_capacity`` 의 반환값이 지금까지는 사유 문자열에만 접혀 있었다
(design #40 §0 서베이: gateway.py:1165-1178). 이 아크는 그 값을 ``VerifyItemVerdict`` 와
``GatewayEvidenceRecord`` 의 **필드**에 싣는다 — item 16(CURRENTNESS)이 non-ADMIT 일 때만, 그리고
그 값이 halt 를 유발한 첫 항목일 때 ``SEND_REFUSED`` 증거까지 전달한다(CUR-INV-011:183).

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


def test_send_refused_evidence_carries_no_obligation_for_a_non_currentness_halt() -> (
    None
):
    """(§1.3, both ways) A halt on a different item records no preserved-capacity obligation."""
    attempt, context = happy_context(construction=None)
    transport = full_fill_transport()
    gateway, sink = build_gateway(attempt=attempt, context=context, transport=transport)
    handoff = gateway(attempt)
    assert handoff.accepted_for_transmission is None
    refusal = sink.records[-1]
    assert refusal.kind == "SEND_REFUSED"
    assert refusal.item is SendVerifyItem.ORDER_CONSTRUCTION
    assert refusal.preserved_worst_credible_capacity is None


def test_gateway_evidence_record_rejects_the_field_only_via_the_model_default() -> None:
    """(§1.3) The field exists on ``GatewayEvidenceRecord`` and defaults to ``None``."""
    from tos.egressgw import GatewayEvidenceRecord

    record = GatewayEvidenceRecord(kind="SEND_REFUSED", attempt_id="a1")
    assert record.preserved_worst_credible_capacity is None
    record2 = GatewayEvidenceRecord(
        kind="SEND_REFUSED",
        attempt_id="a1",
        item=SendVerifyItem.CURRENTNESS,
        preserved_worst_credible_capacity=9,
    )
    assert record2.preserved_worst_credible_capacity == 9
