"""RCL vocabulary — capacity states, command types, transition causes, reasons.

Spec terms = code terms (RCL design §2, boundary design #1 §2.4). The enums are
authored verbatim from ADR-002-002 §10.1 (capacity states), ADR-002-012 §10 +
ADR-002-002 §27 (command types), and ADR-002-002 §10.2 (transition causes).

Pure module: stdlib only; no ``shared.*`` (RCL design §0.3).
"""

from __future__ import annotations

from enum import StrEnum


class CapacityState(StrEnum):
    """The 9 capacity states (ADR-002-002 §10.1 line 506-562).

    The capacity state is independent from Intent, transmission, broker-order, and
    knowledge states (§10 line 508). ``RELEASED`` is terminal for the reservation
    identity (§10.1 line 562).
    """

    COMMITTED_UNBOUND = "COMMITTED_UNBOUND"
    ATTEMPT_BOUND = "ATTEMPT_BOUND"
    POTENTIALLY_LIVE = "POTENTIALLY_LIVE"
    PARTIALLY_CONSUMED = "PARTIALLY_CONSUMED"
    POSITION_CONSUMED = "POSITION_CONSUMED"
    RELEASE_PENDING_PROOF = "RELEASE_PENDING_PROOF"
    QUARANTINED_UNKNOWN = "QUARANTINED_UNKNOWN"
    TRAPPED_CONSUMED = "TRAPPED_CONSUMED"
    RELEASED = "RELEASED"


class CommandType(StrEnum):
    """Conceptual ledger command types (ADR-002-012 §10 + ADR-002-002 §27).

    The persistence layer's 16 commands (ADR-002-012 §10 line 294-311) are the
    primary set; the ADR-002-002 §27 conceptual commands (line 1181-1199) that are
    not already named there are included as well. Both ADRs frame these as
    *semantic-equivalence* names, not a closed literal enum (ADR-012 §10 line 292);
    the enum fixes the vocabulary so a command record's ``command_type`` is a spec
    term. ``CommitReservation`` reduces conservatism-sensitive state and so requires
    stronger proof than a conservatism-increasing command (ADR-002-002 §27 line
    1212; ADR-012 §9 line 273).
    """

    # ADR-002-012 §10 (persistence-layer authoritative commands).
    ACTIVATE_WRITER_EPOCH = "ActivateWriterEpoch"
    COMMIT_RESERVATION = "CommitReservation"
    RESIZE_RESERVATION = "ResizeReservation"
    BIND_ATTEMPT = "BindAttempt"
    AUTHORIZE_TRANSMISSION_CAPABILITY = "AuthorizeTransmissionCapability"
    INVALIDATE_CAPABILITIES = "InvalidateCapabilities"
    CLAIM_CAPABILITY_AND_MARK_SEND_STARTED = "ClaimCapabilityAndMarkSendStarted"
    RECORD_FILL_AND_TRANSFER_USAGE = "RecordFillAndTransferUsage"
    QUARANTINE_UNKNOWN = "QuarantineUnknown"
    APPLY_FINAL_QUANTITY_PROOF = "ApplyFinalQuantityProof"
    RELEASE_RESERVATION = "ReleaseReservation"
    COMMIT_PROTECTIVE_POOL = "CommitProtectivePool"
    ISSUE_PROTECTIVE_LEASE = "IssueProtectiveLease"
    RECONCILE_PROTECTIVE_LEASE = "ReconcileProtectiveLease"
    ADVANCE_RESTORE_GENERATION = "AdvanceRestoreGeneration"
    CHANGE_MEMBERSHIP = "ChangeMembership"

    # ADR-002-002 §27 conceptual commands not already covered above.
    CONSUME_TRANSMISSION_CAPABILITY = "ConsumeTransmissionCapability"
    MARK_SEND_STARTED = "MarkSendStarted"
    RECORD_BROKER_ACKNOWLEDGEMENT = "RecordBrokerAcknowledgement"
    RECORD_BROKER_REJECTION = "RecordBrokerRejection"
    RECORD_FILL = "RecordFill"
    REQUEST_CANCEL = "RequestCancel"
    RECORD_FINAL_QUANTITY_PROOF = "RecordFinalQuantityProof"
    TRANSFER_ORDER_TO_POSITION_USAGE = "TransferOrderToPositionUsage"
    CREATE_EXTERNAL_QUARANTINE = "CreateExternalQuarantine"
    MARK_TRAPPED_EXPOSURE = "MarkTrappedExposure"
    CONSUME_PROTECTIVE_LEASE = "ConsumeProtectiveLease"


class TransitionCause(StrEnum):
    """Cause of a capacity-state transition (ADR-002-002 §10.2 line 566-574).

    The five §10.2 causes plus a distinguished ``FINAL_QUANTITY_PROOF`` (the §5
    INV-007 proof rule that alone may reach ``RELEASED``). The three *weak* causes
    (``TIMEOUT`` / ``ABSENCE`` / ``OPERATOR_ASSUMPTION``) may only **increase**
    conservatism — no less-conservative transition may be made solely from them
    (§10.2 line 574).
    """

    STRONGLY_AUTHORIZED_COMMAND = "STRONGLY_AUTHORIZED_COMMAND"
    BROKER_EVIDENCE_UNDER_PROFILE = "BROKER_EVIDENCE_UNDER_PROFILE"
    RECONCILIATION_PROOF = "RECONCILIATION_PROOF"
    RECOGNIZED_EXTERNAL_CHANGE = "RECOGNIZED_EXTERNAL_CHANGE"
    CONTAINMENT = "CONTAINMENT"
    FINAL_QUANTITY_PROOF = "FINAL_QUANTITY_PROOF"
    # Weak causes — may only increase conservatism (§10.2 line 574).
    TIMEOUT = "TIMEOUT"
    ABSENCE = "ABSENCE"
    OPERATOR_ASSUMPTION = "OPERATOR_ASSUMPTION"


#: The weak causes that may never drive a less-conservative transition (§10.2 574).
WEAK_CAUSES: frozenset[TransitionCause] = frozenset(
    {
        TransitionCause.TIMEOUT,
        TransitionCause.ABSENCE,
        TransitionCause.OPERATOR_ASSUMPTION,
    }
)


class ApplyReason(StrEnum):
    """Outcome reason of the deterministic reducer (RCL design §5.2)."""

    ADMITTED = "ADMITTED"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    REJECTED_UNIDENTIFIED = "REJECTED_UNIDENTIFIED"
    REJECTED_CRITICAL_CONFLICT = "REJECTED_CRITICAL_CONFLICT"
    REJECTED_STALE_REVISION = "REJECTED_STALE_REVISION"
    REJECTED_LIMIT_EXCEEDED = "REJECTED_LIMIT_EXCEEDED"
    REJECTED_UNKNOWN_DIMENSION = "REJECTED_UNKNOWN_DIMENSION"
    REJECTED_TERMINAL = "REJECTED_TERMINAL"
