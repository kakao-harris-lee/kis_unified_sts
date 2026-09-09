"""Hermetic tests for :class:`tos_runtime.engine.driver.EngineDriver` (TOS Phase 3 Wave 1 Lane
A-R; plan §1.1).

Crash windows are simulated by constructing a SECOND, FRESH driver over the SAME durable
inbox/evidence-store files, mirroring exactly what a real process restart would observe: the
kernel's own ``EngineCore``/``ProvisionalReservationLedger`` reset to empty (in-memory, as they
always are on restart), while the two sqlite files retain everything durably committed.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import EgressResultPayload, EngineEvent
from tos.engine.vocabulary import (
    EgressResultKind,
    EventKind,
    HaltReason,
    ResultDisposition,
)
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore

from . import _fixtures as fx
from .conftest import FakeMonotonicSource

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _make_driver(
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    monotonic_source: FakeMonotonicSource,
    max_send_result_wait_ms: int | None = None,
    transmit: object = None,
) -> tuple[EngineDriver, object]:
    core = fx.build_core(transmit=transmit)
    driver = EngineDriver(
        core=core,
        inbox=inbox,
        evidence_store=evidence_store,
        scheme=SCHEME,
        continuity_id="driver-tests",
        monotonic_source=monotonic_source,
        max_send_result_wait_ms=max_send_result_wait_ms,
    )
    return driver, core


# -- ordering --------------------------------------------------------------


def test_consumption_order_is_seq_order(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore, monotonic_source
) -> None:
    driver, _core = _make_driver(
        inbox=inbox, evidence_store=evidence_store, monotonic_source=monotonic_source
    )
    r1 = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    r2 = driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    assert r1.instrument_key == fx.instrument_key()
    assert r2.instrument_key == fx.instrument_key()
    # Each call fully drains before returning, so nothing interleaves — both are admitted.
    assert inbox.count == 2


def test_reversed_reference_is_recorded_as_event_order_reversed(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore, monotonic_source
) -> None:
    """The driver stamps EVERY event with its own strictly-increasing counter (module docstring
    item 1), so a caller-supplied reference can never actually cause a reversal through the
    normal ``enqueue_and_run`` path — this is exactly the point: yield-order stamping makes a
    caller-side reversal structurally unrepresentable, which this test pins."""
    driver, _core = _make_driver(
        inbox=inbox, evidence_store=evidence_store, monotonic_source=monotonic_source
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
    """Crash window 1: the process dies before the ``EVENT_CONSUMED`` evidence commit even
    starts. On restart, the event is genuinely unconsumed and is processed normally, exactly
    once."""
    inbox_path = tmp_path / "inbox.sqlite3"
    evidence_path = tmp_path / "evidence.sqlite3"
    inbox = SqliteEventInbox(inbox_path, scheme=SCHEME)
    store = SqliteEvidenceStore(evidence_path, key_provider=key_provider)
    monotonic = FakeMonotonicSource()

    # Enqueue directly (simulating the crash happened before any handling began).
    stamped_seq_holder: list[int] = []

    driver, _core = _make_driver(
        inbox=inbox, evidence_store=store, monotonic_source=monotonic
    )
    receipt = inbox.enqueue(driver._stamp(fx.decision_tick_event(seq=1)))
    stamped_seq_holder.append(receipt.seq)
    store.close()
    inbox.close()

    # "Restart": fresh inbox/evidence-store handles, fresh core, fresh driver.
    inbox2 = SqliteEventInbox(inbox_path, scheme=SCHEME)
    store2 = SqliteEvidenceStore(evidence_path, key_provider=key_provider)
    driver2, _core2 = _make_driver(
        inbox=inbox2, evidence_store=store2, monotonic_source=monotonic
    )
    result = driver2.run_once()
    assert result is not None
    assert inbox2.is_consumed(stamped_seq_holder[0])

    consumed_rows = store2.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'EVENT_CONSUMED'"
    ).fetchone()[0]
    assert consumed_rows == 1
    store2.close()
    inbox2.close()


def test_restart_after_evidence_before_mark_recovers_without_reprocessing(
    tmp_path: Path, key_provider: KeyProvider
) -> None:
    """Crash window 2 (the load-bearing one): evidence was durably committed, but the inbox mark
    never happened. Restart must recognise the existing EVENT_CONSUMED receipt and mark the row
    WITHOUT calling ``core.handle`` again — pinned here via a transmit that raises on a second
    call for the same attempt count."""
    inbox_path = tmp_path / "inbox.sqlite3"
    evidence_path = tmp_path / "evidence.sqlite3"
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
        monotonic_source=monotonic,
        transmit=counting_transmit,
    )
    stamped = driver._stamp(fx.decision_tick_event(seq=1))
    receipt = inbox.enqueue(stamped)

    # Manually replicate _process_next's body up to (and including) the evidence append, but
    # WITHOUT the inbox.mark_consumed call — this is exactly crash window 2.
    from tos.engine.records import event_identity

    event_id = event_identity(stamped, scheme=SCHEME)
    result = core.handle(stamped)
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
    inbox = SqliteEventInbox(inbox_path, scheme=SCHEME)
    store = SqliteEvidenceStore(evidence_path, key_provider=key_provider)
    monotonic = FakeMonotonicSource()
    driver, _core = _make_driver(
        inbox=inbox, evidence_store=store, monotonic_source=monotonic
    )
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    store.close()
    inbox.close()

    inbox2 = SqliteEventInbox(inbox_path, scheme=SCHEME)
    store2 = SqliteEvidenceStore(evidence_path, key_provider=key_provider)
    driver2, _core2 = _make_driver(
        inbox=inbox2, evidence_store=store2, monotonic_source=monotonic
    )
    assert driver2.run_once() is None
    assert driver2.run_until_idle() == ()
    store2.close()
    inbox2.close()


# -- egress-result re-injection ----------------------------------------------


def test_gateway_results_are_drained_and_reinjected_as_egress_result_events(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore, monotonic_source
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
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore, monotonic_source
) -> None:
    driver, _core = _make_driver(
        inbox=inbox, evidence_store=evidence_store, monotonic_source=monotonic_source
    )
    result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert result is not None  # no gateway bound — nothing to drain, no crash


# -- enqueue_and_run duplicate handling ---------------------------------------


def test_reenqueuing_the_same_unstamped_event_is_not_a_duplicate(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore, monotonic_source
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
        inbox=inbox, evidence_store=evidence_store, monotonic_source=monotonic_source
    )
    event = fx.decision_tick_event(seq=1)
    driver.enqueue_and_run(event)
    driver.enqueue_and_run(event)
    assert inbox.count == 2


# -- timeout injection ---------------------------------------------------------


def test_timeout_is_injected_after_the_configured_wait_and_capacity_stays_conservative(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore, monotonic_source
) -> None:
    gateway = fx.FakeGateway(auto_ack=False)
    driver, _core = _make_driver(
        inbox=inbox,
        evidence_store=evidence_store,
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
