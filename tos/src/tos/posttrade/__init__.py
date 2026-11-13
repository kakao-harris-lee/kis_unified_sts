"""Post-Trade Economic Obligations and Finality — pure models + predicates (ADR-002-030).

What the runtime finality producer and release consumer use: the obligation record, the
finality proof, its leg scope, and the five finality predicates. The rest of the package
(commit idempotency, collateral, statement coverage, the disposition producer) had no
runtime caller and was removed (plan ``docs/plans/2026-11-13-tos-code-halving-plan.md``
§S2-c); it is in git history.

**Finality proves the LEG, not the CONSEQUENCE**: every record carries an all-false
:class:`AllFalsePostTradeConsequence`, unconstructable with any ``True`` flag.

Pure package: ``pydantic`` + stdlib + ``tos.canonical`` only; no sibling ``tos.*``, no
``shared.*``.
"""

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
