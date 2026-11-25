"""Backtest=paper parity + blind resubmit 0 (TOS Phase 3 Wave 3 Lane F-R; plan §3.2 bullets 2-3,"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import EgressResultPayload, EngineEvent
from tos.engine.vocabulary import EgressResultKind, EventKind, ResultDisposition
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore

from . import _fixtures as fx
from . import _parity_fixtures as pfx

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def test_backtest_and_engine_driver_outcome_digests_match_for_the_same_strategy(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source: object,
) -> None:
    """The same admitted strategy, the same event sequence (module docstring's adapter statement"""
    backtest_driver, backtest_core, _fill_model = pfx.build_backtest_driver_and_core()
    backtest_run = backtest_driver.run(backtest_core, pfx.one_bar())
    backtest_digests = tuple(r.outcome_digest for r in backtest_run.event_results)

    gateway = pfx.SyntheticBrokerGateway(quantity=pfx.PARITY_QUANTITY)
    engine_driver, _core = pfx.build_engine_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
        transmit=gateway,
    )
    engine_driver.bind_gateway(gateway)
    tick_result = engine_driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    engine_digests = pfx.ordered_consumed_outcome_digests(evidence_store)

    assert tick_result.flow is not None and tick_result.flow.handed_off is True
    assert backtest_run.handoff_count == 1
    assert tick_result.outcome_digest is not None

    assert len(backtest_digests) == 2
    assert len(engine_digests) == 2

    assert backtest_digests[0] is not None and backtest_digests[1] is not None
    assert engine_digests[0] is not None and engine_digests[1] is not None

    assert tick_result.outcome_digest == backtest_digests[0]
    assert backtest_digests == engine_digests


def test_blind_resubmit_lost_then_late_result_then_a_fresh_decision_uses_a_new_attempt(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source: object,
) -> None:
    """Scenarios 1 (lost result -> TIMEOUT) and 2 (late result -> FULL_FILL after TIMEOUT),"""
    gateway = fx.FakeGateway(auto_ack=False)
    sink = pfx.durable_engine_sink(evidence_store)
    driver, _core = pfx.build_engine_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
        transmit=gateway,
        sink=sink,
        max_send_result_wait_ms=1000,
        registry=pfx.registry_with_two_scopes(),
    )
    driver.bind_gateway(gateway)

    first_tick = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert first_tick.flow is not None and first_tick.flow.handed_off is True
    first_attempt_id = first_tick.flow.attempt.attempt_id  # type: ignore[union-attr]
    assert len(gateway.attempts) == 1

    monotonic_source.advance(1500)  # type: ignore[attr-defined]  # past the 1000ms bound
    timeout_result = driver.run_once()
    assert timeout_result is not None
    assert timeout_result.reservation is not None
    assert timeout_result.reservation.knowledge.value == "UNKNOWN"
    assert timeout_result.reservation.capacity_state.value == "QUARANTINED_UNKNOWN"
    assert len(gateway.attempts) == 1

    assert driver.run_once() is None

    late_fill = EngineEvent(
        kind=EventKind.EGRESS_RESULT,
        egress_result=EgressResultPayload(
            instrument_key=fx.instrument_key(),
            attempt_id=first_attempt_id,
            kind=EgressResultKind.FULL_FILL,
            filled_quantity=Decimal("1"),
            remaining_quantity=Decimal("0"),
        ),
    )
    fill_result = driver.enqueue_and_run(late_fill)
    assert fill_result.result_disposition is ResultDisposition.APPLIED
    assert fill_result.reservation is not None
    assert fill_result.reservation.knowledge.value == "FILLED"
    assert len(gateway.attempts) == 1

    second_tick = driver.enqueue_and_run(pfx.second_decision_tick_event(seq=2))
    assert second_tick.flow is not None and second_tick.flow.handed_off is True
    second_attempt_id = second_tick.flow.attempt.attempt_id  # type: ignore[union-attr]
    assert second_attempt_id != first_attempt_id
    assert len(gateway.attempts) == 2

    created_ids = pfx.attempt_ids_for_kind(evidence_store, "ATTEMPT_REQUEST_CREATED")
    handed_off_ids = pfx.attempt_ids_for_kind(evidence_store, "SEND_HANDED_OFF")
    assert created_ids == [first_attempt_id, second_attempt_id]
    assert handed_off_ids == [first_attempt_id, second_attempt_id]


def test_blind_resubmit_reversed_reference_latches_new_risk_and_refuses_the_next_decision(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source: object,
) -> None:
    """Scenario 3: a result whose reference regresses (a ``FULL_FILL`` crossing an already-applied"""
    gateway = fx.FakeGateway(auto_ack=False)
    sink = pfx.durable_engine_sink(evidence_store)
    driver, _core = pfx.build_engine_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
        transmit=gateway,
        sink=sink,
        max_send_result_wait_ms=pfx.NO_TIMEOUT_WITHIN_TEST,
    )
    driver.bind_gateway(gateway)

    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.flow is not None and tick_result.flow.handed_off is True
    attempt_id = tick_result.flow.attempt.attempt_id  # type: ignore[union-attr]
    assert len(gateway.attempts) == 1

    cancel_result = driver.enqueue_and_run(
        EngineEvent(
            kind=EventKind.EGRESS_RESULT,
            egress_result=EgressResultPayload(
                instrument_key=fx.instrument_key(),
                attempt_id=attempt_id,
                kind=EgressResultKind.CANCEL_ACK,
            ),
        )
    )
    assert cancel_result.result_disposition is ResultDisposition.APPLIED
    assert inbox.new_risk_halt() is None

    reversed_result = driver.enqueue_and_run(
        EngineEvent(
            kind=EventKind.EGRESS_RESULT,
            egress_result=EgressResultPayload(
                instrument_key=fx.instrument_key(),
                attempt_id=attempt_id,
                kind=EgressResultKind.FULL_FILL,
                filled_quantity=Decimal("1"),
                remaining_quantity=Decimal("0"),
            ),
        )
    )
    assert (
        reversed_result.result_disposition is ResultDisposition.NON_MONOTONIC_PROJECTION
    )
    assert len(gateway.attempts) == 1

    halt = inbox.new_risk_halt()
    assert halt is not None

    refused = driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    assert refused.pipeline is None
    assert refused.outcome_digest is None
    assert "NEW_RISK_HALTED_BY_COUPLING_VIOLATION" in (refused.detail or "")
    assert len(gateway.attempts) == 1

    created_ids = pfx.attempt_ids_for_kind(evidence_store, "ATTEMPT_REQUEST_CREATED")
    handed_off_ids = pfx.attempt_ids_for_kind(evidence_store, "SEND_HANDED_OFF")
    assert created_ids == [attempt_id]
    assert handed_off_ids == [attempt_id]
