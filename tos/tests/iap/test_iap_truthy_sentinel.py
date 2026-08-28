"""Truthy-sentinel structural seal regression (design #15 §4.7(나)/§2.2(1) — the critical seal, #14 M1 from the start).

Adopted from the start (before any review): every decision / verdict / status / outcome enum is a
*truthy-untestable* type — ``__bool__`` raises ``TypeError`` on every member — so a future
consumer's ``if result:`` misuse surfaces as a runtime error, never a silent fail-open on the
truthy denial strings (``DENY`` / ``UNKNOWN`` / ``CONSUMED`` / a rejected outcome). The §4.7 canary
requires: (a) ``bool(r)`` raises for every member, (b) ``is`` comparison works both ways, (c) the
positive-identity gate rejects the denial values, and (d) the ``bool | None`` predicates are
consumed ``is True``.
"""

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


# ---------------------------------------------------------------------------
# (a) bool(r) raises TypeError for every member of every sealed enum
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# (b) `is` comparison works both ways (the seal does not break identity)
# ---------------------------------------------------------------------------


def test_is_comparison_works_both_ways() -> None:
    """(§4.7 canary iii-b) `is` identity comparison is intact in both directions."""
    assert ApprovalResult.APPROVE is ApprovalResult.APPROVE
    assert ApprovalResult.DENY is not ApprovalResult.APPROVE
    assert ApprovalResult.UNKNOWN is not ApprovalResult.APPROVE
    assert ConsumptionStatus.ELIGIBLE is ConsumptionStatus.ELIGIBLE
    assert ConsumptionStatus.CONSUMED is not ConsumptionStatus.ELIGIBLE
    # Still StrEnum with the verbatim value (used in digests via model_dump, never via bool).
    assert ApprovalResult.APPROVE.value == "APPROVE"
    assert ConsumptionStatus.ELIGIBLE.value == "ELIGIBLE"


def test_sealed_enums_are_hashable_and_set_safe() -> None:
    """The seal must not break hashing / set membership (used by conflicting_evaluators_unknown)."""
    assert (
        len({ApprovalResult.APPROVE, ApprovalResult.DENY, ApprovalResult.APPROVE}) == 2
    )
    assert ApprovalResult.APPROVE in {ApprovalResult.APPROVE}


# ---------------------------------------------------------------------------
# (c) the positive-identity gate rejects both denial values
# ---------------------------------------------------------------------------


def test_is_approve_gate_rejects_denials() -> None:
    """(§4.7 consume gate) Only APPROVE passes `result is ApprovalResult.APPROVE`."""
    from ._iap_strategies import complete_request, issue_policy, minimal_request

    approve = request_is_complete(complete_request(), issue_policy())
    deny = request_is_complete(minimal_request(), issue_policy())
    unknown = request_is_complete(complete_request(), None)

    assert (approve is ApprovalResult.APPROVE) is True
    assert (deny is ApprovalResult.APPROVE) is False
    assert (unknown is ApprovalResult.APPROVE) is False


# ---------------------------------------------------------------------------
# (d) the `bool | None` predicates are consumed `is True`
# ---------------------------------------------------------------------------


def test_bool_predicate_is_true_gate() -> None:
    """(§4.7(나)) A `bool | None` predicate is gated `is True` — None / False both reject."""
    grants = approval_grants_no_authority(ApprovalAuthorityEffect())
    assert (grants is True) is True  # a real bool

    widened = no_widening_no_union(
        single_exact_decision=None, no_union_of_narrower=True
    )
    assert (widened is True) is False

    confined = unknown_confines(any_unknown_state=True, capacity_available=True)
    assert (confined is True) is True  # UNKNOWN blocks despite available capacity
