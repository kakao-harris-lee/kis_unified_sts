"""Hermetic tests for :class:`tos_runtime.engine.replay_stage.RecordedStage` and
:class:`~tos_runtime.engine.replay_stage.EventCorrelatingCore` (TOS Phase 3, dispatch
CR5-3/CR5-5, 2026-09-09).

Companion to ``test_replay.py`` (which covers the send-boundary half of the same replay-fidelity
class of bug, via ``RecordedTransmit``) — this module covers the commitment-flow-stage half.

CR5-5 rewrites this module for kernel lane K-W2b's ``[KW3-EV]`` (``b9447c9d``): per-step evidence
now carries ``event_id`` and, for steps 9/11, the real ``bound_identity``/``bound_digest`` —
closing both gaps CR5-3's own version of this module reported (encounter-order correlation
fragility under a truncated window, and the step-9/11 "structurally unrecoverable" refusal). The
end-to-end mutation test the original CR5 dispatch wanted is now constructible (see
:func:`test_a_tampered_bound_identity_orphans_the_downstream_egress_result_a_real_end_to_end_
divergence`) — CR5-3's own substitute direct-class-level mutation test
(``test_mutated_stage_evidence_changes_the_reconstructed_verdict``) is kept alongside it since it
still independently demonstrates this class trusts durable evidence verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import StageRequest, StageVerdict, event_identity
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.replay import replay_engine
from tos_runtime.engine.replay_stage import EventCorrelatingCore, RecordedStage
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
    shared :class:`RecordedStage` for every injected step, :class:`RecordedTransmit` iff the
    window ever recorded a hand-off, wrapped in :class:`EventCorrelatingCore` so
    ``RecordedStage`` always knows the current event's id (CR5-5)."""

    def factory():
        recorded_stage = RecordedStage(evidence_store)
        core = fx.build_core(
            stages=dict.fromkeys(fx.admitting_stages(), recorded_stage),
            transmit=(
                RecordedTransmit(evidence_store)
                if any_recorded_hand_off(evidence_store)
                else None
            ),
        )
        return EventCorrelatingCore(
            core=core, recorded_stage=recorded_stage, scheme=SCHEME
        )

    return factory


def _last_admitted_event(inbox: SqliteEventInbox):
    """The most recently admitted event, AS STAMPED by the inbox on admission — ``fx.decision_
    tick_event`` builds an UNSTAMPED event (its own docstring: "the driver replaces reference on
    admission"), so ``event_identity`` must be computed off THIS, never the pre-admission object
    a test happens to still hold a reference to."""
    *_, (_, event) = inbox.replay()
    return event


def _call_for_event(
    recorded_stage: RecordedStage, admitted_event, request: StageRequest
) -> StageVerdict:
    """Direct unit-level call helper: sets the current event_id the same way
    :class:`EventCorrelatingCore` does (off the ADMITTED, stamped event), then calls
    ``recorded_stage`` for one captured request."""
    recorded_stage.set_current_event_id(event_identity(admitted_event, scheme=SCHEME))
    return recorded_stage(request)


def test_a_recorded_refusal_before_the_send_boundary_replays_as_the_same_refusal(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """A tick that halted BEFORE step 9 must replay to the identical halt — fully
    reconstructable from durable evidence alone, no bound-value gap applies here."""
    stages = fx.admitting_stages(
        denied_steps={CommitmentStep.INDEPENDENT_APPROVAL: "denied for CR5 test"}
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


def test_a_real_hand_off_reconstructs_the_live_attempt_id_and_replays_cleanly(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """CR5-5: the kernel/evidence-surface gap CR5-3 reported ([KW3-EV] closes it) — a real
    hand-off must now replay with ZERO divergence, and the reconstructed step-9/11 verdicts must
    carry the EXACT ``bound_identity``/``bound_digest`` the live run's own attempt used, so step
    12 derives the SAME ``attempt_id``.
    """
    stages = fx.admitting_stages()
    recorder_step9 = _RecordingStage(stages[CommitmentStep.ATOMIC_COMMIT])
    recorder_step11 = _RecordingStage(stages[CommitmentStep.ORDER_CONFORMANCE_PROOF])
    stages[CommitmentStep.ATOMIC_COMMIT] = recorder_step9
    stages[CommitmentStep.ORDER_CONFORMANCE_PROOF] = recorder_step11

    gateway = fx.FakeGateway()
    driver = _driver(
        inbox, evidence_store, emergency_log, stages=stages, transmit=gateway
    )
    event = fx.decision_tick_event(seq=1)
    tick_result = driver.enqueue_and_run(event)
    assert tick_result.flow is not None and tick_result.flow.handed_off is True
    assert tick_result.reservation is not None
    live_attempt_id = tick_result.reservation.attempt_id
    assert live_attempt_id is not None
    live_attempt = tick_result.flow.attempt
    assert live_attempt is not None

    # A subsequent result event, whose outcome depends on the ledger state the flow left behind,
    # is what would make ANY reconstruction gap observable via replay_engine's own comparison.
    result_event = driver.enqueue_and_run(
        fx.egress_result_event(attempt_id=live_attempt_id)
    )
    assert result_event.result_disposition is not None

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        _replay_build_core(evidence_store),
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.ok
    assert verdict.diverged == ()
    assert (
        verdict.total_compared == 2
    )  # the DECISION_TICK and the EGRESS_RESULT, both compared
    assert verdict.uncompared == 0

    # Direct confirmation: the reconstructed step-9/11 verdicts carry the SAME bound values the
    # live attempt actually used, and re-deriving the attempt request from them reproduces the
    # live attempt_id exactly. The DECISION_TICK is the FIRST admitted event (the EGRESS_RESULT
    # enqueued above is the second) — _last_admitted_event would grab the wrong one here.
    recorded_stage = RecordedStage(evidence_store)
    admitted_tick_event = next(iter(inbox.replay()))[1]
    step9_verdict = _call_for_event(
        recorded_stage, admitted_tick_event, recorder_step9.captured[0]
    )
    step11_verdict = _call_for_event(
        recorded_stage, admitted_tick_event, recorder_step11.captured[0]
    )
    assert step9_verdict.bound_identity == live_attempt.action_flow_permit_identity
    assert step11_verdict.bound_digest == live_attempt.conformance_proof_digest


def test_window_events_truncation_aligns_by_event_id_not_desynced_by_a_skipped_earlier_flow(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """CR5-5 requirement (a). Before this fix (CR5-3's encounter-order correlation), a window
    that skips an EARLIER flow instance would still desync: the later flow's steps would wrongly
    consume the earlier instance's slot in an ordered list. Correlating by ``event_id`` is immune
    by construction — a lookup for the later event's id finds only ITS OWN recorded rows,
    regardless of which earlier events a window skips.

    Tick 1 is denied early (step 3) — it calls the first injected step (so it WOULD have occupied
    "instance 0" under the old encounter-order scheme) but leaves no ledger state. Tick 2 admits
    fully to a real hand-off. ``window_events=1`` replays ONLY tick 2.
    """
    tick1_stages = fx.admitting_stages(
        denied_steps={
            CommitmentStep.VENUE_ADMISSIBILITY_DECISION: "denied — out of window"
        }
    )
    driver1 = _driver(inbox, evidence_store, emergency_log, stages=tick1_stages)
    tick1 = driver1.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick1.halt_reason is not None and tick1.halt_reason.value == "STAGE_DENIED"

    gateway = fx.FakeGateway()
    driver2 = _driver(
        inbox,
        evidence_store,
        emergency_log,
        stages=fx.admitting_stages(),
        transmit=gateway,
    )
    tick2 = driver2.enqueue_and_run(fx.decision_tick_event(seq=2))
    assert tick2.flow is not None and tick2.flow.handed_off is True

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        _replay_build_core(evidence_store),
        scheme=SCHEME,
        window_events=1,  # only tick 2 is in the window
    )
    assert verdict.ok
    assert verdict.total_compared == 1
    assert verdict.diverged == ()


def test_a_tampered_bound_identity_orphans_the_downstream_egress_result_a_real_end_to_end_divergence(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """CR5-5 requirement (b) — the end-to-end mutation the ORIGINAL CR5 dispatch wanted, now
    constructible: tampering the durable ``bound_identity`` [KW3-EV] recorded for step 9 makes
    replay derive a DIFFERENT ``attempt_id`` than the live run's real one, so the later
    ``EGRESS_RESULT`` (naming the REAL attempt_id) reads as orphaned against replay's ledger —
    a genuine ``replay_engine`` digest divergence. RED quoted in the CR5-5 commit message.
    """
    gateway = fx.FakeGateway()
    driver = _driver(
        inbox,
        evidence_store,
        emergency_log,
        stages=fx.admitting_stages(),
        transmit=gateway,
    )
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.flow is not None and tick_result.flow.handed_off is True
    assert tick_result.reservation is not None
    live_attempt_id = tick_result.reservation.attempt_id
    assert live_attempt_id is not None

    result_event = driver.enqueue_and_run(
        fx.egress_result_event(attempt_id=live_attempt_id)
    )
    assert result_event.result_disposition is not None

    # Sanity: correctly reconstructed, this replays with zero divergence (proven by the previous
    # test) — so any divergence measured below is caused ONLY by the tamper.
    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_update")
    evidence_store.connection.execute(
        "UPDATE entries SET payload_json = "
        'REPLACE(payload_json, \'"bound_identity":"permit-ar-0"\', '
        '\'"bound_identity":"permit-ar-0-TAMPERED"\') '
        "WHERE kind = 'FLOW_STEP_ADMITTED' AND payload_json LIKE '%ATOMIC_COMMIT%'"
    )

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


def test_mutated_stage_evidence_changes_the_reconstructed_verdict(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Direct class-level mutation-sensitivity companion (kept from CR5-3): tampering the ONE
    durable ``FLOW_HALTED`` row for a denied step into a ``FLOW_STEP_ADMITTED`` shape makes a
    freshly-constructed :class:`RecordedStage` reconstruct ``ADMIT`` instead of the live run's
    real ``DENY`` — proving this class trusts durable evidence verbatim and performs no
    independent judgement of its own (by design: it must never call the real stage).
    """
    stages = fx.admitting_stages(
        denied_steps={
            CommitmentStep.VENUE_ADMISSIBILITY_DECISION: "denied for mutation test"
        }
    )
    recorder_step3 = _RecordingStage(
        stages[CommitmentStep.VENUE_ADMISSIBILITY_DECISION]
    )
    stages[CommitmentStep.VENUE_ADMISSIBILITY_DECISION] = recorder_step3

    driver = _driver(inbox, evidence_store, emergency_log, stages=stages)
    event = fx.decision_tick_event(seq=1)
    tick_result = driver.enqueue_and_run(event)
    assert tick_result.halt_reason is not None
    assert tick_result.halt_reason.value == "STAGE_DENIED"

    # Baseline: correctly reproduces the recorded DENY.
    baseline_stage = RecordedStage(evidence_store)
    admitted_event = _last_admitted_event(inbox)
    baseline_verdict = _call_for_event(
        baseline_stage, admitted_event, recorder_step3.captured[0]
    )
    assert baseline_verdict.outcome is StageOutcome.DENY

    # RED: tamper the ONE durable FLOW_HALTED row for step 3 into a FLOW_STEP_ADMITTED shape —
    # never how production code writes evidence (entries is append/no-update by trigger; this
    # bypasses that trigger deliberately, as a test double for "the recorded baseline was
    # corrupted" — the same idiom test_replay.py's own mutation tests use).
    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_update")
    evidence_store.connection.execute(
        "UPDATE entries SET kind = 'FLOW_STEP_ADMITTED' "
        "WHERE kind = 'FLOW_HALTED' AND payload_json LIKE '%VENUE_ADMISSIBILITY_DECISION%'"
    )

    mutated_stage = RecordedStage(
        evidence_store
    )  # fresh instance — re-reads the tampered row
    mutated_verdict = _call_for_event(
        mutated_stage, admitted_event, recorder_step3.captured[0]
    )
    assert mutated_verdict.outcome is StageOutcome.ADMIT


def test_pre_kw3_ev_evidence_without_event_id_fails_closed(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """CR5-5 requirement (c). A durable row with no ``event_id`` (pre-``[KW3-EV]`` evidence, or a
    row corrupted to strip it) is never indexed under any key — a lookup against the current
    event's real id therefore finds nothing and fails closed, never silently matching by
    coincidence or falling back to encounter order (CR5-3's old behavior is gone entirely).
    """
    stages = fx.admitting_stages()
    recorder_step2 = _RecordingStage(
        stages[CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION]
    )
    stages[CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION] = recorder_step2

    driver = _driver(inbox, evidence_store, emergency_log, stages=stages)
    event = fx.decision_tick_event(seq=1)
    tick_result = driver.enqueue_and_run(event)
    assert tick_result.flow is not None
    admitted_event = _last_admitted_event(inbox)
    real_event_id = event_identity(admitted_event, scheme=SCHEME)

    # Strip event_id from the durable row, simulating pre-[KW3-EV] evidence — a direct string
    # replace against the KNOWN real id, the same idiom this package's other mutation tests use.
    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_update")
    evidence_store.connection.execute(
        "UPDATE entries SET payload_json = "
        "REPLACE(payload_json, ?, '\"event_id\":null') "
        "WHERE kind = 'FLOW_STEP_ADMITTED' AND payload_json LIKE '%CANDIDATE_COMMAND_CONSTRUCTION%'",
        (f'"event_id":"{real_event_id}"',),
    )

    stage = RecordedStage(evidence_store)
    verdict = _call_for_event(stage, admitted_event, recorder_step2.captured[0])
    assert verdict.outcome is StageOutcome.UNKNOWN
    assert "REPLAY_STAGE_EVIDENCE_MISSING" in (verdict.reason or "")
