"""Evidence Integrity Policy (design #4 §2.5 B, §3.5, template SoT).

Models ``EVIDENCE-INTEGRITY-POLICY-template.yaml`` (87 lines). Per design §3.5 the
EIP **is** a digest-bound artifact (``content_digest == H_ver(canonicalize(policy
body))``) with an **independent**, non-derived id: ``policy_id`` is stable across
generations while the digest changes per generation, so ``(policy_id, generation,
content_digest)`` identifies a specific version (design §3.5).

**Interpretations (design deviations, reported):**

* The inherited ``canonical_digest`` realizes the template's ``content_digest``
  (design §3.2/§3.5); ``canonicalization_version`` and ``status`` map to the
  template fields of the same name.
* Covered = the policy **body** blocks only (scope / durability / integrity /
  completeness / retention / access_and_redaction / replay / authority_effect —
  design §3.5). Identity/governance meta (``version`` / ``generation`` /
  ``approved_by`` / ``effective_from`` / ``expires_at`` / ``review``) is
  self-excluded.
* All bound values (``required_replication`` / ``anchor_cadence_ms`` /
  ``B_evidence_gap_*`` / ``min_retention_ms``) are **injected** and default
  ``null`` => UNKNOWN => fail-closed at consumption (design §8 — never
  hard-coded). ``anchor_cadence_ms`` in particular lacks an approved profile bound
  (``MAX_anchor_cadence_ms`` is a missing key, Phase-0 §8/§9.2 item 4).

Pure module: ``pydantic`` + stdlib only; no ``shared.*`` (design §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import model_validator

from tos.canonical import ArtifactIntegrityError, FrozenModel
from tos.evidence._base import AllFalseFlags, EvidenceArtifact
from tos.evidence.elements import (
    DurabilityClass,
    RecordClassDurabilityRule,
    RedactionProfile,
    RequiredCausalParentRule,
    RetentionRecordClassRule,
    SourceSequenceRule,
)

_EMERGENCY_JOURNAL_FAILURE_DEFAULT = "APPLY_RESTRICTION_AND_HARD_FENCE"  # line 25
_CONTAIN = "CONTAIN"  # lines 36-37
_STOP_NEW_RISK = "STOP_NEW_RISK"  # line 44
_UNSUPPORTED_BASELINE = "UNSUPPORTED_BASELINE"  # line 69
_DIVERGED = "DIVERGED"  # line 70


class EIPScope(FrozenModel):
    """Policy scope (template lines 11-17)."""

    environments: tuple[str, ...] = ()
    safety_cells: tuple[str, ...] = ()
    capacity_domains: tuple[str, ...] = ()
    accounts: tuple[str, ...] = ()
    brokers: tuple[str, ...] = ()
    record_classes: tuple[str, ...] = ()


class EIPDurability(FrozenModel):
    """Durability policy (template lines 19-26). Fail-closed default class."""

    default_class: DurabilityClass = DurabilityClass.DENY_IF_UNSPECIFIED
    record_class_rules: tuple[RecordClassDurabilityRule, ...] = ()
    required_replication: int | None = None  # injected bound (§8)
    acknowledgement_rule: str | None = None
    emergency_journal_required: bool = True
    emergency_journal_failure_response: str = _EMERGENCY_JOURNAL_FAILURE_DEFAULT
    ordinary_memory_buffer_is_durable: bool = False


class EIPIntegrity(FrozenModel):
    """Integrity policy (template lines 28-37). ``anchor_cadence_ms`` injected (§8)."""

    canonical_serialization: str | None = None
    content_digest_algorithm: str | None = None
    source_authentication: str | None = None
    segment_commitment: str | None = None
    external_anchor: str | None = None
    anchor_cadence_ms: int | None = None  # injected; no approved bound (Phase-0 §8)
    key_rotation_policy: str | None = None
    conflicting_record_id_response: str = _CONTAIN
    fork_or_rollback_response: str = _CONTAIN


class EIPCompleteness(FrozenModel):
    """Completeness policy (template lines 39-44). Gap bounds injected (§8)."""

    required_causal_parent_rules: tuple[RequiredCausalParentRule, ...] = ()
    source_sequence_rules: tuple[SourceSequenceRule, ...] = ()
    B_evidence_gap_detect_ms: int | None = None
    B_evidence_gap_contain_ms: int | None = None
    unresolved_gap_response: str = _STOP_NEW_RISK


class EIPRetention(FrozenModel):
    """Retention policy (template lines 46-52). Economic effect dominates retention."""

    record_class_rules: tuple[RetentionRecordClassRule, ...] = ()
    legal_hold_policy: str | None = None
    compaction_policy: str | None = None
    deletion_policy: str | None = None
    economic_effect_dominates_retention: bool = True
    retain_failed_and_inconclusive: bool = True


class EIPAccessRedaction(FrozenModel):
    """Access + redaction policy (template lines 54-61)."""

    raw_custodians: tuple[str, ...] = ()
    reviewer_roles: tuple[str, ...] = ()
    export_roles: tuple[str, ...] = ()
    deletion_approver_roles: tuple[str, ...] = ()
    redaction_profiles: tuple[RedactionProfile, ...] = ()
    usable_credentials_permitted: bool = False
    access_audit_required: bool = True

    @model_validator(mode="after")
    def _no_usable_credentials(self) -> EIPAccessRedaction:
        """Reject a policy that permits usable credentials (design §0.2/§4.6)."""
        if self.usable_credentials_permitted is True:
            raise ArtifactIntegrityError(
                "usable_credentials_permitted must be false (non-transmitting "
                "kernel — design §0.2/§4.6)"
            )
        return self


class EIPReplay(FrozenModel):
    """Replay policy (template lines 63-70). Isolation flags forced false (§6.3)."""

    isolated_runtime_identity: str | None = None
    live_credentials_permitted: bool = False
    live_broker_route_permitted: bool = False
    production_mutation_permitted: bool = False
    deterministic_boundary_policy: str | None = None
    unsupported_baseline_result: str = _UNSUPPORTED_BASELINE
    divergence_result: str = _DIVERGED

    @model_validator(mode="after")
    def _isolation_flags_false(self) -> EIPReplay:
        """Reject any true live/production replay permission (design §6.3/ERI-INV-008)."""
        for name in (
            "live_credentials_permitted",
            "live_broker_route_permitted",
            "production_mutation_permitted",
        ):
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"EIPReplay.{name} must be false (isolated replay — §6.3)"
                )
        return self


class EIPAuthorityEffect(AllFalseFlags):
    """EIP authority effect — all false (template lines 72-77, design §4.6)."""

    creates_capacity: bool = False
    creates_live_authorization: bool = False
    creates_protective_classification: bool = False
    permits_broker_transmission: bool = False
    may_rearm: bool = False


class EIPReview(FrozenModel):
    """Independent-review governance block (template lines 79-82). Excluded meta."""

    independent_reviewer: str | None = None
    evidence_location: str | None = None
    approval_record: str | None = None


class EvidenceIntegrityPolicy(EvidenceArtifact):
    """A digest-bound Evidence Integrity Policy (design #4 §3.5).

    ``content_digest`` (the inherited ``canonical_digest``) covers the policy body;
    ``policy_id`` is the independent, generation-stable id. An envelope's
    ``evidence_integrity_policy_digest`` binding must equal a known EIP's
    ``content_digest``; a mismatch is policy-substitution / generation-drift
    (design §3.5, detectable via :func:`tos.evidence.predicates.eip_binding_ok`).
    """

    _ID_FIELD: ClassVar[str] = "policy_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "integrity.canonical_serialization",
        "integrity.content_digest_algorithm",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "scope",
            "durability",
            "integrity",
            "completeness",
            "retention",
            "access_and_redaction",
            "replay",
            "authority_effect",
        }
    )

    # ---- Layer-0 identity + governance meta (self-excluded, §3.5) ----
    # canonical_digest (= template content_digest) / status / canonicalization_version
    # inherited.
    policy_id: str | None = None
    version: str | None = None
    generation: int | None = None
    approved_by: tuple[str, ...] = ()
    effective_from: int | None = None
    expires_at: int | None = None
    review: EIPReview = EIPReview()

    # ---- Covered policy body ----
    scope: EIPScope = EIPScope()
    durability: EIPDurability = EIPDurability()
    integrity: EIPIntegrity = EIPIntegrity()
    completeness: EIPCompleteness = EIPCompleteness()
    retention: EIPRetention = EIPRetention()
    access_and_redaction: EIPAccessRedaction = EIPAccessRedaction()
    replay: EIPReplay = EIPReplay()
    authority_effect: EIPAuthorityEffect = EIPAuthorityEffect()
