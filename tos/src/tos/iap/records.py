"""iap value models + the four digest-bound artifacts (design #15 §2)."""

from __future__ import annotations

from typing import ClassVar

from tos.iap._base import (
    AllFalseApprovalAuthority,
    FrozenModel,
    IndependentIdArtifact,
)
from tos.iap.vocabulary import ApprovalResult, ConsumptionStatus, MaterialityVerdict

__all__ = [
    "ApprovalAuthorityEffect",
    "MaterialApprovalChange",
    "TradingApprovalPolicy",
    "ProposalApprovalRequest",
    "IndependentApprovalDecision",
    "ApprovalConsumptionRecord",
]


class ApprovalAuthorityEffect(AllFalseApprovalAuthority):
    """Authority effect of Independent Approval — every flag false (IAP-INV-005 line 150 / §7)."""

    mutates_capacity: bool = False
    creates_headroom: bool = False
    issues_authority: bool = False
    classifies_protection: bool = False
    transmits: bool = False
    clears_halt: bool = False
    rearms: bool = False


class MaterialApprovalChange(FrozenModel):
    """Whether an approval-relevant change is material (ADR-002-023 §5.7 line 124-126)."""

    verdict: MaterialityVerdict = MaterialityVerdict.UNKNOWN

    def resolved_material(self) -> bool:
        """Whether the change is material — unknown materiality is material (§5.7 line 126)."""
        return self.verdict is not MaterialityVerdict.IMMATERIAL


class TradingApprovalPolicy(IndependentIdArtifact):
    """An append-only, spg-governed Trading Approval Policy (ADR-002-023 §5.1 / §8)."""

    _ID_FIELD: ClassVar[str] = "policy_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "policy_generation",
        "policy_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "policy_generation",
            "policy_version",
            "signer_identity",
            "approval_identity",
            "evidence_package_ref",
        }
    )

    policy_id: str | None = None

    policy_generation: int | None = None
    policy_version: str | None = None
    signer_identity: str | None = None
    approval_identity: str | None = None
    evidence_package_ref: str | None = None

    policy_order: int | None = None


class ProposalApprovalRequest(IndependentIdArtifact):
    """An append-only, immutable Proposal Approval Request (ADR-002-023 §5.3 / §9)."""

    _ID_FIELD: ClassVar[str] = "request_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("request_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "request_generation",
            "proposer_identity",
            "environment",
            "account",
            "instrument",
            "action_class",
            "operating_mode",
            "direction",
            "position_effect",
            "quantity_basis",
            "required_scope_complete",
            "proposal_id",
            "proposal_digest",
            "decision_context_capsule_id",
            "decision_context_capsule_digest",
            "critical_input_snapshot_digest",
            "construction_envelope_id",
            "construction_envelope_digest",
            "canonical_broker_command_id",
            "canonical_broker_command_digest",
            "venue_snapshot_digest",
            "venue_admissibility_decision_digest",
            "broker_capability_profile_digest",
            "trading_approval_policy_id",
            "trading_approval_policy_generation",
            "trading_approval_policy_digest",
            "required_independent_facts",
            "common_mode_declarations",
            "max_request_age_ms",
            "single_use",
            "exact_intent_only",
            "invalidation_set",
            "authority_declaration",
        }
    )

    request_id: str | None = None

    request_generation: int | None = None
    proposer_identity: str | None = None
    environment: str | None = None
    account: str | None = None
    instrument: str | None = None
    action_class: str | None = None
    operating_mode: str | None = None
    direction: str | None = None
    position_effect: str | None = None
    quantity_basis: str | None = None
    required_scope_complete: bool | None = None
    proposal_id: str | None = None
    proposal_digest: str | None = None
    decision_context_capsule_id: str | None = None
    decision_context_capsule_digest: str | None = None
    critical_input_snapshot_digest: str | None = None
    construction_envelope_id: str | None = None
    construction_envelope_digest: str | None = None
    canonical_broker_command_id: str | None = None
    canonical_broker_command_digest: str | None = None
    venue_snapshot_digest: str | None = None
    venue_admissibility_decision_digest: str | None = None
    broker_capability_profile_digest: str | None = None
    trading_approval_policy_id: str | None = None
    trading_approval_policy_generation: int | None = None
    trading_approval_policy_digest: str | None = None
    required_independent_facts: tuple[str, ...] = ()
    common_mode_declarations: tuple[str, ...] = ()
    max_request_age_ms: int | None = None
    single_use: bool | None = None
    exact_intent_only: bool | None = None
    invalidation_set: tuple[str, ...] = ()
    authority_declaration: ApprovalAuthorityEffect = ApprovalAuthorityEffect()

    request_order: int | None = None


class IndependentApprovalDecision(IndependentIdArtifact):
    """An append-only, immutable Independent Approval Decision (ADR-002-023 §5.4 / §11)."""

    _ID_FIELD: ClassVar[str] = "decision_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("decision_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "decision_generation",
            "request_id",
            "request_digest",
            "trading_approval_policy_id",
            "trading_approval_policy_generation",
            "trading_approval_policy_digest",
            "result",
            "reason_codes",
            "approved_intent_envelope_id",
            "approved_intent_envelope_digest",
            "max_decision_age_ms",
            "invalidation_generation",
            "supersedes_decision_id",
            "authority_effect",
        }
    )

    decision_id: str | None = None

    decision_generation: int | None = None
    request_id: str | None = None
    request_digest: str | None = None
    trading_approval_policy_id: str | None = None
    trading_approval_policy_generation: int | None = None
    trading_approval_policy_digest: str | None = None
    result: ApprovalResult | None = None
    reason_codes: tuple[str, ...] = ()
    approved_intent_envelope_id: str | None = None
    approved_intent_envelope_digest: str | None = None
    max_decision_age_ms: int | None = None
    invalidation_generation: int | None = None
    supersedes_decision_id: str | None = None
    authority_effect: ApprovalAuthorityEffect = ApprovalAuthorityEffect()

    decision_order: int | None = None


class ApprovalConsumptionRecord(IndependentIdArtifact):
    """An append-only, immutable Approval Consumption Record (ADR-002-023 §5.5 / §12)."""

    _ID_FIELD: ClassVar[str] = "consumption_record_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("consumption_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "consumption_generation",
            "decision_id",
            "decision_digest",
            "request_id",
            "request_digest",
            "intent_identity",
            "policy_generation",
            "writer_epoch",
            "txn_revision",
            "receipt_time_marker",
            "invalidation_generation",
            "result",
            "consumption_status",
            "authority_effect",
        }
    )

    consumption_record_id: str | None = None

    consumption_generation: int | None = None
    decision_id: str | None = None
    decision_digest: str | None = None
    request_id: str | None = None
    request_digest: str | None = None
    intent_identity: str | None = None
    policy_generation: int | None = None
    writer_epoch: int | None = None
    txn_revision: int | None = None
    receipt_time_marker: str | None = None
    invalidation_generation: int | None = None
    result: ApprovalResult | None = None
    consumption_status: ConsumptionStatus | None = None
    authority_effect: ApprovalAuthorityEffect = ApprovalAuthorityEffect()

    consumption_order: int | None = None
