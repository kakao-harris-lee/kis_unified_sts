"""Truthy-sentinel structural seal regression (design #15 §4.7(나)/§2.2(1) — the critical seal, #14 M1 from the start)."""

from __future__ import annotations

import pytest
from tos.iap import (
    ApprovalAuthorityEffect,
    ApprovalResult,
    ConsumptionOutcome,
    ConsumptionStatus,
    MaterialityVerdict,
    approval_grants_no_authority,
    no_widening_no_union,
    request_is_complete,
    unknown_confines,
)

_ALL_SEALED_MEMBERS = [
    *ApprovalResult,
    *ConsumptionStatus,
    *MaterialityVerdict,
    *ConsumptionOutcome,
]


@pytest.mark.parametrize("member", _ALL_SEALED_MEMBERS)
def test_bool_raises_for_every_sealed_member(member: object) -> None:
    """(§4.7 canary iii) bool(r) raises TypeError for every decision / status / outcome member."""
    with pytest.raises(TypeError):
        bool(member)


@pytest.mark.parametrize("member", _ALL_SEALED_MEMBERS)
def test_if_result_would_raise_not_fail_open(member: object) -> None:
    """(§4.7 catastrophic-seal) A bare `if result:` raises rather than silently reading truthy."""
    with pytest.raises(TypeError):
        if member:  # noqa: SIM102 — the point is that this MUST raise, not pass
            pass


def test_is_comparison_works_both_ways() -> None:
    """(§4.7 canary iii-b) `is` identity comparison is intact in both directions."""
    assert ApprovalResult.APPROVE is ApprovalResult.APPROVE
    assert ApprovalResult.DENY is not ApprovalResult.APPROVE
    assert ApprovalResult.UNKNOWN is not ApprovalResult.APPROVE
    assert ConsumptionStatus.ELIGIBLE is ConsumptionStatus.ELIGIBLE
    assert ConsumptionStatus.CONSUMED is not ConsumptionStatus.ELIGIBLE
    assert ApprovalResult.APPROVE.value == "APPROVE"
    assert ConsumptionStatus.ELIGIBLE.value == "ELIGIBLE"


def test_sealed_enums_are_hashable_and_set_safe() -> None:
    """The seal must not break hashing / set membership (used by conflicting_evaluators_unknown)."""
    assert (
        len({ApprovalResult.APPROVE, ApprovalResult.DENY, ApprovalResult.APPROVE}) == 2
    )
    assert ApprovalResult.APPROVE in {ApprovalResult.APPROVE}


def test_is_approve_gate_rejects_denials() -> None:
    """(§4.7 consume gate) Only APPROVE passes `result is ApprovalResult.APPROVE`."""
    from ._iap_strategies import complete_request, issue_policy, minimal_request

    approve = request_is_complete(complete_request(), issue_policy())
    deny = request_is_complete(minimal_request(), issue_policy())
    unknown = request_is_complete(complete_request(), None)

    assert (approve is ApprovalResult.APPROVE) is True
    assert (deny is ApprovalResult.APPROVE) is False
    assert (unknown is ApprovalResult.APPROVE) is False


def test_bool_predicate_is_true_gate() -> None:
    """(§4.7(나)) A `bool | None` predicate is gated `is True` — None / False both reject."""
    grants = approval_grants_no_authority(ApprovalAuthorityEffect())
    assert (grants is True) is True

    widened = no_widening_no_union(
        single_exact_decision=None, no_union_of_narrower=True
    )
    assert (widened is True) is False

    confined = unknown_confines(any_unknown_state=True, capacity_available=True)
    assert (confined is True) is True
