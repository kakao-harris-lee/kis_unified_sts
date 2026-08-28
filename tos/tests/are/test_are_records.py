"""Digest-bound artifact invariants (design #13 §2/§3.1; ARE-EV-001/002 substrate).

id ⊥ digest => a same-id / different-bytes contradictory decision is a detectable
``CRITICAL_CONFLICT`` (the forbidden-verb 'union' seal — two decisions cannot be merged);
the snapshot grants no permission; the final ``AdverseIncrement[s,d]`` is the rcl
``CapacityVector`` type (MAJOR-1 type-seal regression); every artifact is frozen (append-only).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.are import (
    AdverseIncrementResult,
    AggregateRiskDecision,
    AggregateRiskStateSnapshot,
    RiskDecisionResult,
)
from tos.canonical import ArtifactIntegrityError, RecordPairKind, classify_record_pair
from tos.rcl import CapacityVector

from ._are_strategies import (
    SCHEME,
    issue_decision,
    issue_policy,
    issue_scenario_set,
    issue_snapshot,
)

# ---------------------------------------------------------------------------
# digest binding — issuance is reachable under Phase-1 null bounds
# ---------------------------------------------------------------------------


def test_all_four_artifacts_issue_under_null_bounds() -> None:
    """(§2.1) Every digest-bound artifact reaches ISSUED with only structural fields concrete."""
    for artifact in (
        issue_policy(),
        issue_snapshot(),
        issue_scenario_set(),
        issue_decision(),
    ):
        assert artifact.canonical_digest is not None
        assert artifact.status.value == "ISSUED"


def test_digest_substitution_is_unconstructable() -> None:
    """(§4.1) A tampered canonical_digest cannot be constructed (mutate / substitute sealed)."""
    good = issue_decision()
    tampered = {**good.model_dump(), "canonical_digest": "deadbeef"}
    with pytest.raises((ArtifactIntegrityError, ValidationError)):
        AggregateRiskDecision(**tampered)


def test_issued_decision_requires_concrete_result() -> None:
    """(§5.5 required-covered) An issued decision missing its result is unconstructable."""
    with pytest.raises((ArtifactIntegrityError, ValidationError)):
        AggregateRiskDecision.issue(
            scheme=SCHEME, decision_id="d", decision_generation=1
        )


# ---------------------------------------------------------------------------
# id ⊥ digest — same-id / different-bytes is CRITICAL_CONFLICT ('union' seal)
# ---------------------------------------------------------------------------


def test_contradictory_same_id_decision_is_critical_conflict() -> None:
    """(§3.1 / ARE-INV-002) Two same-id decisions with different bytes => CRITICAL_CONFLICT (no union)."""
    a = issue_decision(decision_id="dec-1", result=RiskDecisionResult.GRANT)
    b = issue_decision(
        decision_id="dec-1", result=RiskDecisionResult.DENY
    )  # contradictory
    assert (
        classify_record_pair(
            a.decision_id, a.canonical_digest, b.decision_id, b.canonical_digest
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_identical_reissue_is_idempotent_dup() -> None:
    """A byte-identical re-emission is an idempotent duplicate, not a conflict."""
    a = issue_decision()
    b = issue_decision()
    assert (
        classify_record_pair(
            a.decision_id, a.canonical_digest, b.decision_id, b.canonical_digest
        )
        is RecordPairKind.IDEMPOTENT_DUP
    )


def test_distinct_generation_ids_are_distinct() -> None:
    """(§2.3) A legitimate new generation (fresh id) is DISTINCT — never mis-flagged as conflict."""
    a = issue_decision(decision_id="dec-1")
    b = issue_decision(
        decision_id="dec-2", decision_generation=2, result=RiskDecisionResult.DENY
    )
    assert (
        classify_record_pair(
            a.decision_id, a.canonical_digest, b.decision_id, b.canonical_digest
        )
        is RecordPairKind.DISTINCT
    )


# ---------------------------------------------------------------------------
# snapshot grants no permission (§5.3 line 124)
# ---------------------------------------------------------------------------


def test_snapshot_grants_no_permission() -> None:
    """(§5.3 line 124 / ARE-INV-009) The snapshot carries an all-false authority effect."""
    snap = issue_snapshot()
    assert snap.authority_effect.creates_capacity is False
    assert snap.authority_effect.permits_transmission is False
    assert snap.authority_effect.may_rearm is False


# ---------------------------------------------------------------------------
# dominance type-seal regression (MAJOR-1) — AdverseIncrement is rcl CapacityVector
# ---------------------------------------------------------------------------


def test_adverse_increment_result_uses_rcl_capacity_vector_type() -> None:
    """(MAJOR-1 §0.4c) The final increment field is the rcl CapacityVector type, not a self vector."""
    field = AdverseIncrementResult.model_fields["increment"]
    assert field.annotation is CapacityVector


def test_decision_increment_and_limit_are_rcl_capacity_vector() -> None:
    """(MAJOR-1) The decision's adverse_increment + effective_limit are the rcl CapacityVector type."""
    for name in ("adverse_increment", "effective_limit"):
        assert AggregateRiskDecision.model_fields[name].annotation is CapacityVector


def test_are_defines_no_own_increment_vector_type() -> None:
    """(MAJOR-1 anti-regression) tos.are exposes no self-authored *IncrementVector / capacity vector type."""
    import tos.are as are

    banned = ("IncrementVector", "AdverseVector", "AreCapacityVector")
    for name in dir(are):
        for token in banned:
            assert (
                token not in name
            ), f"tos.are unexpectedly defines its own vector type: {name}"


def test_decision_increment_equals_rcl_commit_coordinate() -> None:
    """(seam parity) The increment the decision carries is the exact rcl CapacityVector instance."""
    vec = CapacityVector()
    decision = AggregateRiskDecision.issue(
        scheme=SCHEME,
        decision_id="d",
        decision_generation=1,
        result=RiskDecisionResult.UNKNOWN,
        adverse_increment=vec,
    )
    assert isinstance(decision.adverse_increment, CapacityVector)


# ---------------------------------------------------------------------------
# frozen / append-only (no mutate)
# ---------------------------------------------------------------------------


def test_artifacts_are_frozen() -> None:
    """(§2.0) Every artifact is frozen — no in-place mutation (append-only)."""
    decision = issue_decision()
    with pytest.raises(ValidationError):
        decision.result = RiskDecisionResult.DENY  # type: ignore[misc]


def test_extra_field_is_forbidden() -> None:
    """(§14 line 362 / extra=forbid) An unknown / silently-dropped field is rejected."""
    with pytest.raises(ValidationError):
        AggregateRiskStateSnapshot(snapshot_id="s", unknown_field=1)  # type: ignore[call-arg]
