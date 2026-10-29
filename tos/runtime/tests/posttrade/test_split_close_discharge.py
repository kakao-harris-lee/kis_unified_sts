"""Regression for one entry discharged by two separately filled close attempts.

Each close is a complete order fill. The broker reports six units remaining after
the first close, then reports a complete flat position after the second. The
cycle uses the production release consumer, durable per-attempt permit joins,
the RCL projection, and the real reconciliation service with an independent
broker witness.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import EgressResultPayload
from tos.engine.vocabulary import EgressResultKind
from tos.rcl import CapacityState
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.release_consumer import FinalityReleaseConsumer
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.rcl.reservation_identity import permit_reservation_id
from tos_runtime.rcl.reservation_lookup import reservation_id_for_attempt
from tos_runtime.recon.ports import WitnessOrder, WitnessOrderState, WitnessSnapshot
from tos_runtime.recon.service import (
    AttemptClassification,
    ReconciliationClass,
    ReconciliationReport,
)

from ..engine.conftest import FakeMonotonicSource, FixedKeyProvider
from . import test_release_consumer as cycle

_SECOND_CLOSE_ATTEMPT = "attempt-relc-close-2"
_SECOND_CLOSE_PERMIT = "afg-permit-relc-close-2"
_SECOND_CLOSE_RESERVATION = permit_reservation_id(
    cycle._ACCOUNT, cycle._INSTRUMENT, _SECOND_CLOSE_PERMIT
)
_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


@pytest.fixture
def evidence_store(tmp_path: Path) -> Iterator[SqliteEvidenceStore]:
    store = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    yield store
    store.close()


@pytest.fixture
def inbox(tmp_path: Path) -> Iterator[SqliteEventInbox]:
    instance = SqliteEventInbox(tmp_path / "inbox.sqlite3", scheme=_SCHEME)
    yield instance
    instance.close()


@pytest.fixture
def rcl_log(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> Iterator[SqliteCommitLog]:
    instance = SqliteCommitLog(tmp_path / "rcl.sqlite3", evidence_port=evidence_store)
    yield instance
    instance.close()


@pytest.fixture
def monotonic_source() -> FakeMonotonicSource:
    return FakeMonotonicSource(start=1_700_000_000_000)


class _CloseHistoryWitness:
    """Independent broker view of the entry and both complete close orders."""

    def __init__(
        self,
        *,
        second_close_quantity: Decimal = Decimal("6"),
        positions: tuple[tuple[str, Decimal], ...] = (),
    ) -> None:
        self._second_close_quantity = second_close_quantity
        self._positions = positions

    def observe(self, _scope) -> WitnessSnapshot:
        return WitnessSnapshot(
            observed_at_generation=1,
            orders=(
                WitnessOrder(
                    attempt_id=cycle._ENTRY_ATTEMPT,
                    broker_execution_id="exec-relc-entry",
                    quantity=Decimal("10"),
                    remaining=Decimal("0"),
                    state=WitnessOrderState.FILLED,
                ),
                WitnessOrder(
                    attempt_id=cycle._CLOSE_ATTEMPT,
                    broker_execution_id="exec-relc-close",
                    quantity=Decimal("4"),
                    remaining=Decimal("0"),
                    state=WitnessOrderState.FILLED,
                ),
                WitnessOrder(
                    attempt_id=_SECOND_CLOSE_ATTEMPT,
                    broker_execution_id="exec-relc-close-2",
                    quantity=self._second_close_quantity,
                    remaining=Decimal("0"),
                    state=WitnessOrderState.FILLED,
                ),
            ),
            positions=self._positions,
            positions_complete=True,
            provenance="independent-broker-double",
            independent_of_evidence_store=True,
        )


def _second_close_payload(quantity: Decimal = Decimal("6")) -> EgressResultPayload:
    return EgressResultPayload(
        instrument_key=cycle._KEY,
        attempt_id=_SECOND_CLOSE_ATTEMPT,
        kind=EgressResultKind.FULL_FILL,
        filled_quantity=quantity,
        remaining_quantity=Decimal("0"),
        broker_execution_id="exec-relc-close-2",
    )


def _record_second_close(
    *,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
    quantity: Decimal = Decimal("6"),
) -> EgressResultPayload:
    cycle._record_join(
        evidence_store,
        attempt_id=_SECOND_CLOSE_ATTEMPT,
        permit_identity=_SECOND_CLOSE_PERMIT,
    )
    cycle._commit_named_reservation(
        rcl_log,
        reservation_id=_SECOND_CLOSE_RESERVATION,
        to_state=CapacityState.POTENTIALLY_LIVE,
        command_id="cmd-relc-close-2",
    )
    cycle._record_receipt(
        evidence_store,
        attempt_id=_SECOND_CLOSE_ATTEMPT,
        filled=quantity,
        remaining=Decimal("0"),
        broker_execution_id="exec-relc-close-2",
    )
    payload = _second_close_payload(quantity)
    produced = cycle._producer().produce(payload)
    assert produced is not None
    evidence_store.append(
        produced.record.model_dump(mode="json"),
        kind="ECONOMIC_OBLIGATION",
        record_class="ECONOMIC_OBLIGATION",
    )
    evidence_store.append(
        produced.proof.model_dump(mode="json"),
        kind="POSTTRADE_FINALITY_PROOF",
        record_class="POSTTRADE_FINALITY_PROOF",
    )
    inbox.record_finality_witness(_SECOND_CLOSE_ATTEMPT, True)
    return payload


def _states(rcl_log: SqliteCommitLog) -> dict[str, CapacityState]:
    return {
        reservation_id: state
        for reservation_id, state, _seq, _scope in rcl_log.reservation_rows()
    }


def _released_transition_count(rcl_log: SqliteCommitLog, reservation_id: str) -> int:
    epoch = rcl_log.current_epoch()
    assert epoch is not None
    history = rcl_log.reservation_transition_history(writer_epoch=epoch)
    return sum(
        record.reservation_id == reservation_id
        and record.to_state is CapacityState.RELEASED
        for record in history.transitions
    )


class _PermittingFlatReconciliation:
    """Isolate missing close evidence from the independent reconciliation gate."""

    def __init__(self, attempt_id: str) -> None:
        self._attempt_id = attempt_id

    def reconcile(self, _scope, *, freshness) -> ReconciliationReport:
        del freshness
        return ReconciliationReport(
            field_confidences=(),
            classifications=(
                AttemptClassification(
                    attempt_id=self._attempt_id,
                    classification=ReconciliationClass.MATCHED,
                ),
            ),
            permits_capacity_release=True,
            permits_rearm=True,
            reason=None,
            observed_positions=(),
            observed_positions_complete=True,
        )


def _consumer_with_permitting_reconciliation(
    *,
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
    attempt_id: str,
) -> FinalityReleaseConsumer:
    return FinalityReleaseConsumer(
        rcl_log=rcl_log,
        projection=SqliteReservationProjectionReader(rcl_log),
        evidence_store=evidence_store,
        inbox=inbox,
        recon_service=_PermittingFlatReconciliation(attempt_id),  # type: ignore[arg-type]
        time_service=cycle._TrustedTimeService(),
        finality_producer=cycle._producer(),
        scheme=cycle.SCHEME,
        monotonic_source=monotonic_source,
        account=cycle._ACCOUNT,
        instrument=cycle._INSTRUMENT,
        release_proof_wait_ms=60_000,
    )


def _run_first_close(
    *,
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
    broker_position: Decimal = Decimal("6"),
) -> EgressResultPayload:
    payload = cycle._arrange_close(
        rcl_log,
        evidence_store,
        inbox,
        close_filled=Decimal("4"),
        close_remaining=Decimal("0"),
    )
    assert isinstance(payload, EgressResultPayload)
    consumer = cycle._cycle_consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=cycle._CycleWitness(
            positions=((cycle._INSTRUMENT, broker_position),),
            close_quantity=Decimal("4"),
        ),
        monotonic_source=monotonic_source,
    )
    consumer.consume(payload)
    return payload


def _run_second_close(
    *,
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
    quantity: Decimal = Decimal("6"),
    broker_positions: tuple[tuple[str, Decimal], ...] = (),
):
    payload = _record_second_close(
        evidence_store=evidence_store,
        inbox=inbox,
        rcl_log=rcl_log,
        quantity=quantity,
    )
    consumer = cycle._cycle_consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=_CloseHistoryWitness(
            second_close_quantity=quantity, positions=broker_positions
        ),
        monotonic_source=monotonic_source,
    )
    return consumer.consume(payload)


def test_two_fully_filled_closes_discharge_the_entry_when_the_broker_is_flat(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """Entry 10 -> close 4 (broker holds 6) -> close 6 (broker flat) releases entry.

    Both close attempts have distinct durable permit bindings and their own fully
    filled receipts. A close order's remaining quantity is zero in each case; the
    position remainder after the first close is independently reported by the
    broker witness.
    """
    first_close = cycle._arrange_close(
        rcl_log,
        evidence_store,
        inbox,
        close_filled=Decimal("4"),
        close_remaining=Decimal("0"),
    )
    # The broker confirms the first order was fully filled but the position is
    # still 6, so only the close's own reservation can be released.
    first_consumer = cycle._cycle_consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=cycle._CycleWitness(
            positions=((cycle._INSTRUMENT, Decimal("6")),),
            close_quantity=Decimal("4"),
        ),
        monotonic_source=monotonic_source,
    )
    first_consumer.consume(first_close)

    entry_reservation_id = cycle._entry_reservation_id()
    first_close_reservation_id = cycle._close_reservation_id()
    assert (
        reservation_id_for_attempt(
            evidence_store,
            cycle.SqliteReservationProjectionReader(rcl_log),
            account=cycle._ACCOUNT,
            instrument=cycle._INSTRUMENT,
            attempt_id=cycle._ENTRY_ATTEMPT,
        )
        == entry_reservation_id
    )
    assert (
        reservation_id_for_attempt(
            evidence_store,
            cycle.SqliteReservationProjectionReader(rcl_log),
            account=cycle._ACCOUNT,
            instrument=cycle._INSTRUMENT,
            attempt_id=cycle._CLOSE_ATTEMPT,
        )
        == first_close_reservation_id
    )
    assert _states(rcl_log)[entry_reservation_id] is CapacityState.POSITION_CONSUMED
    assert _states(rcl_log)[first_close_reservation_id] is CapacityState.RELEASED

    # A second, separately bound close sells the remaining 6. The final witness
    # includes every order and reports the instrument affirmatively flat.
    second_close = _record_second_close(
        evidence_store=evidence_store, inbox=inbox, rcl_log=rcl_log
    )
    assert (
        reservation_id_for_attempt(
            evidence_store,
            cycle.SqliteReservationProjectionReader(rcl_log),
            account=cycle._ACCOUNT,
            instrument=cycle._INSTRUMENT,
            attempt_id=_SECOND_CLOSE_ATTEMPT,
        )
        == _SECOND_CLOSE_RESERVATION
    )
    second_consumer = cycle._cycle_consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=_CloseHistoryWitness(),
        monotonic_source=monotonic_source,
    )
    second_consumer.consume(second_close)

    states = _states(rcl_log)
    assert states[first_close_reservation_id] is CapacityState.RELEASED
    assert states[_SECOND_CLOSE_RESERVATION] is CapacityState.RELEASED
    assert states[entry_reservation_id] is CapacityState.RELEASED


def test_two_fully_filled_closes_keep_the_entry_when_the_broker_still_holds_four(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """The 4+6 order fills do not discharge the entry if the broker still shows 4."""
    _run_first_close(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
    )
    _run_second_close(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
        quantity=Decimal("6"),
        broker_positions=((cycle._INSTRUMENT, Decimal("4")),),
    )

    states = _states(rcl_log)
    assert states[cycle._entry_reservation_id()] is CapacityState.POSITION_CONSUMED
    assert states[_SECOND_CLOSE_RESERVATION] is CapacityState.RELEASED
    held = cycle._held_rows(evidence_store)
    assert held[-1]["reason"] == cycle.ReleaseHoldReason.BROKER_POSITION_NOT_FLAT.value
    assert held[-1]["reservation_id"] == cycle._entry_reservation_id()


def test_two_close_attempts_cannot_overclose_the_entry_by_three(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """Entry 10 followed by complete close fills 4+7 is over the entry quantity."""
    _run_first_close(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
    )
    _run_second_close(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
        quantity=Decimal("7"),
        broker_positions=(),
    )

    states = _states(rcl_log)
    assert states[cycle._entry_reservation_id()] is CapacityState.POSITION_CONSUMED
    assert states[_SECOND_CLOSE_RESERVATION] is CapacityState.RELEASED
    held = cycle._held_rows(evidence_store)
    assert held[-1]["reason"] == cycle.ReleaseHoldReason.ENTRY_QUANTITY_UNPROVEN.value
    assert held[-1]["reservation_id"] == cycle._entry_reservation_id()


def test_replayed_first_close_after_consumer_restart_is_counted_once(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """Replaying close 4 after restart must not turn the later 4+6 into a double count."""
    first_close = _run_first_close(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
    )
    first_close_reservation_id = cycle._close_reservation_id()
    releases_before_replay = _released_transition_count(
        rcl_log, first_close_reservation_id
    )

    restarted_consumer = cycle._cycle_consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=cycle._CycleWitness(
            positions=((cycle._INSTRUMENT, Decimal("6")),),
            close_quantity=Decimal("4"),
        ),
        monotonic_source=monotonic_source,
    )
    restarted_consumer.consume(first_close)
    assert (
        _released_transition_count(rcl_log, first_close_reservation_id)
        == releases_before_replay
        == 1
    )

    _run_second_close(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
        quantity=Decimal("6"),
        broker_positions=(),
    )
    states = _states(rcl_log)
    assert states[cycle._entry_reservation_id()] is CapacityState.RELEASED
    assert _released_transition_count(rcl_log, cycle._entry_reservation_id()) == 1


def test_missing_close_fill_evidence_holds_the_entry_after_flat_report(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """A payload and finality proof do not replace the missing durable close receipt.

    Reconciliation is deliberately supplied a permitting, complete-flat report so
    this test reaches the close-discharge evidence gate instead of turning into an
    early reconciliation failure. The real SQLite stores, reservation projection,
    and production release consumer remain in the path.
    """
    cycle._record_join(
        evidence_store,
        attempt_id=cycle._ENTRY_ATTEMPT,
        permit_identity=cycle._ENTRY_PERMIT,
    )
    cycle._record_join(
        evidence_store,
        attempt_id=cycle._CLOSE_ATTEMPT,
        permit_identity=cycle._CLOSE_PERMIT,
    )
    cycle._commit_named_reservation(
        rcl_log,
        reservation_id=cycle._entry_reservation_id(),
        to_state=CapacityState.POSITION_CONSUMED,
        command_id="cmd-relc-entry",
    )
    cycle._commit_named_reservation(
        rcl_log,
        reservation_id=cycle._close_reservation_id(),
        to_state=CapacityState.POTENTIALLY_LIVE,
        command_id="cmd-relc-close",
    )
    cycle._record_receipt(
        evidence_store,
        attempt_id=cycle._ENTRY_ATTEMPT,
        filled=Decimal("10"),
        remaining=Decimal("0"),
        broker_execution_id="exec-relc-entry",
    )
    evidence_store.append(
        {"idempotency_key": f"synthetic-fqp-proof:{cycle._ENTRY_ATTEMPT}"},
        kind="POSTTRADE_FINALITY_PROOF",
        record_class="POSTTRADE_FINALITY_PROOF",
    )

    payload = cycle._close_payload()
    produced = cycle._producer().produce(payload)
    assert produced is not None
    evidence_store.append(
        produced.record.model_dump(mode="json"),
        kind="ECONOMIC_OBLIGATION",
        record_class="ECONOMIC_OBLIGATION",
    )
    evidence_store.append(
        produced.proof.model_dump(mode="json"),
        kind="POSTTRADE_FINALITY_PROOF",
        record_class="POSTTRADE_FINALITY_PROOF",
    )
    inbox.record_finality_witness(cycle._CLOSE_ATTEMPT, True)
    # Deliberately no EGRESS_RESULT_CONSUMED row for the close attempt.

    consumer = _consumer_with_permitting_reconciliation(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
        attempt_id=cycle._CLOSE_ATTEMPT,
    )
    consumer.consume(payload)

    states = _states(rcl_log)
    assert states[cycle._close_reservation_id()] is CapacityState.RELEASED
    assert states[cycle._entry_reservation_id()] is CapacityState.POSITION_CONSUMED
    held = cycle._held_rows(evidence_store)
    assert held[-1]["reason"] == cycle.ReleaseHoldReason.ENTRY_QUANTITY_UNPROVEN.value


def test_payload_fill_cannot_override_different_durable_current_full_fill(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """Prior 4 plus payload 6 cannot discharge entry when durable current fill is 3."""
    _run_first_close(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
    )
    _record_second_close(
        evidence_store=evidence_store,
        inbox=inbox,
        rcl_log=rcl_log,
        quantity=Decimal("3"),
    )
    payload = _second_close_payload(Decimal("6"))

    receipt_rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
        ("EGRESS_RESULT_CONSUMED",),
    ).fetchall()
    receipts = [json.loads(serialized)["payload"] for (serialized,) in receipt_rows]
    durable_current = next(
        row for row in receipts if row["attempt_id"] == _SECOND_CLOSE_ATTEMPT
    )
    assert durable_current["egress_result_kind"] == "FULL_FILL"
    assert durable_current["filled_quantity"] == "3"
    assert payload.filled_quantity == Decimal("6")

    consumer = _consumer_with_permitting_reconciliation(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
        attempt_id=_SECOND_CLOSE_ATTEMPT,
    )
    consumer.consume(payload)

    states = _states(rcl_log)
    assert states[cycle._entry_reservation_id()] is CapacityState.POSITION_CONSUMED
    assert states[_SECOND_CLOSE_RESERVATION] is CapacityState.RELEASED
    held = cycle._held_rows(evidence_store)
    assert held[-1]["reason"] == cycle.ReleaseHoldReason.ENTRY_QUANTITY_UNPROVEN.value
