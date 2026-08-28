"""Digest-bound artifact invariants (design #15 §2/§3.1; IAP-EV-001/003/004 substrate).

id ⊥ digest => a same-id / different-bytes substituted request / decision / consumption record is
a detectable ``CRITICAL_CONFLICT``; ISSUED is reachable under Phase-1 null bounds; every artifact
is frozen (append-only, no mutate); ``extra="forbid"`` rejects unknown top-level fields (§9 line
255); the authority effect / declaration is all-false; materiality UNKNOWN => material.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.canonical import ArtifactIntegrityError, RecordPairKind, classify_record_pair
from tos.iap import (
    ApprovalAuthorityEffect,
    ApprovalConsumptionRecord,
    IndependentApprovalDecision,
    IndependentIdArtifact,
    MaterialApprovalChange,
    MaterialityVerdict,
    ProposalApprovalRequest,
    TradingApprovalPolicy,
)

from ._iap_strategies import (
    SCHEME,
    complete_request,
    issue_consumption_record,
    issue_decision,
    issue_policy,
    minimal_request,
)

_ALL_ARTIFACT_TYPES = (
    TradingApprovalPolicy,
    ProposalApprovalRequest,
    IndependentApprovalDecision,
    ApprovalConsumptionRecord,
)


# ---------------------------------------------------------------------------
# digest binding — issuance is reachable under Phase-1 null bounds
# ---------------------------------------------------------------------------


def test_all_four_artifacts_issue_under_null_bounds() -> None:
    """(§2.1) Every digest-bound artifact reaches ISSUED with only structural fields concrete."""
    for artifact in (
        issue_policy(),
        minimal_request(),
        issue_decision(),
        issue_consumption_record(),
    ):
        assert artifact.canonical_digest is not None
        assert artifact.status.value == "ISSUED"


def test_all_four_artifacts_are_independent_id_artifacts() -> None:
    """(§3.1/§0.4d) All four citizens are IndependentIdArtifact (id ⊥ digest, not f(digest))."""
    for artifact_type in _ALL_ARTIFACT_TYPES:
        assert issubclass(artifact_type, IndependentIdArtifact)


def test_request_digest_substitution_is_unconstructable() -> None:
    """(§4.1) A tampered canonical_digest cannot be constructed (mutate / substitute sealed)."""
    good = complete_request()
    tampered = {**good.model_dump(), "canonical_digest": "deadbeef"}
    with pytest.raises((ArtifactIntegrityError, ValidationError)):
        ProposalApprovalRequest(**tampered)


def test_issued_decision_requires_concrete_generation() -> None:
    """(§5.4 required-covered) An issued decision missing its generation is unconstructable."""
    with pytest.raises((ArtifactIntegrityError, ValidationError)):
        IndependentApprovalDecision.issue(
            scheme=SCHEME, decision_id="d", request_id="r"
        )


# ---------------------------------------------------------------------------
# id ⊥ digest — same-id / different-bytes is CRITICAL_CONFLICT (substitution / re-issue)
# ---------------------------------------------------------------------------


def test_contradictory_same_id_decision_is_critical_conflict() -> None:
    """(§3.1 / §11 line 298) Two same-id decisions, different bytes => CRITICAL_CONFLICT (substitution seal)."""
    a = issue_decision(decision_id="dec-1", result=None)
    b = issue_decision(decision_id="dec-1", decision_generation=2)
    assert (
        classify_record_pair(
            a.decision_id, a.canonical_digest, b.decision_id, b.canonical_digest
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_identical_reissue_is_idempotent_dup() -> None:
    """A byte-identical re-emission is an idempotent duplicate, not a conflict."""
    a = issue_consumption_record()
    b = issue_consumption_record()
    assert (
        classify_record_pair(
            a.consumption_record_id,
            a.canonical_digest,
            b.consumption_record_id,
            b.canonical_digest,
        )
        is RecordPairKind.IDEMPOTENT_DUP
    )


def test_distinct_generation_ids_are_distinct() -> None:
    """(§2.1) A legitimate new generation (fresh id) is DISTINCT — never mis-flagged as conflict."""
    a = issue_decision(decision_id="dec-1")
    b = issue_decision(decision_id="dec-2", decision_generation=2)
    assert (
        classify_record_pair(
            a.decision_id, a.canonical_digest, b.decision_id, b.canonical_digest
        )
        is RecordPairKind.DISTINCT
    )


def test_decision_id_is_independent_not_derived() -> None:
    """(§0.4d) The decision id is orthogonal to the digest (not a substring — id ⊥ digest)."""
    decision = issue_decision()
    assert decision.decision_id is not None
    assert decision.canonical_digest is not None
    assert decision.canonical_digest not in decision.decision_id


# ---------------------------------------------------------------------------
# all-false authority effect (§7 / IAP-INV-005)
# ---------------------------------------------------------------------------


def test_artifacts_carry_all_false_authority() -> None:
    """(§7 / IAP-INV-005) The request declaration / decision / consumption authority is all-false."""
    effects = (
        complete_request().authority_declaration,
        issue_decision().authority_effect,
        issue_consumption_record().authority_effect,
    )
    for effect in effects:
        assert effect.mutates_capacity is False
        assert effect.creates_headroom is False
        assert effect.issues_authority is False
        assert effect.transmits is False
        assert effect.clears_halt is False
        assert effect.rearms is False


def test_true_authority_flag_is_unconstructable() -> None:
    """(IAP-INV-005 line 150) Any True authority flag makes the effect unconstructable (True⇒unconstructable)."""
    for field in (
        "mutates_capacity",
        "creates_headroom",
        "issues_authority",
        "classifies_protection",
        "transmits",
        "clears_halt",
        "rearms",
    ):
        with pytest.raises((ArtifactIntegrityError, ValidationError)):
            ApprovalAuthorityEffect(**{field: True})


# ---------------------------------------------------------------------------
# materiality — unknown materiality is material (§5.7 line 126)
# ---------------------------------------------------------------------------


def test_unknown_materiality_is_material() -> None:
    """(§5.7 line 126) 'Unknown materiality is material' — UNKNOWN / MATERIAL => material; IMMATERIAL => not."""
    assert (
        MaterialApprovalChange(verdict=MaterialityVerdict.UNKNOWN).resolved_material()
        is True
    )
    assert (
        MaterialApprovalChange(verdict=MaterialityVerdict.MATERIAL).resolved_material()
        is True
    )
    assert (
        MaterialApprovalChange(
            verdict=MaterialityVerdict.IMMATERIAL
        ).resolved_material()
        is False
    )


def test_materiality_defaults_unknown_material() -> None:
    """(§5.7 line 126 fail-closed) The default verdict is UNKNOWN => material."""
    assert MaterialApprovalChange().resolved_material() is True


# ---------------------------------------------------------------------------
# frozen / append-only + extra=forbid (§9 line 255)
# ---------------------------------------------------------------------------


def test_request_is_frozen_no_mutate() -> None:
    """(§2.0 / §9 line 255) A request is frozen — any field change is a NEW identity, not a patch."""
    request = complete_request()
    with pytest.raises(ValidationError):
        request.account = "OTHER"  # type: ignore[misc]


def test_extra_field_is_forbidden() -> None:
    """(extra=forbid) An unknown top-level model field is rejected (§9 line 255 no-patch).

    NB: ``extra="forbid"`` covers only unknown *model fields*. A missing / surplus / substituted
    member of the *artifact tuple* a request binds is NOT caught here — that is the
    ``request_is_complete`` / ``exact_binding_holds`` structural guards' job (§2.0 — no over-claim).
    """
    with pytest.raises(ValidationError):
        ProposalApprovalRequest(request_id="r", unknown_field=1)  # type: ignore[call-arg]
