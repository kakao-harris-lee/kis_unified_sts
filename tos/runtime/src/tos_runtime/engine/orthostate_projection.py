"""``OrthostateProjector`` — TOS Phase 3 Wave 2 Lane C-R (plan §2.2 "커널 결합").

For each ``EGRESS_RESULT`` the driver consumes, this projector derives the proposed
ADR-002-005 :class:`~tos.orthostate.records.CompositeState` via the kernel adapter
(:func:`tos.engine.orthostate_projection.composite_state_for` /
:func:`~tos.engine.orthostate_projection.result_transition_for`, landed by kernel round KW2-C2 —
this module writes against exactly those two names, per the wave-2 dispatch), checks §12
ownership legality for the dimensions this projector actually derives new values for
(:func:`tos.orthostate.may_transition`) plus cross-dimension coupling
(:func:`tos.orthostate.coupling_violations`), and durably keeps the LAST composite per attempt
(:meth:`~tos_runtime.engine.inbox.SqliteEventInbox.record_composite` /
:meth:`~tos_runtime.engine.inbox.SqliteEventInbox.last_composite`) so a restart resumes from a
conservative reconstruction (:func:`tos.orthostate.reconstruct_conservative`) of the last known
composite, never from a wrongly re-derived genesis.

**Actor stand-in (disclosed, synthetic single-process runtime).** ADR-002-005 §12 splits
Broker-Order / Knowledge / Attempt-send-boundary ownership across three DISTINCT roles (Broker
Adapter Evidence, Reconciliation Service, Broker Adapter Egress) that in a real multi-process
deployment would be separate services with their own identity. This compose root has no such
separate processes on the SYNTHETIC paper path — the synthetic gateway and this projector are
the only things that ever touch this data — so this projector checks ownership using the three
roles as FIXED constants (:data:`_ATTEMPT_EGRESS_ACTOR`, :data:`_BROKER_ORDER_ACTOR`,
:data:`_KNOWLEDGE_ACTOR`), standing in for the single synthetic-runtime process that plays all
three. A real multi-process deployment (Phase 5+) would inject the actual per-caller actor
identity instead of these constants. This is defense in depth, not the primary safety property:
the mapping table :func:`~tos.engine.orthostate_projection.result_transition_for` reads is
closed and kernel-authored, so a genuine ownership violation should never actually fire here —
the check exists so a FUTURE drift (e.g. a new ``EgressResultKind`` wired to an off-region
Attempt target) is caught as a halt rather than silently accepted.

**Replace is only ever a new attempt (RFC-005 §11 "retry is a new send").** Neither this module
nor :class:`~tos_runtime.engine.driver.EngineDriver` exposes any method that re-sends an
already-recorded attempt or replays an existing ``attempt_id``'s composite forward by hand — see
``tos/runtime/tests/engine/test_orthostate_projection.py``'s pin test for the grep-style +
behavioural proof.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.engine``/
``tos.orthostate`` + ``tos_runtime.engine.inbox``/``tos_runtime.evidence.*`` only. No
``shared.*``.
"""

from __future__ import annotations

from dataclasses import dataclass

from tos.engine import EventResult
from tos.engine.orthostate_projection import composite_state_for, result_transition_for
from tos.engine.records import EngineEvent
from tos.engine.vocabulary import EventKind
from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    IntentState,
    KnowledgeState,
    StateDimension,
    TransitionAuthority,
    TransmissionAttemptState,
    coupling_violations,
    may_transition,
    reconstruct_conservative,
)

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["OrthostateProjector"]

_COUPLING_VIOLATION_KIND = "COUPLING_VIOLATION"
_OWNERSHIP_VIOLATION_KIND = "ORTHOSTATE_OWNERSHIP_VIOLATION"

# Actor stand-ins — see module docstring's "Actor stand-in" section.
_ATTEMPT_EGRESS_ACTOR = TransitionAuthority.BROKER_ADAPTER_EGRESS
_BROKER_ORDER_ACTOR = TransitionAuthority.BROKER_ADAPTER_EVIDENCE
_KNOWLEDGE_ACTOR = TransitionAuthority.RECONCILIATION_SERVICE

#: Every attempt this projector ever sees already has Intent ``ACTIVE`` (an attempt only exists
#: past Approval + Aggregate-Risk + capacity commitment — ADR-002-005 §5). This runtime has no
#: Intent Registry object (``composite_state_for``'s own docstring), so Intent is never
#: transitioned by this projector; it is fixed at ``ACTIVE`` for every composite this module
#: produces.
_FIXED_INTENT_STATE = IntentState.ACTIVE

#: The virtual "from" triple used for the ownership check on a GENESIS observation (no prior
#: composite recorded yet for this attempt) — the true starting point of each dimension before
#: any result has been observed (ADR-002-005 §6/§7/§8 genesis values), so the very first
#: observation is ownership-checked too, not skipped.
_GENESIS_ATTEMPT_STATE = TransmissionAttemptState.NONE
_GENESIS_BROKER_STATE = BrokerOrderState.NONE_OBSERVED
_GENESIS_KNOWLEDGE_STATE = KnowledgeState.UNOBSERVED


@dataclass
class OrthostateProjector:
    """Projects each consumed ``EGRESS_RESULT`` onto the ADR-002-005 orthostate dimensions and
    durably keeps the last composite per attempt (inbox side table)."""

    inbox: SqliteEventInbox
    evidence_store: SqliteEvidenceStore
    emergency_log: EmergencyAppendLog

    def project(
        self, *, event: EngineEvent, result: EventResult
    ) -> CompositeState | None:
        """Project one consumed event's result onto orthostate, or ``None`` if inapplicable.

        Args:
            event: The (already-stamped) event the driver just consumed.
            result: The ``EventResult`` ``core.handle`` returned for it.

        Returns:
            The newly-derived, durably-recorded ``CompositeState``, or ``None`` for anything
            other than an ``EGRESS_RESULT`` whose reservation projection is present (a
            ``DECISION_TICK`` never reaches this projector at all; a non-``APPLIED`` egress
            result the kernel already refused to project capacity/knowledge for —
            ``EngineCore._handle_egress_result``'s own non-``APPLIED`` branch — carries no
            reservation and is likewise skipped: nothing changed on any dimension this projector
            owns, so there is nothing new to project).
        """
        if event.kind is not EventKind.EGRESS_RESULT:
            return None
        payload = event.egress_result
        if payload is None or result.reservation is None:
            return None
        attempt_id = payload.attempt_id

        prior_raw = self.inbox.last_composite(attempt_id)
        attempt_transition, _broker, _knowledge = result_transition_for(payload.kind)

        if prior_raw is None:
            genesis = (
                _GENESIS_ATTEMPT_STATE,
                _GENESIS_BROKER_STATE,
                _GENESIS_KNOWLEDGE_STATE,
            )
            observation_revision = 1
        else:
            raw, revision = prior_raw
            prior_composite = reconstruct_conservative(
                CompositeState.model_validate(raw)
            )
            genesis = (
                prior_composite.transmission_attempt_state,
                prior_composite.broker_order_state,
                prior_composite.knowledge_state,
            )
            observation_revision = revision + 1

        next_composite = composite_state_for(
            result.reservation,
            intent_state=_FIXED_INTENT_STATE,
            attempt_state=attempt_transition,
        )

        self._check_ownership(genesis, next_composite, attempt_id=attempt_id)

        violations = coupling_violations(next_composite)
        if violations:
            record_halt(
                self.evidence_store,
                self.emergency_log,
                payload={
                    "attempt_id": attempt_id,
                    "violations": sorted(violations),
                    "composite": next_composite.model_dump(mode="json"),
                },
                kind=_COUPLING_VIOLATION_KIND,
                record_class=_COUPLING_VIOLATION_KIND,
            )

        self.inbox.record_composite(
            attempt_id,
            next_composite.model_dump(mode="json"),
            observation_revision=observation_revision,
        )
        return next_composite

    def _check_ownership(
        self,
        genesis: tuple[TransmissionAttemptState, BrokerOrderState, KnowledgeState],
        next_composite: CompositeState,
        *,
        attempt_id: str,
    ) -> None:
        """Halt if this projector's own derived writes are not legal under §12 ownership.

        Defense in depth (see module docstring) — the kernel's own mapping table is closed and
        should never actually violate this; a violation here means a future edit wired a result
        kind to an off-region Attempt target, or an unowned dimension write, and this catches it
        as a durable halt rather than a silent accept.
        """
        attempt_from, broker_from, knowledge_from = genesis
        checks = (
            (
                StateDimension.TRANSMISSION_ATTEMPT,
                _ATTEMPT_EGRESS_ACTOR,
                attempt_from,
                next_composite.transmission_attempt_state,
            ),
            (
                StateDimension.BROKER_ORDER,
                _BROKER_ORDER_ACTOR,
                broker_from,
                next_composite.broker_order_state,
            ),
            (
                StateDimension.KNOWLEDGE,
                _KNOWLEDGE_ACTOR,
                knowledge_from,
                next_composite.knowledge_state,
            ),
        )
        for dimension, actor, from_state, to_state in checks:
            if not may_transition(actor, dimension, from_state, to_state):
                record_halt(
                    self.evidence_store,
                    self.emergency_log,
                    payload={
                        "attempt_id": attempt_id,
                        "dimension": dimension.value,
                        "from_state": str(from_state),
                        "to_state": str(to_state),
                    },
                    kind=_OWNERSHIP_VIOLATION_KIND,
                    record_class=_OWNERSHIP_VIOLATION_KIND,
                )
