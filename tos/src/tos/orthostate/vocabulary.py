"""Orthostate vocabulary — the four local dimension enums + coordination enums."""

from __future__ import annotations

from enum import StrEnum


class IntentState(StrEnum):
    """The 7 Intent-dimension states (ADR-002-005 §5 line 65-77)."""

    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    AUTHORIZED_FOR_CAPACITY = "AUTHORIZED_FOR_CAPACITY"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    DENIED = "DENIED"
    WITHDRAWN = "WITHDRAWN"


class TransmissionAttemptState(StrEnum):
    """The 8 Transmission-Attempt-dimension states (ADR-002-005 §6 line 81-99)."""

    NONE = "NONE"
    PREPARED = "PREPARED"
    CAPABILITY_ISSUED = "CAPABILITY_ISSUED"
    SEND_STARTED = "SEND_STARTED"
    SENT_UNCONFIRMED = "SENT_UNCONFIRMED"
    ACK_OBSERVED = "ACK_OBSERVED"
    SEND_FAILED_PROVEN = "SEND_FAILED_PROVEN"
    SUPERSEDED = "SUPERSEDED"


class BrokerOrderState(StrEnum):
    """The 9 Broker-Order-dimension states (ADR-002-005 §7 line 102-122)."""

    NONE_OBSERVED = "NONE_OBSERVED"
    WORKING = "WORKING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class KnowledgeState(StrEnum):
    """The 7 Knowledge / Evidence-dimension states (ADR-002-005 §8 line 126-142)."""

    UNOBSERVED = "UNOBSERVED"
    CONSISTENT = "CONSISTENT"
    CONFLICTED = "CONFLICTED"
    RECONCILING = "RECONCILING"
    RECONCILED = "RECONCILED"
    QUARANTINED = "QUARANTINED"
    STALE = "STALE"


class StateDimension(StrEnum):
    """The five orthogonal state dimensions (design #8 §6.2; ADR-002-005 §1 line 15-22)."""

    INTENT = "INTENT"
    TRANSMISSION_ATTEMPT = "TRANSMISSION_ATTEMPT"
    BROKER_ORDER = "BROKER_ORDER"
    KNOWLEDGE = "KNOWLEDGE"
    CAPACITY = "CAPACITY"


class TransitionAuthority(StrEnum):
    """The six exclusive transition authorities (design #8 §6.2; ADR-002-005 §12)."""

    INTENT_REGISTRY = "INTENT_REGISTRY"
    EXECUTION_COORDINATOR = "EXECUTION_COORDINATOR"
    BROKER_ADAPTER_EGRESS = "BROKER_ADAPTER_EGRESS"
    BROKER_ADAPTER_EVIDENCE = "BROKER_ADAPTER_EVIDENCE"
    RECONCILIATION_SERVICE = "RECONCILIATION_SERVICE"
    RISK_CAPACITY_LEDGER = "RISK_CAPACITY_LEDGER"


class ConservatismBasis(StrEnum):
    """Basis for a per-dimension conservative-direction transition (design #8 §6.1)."""

    TIMEOUT = "TIMEOUT"
    ABSENCE = "ABSENCE"
    LOCAL_CACHE = "LOCAL_CACHE"
    OPERATOR_ASSERTION = "OPERATOR_ASSERTION"
    RECOVERY_RECONNECT = "RECOVERY_RECONNECT"
    BROKER_EVIDENCE_UNDER_PROFILE = "BROKER_EVIDENCE_UNDER_PROFILE"
    POSITIVE_CORROBORATION = "POSITIVE_CORROBORATION"
    POSITIVE_SEND_FAILURE_PROOF = "POSITIVE_SEND_FAILURE_PROOF"
    AUTHORITY_DECISION = "AUTHORITY_DECISION"


WEAK_BASES: frozenset[ConservatismBasis] = frozenset(
    {
        ConservatismBasis.TIMEOUT,
        ConservatismBasis.ABSENCE,
        ConservatismBasis.LOCAL_CACHE,
        ConservatismBasis.OPERATOR_ASSERTION,
        ConservatismBasis.RECOVERY_RECONNECT,
    }
)
