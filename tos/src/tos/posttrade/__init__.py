"""Post-Trade Economic Obligations and Finality — pure models + predicates (ADR-002-030)."""

from __future__ import annotations

from tos.posttrade._base import ArtifactStatus
from tos.posttrade.predicates import (
    finality_dimensions_orthogonal,
    finality_proof_class_specific,
    finality_proof_current,
    finality_proof_non_transferable,
    obligation_leg_set_complete,
)
from tos.posttrade.records import (
    AllFalsePostTradeConsequence,
    EconomicObligationRecord,
    ObligationLeg,
    ObligationLegScope,
    PostTradeFinalityProof,
)
from tos.posttrade.vocabulary import (
    EventObligationLegKind,
    FinalityDimensionKind,
    ObligationLegDirection,
    PostTradeObligationLifecycleState,
)

__all__ = [
    "AllFalsePostTradeConsequence",
    "ArtifactStatus",
    "EconomicObligationRecord",
    "EventObligationLegKind",
    "FinalityDimensionKind",
    "ObligationLeg",
    "ObligationLegDirection",
    "ObligationLegScope",
    "PostTradeFinalityProof",
    "PostTradeObligationLifecycleState",
    "finality_dimensions_orthogonal",
    "finality_proof_class_specific",
    "finality_proof_current",
    "finality_proof_non_transferable",
    "obligation_leg_set_complete",
]
