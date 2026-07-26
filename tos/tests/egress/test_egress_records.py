"""EGRESS digest-bound artifacts — id ⊥ digest, required-covered, malformed-model (design #22 §2).

Regime tag: structural / coordinate predicate substrate only; EGRESS-EV-004/005 substrate;
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
from tos.egress import (
    ActiveEgressPrincipalSet,
    ArtifactIntegrityError,
    EgressGeneration,
    EgressRequestRecord,
    QuorumCommitCertificate,
    ReplayObservation,
    TrialClaims,
)

from ._egress_strategies import SCHEME, clean_qcc, clean_request, clean_signers

_ALL_ARTIFACTS = (
    QuorumCommitCertificate,
    EgressRequestRecord,
    EgressGeneration,
    ActiveEgressPrincipalSet,
    ReplayObservation,
)


def test_every_artifact_has_an_independent_id_field() -> None:
    """(§2.1) All five artifacts declare an independent (non-derived) id field."""
    for artifact in _ALL_ARTIFACTS:
        assert hasattr(artifact, "_ID_FIELD")
        assert artifact._ID_FIELD in artifact.model_fields


def test_clean_qcc_is_genuinely_digest_bound() -> None:
    """(#8 fixture discipline) The clean QCC is genuinely issued + digest-bound (not a shortcut)."""
    qcc = clean_qcc()
    assert qcc.canonical_digest is not None
    assert qcc.qcc_id == "qcc-1"
    assert len(qcc.signer_coordinates) == 2


def test_qcc_id_independent_of_digest_same_id_diff_bytes_representable() -> None:
    """(§2.1/§3.1) Two same-id / different-bytes QCCs are representable (id ⊥ digest)."""
    a = clean_qcc(qcc_id="qcc-dup", committed_revision=42)
    b = clean_qcc(qcc_id="qcc-dup", committed_revision=43)
    assert a.qcc_id == b.qcc_id
    assert a.canonical_digest != b.canonical_digest


def test_issued_qcc_requires_every_required_covered_field() -> None:
    """(§2.3) An issued QCC missing any _REQUIRED_COVERED field is unconstructable."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        # active_egress_principal is required-covered; leaving it None must fail issuance.
        clean_qcc(active_egress_principal=None)


def test_issued_qcc_missing_commit_proof_coordinate_rejected() -> None:
    """(§2.3) A None commit-proof coordinate (canonical_command_digest) fails issuance."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        clean_qcc(canonical_command_digest=None)


def test_qcc_malformed_trial_claim_coexistence_rejected() -> None:
    """(§2.3 malformed-model) is_restricted_live_trial=True with an incomplete trial group fails."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        clean_qcc(
            is_restricted_live_trial=True,
            trial_claims=TrialClaims(trial_policy_generation=1),  # incomplete
        )


def test_qcc_complete_trial_claim_is_constructable() -> None:
    """(§2.3 both-ways) A complete trial group + the positive claim IS constructable."""
    qcc = clean_qcc(
        is_restricted_live_trial=True,
        trial_claims=TrialClaims(
            trial_policy_generation=1,
            trial_plan_generation=1,
            trial_run_generation=1,
            promotion_generation=1,
            remaining_envelope="env",
            abort_generation=1,
        ),
    )
    assert qcc.is_restricted_live_trial is True
    assert qcc.trial_claims is not None and qcc.trial_claims.is_complete() is True


def test_qcc_no_trial_claim_default_is_constructable() -> None:
    """(§2.3 both-ways) The default (not a trial) QCC needs no trial group."""
    qcc = clean_qcc()
    assert qcc.is_restricted_live_trial is False
    assert qcc.trial_claims is None


def test_egress_request_id_independent_of_digest() -> None:
    """(§2.1) EgressRequestRecord same-id / different-bytes is representable."""
    a = clean_request(request_id="req-dup", request_bytes_digest="bytes-A")
    b = clean_request(request_id="req-dup", request_bytes_digest="bytes-B")
    assert a.request_id == b.request_id
    assert a.canonical_digest != b.canonical_digest


def test_egress_generation_and_active_set_require_generation() -> None:
    """(§2.3) EgressGeneration / ActiveEgressPrincipalSet require a concrete egress_generation."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        EgressGeneration.issue(
            scheme=SCHEME, generation_id="g-1", egress_generation=None
        )
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        ActiveEgressPrincipalSet.issue(
            scheme=SCHEME, set_id="s-1", egress_generation=None
        )


def test_replay_observation_requires_subject_identity() -> None:
    """(§2.3/§5.5) ReplayObservation requires a concrete subject_identity (the classify axis)."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        ReplayObservation.issue(
            scheme=SCHEME, observation_id="o-1", subject_identity=None
        )


def test_extra_field_forbidden_on_qcc() -> None:
    """(§2.0) extra='forbid' — an unknown field is rejected (schema-level omission-is-restrictive)."""
    with pytest.raises((ValueError, TypeError)):
        clean_qcc(unexpected_field="x")  # type: ignore[call-arg]


def test_signer_coordinates_carried_verbatim() -> None:
    """(§2.4) The QCC carries the exact injected signer coordinates (no mutation)."""
    signers = clean_signers()
    qcc = clean_qcc(signer_coordinates=signers)
    assert qcc.signer_coordinates == signers
