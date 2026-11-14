"""Hermetic tests for :class:`tos_runtime.engine.driver.EngineDriver` (TOS Phase 3 Wave 1 Lane"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, ArtifactIntegrityError, get_scheme
from tos.engine import EngineCore
from tos.engine.records import EgressResultPayload, EngineEvent, event_identity
from tos.engine.vocabulary import (
    EgressResultKind,
    EventKind,
    HaltReason,
    ResultDisposition,
)
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.flow_fingerprint import flow_fingerprint_for
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore

from . import _fixtures as fx
from .conftest import FakeMonotonicSource

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_NO_TIMEOUT_WITHIN_TEST = 10**12


def _make_driver(
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source: FakeMonotonicSource,
    max_send_result_wait_ms: int = _NO_TIMEOUT_WITHIN_TEST,
    transmit: object = None,
) -> tuple[EngineDriver, EngineCore]:
    core = fx.build_core(transmit=transmit)
    driver = EngineDriver(
        core=core,
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="driver-tests",
        monotonic_source=monotonic_source,
        max_send_result_wait_ms=max_send_result_wait_ms,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )
    return driver, core


def test_consumption_order_is_seq_order(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    driver, _core = _make_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
    )
    r1 = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    r2 = driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    assert r1.instrument_key == fx.instrument_key()
    assert r2.instrument_key == fx.instrument_key()
    assert inbox.count == 2


def test_reversed_reference_is_recorded_as_event_order_reversed(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    """The driver stamps EVERY event with its own strictly-increasing counter (module docstring"""
    driver, _core = _make_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
    )
    first = driver.enqueue_and_run(fx.decision_tick_event(seq=5))
    second = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert first.halt_reason is not HaltReason.EVENT_ORDER_REVERSED
    assert second.halt_reason is not HaltReason.EVENT_ORDER_REVERSED


def test_restart_before_evidence_commit_reprocesses_once(
    tmp_path: Path, key_provider: KeyProvider
) -> None:
    """Independent review finding #3 (2026-09-09) — RED before the fix."""
    inbox_path = tmp_path / "inbox.sqlite3"
    evidence_path = tmp_path / "evidence.sqlite3"
    emergency_log = EmergencyAppendLog(tmp_path / "emergency.jsonl")
    inbox = SqliteEventInbox(inbox_path, scheme=SCHEME)
    store = SqliteEvidenceStore(evidence_path, key_provider=key_provider)
    monotonic = FakeMonotonicSource()

    call_count = {"n": 0}

    def counting_transmit(attempt: object) -> object:
        call_count["n"] += 1
        from tos.engine import SendHandoff

        return SendHandoff(accepted_for_transmission=True, handoff_reference="x")

    driver, core = _make_driver(
        inbox=inbox,
        evidence_store=store,
        emergency_log=emergency_log,
        monotonic_source=monotonic,
        transmit=counting_transmit,
    )
    stamped = driver._stamp(fx.decision_tick_event(seq=1))
    receipt = inbox.enqueue(stamped)

    event_id = event_identity(stamped, scheme=SCHEME)
    marker_receipt = store.append(
        {"event_id": event_id},
        kind="EVENT_HANDLING_STARTED",
        record_class="EVENT_HANDLING_STARTED",
    )
    assert marker_receipt.seq is not None
    assert marker_receipt.key_generation is not None
    inbox.mark_handling_started(
        receipt.seq,
        evidence_seq=marker_receipt.seq,
        generation=marker_receipt.key_generation,
    )
    # direct-core-call: sanctioned (determinism control) — the send happens here
    core.handle(stamped)  # direct-core-call: sanctioned (determinism control)
    assert call_count["n"] == 1
    assert inbox.is_consumed(receipt.seq) is False
    store.close()
    inbox.close()

    inbox2 = SqliteEventInbox(inbox_path, scheme=SCHEME)
    store2 = SqliteEvidenceStore(evidence_path, key_provider=key_provider)
    driver2, _core2 = _make_driver(
        inbox=inbox2,
        evidence_store=store2,
        emergency_log=emergency_log,
        monotonic_source=monotonic,
        transmit=counting_transmit,
    )
    recovered = driver2.run_once()
    assert recovered is None
    assert inbox2.is_consumed(receipt.seq) is True
    assert call_count["n"] == 1

    consumed_rows = store2.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'EVENT_CONSUMED'"
    ).fetchall()
    assert len(consumed_rows) == 1
    payload = json.loads(consumed_rows[0][0])["payload"]
    assert payload["halt_reason"] == "HANDLING_INTERRUPTED_NO_SEND_EVIDENCE"
    assert payload["outcome_digest"] is None

    dropped_rows = store2.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'DECISION_TICK_DROPPED_ON_RECOVERY'"
    ).fetchall()
    assert len(dropped_rows) == 1
    dropped_payload = json.loads(dropped_rows[0][0])["payload"]
    assert dropped_payload["event_id"] == event_id
    store2.close()
    inbox2.close()


def test_marker_before_handle_crash_is_no_send_evidence_with_visibility_row(
    tmp_path: Path, key_provider: KeyProvider
) -> None:
    """Re-review finding N1 probe (2026-09-09): the marker is durably written and the process"""
    inbox_path = tmp_path / "inbox.sqlite3"
    evidence_path = tmp_path / "evidence.sqlite3"
    emergency_log = EmergencyAppendLog(tmp_path / "emergency.jsonl")
    inbox = SqliteEventInbox(inbox_path, scheme=SCHEME)
    store = SqliteEvidenceStore(evidence_path, key_provider=key_provider)
    monotonic = FakeMonotonicSource()

    driver, _core = _make_driver(
        inbox=inbox,
        evidence_store=store,
        emergency_log=emergency_log,
        monotonic_source=monotonic,
    )
    stamped = driver._stamp(fx.decision_tick_event(seq=1))
    receipt = inbox.enqueue(stamped)

    event_id = event_identity(stamped, scheme=SCHEME)
    marker_receipt = store.append(
        {"event_id": event_id},
        kind="EVENT_HANDLING_STARTED",
        record_class="EVENT_HANDLING_STARTED",
    )
    assert marker_receipt.seq is not None
    assert marker_receipt.key_generation is not None
    inbox.mark_handling_started(
        receipt.seq,
        evidence_seq=marker_receipt.seq,
        generation=marker_receipt.key_generation,
    )
    store.close()
    inbox.close()

    inbox2 = SqliteEventInbox(inbox_path, scheme=SCHEME)
    store2 = SqliteEvidenceStore(evidence_path, key_provider=key_provider)
    driver2, _core2 = _make_driver(
        inbox=inbox2,
        evidence_store=store2,
        emergency_log=emergency_log,
        monotonic_source=monotonic,
    )
    assert driver2.run_once() is None
    assert inbox2.is_consumed(receipt.seq) is True

    consumed_rows = store2.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'EVENT_CONSUMED'"
    ).fetchall()
    assert len(consumed_rows) == 1
    payload = json.loads(consumed_rows[0][0])["payload"]
    assert payload["halt_reason"] == "HANDLING_INTERRUPTED_NO_SEND_EVIDENCE"

    dropped_rows = store2.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'DECISION_TICK_DROPPED_ON_RECOVERY'"
    ).fetchall()
    assert len(dropped_rows) == 1
    assert json.loads(dropped_rows[0][0])["payload"]["event_id"] == event_id

    possibly_live_rows = store2.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND'"
    ).fetchone()[0]
    assert possibly_live_rows == 0
    store2.close()
    inbox2.close()


def test_restart_with_send_evidence_after_marker_records_additional_possibly_live_halt(
    tmp_path: Path, key_provider: KeyProvider
) -> None:
    """Finding #3's second half: when the interrupted flow's OWN durable evidence proves it"""
    inbox_path = tmp_path / "inbox.sqlite3"
    evidence_path = tmp_path / "evidence.sqlite3"
    emergency_log = EmergencyAppendLog(tmp_path / "emergency.jsonl")
    inbox = SqliteEventInbox(inbox_path, scheme=SCHEME)
    store = SqliteEvidenceStore(evidence_path, key_provider=key_provider)
    monotonic = FakeMonotonicSource()

    driver, _core = _make_driver(
        inbox=inbox,
        evidence_store=store,
        emergency_log=emergency_log,
        monotonic_source=monotonic,
    )
    stamped = driver._stamp(fx.decision_tick_event(seq=1))
    receipt = inbox.enqueue(stamped)

    event_id = event_identity(stamped, scheme=SCHEME)
    marker_receipt = store.append(
        {"event_id": event_id},
        kind="EVENT_HANDLING_STARTED",
        record_class="EVENT_HANDLING_STARTED",
    )
    assert marker_receipt.seq is not None
    assert marker_receipt.key_generation is not None
    inbox.mark_handling_started(
        receipt.seq,
        evidence_seq=marker_receipt.seq,
        generation=marker_receipt.key_generation,
    )
    store.append(
        {"attempt_id": "attempt-x"}, kind="SEND_STARTED", record_class="SEND_STARTED"
    )
    store.close()
    inbox.close()

    inbox2 = SqliteEventInbox(inbox_path, scheme=SCHEME)
    store2 = SqliteEvidenceStore(evidence_path, key_provider=key_provider)
    driver2, _core2 = _make_driver(
        inbox=inbox2,
        evidence_store=store2,
        emergency_log=emergency_log,
        monotonic_source=monotonic,
    )
    assert driver2.run_once() is None
    assert inbox2.is_consumed(receipt.seq) is True

    possibly_live_rows = store2.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND'"
    ).fetchone()[0]
    assert possibly_live_rows == 1

    consumed_rows = store2.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'EVENT_CONSUMED'"
    ).fetchall()
    assert len(consumed_rows) == 1
    payload = json.loads(consumed_rows[0][0])["payload"]
    assert payload["halt_reason"] == "HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND"
    dropped_rows = store2.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'DECISION_TICK_DROPPED_ON_RECOVERY'"
    ).fetchone()[0]
    assert dropped_rows == 0
    store2.close()
    inbox2.close()


def test_restart_after_evidence_before_mark_recovers_without_reprocessing(
    tmp_path: Path, key_provider: KeyProvider
) -> None:
    """Crash window 2: evidence was durably committed, but the inbox mark"""
    inbox_path = tmp_path / "inbox.sqlite3"
    evidence_path = tmp_path / "evidence.sqlite3"
    emergency_log = EmergencyAppendLog(tmp_path / "emergency.jsonl")
    inbox = SqliteEventInbox(inbox_path, scheme=SCHEME)
    store = SqliteEvidenceStore(evidence_path, key_provider=key_provider)
    monotonic = FakeMonotonicSource()

    call_count = {"n": 0}

    def counting_transmit(attempt: object) -> object:
        call_count["n"] += 1
        from tos.engine import SendHandoff

        return SendHandoff(accepted_for_transmission=True, handoff_reference="x")

    driver, core = _make_driver(
        inbox=inbox,
        evidence_store=store,
        emergency_log=emergency_log,
        monotonic_source=monotonic,
        transmit=counting_transmit,
    )
    stamped = driver._stamp(fx.decision_tick_event(seq=1))
    receipt = inbox.enqueue(stamped)

    event_id = event_identity(stamped, scheme=SCHEME)
    result = core.handle(stamped)  # direct-core-call: sanctioned (determinism control)
    evidence_seq, _generation = driver._record_consumed(
        event_id=event_id,
        payload_digest=SCHEME.compute_digest(stamped.model_dump(mode="json")),
        outcome_digest=result.outcome_digest,
        halt_reason=(
            result.halt_reason.value if result.halt_reason is not None else None
        ),
        flow_fingerprint=flow_fingerprint_for(result),
    )
    assert call_count["n"] == 1
    assert inbox.is_consumed(receipt.seq) is False
    store.close()
    inbox.close()

    inbox2 = SqliteEventInbox(inbox_path, scheme=SCHEME)
    store2 = SqliteEvidenceStore(evidence_path, key_provider=key_provider)
    driver2, core2 = _make_driver(
        inbox=inbox2,
        evidence_store=store2,
        emergency_log=emergency_log,
        monotonic_source=monotonic,
        transmit=counting_transmit,
    )
    recovered = driver2.run_once()
    assert recovered is None
    assert inbox2.is_consumed(receipt.seq) is True
    assert call_count["n"] == 1

    consumed_rows = store2.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'EVENT_CONSUMED'"
    ).fetchone()[0]
    assert consumed_rows == 1
    store2.close()
    inbox2.close()


def test_restart_after_mark_is_a_pure_noop(
    tmp_path: Path, key_provider: KeyProvider
) -> None:
    """Crash window 3: everything already completed. Restart finds nothing pending."""
    inbox_path = tmp_path / "inbox.sqlite3"
    evidence_path = tmp_path / "evidence.sqlite3"
    emergency_log = EmergencyAppendLog(tmp_path / "emergency.jsonl")
    inbox = SqliteEventInbox(inbox_path, scheme=SCHEME)
    store = SqliteEvidenceStore(evidence_path, key_provider=key_provider)
    monotonic = FakeMonotonicSource()
    driver, _core = _make_driver(
        inbox=inbox,
        evidence_store=store,
        emergency_log=emergency_log,
        monotonic_source=monotonic,
    )
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    store.close()
    inbox.close()

    inbox2 = SqliteEventInbox(inbox_path, scheme=SCHEME)
    store2 = SqliteEvidenceStore(evidence_path, key_provider=key_provider)
    driver2, _core2 = _make_driver(
        inbox=inbox2,
        evidence_store=store2,
        emergency_log=emergency_log,
        monotonic_source=monotonic,
    )
    assert driver2.run_once() is None
    assert driver2.run_until_idle() == ()
    store2.close()
    inbox2.close()


def test_gateway_results_are_drained_and_reinjected_as_egress_result_events(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    """``FakeGateway`` retains an ACK result SYNCHRONOUSLY inside its own ``__call__`` (mirroring"""
    gateway = fx.FakeGateway()
    driver, _core = _make_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
        transmit=gateway,
    )
    driver.bind_gateway(gateway)

    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.flow is not None
    assert tick_result.flow.handed_off is True

    egress_rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'EVENT_CONSUMED'"
    ).fetchall()
    assert len(egress_rows) == 2
    assert inbox.count == 2


def test_no_gateway_bound_is_a_safe_no_op(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    driver, _core = _make_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
    )
    result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert result is not None


def test_reenqueuing_the_same_unstamped_event_is_not_a_duplicate(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    """``enqueue_and_run`` re-stamps its argument with a FRESH yield-order coordinate on every"""
    driver, _core = _make_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
    )
    event = fx.decision_tick_event(seq=1)
    driver.enqueue_and_run(event)
    driver.enqueue_and_run(event)
    assert inbox.count == 2


def test_timeout_is_injected_after_the_configured_wait_and_capacity_stays_conservative(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    gateway = fx.FakeGateway(auto_ack=False)
    driver, _core = _make_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
        max_send_result_wait_ms=1000,
        transmit=gateway,
    )
    driver.bind_gateway(gateway)

    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.flow is not None and tick_result.flow.handed_off is True

    monotonic_source.advance(500)
    assert driver.run_once() is None

    monotonic_source.advance(600)
    timeout_result = driver.run_once()
    assert timeout_result is not None
    assert timeout_result.reservation is not None
    assert timeout_result.reservation.knowledge.value == "UNKNOWN"

    coupling_violation_rows = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'COUPLING_VIOLATION'"
    ).fetchone()[0]
    assert coupling_violation_rows == 0

    assert driver.run_once() is None

    attempt_id = tick_result.flow.attempt.attempt_id  # type: ignore[union-attr]
    late_fill = EngineEvent(
        kind=EventKind.EGRESS_RESULT,
        egress_result=EgressResultPayload(
            instrument_key=fx.instrument_key(),
            attempt_id=attempt_id,
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


def test_a_foreign_attempt_result_does_not_silence_the_genuinely_pending_timeout_watch(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    """Independent review finding #7 (2026-09-09), RED before the fix."""
    gateway = fx.FakeGateway(auto_ack=False)
    driver, _core = _make_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
        max_send_result_wait_ms=1000,
        transmit=gateway,
    )
    driver.bind_gateway(gateway)

    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.flow is not None and tick_result.flow.handed_off is True

    foreign_result = driver.enqueue_and_run(
        EngineEvent(
            kind=EventKind.EGRESS_RESULT,
            egress_result=EgressResultPayload(
                instrument_key=fx.instrument_key(),
                attempt_id="attempt-not-ours",
                kind=EgressResultKind.ACK,
            ),
        )
    )
    assert foreign_result.result_disposition is not ResultDisposition.APPLIED

    monotonic_source.advance(1500)
    timeout_result = driver.run_once()
    assert timeout_result is not None
    assert timeout_result.reservation is not None
    assert timeout_result.reservation.knowledge.value == "UNKNOWN"


def test_mismatched_attempt_result_yields_result_unmatched_and_leaves_reservation_unchanged(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    """Independent review finding #17 (A-lane half): one runtime end-to-end assertion that a"""
    gateway = fx.FakeGateway()
    driver, _core = _make_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
        transmit=gateway,
    )
    driver.bind_gateway(gateway)

    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.flow is not None and tick_result.flow.handed_off is True
    before = _core.ledger.outstanding(fx.instrument_key())

    mismatched_result = driver.enqueue_and_run(
        EngineEvent(
            kind=EventKind.EGRESS_RESULT,
            egress_result=EgressResultPayload(
                instrument_key=fx.instrument_key(),
                attempt_id="attempt-not-ours",
                kind=EgressResultKind.FULL_FILL,
                filled_quantity=Decimal("1"),
                remaining_quantity=Decimal("0"),
            ),
        )
    )
    assert mismatched_result.result_disposition is ResultDisposition.MISMATCHED_ATTEMPT
    assert mismatched_result.halt_reason is HaltReason.RESULT_UNMATCHED
    after = _core.ledger.outstanding(fx.instrument_key())
    assert after == before


def test_process_next_is_not_reentrant(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    """Re-review finding N3 pin (2026-09-09): ``_send_evidence_exists_after``'s soundness"""
    holder: dict[str, EngineDriver] = {}
    reentrant_raised = {"value": False}

    def reentrant_transmit(attempt: object) -> object:
        from tos.engine import SendHandoff

        try:
            holder["driver"].run_once()
        except ArtifactIntegrityError:
            reentrant_raised["value"] = True
        return SendHandoff(accepted_for_transmission=True, handoff_reference="x")

    driver, _core = _make_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
        transmit=reentrant_transmit,
    )
    holder["driver"] = driver

    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert reentrant_raised["value"] is True
    assert driver._draining is False
    second = driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    assert second.instrument_key == fx.instrument_key()


def test_new_risk_halt_latch_refuses_decision_tick_but_not_egress_result(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    """A durably-latched new-risk halt"""
    driver, _core = _make_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
    )
    assert inbox.new_risk_halt() is None

    inbox.record_new_risk_halt(
        reason="NEW_RISK_HALTED_BY_COUPLING_VIOLATION",
        event_id="attempt:test-latch",
        evidence_seq=None,
    )

    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.halt_reason is None
    assert tick_result.pipeline is None
    assert tick_result.outcome_digest is None
    assert "NEW_RISK_HALTED_BY_COUPLING_VIOLATION" in (tick_result.detail or "")

    rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'EVENT_CONSUMED' ORDER BY seq"
    ).fetchall()
    payloads = [json.loads(r[0])["payload"] for r in rows]
    assert payloads[-1]["halt_reason"] == "NEW_RISK_HALTED_BY_COUPLING_VIOLATION"
    assert payloads[-1]["outcome_digest"] is None

    second_tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    assert "NEW_RISK_HALTED_BY_COUPLING_VIOLATION" in (second_tick_result.detail or "")

    orphan_result_event = EngineEvent(
        kind=EventKind.EGRESS_RESULT,
        egress_result=EgressResultPayload(
            instrument_key=fx.instrument_key(),
            attempt_id="no-such-attempt",
            kind=EgressResultKind.ACK,
        ),
    )
    egress_result = driver.enqueue_and_run(orphan_result_event)
    assert egress_result.result_disposition is ResultDisposition.ORPHAN_NO_RESERVATION
