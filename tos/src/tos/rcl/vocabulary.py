"""RCL vocabulary — capacity states, command types, transition causes, reasons."""

from __future__ import annotations

from enum import StrEnum


class CapacityState(StrEnum):
    """The 9 capacity states (ADR-002-002 §10.1 line 506-562)."""

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
    """Conceptual ledger command types (ADR-002-012 §10 + ADR-002-002 §27)."""

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

    ADVANCE_AUTHORITY_EPOCH = "AdvanceAuthorityEpoch"
    CONSUME_APPROVAL_DECISION = "ConsumeApprovalDecision"
    ISSUE_ACTION_FLOW_PERMIT = "IssueActionFlowPermit"
    ISSUE_EGRESS_CURRENTNESS_PROOF = "IssueEgressCurrentnessProof"


class TransitionCause(StrEnum):
    """Cause of a capacity-state transition (ADR-002-002 §10.2 line 566-574)."""

    STRONGLY_AUTHORIZED_COMMAND = "STRONGLY_AUTHORIZED_COMMAND"
    BROKER_EVIDENCE_UNDER_PROFILE = "BROKER_EVIDENCE_UNDER_PROFILE"
    RECONCILIATION_PROOF = "RECONCILIATION_PROOF"
    RECOGNIZED_EXTERNAL_CHANGE = "RECOGNIZED_EXTERNAL_CHANGE"
    CONTAINMENT = "CONTAINMENT"
    FINAL_QUANTITY_PROOF = "FINAL_QUANTITY_PROOF"
    TIMEOUT = "TIMEOUT"
    ABSENCE = "ABSENCE"
    OPERATOR_ASSUMPTION = "OPERATOR_ASSUMPTION"


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
