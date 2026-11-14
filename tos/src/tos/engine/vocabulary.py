"""Closed engine vocabulary — event kinds, stage outcomes, and the 19-step flow (design #31 §2.2/§4)."""

from __future__ import annotations

from enum import StrEnum

from tos.dsl import ADMISSIBLE_CONTEXT_SOURCES
from tos.engine._base import ArtifactIntegrityError

__all__ = [
    "ADMISSIBLE_EVENT_KINDS",
    "CAPSULE_CONTEXT_SOURCE",
    "COMMITMENT_FLOW_ORDER",
    "CONFIG_CONTEXT_SOURCE",
    "COORDINATOR_REALIZED_STEPS",
    "GUARANTEED_FAIL_CLOSED_STEPS",
    "INJECTED_STAGE_STEPS",
    "RESERVATION_DISCARDED_UNSENT_KIND",
    "SEND_BOUNDARY_STEPS",
    "SEQUENCED_STEPS",
    "AdmissionVerdict",
    "CommitmentStep",
    "DispatchResolution",
    "EgressKnowledge",
    "EgressResultKind",
    "EventKind",
    "EvidenceKind",
    "HaltReason",
    "OrderingAdmission",
    "ResultDisposition",
    "StageAuthorityClass",
    "StageOutcome",
    "UnsentDiscardReason",
    "step_number",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that refuses truthiness testing (truthy-sentinel seal, #14 M1 precedent)."""

    def __bool__(self) -> bool:
        """Reject truthiness outright."""
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive-identity "
            "gate (e.g. `outcome is StageOutcome.ADMIT`); a bare `if value:` would read a denial "
            "as a pass (design #31 §4.2 rule 1 / §6)"
        )


class EventKind(StrEnum):
    """The closed set of event kinds the single event core processes (design #31 §2.2)."""

    DECISION_TICK = "DECISION_TICK"
    EGRESS_RESULT = "EGRESS_RESULT"


ADMISSIBLE_EVENT_KINDS: frozenset[EventKind] = frozenset(
    {EventKind.DECISION_TICK, EventKind.EGRESS_RESULT}
)


class EgressResultKind(_NonTruthyStrEnum):
    """The typed results the D-E4 send boundary re-injects (design #31 §2.2)."""

    ACK = "ACK"
    FULL_FILL = "FULL_FILL"
    PARTIAL_FILL = "PARTIAL_FILL"
    REJECT = "REJECT"
    UNKNOWN = "UNKNOWN"
    TIMEOUT = "TIMEOUT"
    CANCEL_ACK = "CANCEL_ACK"
    EXPIRED = "EXPIRED"


FILL_RESULT_KINDS: frozenset[EgressResultKind] = frozenset(
    {EgressResultKind.FULL_FILL, EgressResultKind.PARTIAL_FILL}
)

TERMINAL_RESULT_KINDS: frozenset[EgressResultKind] = frozenset(
    {
        EgressResultKind.FULL_FILL,
        EgressResultKind.REJECT,
        EgressResultKind.CANCEL_ACK,
        EgressResultKind.EXPIRED,
    }
)


class EgressKnowledge(StrEnum):
    """Knowledge about the fate of a handed-off attempt — ``UNKNOWN`` is an explicit member."""

    NOT_SENT = "NOT_SENT"
    SENT_UNCONFIRMED = "SENT_UNCONFIRMED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    CANCEL_ACKNOWLEDGED = "CANCEL_ACKNOWLEDGED"
    EXPIRED = "EXPIRED"


class CommitmentStep(StrEnum):
    """The 19 numbered steps of ADR-002-002 §11 Normal Commitment Flow (design #31 §1.3)."""

    DECISION_PROPOSAL = "DECISION_PROPOSAL"
    CANDIDATE_COMMAND_CONSTRUCTION = "CANDIDATE_COMMAND_CONSTRUCTION"
    VENUE_ADMISSIBILITY_DECISION = "VENUE_ADMISSIBILITY_DECISION"
    INDEPENDENT_APPROVAL = "INDEPENDENT_APPROVAL"
    ECONOMIC_EFFECT_ENVELOPE = "ECONOMIC_EFFECT_ENVELOPE"
    AGGREGATE_RISK_DECISION = "AGGREGATE_RISK_DECISION"
    ACTION_FLOW_DECISION = "ACTION_FLOW_DECISION"
    LEDGER_VERIFICATION = "LEDGER_VERIFICATION"
    ATOMIC_COMMIT = "ATOMIC_COMMIT"
    COMMITMENT_UNAVAILABILITY = "COMMITMENT_UNAVAILABILITY"
    ORDER_CONFORMANCE_PROOF = "ORDER_CONFORMANCE_PROOF"
    ATTEMPT_REQUEST = "ATTEMPT_REQUEST"
    ATTEMPT_BIND_VERIFICATION = "ATTEMPT_BIND_VERIFICATION"
    TRANSMISSION_CAPABILITY = "TRANSMISSION_CAPABILITY"
    SEND_BOUNDARY_VERIFICATION = "SEND_BOUNDARY_VERIFICATION"
    SEND_STARTED_DURABLE = "SEND_STARTED_DURABLE"
    POTENTIALLY_LIVE_TRANSITION = "POTENTIALLY_LIVE_TRANSITION"
    NETWORK_CALL = "NETWORK_CALL"
    EVIDENCE_RECORD = "EVIDENCE_RECORD"


COMMITMENT_FLOW_ORDER: tuple[CommitmentStep, ...] = (
    CommitmentStep.DECISION_PROPOSAL,
    CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION,
    CommitmentStep.VENUE_ADMISSIBILITY_DECISION,
    CommitmentStep.INDEPENDENT_APPROVAL,
    CommitmentStep.ECONOMIC_EFFECT_ENVELOPE,
    CommitmentStep.AGGREGATE_RISK_DECISION,
    CommitmentStep.ACTION_FLOW_DECISION,
    CommitmentStep.LEDGER_VERIFICATION,
    CommitmentStep.ATOMIC_COMMIT,
    CommitmentStep.COMMITMENT_UNAVAILABILITY,
    CommitmentStep.ORDER_CONFORMANCE_PROOF,
    CommitmentStep.ATTEMPT_REQUEST,
    CommitmentStep.ATTEMPT_BIND_VERIFICATION,
    CommitmentStep.TRANSMISSION_CAPABILITY,
    CommitmentStep.SEND_BOUNDARY_VERIFICATION,
    CommitmentStep.SEND_STARTED_DURABLE,
    CommitmentStep.POTENTIALLY_LIVE_TRANSITION,
    CommitmentStep.NETWORK_CALL,
    CommitmentStep.EVIDENCE_RECORD,
)

SEND_BOUNDARY_STEPS: frozenset[CommitmentStep] = frozenset(
    COMMITMENT_FLOW_ORDER[
        COMMITMENT_FLOW_ORDER.index(CommitmentStep.SEND_BOUNDARY_VERIFICATION) :
    ]
)

SEQUENCED_STEPS: tuple[CommitmentStep, ...] = tuple(
    step for step in COMMITMENT_FLOW_ORDER if step not in SEND_BOUNDARY_STEPS
)

GUARANTEED_FAIL_CLOSED_STEPS: frozenset[CommitmentStep] = frozenset(SEQUENCED_STEPS)

COORDINATOR_REALIZED_STEPS: frozenset[CommitmentStep] = frozenset(
    {CommitmentStep.DECISION_PROPOSAL, CommitmentStep.ATTEMPT_REQUEST}
)

INJECTED_STAGE_STEPS: tuple[CommitmentStep, ...] = tuple(
    step for step in SEQUENCED_STEPS if step not in COORDINATOR_REALIZED_STEPS
)


_STEP_NUMBERS: dict[CommitmentStep, int] = {
    step: number for number, step in enumerate(COMMITMENT_FLOW_ORDER, start=1)
}


def step_number(step: CommitmentStep) -> int:
    """Return the ADR-002-002 §11 step number (1-19) of ``step``."""
    number = _STEP_NUMBERS.get(step)
    if number is None:
        raise ArtifactIntegrityError(
            f"{step!r} is not one of the 19 ADR-002-002 §11 Normal Commitment Flow steps"
        )
    return number


class StageOutcome(_NonTruthyStrEnum):
    """The positive-admit wrapping of a stage's native verdict (design #31 §4.1/§4.2)."""

    ADMIT = "ADMIT"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


class StageAuthorityClass(StrEnum):
    """Where a stage's logic comes from — the three sanctioned sources (design #31 §0.4/§4.1)."""

    AVAILABLE_PURE_PREDICATE = "AVAILABLE_PURE_PREDICATE"
    NON_AUTHORITATIVE_PROVISIONAL = "NON_AUTHORITATIVE_PROVISIONAL"
    DEFERRED_SEND_BOUNDARY = "DEFERRED_SEND_BOUNDARY"


class DispatchResolution(_NonTruthyStrEnum):
    """The ∅-both-ways registry resolution (design #31 §6 "∅ 양방향" / §11)."""

    MISSING = "MISSING"
    EXPLICIT_EMPTY = "EXPLICIT_EMPTY"
    DISPATCHED = "DISPATCHED"


class AdmissionVerdict(_NonTruthyStrEnum):
    """The typed-admission verdict for an in-process Authored Strategy (design #31 §3.5)."""

    ADMISSIBLE = "ADMISSIBLE"
    INADMISSIBLE = "INADMISSIBLE"


class ResultDisposition(_NonTruthyStrEnum):
    """The conservative, recorded disposition of a re-injected ``EGRESS_RESULT`` (Phase 3 A-K-2)."""

    APPLIED = "APPLIED"
    ORPHAN_NO_RESERVATION = "ORPHAN_NO_RESERVATION"
    MISMATCHED_ATTEMPT = "MISMATCHED_ATTEMPT"
    DUPLICATE = "DUPLICATE"
    NON_MONOTONIC_PROJECTION = "NON_MONOTONIC_PROJECTION"
    QUANTITY_REGRESSION = "QUANTITY_REGRESSION"


class OrderingAdmission(_NonTruthyStrEnum):
    """Causal-order admission of an incoming event against the last consumed one (§2.1(ii))."""

    MONOTONE = "MONOTONE"
    AMBIGUOUS = "AMBIGUOUS"
    REVERSED = "REVERSED"


class HaltReason(StrEnum):
    """Why a decision-pipeline run or a commitment flow stopped (design #31 §4.2 "중단 사유 기록")."""

    REGISTRY_MISSING = "REGISTRY_MISSING"
    REGISTRY_EXPLICIT_EMPTY = "REGISTRY_EXPLICIT_EMPTY"
    EVENT_STRATEGY_KEY_MISMATCH = "EVENT_STRATEGY_KEY_MISMATCH"
    CAPSULE_ABSENT = "CAPSULE_ABSENT"
    CAPSULE_NOT_ISSUED = "CAPSULE_NOT_ISSUED"
    CAPSULE_INCOMPLETE = "CAPSULE_INCOMPLETE"
    CAPSULE_SCOPE_MISMATCH = "CAPSULE_SCOPE_MISMATCH"
    TIME_NOT_ADMITTED = "TIME_NOT_ADMITTED"
    DEGRADED_BOUND_EXHAUSTED = "DEGRADED_BOUND_EXHAUSTED"
    NO_ACTION_OUTCOME = "NO_ACTION_OUTCOME"
    VECTOR_OUTCOME_UNSUPPORTED = "VECTOR_OUTCOME_UNSUPPORTED"
    PROPOSAL_SCOPE_MISMATCH = "PROPOSAL_SCOPE_MISMATCH"
    STAGE_MISSING = "STAGE_MISSING"
    STAGE_VERDICT_ABSENT = "STAGE_VERDICT_ABSENT"
    STAGE_VERDICT_STEP_MISMATCH = "STAGE_VERDICT_STEP_MISMATCH"
    STAGE_DENIED = "STAGE_DENIED"
    STAGE_UNKNOWN = "STAGE_UNKNOWN"
    STAGE_RAISED = "STAGE_RAISED"
    ATTEMPT_BINDING_INCOMPLETE = "ATTEMPT_BINDING_INCOMPLETE"
    AT_MOST_ONE_EXPOSURE_HELD = "AT_MOST_ONE_EXPOSURE_HELD"
    EVENT_ORDER_REVERSED = "EVENT_ORDER_REVERSED"
    RESULT_UNMATCHED = "RESULT_UNMATCHED"
    TRANSMIT_UNAVAILABLE = "TRANSMIT_UNAVAILABLE"
    TRANSMIT_RAISED = "TRANSMIT_RAISED"
    AUTHORITY_NOT_CURRENT = "AUTHORITY_NOT_CURRENT"
    LIVE_SCOPE_NOT_AUTHORIZED = "LIVE_SCOPE_NOT_AUTHORIZED"


class EvidenceKind(StrEnum):
    """The kinds of record the provisional evidence sink receives (design #31 §12-5)."""

    REGISTRATION_REFUSED = "REGISTRATION_REFUSED"
    EVENT_REFUSED = "EVENT_REFUSED"
    DECISION_WITHHELD = "DECISION_WITHHELD"
    DECISION_DEGRADED = "DECISION_DEGRADED"
    DECISION_OUTCOME_EMITTED = "DECISION_OUTCOME_EMITTED"
    FLOW_STEP_ADMITTED = "FLOW_STEP_ADMITTED"
    FLOW_HALTED = "FLOW_HALTED"
    ATTEMPT_REQUEST_CREATED = "ATTEMPT_REQUEST_CREATED"
    SEND_HANDED_OFF = "SEND_HANDED_OFF"
    EGRESS_RESULT_CONSUMED = "EGRESS_RESULT_CONSUMED"
    RESULT_UNMATCHED = "RESULT_UNMATCHED"
    COORDINATOR_PRECONDITION_REFUSED = "COORDINATOR_PRECONDITION_REFUSED"


class UnsentDiscardReason(StrEnum):
    """Why a never-sent provisional reservation was discarded (2026-11-01 unsent-reservation-"""

    UNSENT_FLOW_NON_EXECUTION = "UNSENT_FLOW_NON_EXECUTION"


RESERVATION_DISCARDED_UNSENT_KIND = "RESERVATION_DISCARDED_UNSENT"


CAPSULE_CONTEXT_SOURCE = "capsule"

CONFIG_CONTEXT_SOURCE = "config"


def _verify_context_source_anchor() -> None:
    """Anchor the two named sources to ``tos.dsl.ADMISSIBLE_CONTEXT_SOURCES`` (enum-drift guard)."""
    named = frozenset({CAPSULE_CONTEXT_SOURCE, CONFIG_CONTEXT_SOURCE})
    if named != ADMISSIBLE_CONTEXT_SOURCES:
        raise ArtifactIntegrityError(
            "engine context-source anchor drifted from tos.dsl.ADMISSIBLE_CONTEXT_SOURCES "
            f"(engine={sorted(named)}, dsl={sorted(ADMISSIBLE_CONTEXT_SOURCES)}) — design #31 "
            "§3.2 (3)"
        )


_verify_context_source_anchor()
