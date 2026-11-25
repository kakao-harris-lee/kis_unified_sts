"""Orthostate ledger-citizen records — composite observation + transition (§2, §4)."""

from __future__ import annotations

from typing import ClassVar

from tos.orthostate._base import IndependentIdArtifact
from tos.orthostate.vocabulary import (
    BrokerOrderState,
    IntentState,
    KnowledgeState,
    StateDimension,
    TransitionAuthority,
    TransmissionAttemptState,
)
from tos.rcl import CapacityState


class CompositeState(IndependentIdArtifact):
    """One append-only observation of the five orthogonal dimensions (§2.2 / §14)."""

    _ID_FIELD: ClassVar[str] = "composite_state_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "intent_identity",
        "intent_state",
        "transmission_attempt_state",
        "broker_order_state",
        "knowledge_state",
        "capacity_state",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "intent_identity",
            "intent_state",
            "transmission_attempt_state",
            "broker_order_state",
            "knowledge_state",
            "capacity_state",
            "state_model_version",
        }
    )

    composite_state_id: str | None = None

    intent_identity: str | None = None
    intent_state: IntentState
    transmission_attempt_state: TransmissionAttemptState
    broker_order_state: BrokerOrderState
    knowledge_state: KnowledgeState
    capacity_state: CapacityState
    state_model_version: str | None = None

    observation_revision: int | None = None


class DimensionTransitionRecord(IndependentIdArtifact):
    """One append-only per-dimension transition record (§2.4; ADR-002-005 §12/§13)."""

    _ID_FIELD: ClassVar[str] = "transition_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "intent_identity",
        "dimension",
        "from_state",
        "to_state",
        "owning_authority",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "intent_identity",
            "dimension",
            "from_state",
            "to_state",
            "owning_authority",
            "basis",
            "evidence_reference",
            "observation_revision",
        }
    )

    transition_id: str | None = None

    intent_identity: str | None = None
    dimension: StateDimension | None = None
    from_state: str | None = None
    to_state: str | None = None
    owning_authority: TransitionAuthority | None = None
    basis: str | None = None
    evidence_reference: str | None = None
    observation_revision: int | None = None
