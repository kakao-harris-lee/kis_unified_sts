"""Independent Proposal Approval + Exact-Decision Binding + Consumption Fencing (Phase 1, EV-L1)."""

from __future__ import annotations

from tos.canonical import RecordPairKind, classify_record_pair
from tos.iap._base import (
    AllFalseApprovalAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    IndependentIdArtifact,
)
from tos.iap.predicates import (
    active_egress_currentness,
    approval_decision,
    approval_grants_no_authority,
    conflicting_evaluators_unknown,
    decision_unexpired,
    exact_binding_holds,
    independent_validation_declared,
    invalidation_closure,
    materiality_is_material,
    no_widening_no_union,
    request_is_complete,
    unknown_confines,
)
from tos.iap.records import (
    ApprovalAuthorityEffect,
    ApprovalConsumptionRecord,
    IndependentApprovalDecision,
    MaterialApprovalChange,
    ProposalApprovalRequest,
    TradingApprovalPolicy,
)
from tos.iap.state import (
    TradingApprovalGeneration,
    consumption_transition,
    economic_effect_outlives,
    recovery_revives_nothing,
    stale_generation_fenced,
)
from tos.iap.vocabulary import (
    ApprovalResult,
    ConsumptionOutcome,
    ConsumptionStatus,
    MaterialityVerdict,
)
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    "AllFalseApprovalAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
    "Ordering",
    "OrderingEvent",
    "compare_order",
    "TradingApprovalGeneration",
    "ApprovalResult",
    "ConsumptionStatus",
    "MaterialityVerdict",
    "ConsumptionOutcome",
    "TradingApprovalPolicy",
    "ProposalApprovalRequest",
    "IndependentApprovalDecision",
    "ApprovalConsumptionRecord",
    "ApprovalAuthorityEffect",
    "MaterialApprovalChange",
    "request_is_complete",
    "approval_decision",
    "exact_binding_holds",
    "invalidation_closure",
    "materiality_is_material",
    "unknown_confines",
    "independent_validation_declared",
    "no_widening_no_union",
    "approval_grants_no_authority",
    "active_egress_currentness",
    "conflicting_evaluators_unknown",
    "consumption_transition",
    "economic_effect_outlives",
    "stale_generation_fenced",
    "recovery_revives_nothing",
    "decision_unexpired",
]
