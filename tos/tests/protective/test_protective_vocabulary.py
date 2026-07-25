"""Vocabulary verbatim + membership (design #11 §2.2).

The StrEnum values / counts are authored verbatim from ADR-002-001 (§3.1.4 guarantee levels,
§3.1.6 ownership, §4.6 domains, §8.5 de-restriction, §6.1/§6.2 outcome). These tests lock the
token strings and cardinalities so a silent rename / drop is caught (the erratum-defect-class
seal, design #11 §2.2).
"""

from __future__ import annotations

from tos.protective import (
    REQUIRED_PROTECTIVE_DOMAINS,
    Admissibility,
    DegradedModeTransition,
    GuaranteeLevel,
    ProtectiveActionKind,
    ProtectiveActionOutcome,
    ProtectiveOwnership,
    ProtectiveResourceDomain,
)


def test_guarantee_level_five_verbatim() -> None:
    """(§3.1.4 line 142) The 5 guarantee levels are verbatim, in order."""
    assert [g.value for g in GuaranteeLevel] == [
        "PHYSICALLY_RESERVED",
        "LOGICALLY_RESERVED",
        "PRIORITIZED_ONLY",
        "BEST_EFFORT",
        "UNAVAILABLE",
    ]


def test_protective_ownership_four_verbatim() -> None:
    """(§3.1.6 line 152) The 4 protective ownership classes are verbatim."""
    assert {o.value for o in ProtectiveOwnership} == {
        "STRATEGY_OWNED",
        "EXECUTION_OWNED",
        "SAFETY_OWNED",
        "OPERATOR_OWNED",
    }


def test_resource_domain_seven_verbatim() -> None:
    """(§4.6 line 205-213) The 7 protective resource domains are verbatim."""
    assert {d.value for d in ProtectiveResourceDomain} == {
        "EXECUTION_WORKERS_AND_QUEUES",
        "BROKER_API_RATE_SESSION_AND_ORDER_RATE",
        "AGGREGATE_RISK_MARGIN_COLLATERAL_RETRY",
        "NETWORK_AND_CONTROL_PATH",
        "RECONCILIATION_AND_EVIDENCE_PERSISTENCE",
        "OPERATOR_EMERGENCY_PATH",
        "TRUSTWORTHY_TIME_AND_PROTECTIVE_AUTHZ",
    }
    assert len(list(ProtectiveResourceDomain)) == 7


def test_required_floor_is_all_seven() -> None:
    """(§4.6 "at least"; §5.1) The minimum required floor is the full 7-domain set."""
    assert frozenset(ProtectiveResourceDomain) == REQUIRED_PROTECTIVE_DOMAINS
    assert len(REQUIRED_PROTECTIVE_DOMAINS) == 7


def test_admissibility_three_local() -> None:
    """(§2.2-(4)) The 3 local admissibility tokens."""
    assert {a.value for a in Admissibility} == {"ADMISSIBLE", "TRAPPED", "PROHIBITED"}


def test_outcome_three_local() -> None:
    """(§2.2-(6)) The 3 local classification outcomes."""
    assert {o.value for o in ProtectiveActionOutcome} == {
        "PROTECTIVE_PROVEN",
        "RISK_INCREASING_DENIED",
        "UNKNOWN_CONSERVATIVE",
    }


def test_degraded_transition_single_governed() -> None:
    """(§8.5 line 381) The single governed de-restriction marker."""
    assert [t.value for t in DegradedModeTransition] == [
        "CONTAINED_TO_DEGRADED_PROTECTIVE"
    ]


def test_action_kind_members() -> None:
    """(§6.2 / §6.5) The local action-kind discriminator members."""
    assert {k.value for k in ProtectiveActionKind} == {
        "OVERLAP_FIRST_ADD_ONLY",
        "CANCEL_FIRST_OR_REMOVAL",
        "NEW_PROTECTIVE_ORDER",
        "CANCELLATION_OF_RISK_INCREASING",
    }


def test_degraded_protective_mode_absent_from_protective_vocab() -> None:
    """(§3.5 / §4.4) The authority mode token DEGRADED_PROTECTIVE is NOT a protective token."""
    protective_tokens = (
        {g.value for g in GuaranteeLevel}
        | {a.value for a in Admissibility}
        | {o.value for o in ProtectiveActionOutcome}
        | {o.value for o in ProtectiveOwnership}
        | {d.value for d in ProtectiveResourceDomain}
    )
    # mode enum values (CONTAINED / DEGRADED_PROTECTIVE / LIVE_NORMAL) are authority's, not here.
    for mode_token in ("CONTAINED", "DEGRADED_PROTECTIVE", "LIVE_NORMAL", "HALTED"):
        assert mode_token not in protective_tokens
