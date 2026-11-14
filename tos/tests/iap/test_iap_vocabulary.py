"""Vocabulary invariants — verbatim members + coordinate non-collapse (design #15 §2.2)."""

from __future__ import annotations

from tos.iap import (
    ApprovalResult,
    ConsumptionOutcome,
    ConsumptionStatus,
    MaterialityVerdict,
)


def test_approval_result_has_three_verbatim_members() -> None:
    """(§1 line 17 / §11 line 289) APPROVE / DENY / UNKNOWN — the verbatim result set."""
    assert [r.value for r in ApprovalResult] == ["APPROVE", "DENY", "UNKNOWN"]


def test_consumption_status_has_two_verbatim_members() -> None:
    """(§12) ELIGIBLE / CONSUMED — the single-use decision-consumption dimension."""
    assert [s.value for s in ConsumptionStatus] == ["ELIGIBLE", "CONSUMED"]


def test_materiality_verdict_has_three_verbatim_members() -> None:
    """(§5.7 line 124-126) MATERIAL / IMMATERIAL / UNKNOWN."""
    assert [v.value for v in MaterialityVerdict] == [
        "MATERIAL",
        "IMMATERIAL",
        "UNKNOWN",
    ]


def test_consumption_outcome_members() -> None:
    """(§6.2) The five single-use consumption outcomes."""
    assert [o.value for o in ConsumptionOutcome] == [
        "CONSUMED_NEW",
        "IDEMPOTENT_REPLAY",
        "REJECTED_INELIGIBLE",
        "REJECTED_CONFLICT",
        "REJECTED_REUSE",
    ]


def test_approval_result_deny_is_not_intent_state_denied() -> None:
    """(§2.2(4)/§3.5) ApprovalResult.DENY is a distinct type/axis from orthostate IntentState.DENIED."""
    assert type(ApprovalResult.DENY).__name__ == "ApprovalResult"
    assert ApprovalResult.DENY.value == "DENY"
    assert ApprovalResult.DENY.value != "DENIED"
