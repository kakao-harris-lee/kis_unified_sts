"""``RecordedStage`` — a side-effect-free ``Stage`` stand-in for boot-time compose-level replay
(TOS Phase 3, dispatch CR5-3/CR5-5, 2026-09-09).

**The bug this fixes.** ``tos_runtime.compose._engine_wiring._ReplayStage`` returned a
restrictive ``StageOutcome.UNKNOWN`` for EVERY injected commitment-flow step, unconditionally —
halting the flow right after step 1, before step 9 (RCL commit/bind) or step 12 (attempt request)
ever ran. No reservation was EVER created during compose-level replay, regardless of what the
live run actually did.

**The fix (design #31 §9 record/replay).** Compose-level replay must re-run the DETERMINISTIC
core against the RECORDED stage verdicts, not against a stand-in that halts unconditionally: for
each (event, step) this class returns exactly the verdict the live run's own durable evidence
recorded, side-effect-free, so the ledger reaches the same state and the digests must match — any
mismatch is then a REAL divergence in the core itself, which is what replay exists to detect.

**Correlation by ``event_id`` (CR5-5, 2026-09-09 — kernel lane K-W2b's ``[KW3-EV]``,
``b9447c9d``).** An earlier revision of this class (CR5-3, ``3e2af6cf``) correlated flow
instances by ENCOUNTER ORDER, because ``EngineEvidenceRecord`` carried no event identity at all.
That was measured to desynchronize under a truncated ``window_events`` (a windowed replay that
skips the events before a flow instance would still consume that instance's slot in the ordered
list). ``[KW3-EV]`` closes this at the kernel: ``tos.engine.core.EngineCore._handle_decision_tick``
now computes ``event_id = event_identity(event, scheme=...)`` once per tick and threads it into
``run_commitment_flow(event_id=...)``, which stamps it onto every ``FLOW_STEP_ADMITTED`` /
``FLOW_HALTED`` / ``ATTEMPT_REQUEST_CREATED`` / ``SEND_HANDED_OFF`` record the flow emits. This
class now groups durable evidence by that EXACT ``event_id`` — the SAME content-addressed
identity :func:`tos_runtime.engine.replay.replay_engine` already keys its own ``EVENT_CONSUMED``
comparison on — and looks up the CURRENT event's own recorded per-step verdicts directly. No
encounter-order fallback: a row with no ``event_id`` (pre-``[KW3-EV]`` evidence) is never indexed
under any key, so a lookup for it finds nothing and fails closed
(:data:`REPLAY_STAGE_EVIDENCE_MISSING`) rather than silently matching the wrong instance or
guessing.

**The seam that threads ``event_id`` in without changing ``engine/replay.py`` (CR5-5).**
:class:`StageRequest` (what this class's ``__call__`` actually receives) carries no event
identity — only a transformed ``proposal``/``reference`` view, not the raw
:class:`~tos.engine.records.EngineEvent` :func:`~tos.engine.records.event_identity` needs. This
class therefore cannot recompute the current event's id on its own; it must be told.
:func:`tos_runtime.engine.replay.replay_engine` calls only the core's own per-event handler on
whatever its injected ``build_core`` factory returns (measured directly against that module's own
source) — so
:class:`EventCorrelatingCore` wraps the real :class:`~tos.engine.EngineCore` the factory builds,
computing ``event_id`` and calling :meth:`RecordedStage.set_current_event_id` immediately BEFORE
delegating to the real core's own ``handle``. ``replay_engine`` needs no changes at all: it never
inspects what ``build_core()`` returns beyond calling ``.handle(event)`` on it.

**Steps 9/11 are no longer structurally unrecoverable (CR5-5 — closed by ``[KW3-EV]``).** CR5-3's
own docstring reported that ``tos.engine.sequencer._bindings_from`` needs ``StageVerdict
.bound_digest`` (step 11) / ``bound_identity`` (step 9) to derive step 12's content-addressed
``attempt_id``, and that neither field survived a reboot (only living on an in-memory
``VerdictRecorder.last_verdict``). ``[KW3-EV]`` adds both fields directly to
``EngineEvidenceRecord`` and stamps them verbatim onto the ``FLOW_STEP_ADMITTED`` record for
steps 9/11 (``None`` for every other step — verified by the kernel's own
``test_step_9_and_11_admit_records_carry_exactly_the_verdicts_bound_values``). This class now
reads them straight off the durable record and reconstructs the ADMIT verdict faithfully — step
12 (realized directly by the sequencer, never stage-injected) then derives the SAME ``attempt_id``
the live run did, and every later ``EGRESS_RESULT`` naming that ``attempt_id`` replays against
the correct reservation instead of an orphaned one.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope, extended by CR5's own AST pin in
``tests/engine/test_no_transport_during_replay.py``): stdlib (``json``) + ``tos.canonical`` +
``tos.engine``/``tos.engine.records`` + ``tos_runtime.evidence.store`` only. No
``tos.brokeradapter``, no ``tos.egressgw``, no ``tos_runtime.authority``/``risk``/``currentness``
service package — this class calls no service, no transport, no RCL, no time source; it only
reads rows a PRIOR boot's real run already durably wrote.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from tos.canonical import CanonicalizationScheme
from tos.engine import EngineCore, EngineEvent, EventResult
from tos.engine.records import StageRequest, StageVerdict, event_identity
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

#: The two halt reasons that mean "the injected stage itself returned a non-ADMIT verdict" —
#: the ONLY halt reasons this class ever needs to reproduce as a stage return value. Every OTHER
#: stage-hosted-step halt reason (``AT_MOST_ONE_EXPOSURE_HELD`` at step 8,
#: ``ATTEMPT_BINDING_INCOMPLETE`` at step 12) is reached WITHOUT ever consulting the injected
#: stage (the sequencer's own ledger/binding check runs first) — replay reproduces THOSE by
#: genuinely re-deriving them from its own ledger state, never by asking this class.
_STAGE_OWN_HALT_REASONS = frozenset(
    {HaltReason.STAGE_DENIED.value, HaltReason.STAGE_UNKNOWN.value}
)

#: The fail-closed refusal detail prefix — searchable in the recorded ``StageVerdict.reason``
#: whenever this class refuses to guess (CR5-3/CR5-5's own required label).
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
    """Group the durable ``FLOW_STEP_ADMITTED``/``FLOW_HALTED`` history by ``event_id`` (module
    docstring's own "correlation by event_id" section). A row with no ``event_id`` (pre-
    ``[KW3-EV]`` evidence) is never indexed under any key — a lookup against it therefore always
    misses and fails closed, by construction, never by an explicit check here."""
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
            # Steps 1 (proposal) / 12 (attempt request) / 15-19 (send boundary) are Coordinator-
            # or D-E4-realized, never stage-injected — irrelevant to this stand-in.
            continue
        instance = instances.setdefault(event_id, _RecordedFlowInstance())
        if kind == _FLOW_STEP_ADMITTED_KIND:
            instance.admitted[step] = payload
        elif payload.get("halt_reason") in _STAGE_OWN_HALT_REASONS:
            instance.halted_step = step
            instance.halted_reason = payload.get("halt_reason")
            instance.halted_detail = payload.get("detail")
        # A FLOW_HALTED row for a stage-hosted step whose halt_reason is NOT one of the stage's
        # own two (e.g. AT_MOST_ONE_EXPOSURE_HELD) still belongs to this event_id's instance, but
        # this class is never asked about that step in that case (module docstring).
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
    """A ``Stage`` (``tos.engine.sequencer.Stage`` Protocol) stand-in that reproduces the live
    run's own recorded per-step verdict during boot-time compose replay — never a real stage
    call, never I/O, never a guess (module docstring).

    A single instance is shared across EVERY injected step (mirroring the wiring's own prior
    ``dict.fromkeys(stages, replay_stage)`` pattern) — correlation is keyed by ``event_id``
    (:meth:`set_current_event_id`, called by :class:`EventCorrelatingCore` before each event),
    never by which step or how many times this instance has been called.
    """

    evidence_store: SqliteEvidenceStore
    _instances_by_event_id: dict[str, _RecordedFlowInstance] = field(
        init=False, repr=False
    )
    _current_event_id: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._instances_by_event_id = _load_instances_by_event_id(self.evidence_store)

    def set_current_event_id(self, event_id: str) -> None:
        """Set the ``event_id`` of the event about to be handled — called by
        :class:`EventCorrelatingCore` immediately before delegating to the real core, the seam
        that lets this class correlate by id without ``engine/replay.py`` needing to change
        (module docstring)."""
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
    """Wraps the real :class:`~tos.engine.EngineCore` a boot-time replay factory builds, so a
    shared :class:`RecordedStage` always knows the ``event_id`` of the event it is about to
    replay (module docstring's own "the seam that threads event_id in" section).

    Deliberately NOT a subclass of :class:`~tos.engine.EngineCore` — this class exposes only the
    one method :func:`~tos_runtime.engine.replay.replay_engine` ever calls on whatever its
    ``build_core`` factory returns (``.handle(event)``, verified directly against that module's
    own source), so a duck-typed wrapper is both sufficient and simpler than reproducing
    ``EngineCore``'s full constructor surface. Callers that need the type checker to accept this
    in an ``EngineCore``-typed slot (e.g. ``tos_runtime.compose._boot_integrity
    .verify_engine_replay_or_halt``'s ``build_core: Callable[[], EngineCore]`` parameter) use
    ``typing.cast`` at the call site — a structural, not nominal, substitution, justified by the
    single-method usage this docstring cites.
    """

    core: EngineCore
    recorded_stage: RecordedStage
    scheme: CanonicalizationScheme

    def handle(self, event: EngineEvent) -> EventResult:
        event_id = event_identity(event, scheme=self.scheme)
        self.recorded_stage.set_current_event_id(event_id)
        # This class's own docstring is the sanction: it exists SOLELY to prime
        # RecordedStage's event_id before delegating to the real core.
        core = self.core
        return core.handle(event)  # direct-core-call: sanctioned (determinism control)
