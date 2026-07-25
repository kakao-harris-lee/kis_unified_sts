"""Vocabulary invariants — verbatim members + coordinate non-collapse (design #15 §2.2).

The four approval-axis enums carry the ADR-002-023 verbatim members (§1 line 17 / §11 line 289 /
§12 / §5.7). Token overlap with orthostate ``IntentState`` is possible, but the values are
distinct types on distinct axes (§2.2(4)/§2.3) — asserted structurally (a distinct type, never a
sibling import).
"""

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
    """(§2.2(4)/§3.5) ApprovalResult.DENY is a distinct type/axis from orthostate IntentState.DENIED.

    The critical non-collapse: the two share the value token family "DEN…" but are distinct types
    on distinct axes (a decision-result vs an Intent lifecycle state). ``tos.iap`` never imports
    ``tos.orthostate`` (sibling edge 0), so a value from one can never be coerced onto the other.
    The causal boundary (DENY causes no Intent transition) is asserted in test_seam_orthostate.
    """
    # A distinct enum type — not the orthostate IntentState (which iap does not import here).
    assert type(ApprovalResult.DENY).__name__ == "ApprovalResult"
    assert ApprovalResult.DENY.value == "DENY"  # not "DENIED"
    assert ApprovalResult.DENY.value != "DENIED"
