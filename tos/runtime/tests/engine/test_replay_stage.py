"""Hermetic tests for :class:`tos_runtime.engine.replay_stage.RecordedStage` and"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine import Stage
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
    """Wraps a real fixture stage, remembering every :class:`StageRequest` it receives — a test"""

    inner: object
    captured: list[StageRequest] = field(default_factory=list)

    def __call__(self, request: StageRequest) -> StageVerdict:
        self.captured.append(request)
        result = self.inner(request)  # type: ignore[operator]
        assert isinstance(
            result, StageVerdict
        ), f"wrapped stage returned {type(result).__name__}"
        return result


def _driver(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    *,
    stages: dict[CommitmentStep, Stage],
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
    """Mirrors ``_engine_wiring.py``'s own ``_replay_core_factory`` shape exactly: a single"""

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
    """The most recently admitted event, AS STAMPED by the inbox on admission — ``fx.decision_"""
    *_, (_, event) = inbox.replay()
    return event


def _call_for_event(
    recorded_stage: RecordedStage, admitted_event, request: StageRequest
) -> StageVerdict:
    """Direct unit-level call helper: sets the current event_id the same way"""
    recorded_stage.set_current_event_id(event_identity(admitted_event, scheme=SCHEME))
    return recorded_stage(request)


def test_a_recorded_refusal_before_the_send_boundary_replays_as_the_same_refusal(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """A tick that halted BEFORE step 9 must replay to the identical halt — fully"""
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
    """CR5-5: the kernel/evidence-surface gap CR5-3 reported ([KW3-EV] closes it) — a real"""
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
    assert verdict.total_compared == 2
    assert verdict.uncompared == 0

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
    """CR5-5 requirement (a). Before this fix (CR5-3's encounter-order correlation), a window"""
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
        window_events=1,
    )
    assert verdict.ok
    assert verdict.total_compared == 1
    assert verdict.diverged == ()


def test_a_tampered_bound_identity_orphans_the_downstream_egress_result_a_real_end_to_end_divergence(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """CR5-5 requirement (b) — the end-to-end mutation the ORIGINAL CR5 dispatch wanted, now"""
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
    assert len(verdict.diverged) == 2


def test_mutated_stage_evidence_changes_the_reconstructed_verdict(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Direct class-level mutation-sensitivity companion (kept from CR5-3): tampering the ONE"""
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

    baseline_stage = RecordedStage(evidence_store)
    admitted_event = _last_admitted_event(inbox)
    baseline_verdict = _call_for_event(
        baseline_stage, admitted_event, recorder_step3.captured[0]
    )
    assert baseline_verdict.outcome is StageOutcome.DENY

    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_update")
    evidence_store.connection.execute(
        "UPDATE entries SET kind = 'FLOW_STEP_ADMITTED' "
        "WHERE kind = 'FLOW_HALTED' AND payload_json LIKE '%VENUE_ADMISSIBILITY_DECISION%'"
    )

    mutated_stage = RecordedStage(evidence_store)
    mutated_verdict = _call_for_event(
        mutated_stage, admitted_event, recorder_step3.captured[0]
    )
    assert mutated_verdict.outcome is StageOutcome.ADMIT


def test_pre_kw3_ev_evidence_without_event_id_fails_closed(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """CR5-5 requirement (c). A durable row with no ``event_id`` (pre-``[KW3-EV]`` evidence, or a"""
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


def test_p5_deleting_all_flow_step_admitted_rows_on_a_tick_only_inbox_now_diverges(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Wave-3 review probe P5, reproduced exactly (CR6 finding #1). Before this fix, a"""
    gateway = fx.FakeGateway()
    driver = _driver(
        inbox,
        evidence_store,
        emergency_log,
        stages=fx.admitting_stages(),
        transmit=gateway,
    )
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))

    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_delete")
    deleted = evidence_store.connection.execute(
        "DELETE FROM entries WHERE kind = 'FLOW_STEP_ADMITTED'"
    )
    assert deleted.rowcount == 12

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

    (row,) = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'REPLAY_DIVERGED'"
    ).fetchall()
    detail = json.loads(row[0])["payload"]
    assert detail["fingerprint_mismatch_field"] == "handed_off"


def test_p6_deleting_send_handed_off_on_a_tick_only_inbox_now_diverges(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Wave-3 review probe P6, reproduced exactly (CR6 finding #1). Deleting ONLY the"""
    gateway = fx.FakeGateway()
    driver = _driver(
        inbox,
        evidence_store,
        emergency_log,
        stages=fx.admitting_stages(),
        transmit=gateway,
    )
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))

    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_delete")
    deleted = evidence_store.connection.execute(
        "DELETE FROM entries WHERE kind = 'SEND_HANDED_OFF'"
    )
    assert deleted.rowcount == 1

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

    (row,) = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'REPLAY_DIVERGED'"
    ).fetchall()
    detail = json.loads(row[0])["payload"]
    assert detail["fingerprint_mismatch_field"] == "handed_off"


def test_p7_untampered_tick_only_inbox_stays_ok_and_the_tick_is_genuinely_compared(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Wave-3 review probe P7 (sanity control), reproduced exactly. An UNTAMPERED tick-only"""
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
    assert verdict.total_compared == 1
    assert verdict.uncompared == 0


def test_p8_deleting_the_flow_halted_row_for_a_denied_tick_now_diverges(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Re-review probe P8: a tick denied at step 3 whose ONE ``FLOW_HALTED`` row is deleted"""
    stages = fx.admitting_stages(
        denied_steps={CommitmentStep.VENUE_ADMISSIBILITY_DECISION: "denied for P8"}
    )
    driver = _driver(inbox, evidence_store, emergency_log, stages=stages)
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.halt_reason is not None
    assert tick_result.halt_reason.value == "STAGE_DENIED"

    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_delete")
    deleted = evidence_store.connection.execute(
        "DELETE FROM entries WHERE kind = 'FLOW_HALTED'"
    )
    assert deleted.rowcount == 1

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

    (row,) = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'REPLAY_DIVERGED'"
    ).fetchall()
    detail = json.loads(row[0])["payload"]
    assert detail["fingerprint_mismatch_field"] == "halt_reason"


def test_p8b_mutating_stage_denied_to_stage_unknown_on_the_flow_halted_row_now_diverges(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Re-review probe P8b: instead of deleting the ``FLOW_HALTED`` row, tamper its own"""
    stages = fx.admitting_stages(
        denied_steps={CommitmentStep.VENUE_ADMISSIBILITY_DECISION: "denied for P8b"}
    )
    driver = _driver(inbox, evidence_store, emergency_log, stages=stages)
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.halt_reason is not None
    assert tick_result.halt_reason.value == "STAGE_DENIED"

    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_update")
    updated = evidence_store.connection.execute(
        "UPDATE entries SET payload_json = "
        'REPLACE(payload_json, \'"halt_reason":"STAGE_DENIED"\', '
        '\'"halt_reason":"STAGE_UNKNOWN"\') '
        "WHERE kind = 'FLOW_HALTED'"
    )
    assert updated.rowcount == 1

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


def test_p9_a_fingerprint_less_receipt_still_gets_its_digest_compared(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Re-review finding R1, reproduced exactly: disabling ONLY the ``flow_fingerprint`` key on"""
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

    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_update")
    updated = evidence_store.connection.execute(
        "UPDATE entries SET payload_json = "
        "REPLACE(payload_json, '\"flow_fingerprint\":', '\"flow_fingerprint_DISABLED\":') "
        "WHERE kind = 'EVENT_CONSUMED'"
    )
    assert updated.rowcount == 1

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
    assert verdict.total_compared == 1
    assert verdict.uncompared == 0
    assert verdict.has_unverifiable_receipts is True
    admitted_event = next(iter(inbox.replay()))[1]
    tick_event_id = event_identity(admitted_event, scheme=SCHEME)
    assert (
        tick_event_id,
        "RECEIPT_FINGERPRINT_MISSING",
    ) in verdict.uncompared_halt_reasons


def test_p9b_a_fingerprint_less_receipt_cannot_see_a_flow_only_divergence(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Re-review probe P9b: P9's fingerprint-disabling tamper PLUS deleting all 12"""
    gateway = fx.FakeGateway()
    driver = _driver(
        inbox,
        evidence_store,
        emergency_log,
        stages=fx.admitting_stages(),
        transmit=gateway,
    )
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))

    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_update")
    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_delete")
    updated = evidence_store.connection.execute(
        "UPDATE entries SET payload_json = "
        "REPLACE(payload_json, '\"flow_fingerprint\":', '\"flow_fingerprint_DISABLED\":') "
        "WHERE kind = 'EVENT_CONSUMED'"
    )
    assert updated.rowcount == 1
    deleted = evidence_store.connection.execute(
        "DELETE FROM entries WHERE kind = 'FLOW_STEP_ADMITTED'"
    )
    assert deleted.rowcount == 12

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
    assert verdict.total_compared == 1
    assert verdict.has_unverifiable_receipts is True
