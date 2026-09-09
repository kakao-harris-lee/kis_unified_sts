"""Hermetic tests for :class:`tos_runtime.engine.replay_stage.RecordedStage` (TOS Phase 3,
dispatch CR5-3, 2026-09-09).

Companion to ``test_replay.py`` (which covers the send-boundary half of the same replay-fidelity
class of bug, via ``RecordedTransmit``) — this module covers the commitment-flow-stage half.

**Scope note, reported precisely (mirrors this whole task's own "report precisely" discipline;
see :mod:`tos_runtime.engine.replay`'s and :mod:`tos_runtime.engine.replay_stage`'s own module
docstrings).** The CR5-3 dispatch asked for an end-to-end mutation test routed through
:func:`~tos_runtime.engine.replay.replay_engine` itself: "make RecordedStage return PASS for a
step whose evidence says REFUSED ⇒ divergence (quote RED)". **Measured directly: this is not
constructible with the current evidence surface.** ``EventResult.outcome_digest`` — the ONLY
value ``replay_engine`` ever compares — is fixed by the decision pipeline strictly BEFORE the
commitment flow starts, for every ``DECISION_TICK`` (see :class:`RecordedStage`'s own module
docstring). The commitment flow's ONLY effect ``replay_engine`` can ever observe (through a
LATER event's digest) is a mutation of ``tos.engine.state.ProvisionalReservationLedger`` — and
that ledger is untouched by every step before step 9 (``ATOMIC_COMMIT``, the first
``ledger.commit_unbound`` call). A stage-verdict flip at steps 2-8 therefore has ZERO observable
effect via ``replay_engine``'s digest comparison, by construction — no reservation exists either
way for a later event to diverge against. A flip AT step 9 (or 11) is instead absorbed by
:class:`RecordedStage`'s OWN separate, already-reported fail-closed refusal (the "structurally
unrecoverable steps" section of that class's docstring) — an evidence store that records step 9
as denied and one that (through tampering) looks admitted both end up producing no ledger commit
during replay, because reconstructing step 9's ADMIT verdict correctly would ALSO require the
Action Flow Permit identity, which durable evidence never carries either way. There is therefore
no scenario, given the current evidence surface, where a stage-verdict mutation is observable
through ``replay_engine``'s digest comparison at all. This is a NARROWER, separate consequence of
the SAME kernel/evidence-surface gap :class:`RecordedStage`'s own docstring already reports — not
a new one — flagged here explicitly rather than silently working around it.

The mutation-sensitivity test below (:func:`test_mutated_stage_evidence_changes_the_reconstructed_
verdict`) is therefore a DIRECT class-level test instead: it demonstrates that
:class:`RecordedStage` faithfully reflects whatever the durable evidence says (including a
tampered row), never independently re-deriving or cross-checking a stage's real judgement — the
same "trust the evidence, don't call the real stage" contract :class:`RecordedTransmit` upholds,
tested the same direct way ``test_replay.py``'s own
``test_recorded_transmit_refuses_to_guess_a_hand_off_the_evidence_does_not_corroborate`` does.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import StageRequest, StageVerdict
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.replay import replay_engine
from tos_runtime.engine.replay_stage import REPLAY_STAGE_EVIDENCE_MISSING, RecordedStage
from tos_runtime.engine.replay_transmit import RecordedTransmit, any_recorded_hand_off
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.sinks import EngineEvidenceSinkAdapter
from tos_runtime.evidence.store import SqliteEvidenceStore

from . import _fixtures as fx
from .conftest import FakeMonotonicSource

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_NO_TIMEOUT_WITHIN_TEST = 10**12


@dataclass
class _RecordingStage:
    """Wraps a real fixture stage, remembering every :class:`StageRequest` it receives — a test
    double letting a test replay the EXACT request object a live run's flow constructed, so a
    direct :class:`RecordedStage` unit call can be driven with realistic data."""

    inner: object
    captured: list[StageRequest] = field(default_factory=list)

    def __call__(self, request: StageRequest) -> StageVerdict:
        self.captured.append(request)
        return self.inner(request)  # type: ignore[operator]


def _driver(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    *,
    stages: dict[CommitmentStep, object],
    transmit: object = None,
) -> EngineDriver:
    return EngineDriver(
        core=fx.build_core(
            stages=stages,
            transmit=transmit,
            sink=EngineEvidenceSinkAdapter(evidence_store),
        ),
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="replay-stage-tests",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )


def _replay_build_core(evidence_store: SqliteEvidenceStore):
    """Mirrors ``_engine_wiring.py``'s own ``_replay_core_factory`` shape exactly: a single
    shared :class:`RecordedStage` for every injected step, and :class:`RecordedTransmit` iff the
    window ever recorded a hand-off."""

    def factory():
        recorded_stage = RecordedStage(evidence_store)
        return fx.build_core(
            stages=dict.fromkeys(fx.admitting_stages(), recorded_stage),
            transmit=(
                RecordedTransmit(evidence_store)
                if any_recorded_hand_off(evidence_store)
                else None
            ),
        )

    return factory


def test_a_recorded_refusal_before_the_send_boundary_replays_as_the_same_refusal(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """CR5-3 requirement (3): a tick that halted BEFORE step 9 (never touching the
    structurally-unrecoverable steps) must replay to the identical halt. This is fully
    reconstructable from durable evidence alone — no missing-field gap applies here."""
    stages = fx.admitting_stages(
        denied_steps={CommitmentStep.INDEPENDENT_APPROVAL: "denied for CR5-3 test"}
    )
    driver = _driver(inbox, evidence_store, emergency_log, stages=stages)
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.halt_reason is not None
    assert tick_result.halt_reason.value == "STAGE_DENIED"

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        _replay_build_core(evidence_store),
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.ok
    assert verdict.total_compared == 1
    assert verdict.diverged == ()


def test_missing_stage_evidence_after_a_real_hand_off_surfaces_as_a_divergence_with_detail(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """CR5-3 requirement (2): the kernel/evidence-surface gap (module docstring's "scope note")
    must surface as a REFUSED, DETECTED divergence — never a silently-guessed ADMIT. Also
    verifies the ``REPLAY_STAGE_EVIDENCE_MISSING`` detail directly on the reconstructed verdict
    (captured via a wrapped stage, since the label lives on an in-flight ``StageVerdict.reason``,
    not on anything ``replay_engine`` itself durably records under its own name).
    """
    stages = fx.admitting_stages()
    recorder_step2 = _RecordingStage(
        stages[CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION]
    )
    recorder_step9 = _RecordingStage(stages[CommitmentStep.ATOMIC_COMMIT])
    stages[CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION] = recorder_step2
    stages[CommitmentStep.ATOMIC_COMMIT] = recorder_step9

    gateway = fx.FakeGateway()
    driver = _driver(
        inbox, evidence_store, emergency_log, stages=stages, transmit=gateway
    )
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.flow is not None and tick_result.flow.handed_off is True
    assert tick_result.reservation is not None
    attempt_id = tick_result.reservation.attempt_id
    assert attempt_id is not None

    # The DECISION_TICK's own outcome_digest is fixed by the pipeline before the commitment flow
    # ever runs (module docstring) — it alone can never expose the gap. A SUBSEQUENT result event,
    # whose outcome depends on the ledger state the (unreconstructable) flow left behind, is what
    # makes the divergence observable.
    result_event = driver.enqueue_and_run(fx.egress_result_event(attempt_id=attempt_id))
    assert result_event.result_disposition is not None

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        _replay_build_core(evidence_store),
        scheme=SCHEME,
        window_events=None,
    )
    assert not verdict.ok
    assert len(verdict.diverged) == 1

    # Direct confirmation of the detail label, replaying the exact captured requests in order.
    recorded_stage = RecordedStage(evidence_store)
    recorded_stage(recorder_step2.captured[0])
    step9_verdict = recorded_stage(recorder_step9.captured[0])
    assert step9_verdict.outcome is StageOutcome.UNKNOWN
    assert REPLAY_STAGE_EVIDENCE_MISSING in (step9_verdict.reason or "")


def test_mutated_stage_evidence_changes_the_reconstructed_verdict(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Mutation-sensitivity companion to the class-level fail-closed test above (module
    docstring's "scope note" explains why this cannot instead be routed through
    ``replay_engine``'s own digest comparison, unlike every other mutation test in this package).

    A live tick denied at step 3 (``VENUE_ADMISSIBILITY_DECISION``) records a genuine
    ``FLOW_HALTED``/``STAGE_DENIED`` row. Tampering that ONE durable row to look like an ADMIT
    (the shape a genuine ``FLOW_STEP_ADMITTED`` receipt takes) makes a freshly-constructed
    :class:`RecordedStage` reconstruct ``ADMIT`` instead of the live run's real ``DENY`` — proving
    this class trusts durable evidence verbatim and performs no independent judgement of its own
    (by design: it must never call the real stage — see its own module docstring).
    """
    stages = fx.admitting_stages(
        denied_steps={
            CommitmentStep.VENUE_ADMISSIBILITY_DECISION: "denied for CR5-3 mutation test"
        }
    )
    recorder_step2 = _RecordingStage(
        stages[CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION]
    )
    recorder_step3 = _RecordingStage(
        stages[CommitmentStep.VENUE_ADMISSIBILITY_DECISION]
    )
    stages[CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION] = recorder_step2
    stages[CommitmentStep.VENUE_ADMISSIBILITY_DECISION] = recorder_step3

    driver = _driver(inbox, evidence_store, emergency_log, stages=stages)
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.halt_reason is not None
    assert tick_result.halt_reason.value == "STAGE_DENIED"

    # Baseline: correctly reproduces the recorded DENY.
    baseline_stage = RecordedStage(evidence_store)
    baseline_stage(recorder_step2.captured[0])
    baseline_verdict = baseline_stage(recorder_step3.captured[0])
    assert baseline_verdict.outcome is StageOutcome.DENY

    # RED: tamper the ONE durable FLOW_HALTED row for step 3 into a FLOW_STEP_ADMITTED shape —
    # never how production code writes evidence (entries is append/no-update by trigger; this
    # bypasses that trigger deliberately, as a test double for "the recorded baseline was
    # corrupted" — the same idiom test_replay.py's own mutation tests use).
    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_update")
    evidence_store.connection.execute(
        "UPDATE entries SET kind = 'FLOW_STEP_ADMITTED', payload_json = "
        'REPLACE(payload_json, \'"halt_reason": "STAGE_DENIED"\', '
        '\'"stage_outcome": "ADMIT", "authority_class": "NON_AUTHORITATIVE_PROVISIONAL"\') '
        "WHERE kind = 'FLOW_HALTED' AND payload_json LIKE '%VENUE_ADMISSIBILITY_DECISION%'"
    )

    mutated_stage = RecordedStage(
        evidence_store
    )  # fresh instance — re-reads the tampered row
    mutated_stage(recorder_step2.captured[0])
    mutated_verdict = mutated_stage(recorder_step3.captured[0])
    assert mutated_verdict.outcome is StageOutcome.ADMIT
