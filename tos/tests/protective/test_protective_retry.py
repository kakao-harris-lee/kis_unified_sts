"""§13 bounded retry + exhaustion (design #11 §6.4; produces protective_capacity_exhausted).

A retry is admissible only with a positive budget, an impossible duplicate economic effect,
and (for UNKNOWN outcomes) proven dedup. Budget exhaustion is itself a containment trigger.
protective_capacity_exhausted is the produced bool authority ``degraded_lease_invalidated``
consumes (True / None invalidates — polarity aligned). PR-EV-007 / FD-EV-010 / AFG-EV-003
substrate — closes nothing.
"""

from __future__ import annotations

from tos.protective import (
    ProtectiveResourceDomain,
    protective_capacity_exhausted,
    retry_admissible,
)

from ._protective_strategies import issue_profile, reserved_declaration

# ---------------------------------------------------------------------------
# retry_admissible both-ways
# ---------------------------------------------------------------------------


def test_bounded_nondup_retry_admissible() -> None:
    """(§13 canary b) Positive budget ∧ no duplicate effect ∧ known outcome => retry True."""
    assert (
        retry_admissible(
            budget_remaining=3,
            duplicate_economic_effect_possible=False,
            unknown_outcome=False,
            dedup_proven=None,
        )
        is True
    )


def test_zero_budget_denies_retry() -> None:
    """(§13 line 594 canary a) A zero budget => no retry (containment trigger)."""
    assert (
        retry_admissible(
            budget_remaining=0,
            duplicate_economic_effect_possible=False,
            unknown_outcome=False,
            dedup_proven=None,
        )
        is False
    )


def test_none_budget_denies_retry() -> None:
    """(§8 fail-closed) A None budget => no retry (bound injected, never hardcoded)."""
    assert (
        retry_admissible(
            budget_remaining=None,
            duplicate_economic_effect_possible=False,
            unknown_outcome=False,
            dedup_proven=None,
        )
        is False
    )


def test_possible_duplicate_effect_denies_retry() -> None:
    """(§13.3) A possible / unknown duplicate economic effect (True / None) => no retry.

    Design doc v1.2 [D2] maintenance obligation: the duplicate gate precedes the
    unknown-outcome branch and requires a positive ``False`` proof, so the denial
    must hold for every ``unknown_outcome`` / ``dedup_proven`` combination —
    including ``unknown_outcome=None`` and ``dedup_proven=True``.
    """
    for value in (True, None):
        for unknown in (True, False, None):
            for dedup in (True, False, None):
                assert (
                    retry_admissible(
                        budget_remaining=3,
                        duplicate_economic_effect_possible=value,
                        unknown_outcome=unknown,
                        dedup_proven=dedup,
                    )
                    is False
                )


def test_unknown_outcome_without_dedup_denies_retry() -> None:
    """(§14.4 line 639 canary a) UNKNOWN outcome without proven dedup => blind resend prohibited."""
    assert (
        retry_admissible(
            budget_remaining=3,
            duplicate_economic_effect_possible=False,
            unknown_outcome=True,
            dedup_proven=None,
        )
        is False
    )


def test_unknown_outcome_with_dedup_allows_retry() -> None:
    """(§14.4) UNKNOWN outcome WITH proven dedup + budget + no-dup => retry admissible."""
    assert (
        retry_admissible(
            budget_remaining=3,
            duplicate_economic_effect_possible=False,
            unknown_outcome=True,
            dedup_proven=True,
        )
        is True
    )


# ---------------------------------------------------------------------------
# protective_capacity_exhausted (produced bool)
# ---------------------------------------------------------------------------


def test_exhausted_on_zero_budget() -> None:
    """(§13 line 594 canary a) budget <= 0 => exhausted True (containment)."""
    assert protective_capacity_exhausted(issue_profile(), budget_remaining=0) is True


def test_exhausted_on_none_budget() -> None:
    """(fail-closed) A None budget => exhausted True."""
    assert protective_capacity_exhausted(issue_profile(), budget_remaining=None) is True


def test_exhausted_on_none_profile() -> None:
    """(fail-closed) A None profile => exhausted True."""
    assert protective_capacity_exhausted(None, budget_remaining=5) is True


def test_exhausted_when_a_required_domain_unavailable() -> None:
    """(§13 line 578) A required domain resolving UNAVAILABLE => exhausted True."""
    from tos.protective import GuaranteeLevel

    # Every domain declared, but one explicitly UNAVAILABLE.
    decls = tuple(
        (
            reserved_declaration(domain=d, guarantee_level=GuaranteeLevel.UNAVAILABLE)
            if d is ProtectiveResourceDomain.NETWORK_AND_CONTROL_PATH
            else reserved_declaration(domain=d)
        )
        for d in ProtectiveResourceDomain
    )
    profile = issue_profile(declarations=decls)
    assert protective_capacity_exhausted(profile, budget_remaining=5) is True


def test_not_exhausted_when_all_reserved_and_budget_positive() -> None:
    """(§13 canary b) All domains reserved + positive budget => not exhausted (positive side)."""
    assert protective_capacity_exhausted(issue_profile(), budget_remaining=5) is False


def test_exhausted_empty_declarations_fail_closed() -> None:
    """(∅ fail-closed) An empty-declarations profile => every required domain UNAVAILABLE => exhausted."""
    assert (
        protective_capacity_exhausted(
            issue_profile(declarations=()), budget_remaining=5
        )
        is True
    )
