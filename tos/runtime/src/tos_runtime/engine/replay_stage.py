"""``RecordedStage`` — a side-effect-free ``Stage`` stand-in for boot-time compose-level replay"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from tos.canonical import CanonicalizationScheme
from tos.engine import EngineCore, EngineEvent, EventResult
from tos.engine.records import StageRequest, StageVerdict, event_identity
from tos.engine.state import ProvisionalReservationLedger
from tos.engine.vocabulary import (
    INJECTED_STAGE_STEPS,
    CommitmentStep,
    HaltReason,
    StageAuthorityClass,
    StageOutcome,
    step_number,
)

from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["REPLAY_STAGE_EVIDENCE_MISSING", "RecordedStage", "EventCorrelatingCore"]

_FLOW_STEP_ADMITTED_KIND = "FLOW_STEP_ADMITTED"
_FLOW_HALTED_KIND = "FLOW_HALTED"

_STAGE_OWN_HALT_REASONS = frozenset(
    {HaltReason.STAGE_DENIED.value, HaltReason.STAGE_UNKNOWN.value}
)

REPLAY_STAGE_EVIDENCE_MISSING = "REPLAY_STAGE_EVIDENCE_MISSING"


@dataclass
class _RecordedFlowInstance:
    """One live-run commitment-flow invocation's recorded per-step outcome, for ONE event_id."""

    admitted: dict[CommitmentStep, dict[str, object]] = field(default_factory=dict)
    halted_step: CommitmentStep | None = None
    halted_reason: str | None = None
    halted_detail: str | None = None


def _load_instances_by_event_id(
    evidence_store: SqliteEvidenceStore,
) -> dict[str, _RecordedFlowInstance]:
    """Group the durable ``FLOW_STEP_ADMITTED``/``FLOW_HALTED`` history by ``event_id`` (module"""
    cur = evidence_store.connection.execute(
        "SELECT kind, payload_json FROM entries WHERE kind IN (?, ?) ORDER BY seq ASC",
        (_FLOW_STEP_ADMITTED_KIND, _FLOW_HALTED_KIND),
    )
    instances: dict[str, _RecordedFlowInstance] = {}
    for kind, payload_json in cur:
        payload = json.loads(payload_json).get("payload", {})
        event_id = payload.get("event_id")
        if not event_id:
            continue
        step_value = payload.get("step")
        if step_value is None:
            continue
        step = CommitmentStep(step_value)
        if step not in INJECTED_STAGE_STEPS:
            continue
        instance = instances.setdefault(event_id, _RecordedFlowInstance())
        if kind == _FLOW_STEP_ADMITTED_KIND:
            instance.admitted[step] = payload
        elif payload.get("halt_reason") in _STAGE_OWN_HALT_REASONS:
            instance.halted_step = step
            instance.halted_reason = payload.get("halt_reason")
            instance.halted_detail = payload.get("detail")
    return instances


def _missing_verdict(step: CommitmentStep, why: str) -> StageVerdict:
    """The fail-closed refusal — never a guessed ``ADMIT`` (module docstring)."""
    return StageVerdict(
        step=step,
        outcome=StageOutcome.UNKNOWN,
        authority_class=StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL,
        reason=f"{REPLAY_STAGE_EVIDENCE_MISSING}: {why}",
    )


@dataclass
class RecordedStage:
    """A ``Stage`` (``tos.engine.sequencer.Stage`` Protocol) stand-in that reproduces the live"""

    evidence_store: SqliteEvidenceStore
    _instances_by_event_id: dict[str, _RecordedFlowInstance] = field(
        init=False, repr=False
    )
    _current_event_id: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._instances_by_event_id = _load_instances_by_event_id(self.evidence_store)

    def set_current_event_id(self, event_id: str) -> None:
        """Set the ``event_id`` of the event about to be handled — called by"""
        self._current_event_id = event_id

    def __call__(self, request: StageRequest) -> StageVerdict:
        step = request.step
        if self._current_event_id is None:
            return _missing_verdict(
                step,
                "no current event_id set — RecordedStage must be driven through "
                "EventCorrelatingCore, never called directly against a bare EngineCore",
            )
        current = self._instances_by_event_id.get(self._current_event_id)
        if current is None:
            return _missing_verdict(
                step,
                f"no durable per-step evidence recorded for event_id="
                f"{self._current_event_id!r} (pre-[KW3-EV] evidence with no stamped event_id, "
                "or this event's flow genuinely never reached this step)",
            )
        if step in current.admitted:
            record = current.admitted[step]
            authority_value = record.get("authority_class")
            detail_value = record.get("detail")
            bound_identity = record.get("bound_identity")
            bound_digest = record.get("bound_digest")
            return StageVerdict(
                step=step,
                outcome=StageOutcome.ADMIT,
                authority_class=(
                    StageAuthorityClass(str(authority_value))
                    if authority_value is not None
                    else StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL
                ),
                reason=None if detail_value is None else str(detail_value),
                bound_identity=None if bound_identity is None else str(bound_identity),
                bound_digest=None if bound_digest is None else str(bound_digest),
            )
        if step is current.halted_step:
            outcome = (
                StageOutcome.UNKNOWN
                if current.halted_reason == HaltReason.STAGE_UNKNOWN.value
                else StageOutcome.DENY
            )
            return StageVerdict(
                step=step,
                outcome=outcome,
                authority_class=StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL,
                reason=current.halted_detail,
            )
        return _missing_verdict(
            step,
            f"step {step_number(step)} ({step}) was neither admitted nor the halt step for "
            f"event_id={self._current_event_id!r}",
        )


@dataclass
class EventCorrelatingCore:
    """Wraps the real :class:`~tos.engine.EngineCore` a boot-time replay factory builds, so a"""

    core: EngineCore
    recorded_stage: RecordedStage
    scheme: CanonicalizationScheme

    @property
    def ledger(self) -> ProvisionalReservationLedger:
        """The wrapped core's projection — :func:`~tos_runtime.engine.replay.replay_engine`"""
        return self.core.ledger

    def handle(self, event: EngineEvent) -> EventResult:
        event_id = event_identity(event, scheme=self.scheme)
        self.recorded_stage.set_current_event_id(event_id)
        return self.core.handle(event)
