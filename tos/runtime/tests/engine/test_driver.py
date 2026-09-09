"""Hermetic tests for :class:`tos_runtime.engine.driver.EngineDriver` (TOS Phase 3 Wave 1 Lane
A-R; plan §1.1).

Crash windows are simulated by constructing a SECOND, FRESH driver over the SAME durable
inbox/evidence-store files, mirroring exactly what a real process restart would observe: the
kernel's own ``EngineCore``/``ProvisionalReservationLedger`` reset to empty (in-memory, as they
always are on restart), while the two sqlite files retain everything durably committed.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, ArtifactIntegrityError, get_scheme
from tos.engine.records import EgressResultPayload, EngineEvent, event_identity
from tos.engine.vocabulary import (
    EgressResultKind,
    EventKind,
    HaltReason,
    ResultDisposition,
)
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore

from . import _fixtures as fx
from .conftest import FakeMonotonicSource

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

#: Independent review finding #14: ``max_send_result_wait_ms`` is a concrete positive int now,
#: never ``None`` — a caller that wants "timeout injection never fires within this test" passes a
#: bound far larger than anything the test advances its ``FakeMonotonicSource`` by.
_NO_TIMEOUT_WITHIN_TEST = 10**12


def _make_driver(
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source: FakeMonotonicSource,
    max_send_result_wait_ms: int = _NO_TIMEOUT_WITHIN_TEST,
    transmit: object = None,
) -> tuple[EngineDriver, object]:
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


# -- ordering --------------------------------------------------------------


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
    # Each call fully drains before returning, so nothing interleaves — both are admitted.
    assert inbox.count == 2


def test_reversed_reference_is_recorded_as_event_order_reversed(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    """The driver stamps EVERY event with its own strictly-increasing counter (module docstring
    item 1), so a caller-supplied reference can never actually cause a reversal through the
    normal ``enqueue_and_run`` path — this is exactly the point: yield-order stamping makes a
    caller-side reversal structurally unrepresentable, which this test pins."""
    driver, _core = _make_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
    )
    first = driver.enqueue_and_run(fx.decision_tick_event(seq=5))
    second = driver.enqueue_and_run(
        fx.decision_tick_event(seq=1)
    )  # "earlier" seq, doesn't matter
    assert first.halt_reason is not HaltReason.EVENT_ORDER_REVERSED
    assert second.halt_reason is not HaltReason.EVENT_ORDER_REVERSED


# -- crash-window idempotency ------------------------------------------------


def test_restart_before_evidence_commit_reprocesses_once(
    tmp_path: Path, key_provider: KeyProvider
) -> None:
    """Independent review finding #3 (2026-09-09) — RED before the fix.

    This is the WIDEST of the three crash windows: ``core.handle`` has ALREADY run (including a
    real send, simulated here by ``counting_transmit``) but the process crashes before ANY
    ``EVENT_CONSUMED`` evidence is written at all — not evidence-committed-but-unmarked (that is
    the narrower window ``test_restart_after_evidence_before_mark_recovers_without_reprocessing``
    below exercises), but nothing durable about the consumption at all.

    Before this fix, the driver had no way to distinguish this from "never started" on restart,
    so it silently RE-HANDLED the event — re-invoking the send. The write-ahead
    ``EVENT_HANDLING_STARTED`` marker (durably recorded BEFORE ``core.handle``, independent of the
    ``EVENT_CONSUMED`` receipt) now lets restart recognise this window and refuse to re-handle:
    the transport call count must stay at 1, and the event is marked consumed with a
    ``HANDLING_INTERRUPTED_NO_SEND_EVIDENCE`` halt instead (re-review finding N1, 2026-09-09:
    this test's fake ``counting_transmit`` never writes real ``SEND_STARTED``/``SEND_HANDED_OFF``
    evidence the way the real gateway/sequencer would, so from the driver's own evidence-based
    view no send evidence exists after the marker — the conservative, correctly-scoped
    classification for what this durable evidence actually shows, even though the fake transport
    incremented ``call_count`` in memory).
    """
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

    # Manually replicate _process_next's body up to (and including) core.handle — the send has
    # ALREADY happened by this point — but WITHOUT the EVENT_CONSUMED evidence append or the
    # inbox mark. This is exactly the widest crash window (finding #3).
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
    assert (
        inbox.is_consumed(receipt.seq) is False
    )  # the crash window: nothing marked at all
    store.close()
    inbox.close()

    # "Restart": fresh inbox/evidence-store handles, fresh core, fresh driver.
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
    assert recovered is None  # no NEW EventResult — recovery, never a re-handling
    assert inbox2.is_consumed(receipt.seq) is True
    assert (
        call_count["n"] == 1
    )  # core.handle was NOT called again — the load-bearing assertion

    consumed_rows = store2.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'EVENT_CONSUMED'"
    ).fetchall()
    assert (
        len(consumed_rows) == 1
    )  # exactly one receipt, never a re-handling's second one
    payload = json.loads(consumed_rows[0][0])["payload"]
    assert payload["halt_reason"] == "HANDLING_INTERRUPTED_NO_SEND_EVIDENCE"
    assert (
        payload["outcome_digest"] is None
    )  # never fabricated — this event was never replayed

    # N1: the silent loss is ALSO durably visible as a non-halt evidence row, by kind alone.
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
    """Re-review finding N1 probe (2026-09-09): the marker is durably written and the process
    crashes BEFORE ``core.handle`` is ever called — the ordinary, safe half of finding #3's
    crash window, not the "already sent" half. Before N1 this was misreported with the same
    scary ``HANDLING_INTERRUPTED_POSSIBLY_LIVE`` name as a genuinely-possibly-live send; it is
    also silent (a DECISION_TICK dropped and never evaluated, discoverable only by scanning
    ``EVENT_CONSUMED`` payloads for a halt-reason string). N1 fixes both: the halt reason is
    ``HANDLING_INTERRUPTED_NO_SEND_EVIDENCE`` and a ``DECISION_TICK_DROPPED_ON_RECOVERY``
    evidence row makes the loss visible by ``kind`` alone."""
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

    # Write ONLY the write-ahead marker — core.handle is never called at all, simulating a crash
    # strictly between the marker append and the handle call (the narrowest possible window).
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

    # This window never reaches HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND — nothing was sent.
    possibly_live_rows = store2.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND'"
    ).fetchone()[0]
    assert possibly_live_rows == 0
    store2.close()
    inbox2.close()


def test_restart_with_send_evidence_after_marker_records_additional_possibly_live_halt(
    tmp_path: Path, key_provider: KeyProvider
) -> None:
    """Finding #3's second half: when the interrupted flow's OWN durable evidence proves it
    reached the send boundary before the crash (a real ``SEND_STARTED``/``SEND_HANDED_OFF``
    record after the ``EVENT_HANDLING_STARTED`` marker — written, in production, by
    ``tos.egressgw``'s gateway or ``tos.engine.sequencer`` respectively, both bound to this SAME
    durable evidence store per independent review finding #2's own measurement), the driver ALSO
    records a dual-path ``HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND`` HALT — durable,
    operator-visible proof that this attempt's broker-side fate is genuinely unknown, never a
    silently-dropped fact."""
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
    # A test double for the real gateway's own durable pre-send record — never fabricated by
    # EngineDriver itself in production; here it stands in for what the real send boundary would
    # have already written before the crash.
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

    # N1: this branch's own EVENT_CONSUMED receipt carries the SEND-specific reason, never the
    # NO_SEND_EVIDENCE one, and no visibility row is appended (nothing was silently dropped —
    # the possibly-live HALT above already makes this attempt operator-visible).
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
    """Crash window 2: evidence was durably committed, but the inbox mark
    never happened. Restart must recognise the existing EVENT_CONSUMED receipt and mark the row
    WITHOUT calling ``core.handle`` again — pinned here via a transmit that raises on a second
    call for the same attempt count."""
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

    # Manually replicate _process_next's body up to (and including) the evidence append, but
    # WITHOUT the inbox.mark_consumed call — this is exactly crash window 2. (The write-ahead
    # EVENT_HANDLING_STARTED marker is skipped here on purpose — this test exercises the
    # EVENT_CONSUMED-exists recovery path specifically, not the marker-only one.)
    event_id = event_identity(stamped, scheme=SCHEME)
    result = core.handle(stamped)  # direct-core-call: sanctioned (determinism control)
    evidence_seq, _generation = driver._record_consumed(
        event_id=event_id,
        payload_digest=SCHEME.compute_digest(stamped.model_dump(mode="json")),
        outcome_digest=result.outcome_digest,
        halt_reason=(
            result.halt_reason.value if result.halt_reason is not None else None
        ),
    )
    assert call_count["n"] == 1
    assert inbox.is_consumed(receipt.seq) is False  # the crash window: not yet marked
    store.close()
    inbox.close()

    # "Restart".
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
    assert recovered is None  # no NEW EventResult — recovery, not re-handling
    assert inbox2.is_consumed(receipt.seq) is True
    assert (
        call_count["n"] == 1
    )  # core.handle was NOT called again — the load-bearing assertion

    consumed_rows = store2.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'EVENT_CONSUMED'"
    ).fetchone()[0]
    assert consumed_rows == 1  # no duplicate EVENT_CONSUMED receipt either
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


# -- egress-result re-injection ----------------------------------------------


def test_gateway_results_are_drained_and_reinjected_as_egress_result_events(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    """``FakeGateway`` retains an ACK result SYNCHRONOUSLY inside its own ``__call__`` (mirroring
    the real ``BrokerEgressGateway``'s step-18/19 ordering), so ONE ``enqueue_and_run`` call must
    durably record BOTH the tick's own consumption AND the re-injected result's — never calling
    ``core.handle`` on the gateway result directly (it is enqueued and drained through the normal
    admit path, picked up on the very next drain iteration)."""
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
    assert len(egress_rows) == 2  # the tick + the re-injected ACK result
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
    assert result is not None  # no gateway bound — nothing to drain, no crash


# -- enqueue_and_run duplicate handling ---------------------------------------


def test_reenqueuing_the_same_unstamped_event_is_not_a_duplicate(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    """``enqueue_and_run`` re-stamps its argument with a FRESH yield-order coordinate on every
    call (module docstring item 1), so passing the identical unstamped ``EngineEvent`` twice
    produces two genuinely DIFFERENT admitted events (different reference -> different
    content-addressed id) — this is by design, not a duplicate. The inbox-level duplicate
    refusal is exercised directly in ``test_inbox.py``; ``enqueue_and_run``'s own duplicate
    branch is a defensive fail-safe for the crash-window recovery path
    (``test_restart_after_evidence_before_mark_recovers_without_reprocessing``), which enqueues
    an ALREADY-stamped event directly rather than through this re-stamping entry point.
    """
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


# -- timeout injection ---------------------------------------------------------


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

    # Not yet due.
    monotonic_source.advance(500)
    assert driver.run_once() is None

    # Now due.
    monotonic_source.advance(600)
    timeout_result = driver.run_once()
    assert timeout_result is not None
    assert timeout_result.reservation is not None
    assert timeout_result.reservation.knowledge.value == "UNKNOWN"

    # It fires only once — no repeated TIMEOUT spam.
    assert driver.run_once() is None

    # A late real FILL, for the SAME attempt, arrives after the TIMEOUT: it is APPLIED (RFC-005
    # §11 "later valid fill accepted" / ADR-002-002 §15.2), never rejected as a duplicate or
    # mismatch — and, load-bearingly, the transport was called exactly once for the whole
    # scenario: TIMEOUT never triggers a second, blind resubmission attempt (plan §1.1 "blind
    # resubmit 0").
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
    assert (
        len(gateway.attempts) == 1
    )  # exactly one transport call for the whole scenario


def test_a_foreign_attempt_result_does_not_silence_the_genuinely_pending_timeout_watch(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    """Independent review finding #7 (2026-09-09), RED before the fix.

    Reproduces the reviewer's exact probe: hand off (a real pending attempt is now watched), then
    a result naming a COMPLETELY DIFFERENT ("foreign") attempt lands on the SAME scope, then the
    wait bound elapses. Before the fix, ``_TimeoutTracker.observe_result`` popped the pending
    entry for ANY result "applied or not" — so the foreign result silenced the watch for the
    genuinely pending attempt and NO ``TIMEOUT`` was ever injected, defeating plan §1.1's "결과
    유실 ⇒ TIMEOUT" guarantee. After the fix, the watch clears ONLY on an ``APPLIED`` result for
    the EXACT tracked ``attempt_id`` — a foreign result is refused by the kernel itself
    (``MISMATCHED_ATTEMPT``/``ORPHAN_NO_RESERVATION``) and must not touch the watch."""
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

    # A result for a completely different ("foreign") attempt lands on the SAME scope.
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

    # The wait bound elapses — the genuinely pending attempt's TIMEOUT must still fire.
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
    """Independent review finding #17 (A-lane half): one runtime end-to-end assertion that a
    mismatched-attempt ``EGRESS_RESULT`` enqueued THROUGH THE DRIVER yields
    ``ResultDisposition``/``HaltReason`` ``RESULT_UNMATCHED`` and leaves the reservation
    projection byte-identical — the kernel already covers this (M1's own mutation kill), but the
    runtime suite had no end-to-end assertion of its own (finding #17's own coverage-asymmetry
    point)."""
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
    assert after == before  # never relaxed, never advanced — byte-identical projection


# -- re-entrancy guard (finding N3) ------------------------------------------


def test_process_next_is_not_reentrant(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    """Re-review finding N3 pin (2026-09-09): ``_send_evidence_exists_after``'s soundness
    (see its own docstring) depends on the driver never draining two events concurrently or
    re-entrantly. This proves the guard is real, not merely documented: something reachable
    from ``core.handle`` (here, the injected ``transmit`` callable) that calls back into the
    SAME driver's ``run_once`` while a drain is already in flight gets a hard
    ``ArtifactIntegrityError``.

    The kernel's own send boundary (``tos.engine.sequencer``) deliberately catches ANY exception
    ``transmit`` raises and converts it to a ``TRANSMIT_RAISED`` halt (``# noqa: BLE001`` —
    "a failed hand-off is not proof of not sent") rather than propagating it, so this test
    catches the re-entrant ``ArtifactIntegrityError`` INSIDE ``transmit`` itself (where the guard
    actually fires) instead of expecting it to surface at ``enqueue_and_run``'s own call
    boundary — never re-raising, since the kernel would swallow that anyway."""
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
    # The guard resets on the way out (``finally``) — the driver is usable afterward, on a
    # FRESH event.
    assert driver._draining is False
    second = driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    assert second.instrument_key == fx.instrument_key()
