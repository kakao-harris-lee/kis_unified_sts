"""``OrthostateProjector`` — TOS Phase 3 Wave 2 Lane C-R (plan §2.2 "커널 결합")."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from tos.engine import EventResult
from tos.engine.orthostate_projection import composite_state_for, result_transition_for
from tos.engine.records import EgressResultPayload, EngineEvent
from tos.engine.vocabulary import EgressResultKind, EventKind, ResultDisposition
from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    CouplingSideConditions,
    IntentState,
    KnowledgeState,
    StateDimension,
    TransitionAuthority,
    TransmissionAttemptState,
    conservative_direction_ok,
    coupling_violations,
    may_transition,
    reconstruct_conservative,
)

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["OrthostateProjector", "NEW_RISK_HALTED_BY_COUPLING_VIOLATION"]

_COUPLING_VIOLATION_KIND = "COUPLING_VIOLATION"
_OWNERSHIP_VIOLATION_KIND = "ORTHOSTATE_OWNERSHIP_VIOLATION"

NEW_RISK_HALTED_BY_COUPLING_VIOLATION = "NEW_RISK_HALTED_BY_COUPLING_VIOLATION"

_ATTEMPT_EGRESS_ACTOR = TransitionAuthority.BROKER_ADAPTER_EGRESS

_FIXED_INTENT_STATE = IntentState.ACTIVE

_GENESIS_ATTEMPT_STATE = TransmissionAttemptState.NONE

_CANCEL_CROSSING_FILL_BROKER_STATE: dict[EgressResultKind, BrokerOrderState] = {
    EgressResultKind.FULL_FILL: BrokerOrderState.FILLED,
    EgressResultKind.PARTIAL_FILL: BrokerOrderState.PARTIALLY_FILLED,
}


@dataclass
class OrthostateProjector:
    """Projects each consumed ``EGRESS_RESULT`` onto the ADR-002-005 orthostate dimensions and"""

    inbox: SqliteEventInbox
    evidence_store: SqliteEvidenceStore
    emergency_log: EmergencyAppendLog
    authority_epoch_current: Callable[[], bool | None]
    _seen_attempts: set[str] = field(
        default_factory=set, init=False, repr=False, compare=False
    )

    def project(
        self, *, event: EngineEvent, result: EventResult
    ) -> CompositeState | None:
        """Project one consumed event's result onto orthostate, or ``None`` if inapplicable."""
        if event.kind is not EventKind.EGRESS_RESULT:
            return None
        payload = event.egress_result
        if payload is None or result.reservation is None:
            return None
        attempt_id = payload.attempt_id

        prior_raw = self.inbox.last_composite(attempt_id)
        prior_composite: CompositeState | None = None
        prior_revision = 0
        if prior_raw is not None:
            raw, prior_revision = prior_raw
            prior_composite = reconstruct_conservative(
                CompositeState.model_validate(raw)
            )

        if result.result_disposition is not ResultDisposition.APPLIED:
            return self._project_non_applied(
                payload=payload,
                result=result,
                attempt_id=attempt_id,
                prior_composite=prior_composite,
                prior_revision=prior_revision,
            )

        attempt_transition, _broker, _knowledge = result_transition_for(payload.kind)
        if prior_composite is None:
            genesis_attempt_state = _GENESIS_ATTEMPT_STATE
            observation_revision = 1
        else:
            genesis_attempt_state = prior_composite.transmission_attempt_state
            observation_revision = prior_revision + 1

        next_composite = composite_state_for(
            result.reservation,
            intent_state=_FIXED_INTENT_STATE,
            attempt_state=attempt_transition,
        )
        next_composite = self._inherit_conservative_knowledge_on_first_touch(
            prior_composite, next_composite, attempt_id=attempt_id
        )

        self._check_ownership(
            genesis_attempt_state, next_composite, attempt_id=attempt_id
        )
        self._evaluate_coupling(next_composite, attempt_id=attempt_id)

        self.inbox.record_composite(
            attempt_id,
            next_composite.model_dump(mode="json"),
            observation_revision=observation_revision,
        )
        return next_composite

    def _project_non_applied(
        self,
        *,
        payload: EgressResultPayload,
        result: EventResult,
        attempt_id: str,
        prior_composite: CompositeState | None,
        prior_revision: int,
    ) -> CompositeState | None:
        """Independent review finding #8: correct the Broker Order dimension for a"""
        corrected_broker = _CANCEL_CROSSING_FILL_BROKER_STATE.get(payload.kind)
        if (
            result.result_disposition is not ResultDisposition.NON_MONOTONIC_PROJECTION
            or corrected_broker is None
            or prior_composite is None
        ):
            return None

        next_composite = prior_composite.model_copy(
            update={
                "broker_order_state": corrected_broker,
                "knowledge_state": KnowledgeState.CONFLICTED,
            }
        )
        self._evaluate_coupling(next_composite, attempt_id=attempt_id)
        self.inbox.record_composite(
            attempt_id,
            next_composite.model_dump(mode="json"),
            observation_revision=prior_revision + 1,
        )
        return next_composite

    def _inherit_conservative_knowledge_on_first_touch(
        self,
        prior_composite: CompositeState | None,
        next_composite: CompositeState,
        *,
        attempt_id: str,
    ) -> CompositeState:
        """Independent review finding #5: on THIS instance's first touch of a KNOWN attempt,"""
        first_touch = attempt_id not in self._seen_attempts
        self._seen_attempts.add(attempt_id)
        if prior_composite is None or not first_touch:
            return next_composite
        if conservative_direction_ok(
            StateDimension.KNOWLEDGE,
            prior_composite.knowledge_state,
            next_composite.knowledge_state,
            None,
        ):
            return next_composite
        return next_composite.model_copy(
            update={"knowledge_state": prior_composite.knowledge_state}
        )

    def _check_ownership(
        self,
        genesis_attempt_state: TransmissionAttemptState,
        next_composite: CompositeState,
        *,
        attempt_id: str,
    ) -> None:
        """Halt (and durably latch a new-risk halt) if this projector's own derived"""
        to_state = next_composite.transmission_attempt_state
        if not may_transition(
            _ATTEMPT_EGRESS_ACTOR,
            StateDimension.TRANSMISSION_ATTEMPT,
            genesis_attempt_state,
            to_state,
        ):
            receipt = record_halt(
                self.evidence_store,
                self.emergency_log,
                payload={
                    "attempt_id": attempt_id,
                    "dimension": StateDimension.TRANSMISSION_ATTEMPT.value,
                    "from_state": str(genesis_attempt_state),
                    "to_state": str(to_state),
                },
                kind=_OWNERSHIP_VIOLATION_KIND,
                record_class=_OWNERSHIP_VIOLATION_KIND,
            )
            self.inbox.record_new_risk_halt(
                reason=NEW_RISK_HALTED_BY_COUPLING_VIOLATION,
                event_id=f"attempt:{attempt_id}",
                evidence_seq=receipt.seq,
            )

    def _evaluate_coupling(self, composite: CompositeState, *, attempt_id: str) -> None:
        """Evaluate :func:`~tos.orthostate.coupling_violations` and, on a violation, durably"""
        side = CouplingSideConditions(
            authority_epoch_current=self.authority_epoch_current()
        )
        violations = coupling_violations(composite, side)
        if violations:
            receipt = record_halt(
                self.evidence_store,
                self.emergency_log,
                payload={
                    "attempt_id": attempt_id,
                    "violations": sorted(violations),
                    "composite": composite.model_dump(mode="json"),
                },
                kind=_COUPLING_VIOLATION_KIND,
                record_class=_COUPLING_VIOLATION_KIND,
            )
            self.inbox.record_new_risk_halt(
                reason=NEW_RISK_HALTED_BY_COUPLING_VIOLATION,
                event_id=f"attempt:{attempt_id}",
                evidence_seq=receipt.seq,
            )
