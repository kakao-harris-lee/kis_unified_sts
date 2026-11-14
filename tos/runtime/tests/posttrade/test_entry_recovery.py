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
from tos_runtime.posttrade.entry_recovery_pending import ENTRY_DISCHARGE_PENDING_KIND
from tos_runtime.posttrade.release_consumer import (
    FinalityReleaseConsumer,
    ReleaseOutcome,
)
from tos_runtime.rcl.log import ReservationTransitionHistory, SqliteCommitLog

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


def _count_history_reads(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Spy on the one expensive read: ``verify_replay`` plus a full row decode (#1008)."""
    reads = [0]
    original = SqliteCommitLog.reservation_transition_history

    def counted(
        self: SqliteCommitLog, *, writer_epoch: int
    ) -> ReservationTransitionHistory:
        reads[0] += 1
        return original(self, writer_epoch=writer_epoch)

    monkeypatch.setattr(SqliteCommitLog, "reservation_transition_history", counted)
    return reads


def _arrange_pending_row(
    *,
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
    monkeypatch: pytest.MonkeyPatch,
) -> EgressResultPayload:
    """One durable pending row: the close released its own reservation, then the process died."""
    payload = cycle._arrange_close(rcl_log, evidence_store, inbox)
    assert isinstance(payload, EgressResultPayload)

    def crash_before_entry(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated process stop before entry discharge")

    monkeypatch.setattr(FinalityReleaseConsumer, "_discharge_entry", crash_before_entry)
    with pytest.raises(RuntimeError, match="simulated process stop"):
        _consumer(
            rcl_log=rcl_log,
            evidence_store=evidence_store,
            inbox=inbox,
            monotonic_source=monotonic_source,
        ).consume(payload)
    return payload


def _commit_a_scanned_pending_row(
    rcl_log: SqliteCommitLog, evidence_store: SqliteEvidenceStore, index: int
) -> None:
    """One more pending row the scan must walk, with its close-release command committed."""
    attempt_id = f"attempt-accumulated-{index}"
    cycle._commit_named_reservation(
        rcl_log,
        reservation_id=f"res-accumulated-{index}",
        to_state=CapacityState.POSITION_CONSUMED,
        command_id=f"release-{attempt_id}",
    )
    evidence_store.append(
        {
            "attempt_id": attempt_id,
            "close_reservation_id": f"res-accumulated-{index}",
            "close_last_seq": 0,
            "close_state": CapacityState.POTENTIALLY_LIVE.value,
            "entry_reservation_id": f"res-accumulated-entry-{index}",
            "entry_last_seq": 0,
            "account": cycle._ACCOUNT,
            "instrument": cycle._INSTRUMENT,
            "proof_id": f"proof-accumulated-{index}",
            "egress_payload": {},
        },
        kind=ENTRY_DISCHARGE_PENDING_KIND,
        record_class=ENTRY_DISCHARGE_PENDING_KIND,
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


def test_idle_pass_does_not_reread_the_rcl_history_until_the_tip_moves(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#1008 — a pass that committed nothing reuses the snapshot it already holds."""
    payload = _arrange_pending_row(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
        monkeypatch=monkeypatch,
    )
    restarted = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
    )
    reads = _count_history_reads(monkeypatch)

    assert restarted.pending_recovery_attempt_ids() == (payload.attempt_id,)
    cold = reads[0]
    assert cold >= 1
    assert restarted.pending_recovery_attempt_ids() == (payload.attempt_id,)
    assert reads[0] == cold

    cycle._commit_named_reservation(
        rcl_log,
        reservation_id="res-tip-moved",
        to_state=CapacityState.POSITION_CONSUMED,
        command_id="cmd-tip-moved",
    )
    assert restarted.pending_recovery_attempt_ids() == (payload.attempt_id,)
    assert reads[0] > cold


def test_accumulated_pending_rows_do_not_cost_one_full_read_each(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#1008 — per-pass read count is independent of how many pending rows are recorded."""
    payload = _arrange_pending_row(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
        monkeypatch=monkeypatch,
    )
    restarted = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        monotonic_source=monotonic_source,
    )
    reads = _count_history_reads(monkeypatch)

    assert restarted.pending_recovery_attempt_ids() == (payload.attempt_id,)
    one_row_cost = reads[0]
    assert one_row_cost == 1

    for index in range(8):
        _commit_a_scanned_pending_row(rcl_log, evidence_store, index)
    mark = reads[0]

    assert restarted.pending_recovery_attempt_ids() == (payload.attempt_id,)
    assert reads[0] - mark == one_row_cost
