"""Pure orthostate predicates (design #8 §5, §6; ADR-002-005 §10-§13)."""

from __future__ import annotations

from tos.orthostate.records import CompositeState
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
from tos.rcl import (
    CapacityState,
    TransitionCause,
    capacity_at_least_as_conservative,
    transition_allowed,
)

_ATTEMPT_POTENTIALLY_LIVE: frozenset[TransmissionAttemptState] = frozenset(
    {TransmissionAttemptState.SEND_STARTED, TransmissionAttemptState.SENT_UNCONFIRMED}
)

_CPL2_RELEASE_BROKER_STATES: frozenset[BrokerOrderState] = frozenset(
    {
        BrokerOrderState.CANCELLED,
        BrokerOrderState.REJECTED,
        BrokerOrderState.EXPIRED,
        BrokerOrderState.FILLED,
    }
)

_CPL5_KNOWLEDGE_STATES: frozenset[KnowledgeState] = frozenset(
    {KnowledgeState.CONFLICTED, KnowledgeState.QUARANTINED}
)

_ATTEMPT_SEND_STARTED_AND_BEYOND: frozenset[TransmissionAttemptState] = frozenset(
    {
        TransmissionAttemptState.SEND_STARTED,
        TransmissionAttemptState.SENT_UNCONFIRMED,
        TransmissionAttemptState.ACK_OBSERVED,
        TransmissionAttemptState.SEND_FAILED_PROVEN,
        TransmissionAttemptState.SUPERSEDED,
    }
)


def coupling_violations(
    composite: CompositeState,
    side: CouplingSideConditions | None = None,
) -> frozenset[str]:
    """The set of violated cross-dimension coupling invariants (design #8 §5; §10)."""
    if side is None:
        side = CouplingSideConditions()

    attempt = composite.transmission_attempt_state
    broker = composite.broker_order_state
    knowledge = composite.knowledge_state
    cap = composite.capacity_state

    violations: set[str] = set()

    if attempt in _ATTEMPT_POTENTIALLY_LIVE or broker is BrokerOrderState.UNKNOWN:
        if not capacity_at_least_as_conservative(cap, CapacityState.POTENTIALLY_LIVE):
            violations.add("CPL-1")

    if cap is CapacityState.RELEASED:
        knowledge_proven = knowledge is KnowledgeState.RECONCILED or (
            knowledge is KnowledgeState.CONSISTENT
            and side.consistent_release_proof_rule is True
        )
        broker_terminal = broker in _CPL2_RELEASE_BROKER_STATES
        fqp_proven = side.final_quantity_proof is True
        if not (knowledge_proven and broker_terminal and fqp_proven):
            violations.add("CPL-2")

    if broker is BrokerOrderState.FILLED and cap is not CapacityState.POSITION_CONSUMED:
        violations.add("CPL-3")
    if (
        broker is BrokerOrderState.PARTIALLY_FILLED
        and cap is not CapacityState.PARTIALLY_CONSUMED
    ):
        violations.add("CPL-3")

    bare_cancel_ack = (
        broker is BrokerOrderState.CANCELLED and side.final_quantity_proof is None
    )
    if broker is BrokerOrderState.CANCEL_PENDING or bare_cancel_ack:
        if cap is CapacityState.RELEASED:
            violations.add("CPL-4")

    if broker is BrokerOrderState.UNKNOWN or knowledge in _CPL5_KNOWLEDGE_STATES:
        if cap is not CapacityState.QUARANTINED_UNKNOWN:
            violations.add("CPL-5")

    if attempt in _ATTEMPT_SEND_STARTED_AND_BEYOND:
        if side.authority_epoch_current is not True:
            violations.add("CPL-6")

    if side.non_reducible_exposure is True:
        if cap is not CapacityState.TRAPPED_CONSUMED:
            violations.add("CPL-7")

    return frozenset(violations)


def no_coupling_violation(
    composite: CompositeState,
    side: CouplingSideConditions | None = None,
) -> bool:
    """Whether no CPL invariant violation is detected (design #8 §5.1)."""
    return not coupling_violations(composite, side)


_INTENT_CONSERVATISM_RANK: dict[IntentState, int] = {
    IntentState.CLOSED: 0,
    IntentState.WITHDRAWN: 0,
    IntentState.ACTIVE: 1,
    IntentState.AUTHORIZED_FOR_CAPACITY: 2,
    IntentState.APPROVED: 3,
    IntentState.PROPOSED: 4,
    IntentState.DENIED: 5,
}

_ATTEMPT_CONSERVATISM_RANK: dict[TransmissionAttemptState, int] = {
    TransmissionAttemptState.SEND_FAILED_PROVEN: 0,
    TransmissionAttemptState.NONE: 1,
    TransmissionAttemptState.PREPARED: 2,
    TransmissionAttemptState.CAPABILITY_ISSUED: 3,
    TransmissionAttemptState.SUPERSEDED: 4,
    TransmissionAttemptState.ACK_OBSERVED: 5,
    TransmissionAttemptState.SENT_UNCONFIRMED: 6,
    TransmissionAttemptState.SEND_STARTED: 7,
}

_BROKER_CONSERVATISM_RANK: dict[BrokerOrderState, int] = {
    BrokerOrderState.NONE_OBSERVED: 0,
    BrokerOrderState.CANCELLED: 1,
    BrokerOrderState.REJECTED: 1,
    BrokerOrderState.EXPIRED: 1,
    BrokerOrderState.WORKING: 2,
    BrokerOrderState.CANCEL_PENDING: 3,
    BrokerOrderState.PARTIALLY_FILLED: 4,
    BrokerOrderState.FILLED: 5,
    BrokerOrderState.UNKNOWN: 6,
}

_KNOWLEDGE_CONSERVATISM_RANK: dict[KnowledgeState, int] = {
    KnowledgeState.RECONCILED: 0,
    KnowledgeState.CONSISTENT: 1,
    KnowledgeState.RECONCILING: 2,
    KnowledgeState.UNOBSERVED: 3,
    KnowledgeState.STALE: 4,
    KnowledgeState.CONFLICTED: 5,
    KnowledgeState.QUARANTINED: 6,
}

_LOCAL_CONSERVATISM_RANK: dict[StateDimension, dict] = {
    StateDimension.INTENT: _INTENT_CONSERVATISM_RANK,
    StateDimension.TRANSMISSION_ATTEMPT: _ATTEMPT_CONSERVATISM_RANK,
    StateDimension.BROKER_ORDER: _BROKER_CONSERVATISM_RANK,
    StateDimension.KNOWLEDGE: _KNOWLEDGE_CONSERVATISM_RANK,
}


def conservative_direction_ok(
    dimension: StateDimension,
    from_state: object,
    to_state: object,
    basis: ConservatismBasis | TransitionCause | None,
) -> bool:
    """Whether a per-dimension transition respects the conservative-direction rule (§6.1)."""
    if dimension is StateDimension.CAPACITY:
        if not isinstance(from_state, CapacityState) or not isinstance(
            to_state, CapacityState
        ):
            return False
        if not isinstance(basis, TransitionCause):
            return False
        return transition_allowed(from_state, to_state, basis)

    rank = _LOCAL_CONSERVATISM_RANK.get(dimension)
    if rank is None:
        return False
    if from_state not in rank or to_state not in rank:
        return False
    if rank[to_state] >= rank[from_state]:
        return True
    return isinstance(basis, ConservatismBasis) and basis not in WEAK_BASES


_INTENT_TRANSITIONS: frozenset[tuple[IntentState, IntentState]] = frozenset(
    {
        (IntentState.PROPOSED, IntentState.APPROVED),
        (IntentState.APPROVED, IntentState.AUTHORIZED_FOR_CAPACITY),
        (IntentState.APPROVED, IntentState.DENIED),
        (IntentState.AUTHORIZED_FOR_CAPACITY, IntentState.ACTIVE),
        (IntentState.ACTIVE, IntentState.CLOSED),
        (IntentState.ACTIVE, IntentState.WITHDRAWN),
    }
)

_INTENT_PROOF_REQUIRED: frozenset[IntentState] = frozenset(
    {IntentState.CLOSED, IntentState.WITHDRAWN}
)

_ATTEMPT_TRANSITIONS: frozenset[
    tuple[TransmissionAttemptState, TransmissionAttemptState]
] = frozenset(
    {
        (TransmissionAttemptState.NONE, TransmissionAttemptState.PREPARED),
        (
            TransmissionAttemptState.PREPARED,
            TransmissionAttemptState.CAPABILITY_ISSUED,
        ),
        (
            TransmissionAttemptState.CAPABILITY_ISSUED,
            TransmissionAttemptState.SEND_STARTED,
        ),
        (
            TransmissionAttemptState.SEND_STARTED,
            TransmissionAttemptState.SENT_UNCONFIRMED,
        ),
        (
            TransmissionAttemptState.SENT_UNCONFIRMED,
            TransmissionAttemptState.ACK_OBSERVED,
        ),
        (
            TransmissionAttemptState.SENT_UNCONFIRMED,
            TransmissionAttemptState.SEND_FAILED_PROVEN,
        ),
        (
            TransmissionAttemptState.SENT_UNCONFIRMED,
            TransmissionAttemptState.SUPERSEDED,
        ),
    }
)

_KNOWLEDGE_TRANSITIONS: frozenset[tuple[KnowledgeState, KnowledgeState]] = frozenset(
    {
        (KnowledgeState.UNOBSERVED, KnowledgeState.CONSISTENT),
        (KnowledgeState.UNOBSERVED, KnowledgeState.CONFLICTED),
        (KnowledgeState.CONSISTENT, KnowledgeState.CONFLICTED),
        (KnowledgeState.RECONCILED, KnowledgeState.CONFLICTED),
        (KnowledgeState.CONFLICTED, KnowledgeState.RECONCILING),
        (KnowledgeState.RECONCILING, KnowledgeState.RECONCILED),
        (KnowledgeState.RECONCILING, KnowledgeState.QUARANTINED),
        (KnowledgeState.QUARANTINED, KnowledgeState.RECONCILING),
        (KnowledgeState.CONSISTENT, KnowledgeState.STALE),
        (KnowledgeState.RECONCILED, KnowledgeState.STALE),
    }
)


def intent_transition_allowed(
    from_state: IntentState | None,
    to_state: IntentState | None,
    *,
    no_potentially_live_proof: bool | None = None,
) -> bool:
    """Whether an Intent transition is legal (design #8 §6; ADR-002-005 §5)."""
    if from_state is None or to_state is None:
        return False
    if (from_state, to_state) not in _INTENT_TRANSITIONS:
        return False
    if to_state in _INTENT_PROOF_REQUIRED:
        return no_potentially_live_proof is True
    return True


def attempt_transition_allowed(
    from_state: TransmissionAttemptState | None,
    to_state: TransmissionAttemptState | None,
    *,
    positive_send_failure_evidence: bool | None = None,
) -> bool:
    """Whether a Transmission-Attempt transition is legal (design #8 §6; ADR-002-005 §6)."""
    if from_state is None or to_state is None:
        return False
    if (from_state, to_state) not in _ATTEMPT_TRANSITIONS:
        return False
    if to_state is TransmissionAttemptState.SEND_FAILED_PROVEN:
        return positive_send_failure_evidence is True
    return True


def knowledge_transition_allowed(
    from_state: KnowledgeState | None,
    to_state: KnowledgeState | None,
    *,
    corroboration: bool | None = None,
    final_quantity_proof_where_broker_involved: bool | None = None,
    freshness_lost: bool | None = None,
    quarantine_exit_evidence: bool | None = None,
) -> bool:
    """Whether a Knowledge transition is legal (design #8 §6; ADR-002-005 §8)."""
    if from_state is None or to_state is None:
        return False
    if (from_state, to_state) not in _KNOWLEDGE_TRANSITIONS:
        return False
    if to_state is KnowledgeState.RECONCILED:
        return (
            corroboration is True and final_quantity_proof_where_broker_involved is True
        )
    if to_state is KnowledgeState.STALE:
        return freshness_lost is True
    if from_state is KnowledgeState.QUARANTINED:
        return quarantine_exit_evidence is True
    return True


_DIMENSION_OWNERS: dict[StateDimension, frozenset[TransitionAuthority]] = {
    StateDimension.INTENT: frozenset({TransitionAuthority.INTENT_REGISTRY}),
    StateDimension.BROKER_ORDER: frozenset(
        {TransitionAuthority.BROKER_ADAPTER_EVIDENCE}
    ),
    StateDimension.KNOWLEDGE: frozenset({TransitionAuthority.RECONCILIATION_SERVICE}),
    StateDimension.CAPACITY: frozenset({TransitionAuthority.RISK_CAPACITY_LEDGER}),
}

_ATTEMPT_PREP_REGION: frozenset[TransmissionAttemptState] = frozenset(
    {
        TransmissionAttemptState.PREPARED,
        TransmissionAttemptState.CAPABILITY_ISSUED,
    }
)

_ATTEMPT_SEND_BOUNDARY_REGION: frozenset[TransmissionAttemptState] = frozenset(
    {
        TransmissionAttemptState.SEND_STARTED,
        TransmissionAttemptState.SENT_UNCONFIRMED,
        TransmissionAttemptState.ACK_OBSERVED,
        TransmissionAttemptState.SEND_FAILED_PROVEN,
        TransmissionAttemptState.SUPERSEDED,
    }
)


def may_transition(
    actor: TransitionAuthority | None,
    dimension: StateDimension,
    from_state: object,
    to_state: object,
) -> bool:
    """Whether ``actor`` owns the authority for this dimension transition (§6.2; §12)."""
    if actor is None:
        return False
    if dimension is StateDimension.TRANSMISSION_ATTEMPT:
        if from_state is None or to_state is None:
            return False
        if to_state in _ATTEMPT_PREP_REGION:
            return actor is TransitionAuthority.EXECUTION_COORDINATOR
        if to_state in _ATTEMPT_SEND_BOUNDARY_REGION:
            return actor is TransitionAuthority.BROKER_ADAPTER_EGRESS
        return False
    owners = _DIMENSION_OWNERS.get(dimension)
    if owners is None:
        return False
    return actor in owners


_ATTEMPT_POTENTIALLY_LIVE_AFTER_RESTART: frozenset[TransmissionAttemptState] = (
    frozenset(
        {
            TransmissionAttemptState.SEND_STARTED,
            TransmissionAttemptState.SENT_UNCONFIRMED,
            TransmissionAttemptState.ACK_OBSERVED,
            TransmissionAttemptState.SUPERSEDED,
        }
    )
)

_BROKER_STRUCTURALLY_TERMINAL: frozenset[BrokerOrderState] = frozenset(
    {
        BrokerOrderState.FILLED,
        BrokerOrderState.CANCELLED,
        BrokerOrderState.REJECTED,
        BrokerOrderState.EXPIRED,
    }
)

_KNOWLEDGE_DOWNGRADE_ON_RESTART: frozenset[KnowledgeState] = frozenset(
    {KnowledgeState.RECONCILED, KnowledgeState.CONSISTENT}
)


def reconstruct_conservative(pre: CompositeState) -> CompositeState:
    """Project a pre-restart composite to a conservative post-restart one (§6.3; §13)."""
    post_capacity = pre.capacity_state
    if pre.transmission_attempt_state in _ATTEMPT_POTENTIALLY_LIVE_AFTER_RESTART:
        if not capacity_at_least_as_conservative(
            pre.capacity_state, CapacityState.POTENTIALLY_LIVE
        ):
            post_capacity = CapacityState.POTENTIALLY_LIVE

    if (
        pre.broker_order_state in _BROKER_STRUCTURALLY_TERMINAL
        or pre.broker_order_state is BrokerOrderState.UNKNOWN
    ):
        post_broker = pre.broker_order_state
    else:
        post_broker = BrokerOrderState.UNKNOWN

    if pre.knowledge_state in _KNOWLEDGE_DOWNGRADE_ON_RESTART:
        post_knowledge = KnowledgeState.CONFLICTED
    else:
        post_knowledge = pre.knowledge_state

    return CompositeState(
        intent_identity=pre.intent_identity,
        intent_state=pre.intent_state,
        transmission_attempt_state=pre.transmission_attempt_state,
        broker_order_state=post_broker,
        knowledge_state=post_knowledge,
        capacity_state=post_capacity,
        state_model_version=pre.state_model_version,
    )
