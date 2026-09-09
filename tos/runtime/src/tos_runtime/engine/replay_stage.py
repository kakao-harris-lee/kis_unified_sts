"""``RecordedStage`` — a side-effect-free ``Stage`` stand-in for boot-time compose-level replay
(TOS Phase 3, dispatch CR5-3, 2026-09-09).

**The bug this fixes.** ``tos_runtime.compose._engine_wiring._ReplayStage`` returned a
restrictive ``StageOutcome.UNKNOWN`` for EVERY injected commitment-flow step, unconditionally.
That is a positive-admit-gate stop (``tos.engine.sequencer.run_commitment_flow``'s own rule:
"deny / UNKNOWN / missing ⇒ immediate stop"), so compose-level replay never advanced past the
very FIRST injected step (:data:`~tos.engine.vocabulary.INJECTED_STAGE_STEPS`'s first member,
``CANDIDATE_COMMAND_CONSTRUCTION``, step 2) — no reservation was EVER created during replay,
regardless of what the live run actually did. Kernel lane KW3-RD (``783fadf0``) gave
``EGRESS_RESULT`` events a real ``outcome_digest``, which made this gap externally visible for
the first time: a later result event, applied against replay's permanently-empty ledger
(``ORPHAN_NO_RESERVATION``) instead of the live run's actual reservation state, diverges.

**The fix (design #31 §9 record/replay).** Compose-level replay must re-run the DETERMINISTIC
core against the RECORDED stage verdicts, not against a stand-in that halts unconditionally: for
each (event, step) this class returns exactly the verdict the live run's own durable evidence
recorded, side-effect-free, so the ledger reaches the same state and the digests must match — any
mismatch is then a REAL divergence in the core itself, which is what replay exists to detect.

**How correlation works (evidence carries no event id).**
:class:`tos.engine.records.EngineEvidenceRecord` — the durable shape
``EvidenceKind.FLOW_STEP_ADMITTED``/``FLOW_HALTED`` rows take (written by
``tos.engine.sequencer.run_commitment_flow`` via the engine's own injected
:class:`~tos.engine.sink.EvidenceSink`) — carries ``step``/``stage_outcome``/``authority_class``/
``halt_reason``/``detail``, but no event identity at all. This class instead correlates by
ENCOUNTER ORDER: every commitment-flow invocation calls the first injected step
(``CANDIDATE_COMMAND_CONSTRUCTION``) before any other, unconditionally (``SEQUENCED_STEPS``'s own
fixed order) — so grouping the durable rows into contiguous runs, each starting at that step,
reproduces the SAME ordered sequence of "flow instances" the live run went through. Since replay
walks the SAME admitted-event stream in the SAME ``seq`` order (:func:`tos_runtime.engine.replay
.replay_engine`), the Nth commitment-flow-invoking event during replay is the Nth one recorded
live, and this class's internal cursor (advanced only when ``CANDIDATE_COMMAND_CONSTRUCTION`` is
requested) stays aligned automatically — no explicit correlation key is needed, or available.

**⚠ Windowed-replay caveat, inherited and widened (see :mod:`tos_runtime.engine.replay`'s own
"window_events path-dependency" docstring section for the pre-existing ledger-state half of
this).** This class's instance list is built once, from the evidence store's ENTIRE durable
history, regardless of ``window_events`` — but :func:`~tos_runtime.engine.replay.replay_engine`
only calls the core's own per-event handler for admitted events INSIDE the window. If the window's start
does not align with a commitment-flow instance boundary in exactly the way the live run's own
event stream did, this class's cursor and the windowed event stream can desynchronize. Every
current caller configures ``replay_window_events`` large enough to cover the whole compose test's
history (measured: ``tos_runtime/tests/compose/conftest.py`` uses ``1000``), so this is a reported
caveat, not a fix silently assumed away — the module docstring's own "window_events=None is the
only generally correct choice for a ledger-carrying stream" advice applies here too, for the same
reason, just one layer deeper (stage-instance alignment, not only ledger state).

**Structurally unrecoverable steps — fail-closed, not fabricated (CR5-3 dispatch's own
contingency).** ``tos.engine.sequencer._bindings_from`` derives step 12's
(``conformance_proof_digest``, ``action_flow_permit_identity``) from ``StageVerdict.bound_digest``
(step 11, ``ORDER_CONFORMANCE_PROOF``) and ``StageVerdict.bound_identity`` (step 9,
``ATOMIC_COMMIT``) respectively — both required to be non-empty by
``tos.engine.sequencer.build_attempt_request``, or step 12 halts
``ATTEMPT_BINDING_INCOMPLETE``. **Measured directly: neither field is ever written to durable
evidence.** ``EngineEvidenceRecord`` (the ``FLOW_STEP_ADMITTED`` row's own shape) has no
``bound_digest``/``bound_identity`` field at all; the only place these values exist after a stage
runs is ``tos_runtime.compose.context.VerdictRecorder.last_verdict`` — an in-memory Python
attribute that does not survive a reboot, by construction (its own docstring: "remembering the
last ``StageVerdict`` it returned", nothing more). A placeholder value would not do — the exact
digest/identity feeds a CONTENT-ADDRESSED ``attempt_id`` derivation
(``tos.engine.sequencer.build_attempt_request``), so any value this class invented would derive a
DIFFERENT ``attempt_id`` than the live run's real one, and every later ``EGRESS_RESULT`` event
(which names the live run's REAL ``attempt_id``) would then read as an orphaned reference against
replay's ledger — the exact divergence this whole fix exists to eliminate, just relocated one step
later. This class therefore REFUSES (returns the fail-closed
:data:`REPLAY_STAGE_EVIDENCE_MISSING` detail, never a guessed ``ADMIT``) whenever it is asked for
step 9 or step 11's verdict in a flow instance where the live run recorded an ``ADMIT`` there —
this is a genuine kernel/evidence-surface gap (a future K-item's concern, not a runtime-shell fix),
reported here rather than silently worked around.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope, extended by ``CR5-3``'s own AST pin
in ``tests/engine/test_no_transport_during_replay.py``): stdlib (``json``) + ``tos.engine`` +
``tos_runtime.evidence.store`` only. No ``tos.brokeradapter``, no ``tos.egressgw``, no
``tos_runtime.authority``/``risk``/``currentness`` service package — this class calls no service,
no transport, no RCL, no time source; it only reads rows a PRIOR boot's real run already
durably wrote.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from tos.engine.records import StageRequest, StageVerdict
from tos.engine.vocabulary import (
    INJECTED_STAGE_STEPS,
    CommitmentStep,
    HaltReason,
    StageAuthorityClass,
    StageOutcome,
    step_number,
)

from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["REPLAY_STAGE_EVIDENCE_MISSING", "RecordedStage"]

_FLOW_STEP_ADMITTED_KIND = "FLOW_STEP_ADMITTED"
_FLOW_HALTED_KIND = "FLOW_HALTED"

#: Every commitment-flow invocation calls this step first, unconditionally (module docstring's
#: own "how correlation works" section) — the instance-boundary marker.
_FIRST_INJECTED_STEP = INJECTED_STAGE_STEPS[0]

#: The two halt reasons that mean "the injected stage itself returned a non-ADMIT verdict" —
#: the ONLY halt reasons this class ever needs to reproduce as a stage return value. Every OTHER
#: stage-hosted-step halt reason (``AT_MOST_ONE_EXPOSURE_HELD`` at step 8,
#: ``ATTEMPT_BINDING_INCOMPLETE`` at step 12) is reached WITHOUT ever consulting the injected
#: stage (the sequencer's own ledger/binding check runs first) — replay reproduces THOSE by
#: genuinely re-deriving them from its own ledger state, never by asking this class.
_STAGE_OWN_HALT_REASONS = frozenset(
    {HaltReason.STAGE_DENIED.value, HaltReason.STAGE_UNKNOWN.value}
)

#: Steps whose live-run ADMIT verdict cannot be faithfully reconstructed from durable evidence at
#: all (module docstring's "structurally unrecoverable steps" section) — mapped to a human
#: description of the missing field, for the refusal detail.
_STRUCTURALLY_UNRECOVERABLE_STEPS: dict[CommitmentStep, str] = {
    CommitmentStep.ATOMIC_COMMIT: (
        "bound_identity (the Action Flow Permit identity step 9 binds) — "
        "EngineEvidenceRecord carries no such field"
    ),
    CommitmentStep.ORDER_CONFORMANCE_PROOF: (
        "bound_digest (the Order Conformance Proof digest step 11 binds) — "
        "EngineEvidenceRecord carries no such field"
    ),
}

#: The fail-closed refusal detail prefix — searchable in the recorded ``StageVerdict.reason``
#: (surfaced onward into the sequencer's own ``FLOW_HALTED`` evidence detail on that replay run)
#: whenever this class refuses to guess (CR5-3 dispatch's own required label).
REPLAY_STAGE_EVIDENCE_MISSING = "REPLAY_STAGE_EVIDENCE_MISSING"


@dataclass
class _RecordedFlowInstance:
    """One live-run commitment-flow invocation's recorded per-step outcome."""

    admitted: dict[CommitmentStep, dict[str, object]] = field(default_factory=dict)
    halted_step: CommitmentStep | None = None
    halted_reason: str | None = None
    halted_detail: str | None = None


def _load_instances(evidence_store: SqliteEvidenceStore) -> list[_RecordedFlowInstance]:
    """Group the durable ``FLOW_STEP_ADMITTED``/``FLOW_HALTED`` history into ordered flow
    instances (module docstring's own "how correlation works" section)."""
    cur = evidence_store.connection.execute(
        "SELECT kind, payload_json FROM entries WHERE kind IN (?, ?) ORDER BY seq ASC",
        (_FLOW_STEP_ADMITTED_KIND, _FLOW_HALTED_KIND),
    )
    instances: list[_RecordedFlowInstance] = []
    current: _RecordedFlowInstance | None = None
    for kind, payload_json in cur:
        payload = json.loads(payload_json).get("payload", {})
        step_value = payload.get("step")
        if step_value is None:
            continue
        step = CommitmentStep(step_value)
        if step not in INJECTED_STAGE_STEPS:
            # Steps 1 (proposal) / 12 (attempt request) / 15-19 (send boundary) are Coordinator-
            # or D-E4-realized, never stage-injected — irrelevant to this stand-in (module
            # docstring: RecordedTransmit covers 15-19, the sequencer itself realizes 1 and 12).
            continue
        if step is _FIRST_INJECTED_STEP:
            current = _RecordedFlowInstance()
            instances.append(current)
        if (
            current is None
        ):  # pragma: no cover - defensive; step 2 always leads every instance
            continue
        if kind == _FLOW_STEP_ADMITTED_KIND:
            current.admitted[step] = payload
        elif payload.get("halt_reason") in _STAGE_OWN_HALT_REASONS:
            current.halted_step = step
            current.halted_reason = payload.get("halt_reason")
            current.halted_detail = payload.get("detail")
        # A FLOW_HALTED row for a stage-hosted step whose halt_reason is NOT one of the stage's
        # own two (e.g. AT_MOST_ONE_EXPOSURE_HELD) still ends this instance, but this class is
        # never asked about that step in that case — see module docstring.
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
    ``dict.fromkeys(stages, replay_stage)`` pattern for ``_ReplayStage``) — the internal
    instance-cursor genuinely needs to be shared across steps to track which live-run flow
    invocation is currently being replayed, so one instance is simpler and equivalent to (rather
    than N cooperating instances of) a per-step construction.
    """

    evidence_store: SqliteEvidenceStore
    _instances: list[_RecordedFlowInstance] = field(init=False, repr=False)
    _index: int = field(default=-1, init=False, repr=False)
    _current: _RecordedFlowInstance | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._instances = _load_instances(self.evidence_store)

    def __call__(self, request: StageRequest) -> StageVerdict:
        step = request.step
        if step is _FIRST_INJECTED_STEP:
            self._index += 1
            self._current = (
                self._instances[self._index]
                if 0 <= self._index < len(self._instances)
                else None
            )
        if self._current is None:
            return _missing_verdict(
                step,
                "no recorded commitment-flow instance at this position in the admitted-event "
                "stream (evidence exhausted or never had one here)",
            )
        if step in self._current.admitted:
            if step in _STRUCTURALLY_UNRECOVERABLE_STEPS:
                return _missing_verdict(
                    step,
                    f"live run ADMITted step {step_number(step)} ({step}) but "
                    f"{_STRUCTURALLY_UNRECOVERABLE_STEPS[step]} (CR5-3, 2026-09-09)",
                )
            record = self._current.admitted[step]
            authority_value = record.get("authority_class")
            detail_value = record.get("detail")
            return StageVerdict(
                step=step,
                outcome=StageOutcome.ADMIT,
                authority_class=(
                    StageAuthorityClass(str(authority_value))
                    if authority_value is not None
                    else StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL
                ),
                reason=None if detail_value is None else str(detail_value),
            )
        if step is self._current.halted_step:
            outcome = (
                StageOutcome.UNKNOWN
                if self._current.halted_reason == HaltReason.STAGE_UNKNOWN.value
                else StageOutcome.DENY
            )
            return StageVerdict(
                step=step,
                outcome=outcome,
                authority_class=StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL,
                reason=self._current.halted_detail,
            )
        return _missing_verdict(
            step,
            f"step {step_number(step)} ({step}) was neither admitted nor the halt step in the "
            "recorded flow instance at this position",
        )
