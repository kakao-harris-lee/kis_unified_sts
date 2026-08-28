"""hag records — id ⊥ digest, substitution detection, all-false authority (design #20 §2.1/§2.4/§7).

Regime tag: predicate / model substrate only; HAG-EV-002/004/012 substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
from tos.hag import (
    ApprovalSetConsumptionRecord,
    ArtifactStatus,
    AttestationDecision,
    EffectivePrincipalGraph,
    HumanApprovalAttestation,
    HumanApprovalRequest,
    HumanApprovalSet,
    HumanAuthorityEffect,
    HumanAuthorityPolicy,
    HumanDelegationRecord,
    HumanHaltCommand,
    RecordPairKind,
    classify_record_pair,
)
from tos.hag._base import ArtifactIntegrityError

from ._hag_strategies import (
    SCHEME,
    clean_approval_set,
    clean_attestation,
    clean_request,
)

_ALL_ARTIFACTS = (
    HumanAuthorityPolicy,
    EffectivePrincipalGraph,
    HumanApprovalRequest,
    HumanApprovalAttestation,
    HumanApprovalSet,
    ApprovalSetConsumptionRecord,
    HumanHaltCommand,
    HumanDelegationRecord,
)

_AUTHORITY_BEARING = (
    HumanAuthorityPolicy,
    HumanApprovalRequest,
    HumanApprovalAttestation,
    HumanApprovalSet,
    ApprovalSetConsumptionRecord,
    HumanHaltCommand,
    HumanDelegationRecord,
)


def test_all_eight_artifacts_are_id_independent() -> None:
    """(§2.1) Every artifact declares an independent id field (id != f(digest))."""
    assert len(_ALL_ARTIFACTS) == 8
    for cls in _ALL_ARTIFACTS:
        assert isinstance(cls._ID_FIELD, str)


def test_attestation_id_is_independent_of_digest() -> None:
    """(§2.1) An issued attestation's id is separately injected, not derived from the digest."""
    att = clean_attestation(attestation_id="att-x", principal_id="alice")
    assert att.attestation_id == "att-x"
    assert att.canonical_digest is not None
    assert att.attestation_id != att.canonical_digest


def test_same_id_different_bytes_is_critical_conflict() -> None:
    """(§5.2/§5.8) A same-id / different-decision attestation is a CRITICAL_CONFLICT (forgery)."""
    approve = clean_attestation(
        attestation_id="att-1",
        principal_id="alice",
        decision=AttestationDecision.APPROVE,
    )
    deny = clean_attestation(
        attestation_id="att-1", principal_id="alice", decision=AttestationDecision.DENY
    )
    assert approve.attestation_id == deny.attestation_id
    assert approve.canonical_digest != deny.canonical_digest
    kind = classify_record_pair(
        approve.attestation_id,
        approve.canonical_digest,
        deny.attestation_id,
        deny.canonical_digest,
    )
    assert kind is RecordPairKind.CRITICAL_CONFLICT


def test_same_content_is_idempotent_dup() -> None:
    """(§2.1) A same-id / same-bytes attestation is an idempotent duplicate, not a conflict."""
    a1 = clean_attestation(attestation_id="att-1", principal_id="alice")
    a2 = clean_attestation(attestation_id="att-1", principal_id="alice")
    assert a1.canonical_digest == a2.canonical_digest
    kind = classify_record_pair(
        a1.attestation_id, a1.canonical_digest, a2.attestation_id, a2.canonical_digest
    )
    assert kind is RecordPairKind.IDEMPOTENT_DUP


def test_issued_artifact_requires_concrete_id() -> None:
    """(canonical §3.1) An ISSUED artifact with a null id is unconstructable."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        HumanApprovalAttestation(
            attestation_id=None,
            request_digest="rd",
            canonical_digest="x",
            status=ArtifactStatus.ISSUED,
            canonicalization_version=SCHEME.version,
        )


# ---------------------------------------------------------------------------
# all-false HumanAuthorityEffect (§2.4 / §4.3 / HAG-INV-004)
# ---------------------------------------------------------------------------


def test_default_authority_effect_is_all_false() -> None:
    """(HAG-INV-004) The default human-authority effect has every flag False."""
    effect = HumanAuthorityEffect()
    assert effect.mutates_capacity is False
    assert effect.activates_configuration is False
    assert effect.issues_live_authorization is False
    assert effect.clears_deny_latch is False
    assert effect.transmits_to_broker is False
    assert effect.re_arms is False


def test_any_true_authority_flag_is_unconstructable() -> None:
    """(HAG-INV-004 / §4.3) Any True authority flag makes the effect unconstructable."""
    for flag in (
        "mutates_capacity",
        "activates_configuration",
        "issues_live_authorization",
        "clears_deny_latch",
        "transmits_to_broker",
        "re_arms",
    ):
        with pytest.raises((ArtifactIntegrityError, ValueError)):
            HumanAuthorityEffect(**{flag: True})


def test_authority_bearing_artifacts_carry_all_false_effect() -> None:
    """(§2.4) Every authority-bearing artifact carries an all-false human-authority effect."""
    request = clean_request()
    approval_set = clean_approval_set()
    for artifact in (request, approval_set):
        effect = artifact.human_authority_effect
        assert effect.mutates_capacity is False
        assert effect.transmits_to_broker is False
        assert effect.re_arms is False


def test_effective_principal_graph_carries_no_authority_field() -> None:
    """(§2.4) The graph is a pure structural artifact — it has no human_authority_effect field."""
    assert "human_authority_effect" not in EffectivePrincipalGraph.model_fields
    for cls in _AUTHORITY_BEARING:
        assert "human_authority_effect" in cls.model_fields


# ---------------------------------------------------------------------------
# frozen / extra-forbid discipline
# ---------------------------------------------------------------------------


def test_records_are_frozen_and_extra_forbid() -> None:
    """(§2.0) Models are frozen (no mutation) and forbid unknown fields."""
    att = clean_attestation(attestation_id="att-1", principal_id="alice")
    with pytest.raises((ValueError, TypeError)):
        att.decision = AttestationDecision.DENY  # type: ignore[misc]
    with pytest.raises((ValueError, TypeError)):
        HumanHaltCommand(command_id="c", unknown_field="y")  # type: ignore[call-arg]


def test_policy_quorum_for_returns_none_when_undeclared() -> None:
    """(§8 fail-closed) An undeclared approval type has no quorum (None => fail-closed at predicate)."""
    from tos.hag import AuthorityClass, QuorumRule

    policy = HumanAuthorityPolicy.issue(
        scheme=SCHEME,
        policy_id="pol-1",
        policy_generation=1,
        quorum_by_approval_type=(
            QuorumRule(approval_type=AuthorityClass.APPROVE_REARM, quorum_n=2),
        ),
    )
    assert policy.quorum_for(AuthorityClass.APPROVE_REARM) == 2
    assert policy.quorum_for(AuthorityClass.CAPACITY_MUTATION) is None
