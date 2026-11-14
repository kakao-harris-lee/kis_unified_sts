"""Orthogonal Trading State pure data models + predicates (Phase 1, EV-L1)."""

from __future__ import annotations

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.orthostate._base import (
    ArtifactIntegrityError,
    ArtifactStatus,
    IndependentIdArtifact,
)
from tos.orthostate.predicates import (
    attempt_transition_allowed,
    conservative_direction_ok,
    coupling_violations,
    intent_transition_allowed,
    knowledge_transition_allowed,
    may_transition,
    no_coupling_violation,
    reconstruct_conservative,
)
from tos.orthostate.records import CompositeState, DimensionTransitionRecord
from tos.orthostate.state import CouplingSideConditions
from tos.orthostate.vocabulary import (
    WEAK_BASES,
    BrokerOrderState,
    ConservatismBasis,
    IntentState,
    KnowledgeState,
    StateDimension,
    TransitionAuthority,
    TransmissionAttemptState,
)

__all__ = [
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "IndependentIdArtifact",
    "Ordering",
    "OrderingEvent",
    "compare_order",
    "BrokerOrderState",
    "ConservatismBasis",
    "IntentState",
    "KnowledgeState",
    "StateDimension",
    "TransitionAuthority",
    "TransmissionAttemptState",
    "WEAK_BASES",
    "CompositeState",
    "DimensionTransitionRecord",
    "CouplingSideConditions",
    "attempt_transition_allowed",
    "conservative_direction_ok",
    "coupling_violations",
    "intent_transition_allowed",
    "knowledge_transition_allowed",
    "may_transition",
    "no_coupling_violation",
    "reconstruct_conservative",
]
