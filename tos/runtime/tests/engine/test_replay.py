"""Hermetic tests for :func:`tos_runtime.engine.replay.replay_engine` (TOS Phase 3 Wave 1"""

from __future__ import annotations

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine import EngineCore
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.orthostate_projection import (
    NEW_RISK_HALTED_BY_COUPLING_VIOLATION,
)
from tos_runtime.engine.replay import replay_engine
from tos_runtime.engine.replay_transmit import (
    RecordedTransmit,
    ReplayTransmitEvidenceMissing,
    any_recorded_hand_off,
)
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.sinks import EngineEvidenceSinkAdapter
from tos_runtime.evidence.store import SqliteEvidenceStore

from . import _fixtures as fx
from .conftest import FakeMonotonicSource

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_NO_TIMEOUT_WITHIN_TEST = 10**12


def _driver(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    *,
    core: EngineCore | None = None,
) -> EngineDriver:
    """This suite's one driver wiring; ``core`` overrides the default engine core."""
    return EngineDriver(
        core=fx.build_core(transmit=None) if core is None else core,
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="replay-tests",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )


def test_identical_replay_matches_for_every_event(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    driver = _driver(inbox, evidence_store, emergency_log)
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    driver.enqueue_and_run(fx.decision_tick_event(seq=3))

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=None),
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.ok
    assert verdict.total_compared == 3
    assert verdict.diverged == ()


def test_window_events_limits_the_replay_to_the_most_recent_n(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """A windowed replay is only sound when the events outside the window carry no ledger state"""
    registry = fx.registry_with(fx.never_fires_policy())
    driver = _driver(
        inbox,
        evidence_store,
        emergency_log,
        core=fx.build_core(registry=registry, transmit=None),
    )
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    driver.enqueue_and_run(fx.decision_tick_event(seq=3))

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(registry=registry, transmit=None),
        scheme=SCHEME,
        window_events=1,
    )
    assert verdict.ok
    assert verdict.total_compared == 1


def test_zero_or_negative_window_is_rejected(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    with pytest.raises(ValueError, match="positive int or None"):
        replay_engine(
            inbox,
            evidence_store,
            emergency_log,
            lambda: fx.build_core(transmit=None),
            scheme=SCHEME,
            window_events=0,
        )


def test_mutated_recorded_outcome_digest_is_detected_as_a_divergence(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Mutation test (plan §1.1 "재생 비교 제거 red" companion): tamper with the recorded"""
    driver = _driver(inbox, evidence_store, emergency_log)
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))

    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_update")
    evidence_store.connection.execute(
        "UPDATE entries SET payload_json = "
        "REPLACE(payload_json, '\"outcome_digest\":', '\"outcome_digest_untouched\":') "
        "WHERE kind = 'EVENT_CONSUMED'"
    )

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=None),
        scheme=SCHEME,
        window_events=None,
    )
    assert not verdict.ok
    assert len(verdict.diverged) == 1

    halts = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'REPLAY_DIVERGED'"
    ).fetchone()[0]
    assert halts == 1


def test_mutated_recorded_egress_result_outcome_digest_is_detected_as_a_divergence(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """CR5 (2026-09-09), companion to the DECISION_TICK mutation test above, extended to an"""
    gateway = fx.FakeGateway()
    driver = _driver(
        inbox,
        evidence_store,
        emergency_log,
        core=fx.build_core(
            transmit=gateway, sink=EngineEvidenceSinkAdapter(evidence_store)
        ),
    )
    driver.bind_gateway(gateway)
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.flow is not None and tick_result.flow.handed_off is True
    assert inbox.count == 2
    assert any_recorded_hand_off(evidence_store)

    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_update")
    evidence_store.connection.execute(
        "UPDATE entries SET payload_json = "
        "REPLACE(payload_json, '\"outcome_digest\":', '\"outcome_digest_untouched\":') "
        "WHERE kind = 'EVENT_CONSUMED' AND seq = "
        "(SELECT MAX(seq) FROM entries WHERE kind = 'EVENT_CONSUMED')"
    )

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=RecordedTransmit(evidence_store)),
        scheme=SCHEME,
        window_events=None,
    )
    assert not verdict.ok
    assert len(verdict.diverged) == 1

    halts = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'REPLAY_DIVERGED'"
    ).fetchone()[0]
    assert halts == 1


def test_replay_never_calls_the_live_runs_transport(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """CR5 (2026-09-09) — behavioral companion to"""
    gateway = fx.FakeGateway()
    driver = _driver(
        inbox,
        evidence_store,
        emergency_log,
        core=fx.build_core(
            transmit=gateway, sink=EngineEvidenceSinkAdapter(evidence_store)
        ),
    )
    driver.bind_gateway(gateway)
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.flow is not None and tick_result.flow.handed_off is True
    assert len(gateway.attempts) == 1

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=RecordedTransmit(evidence_store)),
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.ok
    assert len(gateway.attempts) == 1


def test_events_outside_the_recorded_baseline_are_skipped_not_diverged(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """An admitted-but-not-yet-consumed row (no ``EVENT_CONSUMED`` receipt to compare against)"""
    inbox.enqueue(fx.decision_tick_event(seq=1))

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=None),
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.ok
    assert verdict.total_compared == 0


def test_recorded_transmit_refuses_to_guess_a_hand_off_the_evidence_does_not_corroborate(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """CR5 (2026-09-09) unit test for the fail-closed guard the dispatch's own disposition"""
    from tos.engine.records import AttemptRequest

    stand_in = RecordedTransmit(evidence_store)
    attempt = AttemptRequest(
        attempt_id="attempt-never-recorded",
        conformance_proof_digest="digest-proof",
        action_flow_permit_identity="permit-identity",
        reference_coordinate_digest="digest-reference",
    )
    with pytest.raises(ReplayTransmitEvidenceMissing):
        stand_in(attempt)


def test_egress_result_outcome_digest_is_compared_and_matches(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """CR5 (2026-09-09), RED before the fix — renamed from ``test_egress_result_none_outcome_"""
    gateway = fx.FakeGateway()
    driver = _driver(
        inbox,
        evidence_store,
        emergency_log,
        core=fx.build_core(
            transmit=gateway, sink=EngineEvidenceSinkAdapter(evidence_store)
        ),
    )
    driver.bind_gateway(gateway)
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.flow is not None and tick_result.flow.handed_off is True
    assert inbox.count == 2
    assert any_recorded_hand_off(evidence_store)

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=RecordedTransmit(evidence_store)),
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.ok
    assert verdict.diverged == ()
    assert verdict.total_compared == 2
    assert verdict.uncompared == 0


def test_installing_the_standin_when_the_live_run_never_had_a_send_boundary_diverges(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """CR5 (2026-09-09) — the negative the dispatch asked for ("the stand-in returning the wrong"""
    from tos.engine.records import EgressResultPayload, EngineEvent
    from tos.engine.vocabulary import EgressResultKind, EventKind

    driver = _driver(
        inbox,
        evidence_store,
        emergency_log,
        core=fx.build_core(
            transmit=None, sink=EngineEvidenceSinkAdapter(evidence_store)
        ),
    )
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.halt_reason is not None
    assert tick_result.halt_reason.value == "TRANSMIT_UNAVAILABLE"
    assert tick_result.reservation is not None
    attempt_id = tick_result.reservation.attempt_id
    assert attempt_id is not None
    assert not any_recorded_hand_off(evidence_store)

    late_result = EngineEvent(
        kind=EventKind.EGRESS_RESULT,
        egress_result=EgressResultPayload(
            instrument_key=fx.instrument_key(),
            attempt_id=attempt_id,
            kind=EgressResultKind.ACK,
        ),
    )
    result_event = driver.enqueue_and_run(late_result)
    assert result_event.result_disposition is not None

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=RecordedTransmit(evidence_store)),
        scheme=SCHEME,
        window_events=None,
    )
    assert not verdict.ok
    assert len(verdict.diverged) >= 1


class _AlwaysRefusedPreconditions:
    """A ``False``/``False`` ``CoordinatorPreconditions`` double — every ``DECISION_TICK`` this"""

    def authority_epoch_current(self) -> bool | None:
        return False

    def live_scope_authorized(self, _transport_nature: object) -> bool | None:
        return False


def test_coordinator_gate_refusal_receipt_is_uncompared_not_diverged(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Independent review finding #1, wave 2 (2026-09-09), RED before the fix."""
    driver = _driver(
        inbox,
        evidence_store,
        emergency_log,
        core=fx.build_core(transmit=None, preconditions=_AlwaysRefusedPreconditions()),
    )
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.halt_reason is not None
    assert tick_result.halt_reason.value == "AUTHORITY_NOT_CURRENT"
    assert tick_result.outcome_digest is None

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=None),
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.ok
    assert verdict.diverged == ()
    assert verdict.total_compared == 0
    assert verdict.uncompared == 1
    assert len(verdict.uncompared_halt_reasons) == 1
    event_id, halt_reason = verdict.uncompared_halt_reasons[0]
    assert halt_reason == "AUTHORITY_NOT_CURRENT"


def test_new_risk_halt_latch_receipt_is_uncompared_not_diverged(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Re-review finding R1 (2026-09-09), RED before the fix."""
    driver = _driver(
        inbox,
        evidence_store,
        emergency_log,
        core=fx.build_core(transmit=None),
    )
    inbox.record_new_risk_halt(
        reason=NEW_RISK_HALTED_BY_COUPLING_VIOLATION,
        event_id="attempt:test-r1",
        evidence_seq=None,
    )
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.pipeline is None
    assert tick_result.outcome_digest is None

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=None),
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.ok
    assert verdict.diverged == ()
    assert verdict.total_compared == 0
    assert verdict.uncompared == 1
    assert len(verdict.uncompared_halt_reasons) == 1
    event_id, halt_reason = verdict.uncompared_halt_reasons[0]
    assert halt_reason == NEW_RISK_HALTED_BY_COUPLING_VIOLATION
