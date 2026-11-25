"""``EgressResultKind`` / reservation projection -> ADR-002-005 ``CompositeState`` adapter."""

from __future__ import annotations

from tos.engine._base import ArtifactIntegrityError
from tos.engine.records import ProvisionalReservation
from tos.engine.state import knowledge_for_result
from tos.engine.vocabulary import EgressKnowledge, EgressResultKind
from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    IntentState,
    KnowledgeState,
    TransmissionAttemptState,
)

__all__ = [
    "composite_state_for",
    "result_transition_for",
]


_KNOWLEDGE_ORTHOSTATE_PROJECTION: dict[
    EgressKnowledge, tuple[BrokerOrderState, KnowledgeState]
] = {
    EgressKnowledge.NOT_SENT: (
        BrokerOrderState.NONE_OBSERVED,
        KnowledgeState.UNOBSERVED,
    ),
    EgressKnowledge.SENT_UNCONFIRMED: (
        BrokerOrderState.NONE_OBSERVED,
        KnowledgeState.UNOBSERVED,
    ),
    EgressKnowledge.ACKNOWLEDGED: (BrokerOrderState.WORKING, KnowledgeState.CONSISTENT),
    EgressKnowledge.PARTIALLY_FILLED: (
        BrokerOrderState.PARTIALLY_FILLED,
        KnowledgeState.CONSISTENT,
    ),
    EgressKnowledge.FILLED: (BrokerOrderState.FILLED, KnowledgeState.CONSISTENT),
    EgressKnowledge.REJECTED: (BrokerOrderState.REJECTED, KnowledgeState.CONSISTENT),
    EgressKnowledge.UNKNOWN: (BrokerOrderState.UNKNOWN, KnowledgeState.UNOBSERVED),
    EgressKnowledge.CANCEL_ACKNOWLEDGED: (
        BrokerOrderState.CANCEL_PENDING,
        KnowledgeState.CONSISTENT,
    ),
    EgressKnowledge.EXPIRED: (BrokerOrderState.EXPIRED, KnowledgeState.CONSISTENT),
}

_RESULT_ATTEMPT_TRANSITION: dict[EgressResultKind, TransmissionAttemptState] = {
    EgressResultKind.ACK: TransmissionAttemptState.ACK_OBSERVED,
    EgressResultKind.FULL_FILL: TransmissionAttemptState.ACK_OBSERVED,
    EgressResultKind.PARTIAL_FILL: TransmissionAttemptState.ACK_OBSERVED,
    EgressResultKind.REJECT: TransmissionAttemptState.SEND_FAILED_PROVEN,
    EgressResultKind.UNKNOWN: TransmissionAttemptState.SENT_UNCONFIRMED,
    EgressResultKind.TIMEOUT: TransmissionAttemptState.SENT_UNCONFIRMED,
    EgressResultKind.CANCEL_ACK: TransmissionAttemptState.ACK_OBSERVED,
    EgressResultKind.EXPIRED: TransmissionAttemptState.ACK_OBSERVED,
}


def result_transition_for(
    kind: EgressResultKind,
) -> tuple[TransmissionAttemptState, BrokerOrderState, KnowledgeState]:
    """The ADR-002-005 §6-§8 triple a fresh ``EGRESS_RESULT`` of ``kind`` projects onto."""
    attempt = _RESULT_ATTEMPT_TRANSITION.get(kind)
    if attempt is None:
        raise ArtifactIntegrityError(
            f"no orthostate Transmission-Attempt projection is declared for egress result "
            f"kind {kind!r} (fail-closed) — engine/orthostate_projection.py must map every "
            "member of the closed EgressResultKind vocabulary"
        )
    broker, knowledge = _KNOWLEDGE_ORTHOSTATE_PROJECTION[knowledge_for_result(kind)]
    return attempt, broker, knowledge


def composite_state_for(
    projection: ProvisionalReservation,
    *,
    intent_state: IntentState,
    attempt_state: TransmissionAttemptState,
) -> CompositeState:
    """Build one ADR-002-005 ``CompositeState`` observation from the engine's own projection."""
    mapped = _KNOWLEDGE_ORTHOSTATE_PROJECTION.get(projection.knowledge)
    if mapped is None:
        raise ArtifactIntegrityError(
            f"no orthostate Broker-Order/Knowledge projection is declared for "
            f"EgressKnowledge {projection.knowledge!r} (fail-closed)"
        )
    broker, knowledge = mapped
    return CompositeState(
        intent_identity=projection.proposal_id,
        intent_state=intent_state,
        transmission_attempt_state=attempt_state,
        broker_order_state=broker,
        knowledge_state=knowledge,
        capacity_state=projection.capacity_state,
    )
