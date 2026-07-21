"""Evidence Store pure data models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-016 part of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per
the ratified design contract
``docs/plans/2026-07-20-tos-evidence-store-design.md`` (v1.1).

This package is **pure, non-transmitting, and authority-free** (design §0.2/§4.6):
frozen pydantic models, an append-only ledger skeleton, injectable
canonicalization + segment-commitment, and conservative derived predicates. It
imports only ``pydantic`` + stdlib + ``tos.canonical``/``tos.evidence`` — no
``numpy``/``pandas``, no ``shared.config`` / ``shared.*`` operational packages, no
``tos.capsule`` (design §0.3/§3.1 layering), and no network / process / env
access — actively verified by the §7.1 import-closure test in ``tos/tests``.

Identity is **independent, not** ``f(digest)`` (design #4 §3.1): so a §12 same
record id + different canonical bytes conflict stays representable and detectable.

Public surface groups by module:

* :mod:`tos.evidence.elements` — authored template-array element schemas + enums.
* :mod:`tos.evidence.envelope` — Safety Evidence Envelope.
* :mod:`tos.evidence.receipt` — Evidence Commit Receipt (UNVERIFIED-only, gap 5).
* :mod:`tos.evidence.gap` — Evidence Gap Record + gap state machine.
* :mod:`tos.evidence.policy` — Evidence Integrity Policy (digest-bound).
* :mod:`tos.evidence.replay` — Replay Capsule + divergence result.
* :mod:`tos.evidence.ledger` — segment-commitment Protocol + provisional chain.
* :mod:`tos.evidence.predicates` — conflict / ordering / gap / retention / replay /
  redaction / receipt-binding / authority-absence predicates.
"""

from __future__ import annotations

from tos.evidence._base import AllFalseFlags, EvidenceArtifact
from tos.evidence.elements import (
    CausalLink,
    DurabilityClass,
    EdgeType,
    NondeterministicBoundary,
    NormalizedViewVersion,
    ObservedBranch,
    PreservedProperty,
    RecordClassDurabilityRule,
    RecoverySource,
    RedactionProfile,
    RemainingUncertainty,
    RequiredCausalParentRule,
    RetentionHorizon,
    RetentionRecordClassRule,
    SourceContinuityVector,
    SourceSequenceRule,
    Tolerance,
    ToleranceKind,
)
from tos.evidence.envelope import SafetyEvidenceEnvelope
from tos.evidence.gap import (
    GAP_STATUS_ORDER,
    CapacityTreatment,
    EvidenceGapRecord,
    GapStatus,
)
from tos.evidence.ledger import (
    EV_L1_PROVISIONAL_CHAIN_VERSION,
    EvidenceSegment,
    IntegrityAnchor,
    ProvisionalHashChainScheme,
    SegmentCommitmentScheme,
)
from tos.evidence.policy import EvidenceIntegrityPolicy
from tos.evidence.predicates import (
    Ordering,
    OrderingEvent,
    RecordPairKind,
    RetentionSubject,
    causal_chain_complete,
    classify_record_pair,
    compare_order,
    corrected_by,
    economic_effects_after_retention,
    effective_retention_horizon,
    eip_binding_ok,
    gap_blocks_new_risk,
    gap_chain_current_status,
    gap_chain_valid,
    gap_transition_allowed,
    grants_no_authority,
    is_critical_conflict,
    receipt_binds_record,
    receipt_substitution_rejected,
    redaction_preserves_digest,
    redaction_profile_valid,
    reevaluation_is_distinct_named_result,
    repair_preserves_uncertainty,
    replay_baseline_supported,
)
from tos.evidence.receipt import EvidenceCommitReceipt, ReceiptVerificationStatus
from tos.evidence.replay import (
    ReplayCapsule,
    ReplayResultState,
    compute_replay_result,
)

__all__ = [
    # base
    "AllFalseFlags",
    "EvidenceArtifact",
    # elements + enums
    "CausalLink",
    "DurabilityClass",
    "EdgeType",
    "NondeterministicBoundary",
    "NormalizedViewVersion",
    "ObservedBranch",
    "PreservedProperty",
    "RecordClassDurabilityRule",
    "RecoverySource",
    "RedactionProfile",
    "RemainingUncertainty",
    "RequiredCausalParentRule",
    "RetentionHorizon",
    "RetentionRecordClassRule",
    "SourceContinuityVector",
    "SourceSequenceRule",
    "Tolerance",
    "ToleranceKind",
    # artifacts
    "SafetyEvidenceEnvelope",
    "EvidenceCommitReceipt",
    "ReceiptVerificationStatus",
    "EvidenceGapRecord",
    "GapStatus",
    "GAP_STATUS_ORDER",
    "CapacityTreatment",
    "EvidenceIntegrityPolicy",
    "ReplayCapsule",
    "ReplayResultState",
    "compute_replay_result",
    # ledger
    "EV_L1_PROVISIONAL_CHAIN_VERSION",
    "EvidenceSegment",
    "IntegrityAnchor",
    "ProvisionalHashChainScheme",
    "SegmentCommitmentScheme",
    # predicates
    "Ordering",
    "OrderingEvent",
    "RecordPairKind",
    "RetentionSubject",
    "causal_chain_complete",
    "classify_record_pair",
    "compare_order",
    "corrected_by",
    "economic_effects_after_retention",
    "effective_retention_horizon",
    "eip_binding_ok",
    "gap_blocks_new_risk",
    "gap_chain_current_status",
    "gap_chain_valid",
    "gap_transition_allowed",
    "grants_no_authority",
    "is_critical_conflict",
    "receipt_binds_record",
    "receipt_substitution_rejected",
    "redaction_preserves_digest",
    "redaction_profile_valid",
    "reevaluation_is_distinct_named_result",
    "repair_preserves_uncertainty",
    "replay_baseline_supported",
]
