"""Crash cuts for durable split-close entry discharge recovery."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import EgressResultPayload, InstrumentKey
from tos.rcl import (
    AppendRefusal,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    ReservationScope,
    TransitionCause,
)
from tos.workload import RuntimeIdentity
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.entry_recovery import prepare_entry_discharge_pending
from tos_runtime.posttrade.release_consumer import (
    FinalityReleaseConsumer,
    ReleaseOutcome,
)
from tos_runtime.rcl.log import SqliteCommitLog

from ..engine.conftest import FakeMonotonicSource, FixedKeyProvider
from . import test_release_consumer as cycle

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


def _consumer(
    *,
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> FinalityReleaseConsumer:
    return cycle._cycle_consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=cycle._CycleWitness(),
        monotonic_source=monotonic_source,
    )


def _entry_release_rows(
    rcl_log: SqliteCommitLog, entry_reservation_id: str
) -> tuple[object, ...]:
    history = rcl_log.reservation_transition_history(
        writer_epoch=rcl_log.current_epoch()
    )
    return tuple(
        row
        for row in history.transitions
        if row.reservation_id == entry_reservation_id
        and row.to_state is CapacityState.RELEASED
    )


def test_pending_candidate_alone_does_not_authorize_entry_release(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    payload = cycle._arrange_close(rcl_log, evidence_store, inbox)
    consumer = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
    )
    entry = next(
        row
        for row in consumer.projection.scope_reservations(
            InstrumentKey(account=cycle._ACCOUNT, instrument=cycle._INSTRUMENT)
        )
        if row.reservation_id == cycle._entry_reservation_id()
    )
    proof = consumer._reload_proof(
        payload.attempt_id,
        id_prefix=consumer.finality_producer.full_fill_proof_prefix,
    )
    assert proof is not None
    assert proof.proof_id is not None
    assert prepare_entry_discharge_pending(
        consumer,
        payload,
        close_reservation_id=cycle._close_reservation_id(),
        entry=entry,
        proof_id=proof.proof_id,
    )

    assert consumer.pending_recovery_attempt_ids() == ()
    assert not consumer.resume_entry_discharge(payload.attempt_id)
    assert consumer.projection.reservation_state(cycle._entry_reservation_id()) is (
        CapacityState.POSITION_CONSUMED
    )
    assert _entry_release_rows(rcl_log, cycle._entry_reservation_id()) == ()


def test_restart_recovers_crash_after_close_own_release_before_entry_discharge(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = cycle._arrange_close(rcl_log, evidence_store, inbox)
    consumer = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
    )

    def crash_before_entry(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated process stop before entry discharge")

    monkeypatch.setattr(FinalityReleaseConsumer, "_discharge_entry", crash_before_entry)
    with pytest.raises(RuntimeError, match="simulated process stop"):
        consumer.consume(payload)

    restarted = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
    )
    assert restarted.pending_recovery_attempt_ids() == (payload.attempt_id,)
    assert restarted.resume_entry_discharge(payload.attempt_id)
    assert restarted.projection.reservation_state(cycle._entry_reservation_id()) is (
        CapacityState.RELEASED
    )
    assert len(_entry_release_rows(rcl_log, cycle._entry_reservation_id())) == 1


def test_restart_after_entry_commit_is_idempotent(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = cycle._arrange_close(rcl_log, evidence_store, inbox)
    original_release = FinalityReleaseConsumer._release

    def crash_after_entry_commit(
        self: FinalityReleaseConsumer,
        payload: EgressResultPayload,
        **kwargs: Any,
    ) -> ReleaseOutcome:
        result = original_release(self, payload, **kwargs)
        if (
            kwargs.get("reservation_id") == cycle._entry_reservation_id()
            and result.released
        ):
            raise RuntimeError("simulated process stop after entry RCL commit")
        return result

    monkeypatch.setattr(FinalityReleaseConsumer, "_release", crash_after_entry_commit)
    with pytest.raises(RuntimeError, match="after entry RCL commit"):
        _consumer(
            rcl_log=rcl_log,
            evidence_store=evidence_store,
            inbox=inbox,
            monotonic_source=monotonic_source,
        ).consume(payload)

    restarted = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
    )
    assert restarted.resume_entry_discharge(payload.attempt_id)
    assert restarted.pending_recovery_attempt_ids() == ()
    assert len(_entry_release_rows(rcl_log, cycle._entry_reservation_id())) == 1


def test_entry_version_change_after_pending_fails_closed(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = cycle._arrange_close(rcl_log, evidence_store, inbox)

    def crash_before_entry(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated process stop before entry discharge")

    monkeypatch.setattr(FinalityReleaseConsumer, "_discharge_entry", crash_before_entry)
    with pytest.raises(RuntimeError):
        _consumer(
            rcl_log=rcl_log,
            evidence_store=evidence_store,
            inbox=inbox,
            monotonic_source=monotonic_source,
        ).consume(payload)

    epoch = rcl_log.current_epoch() or rcl_log.acquire_epoch(
        RuntimeIdentity(cell_id="entry-recovery-test", process_nonce="version-change")
    )
    view = rcl_log.read_linearizable(writer_epoch=epoch)
    receipt = rcl_log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id=cycle._entry_reservation_id(),
            writer_epoch=epoch,
            from_state=CapacityState.POSITION_CONSUMED,
            to_state=CapacityState.POSITION_CONSUMED,
            scope=ReservationScope(
                account=cycle._ACCOUNT, instrument=cycle._INSTRUMENT
            ),
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.RESIZE_RESERVATION,
        command_id="entry-recovery-version-bump",
        command_digest="entry-recovery-version-bump",
        expected_seq=-1 if view.last_seq is None else view.last_seq,
        finality_witness=True,
    )
    assert not isinstance(receipt, AppendRefusal)

    restarted = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
    )
    assert restarted.pending_recovery_attempt_ids() == (payload.attempt_id,)
    assert not restarted.resume_entry_discharge(payload.attempt_id)
    assert restarted.projection.reservation_state(cycle._entry_reservation_id()) is (
        CapacityState.POSITION_CONSUMED
    )
    assert _entry_release_rows(rcl_log, cycle._entry_reservation_id()) == ()
