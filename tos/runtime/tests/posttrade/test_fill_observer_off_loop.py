"""Issue #950 — the fill observer's broker reads run off the session loop's thread.

:meth:`~tos_runtime.posttrade.fill_observer.KisMockFillObserver.poll_if_due` is what the session
loop calls every pass. These tests drive it with an injected SLOW broker (a reader that holds the
GET until the test lets it go) and pin:

* §1 cadence: while a GET is in flight for seconds, every ``poll_if_due`` returns at once;
* §2 APPLY happens on the loop thread only — engine feed, finality re-run, every evidence row
  the observer writes — while the GET itself ran on another thread;
* §3 the release reconciliation's broker read is prefetched on the FETCH thread and served on
  the loop thread (``fill_fetch`` module docstring);
* §4 fail-closed behaviour is unchanged through the async path (#939's
  ``FILL_OBSERVER_ENGINE_RESERVATION_ABSENT``; a failed read is recorded);
* §5 shutdown: the worker stops with the session, is joined, and a FETCH in flight at shutdown
  is never applied.

Hermetic: no network at all — the broker is an in-process fake; the store is a ``tmp_path`` file.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from tos.engine.records import EgressResultPayload
from tos.engine.vocabulary import EgressResultKind, ResultDisposition
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.fill_fetch import PrefetchedSnapshot, SnapshotUse
from tos_runtime.posttrade.fill_observer import (
    FILL_OBSERVED_KIND,
    FILL_OBSERVER_ENGINE_RESERVATION_ABSENT_KIND,
    FILL_OBSERVER_READ_FAILED_KIND,
    FillObserverConfig,
    KisMockFillObserver,
)
from tos_runtime.recon.ports import WitnessScope, WitnessSnapshot, WitnessUnavailable
from tos_runtime.recon.witness_kis import KisOrderRow
from tos_runtime.time.sources import ProcessMonotonicSource

from ..evidence.conftest import FixedKeyProvider

_ACCOUNT = "5000000001"
_INSTRUMENT = "005930"
_DATE = "20260914"
_ODNO = "0000012345"
_ATTEMPT = "attempt-1"
_QTY = Decimal(3)
#: Long enough that a blocking design visibly fails, short enough for a hermetic suite.
_SLOW_GET_S = 3.0
#: What one loop pass may spend in the hook — far below the slow GET.
_PASS_BUDGET_S = 0.1


def _config(**overrides: Any) -> FillObserverConfig:
    values: dict[str, Any] = {
        "witness_fields": {},
        "poll_interval_ms": 1,
        "overdue_after_ms": 600_000,
        "finality_retry_interval_ms": 60_000,
        "prior_day_poll_interval_ms": 60_000,
        "poll_deadline_ms": 10_000,
        "witness_request_timeout_s": 2.0,
        "release_snapshot_max_age_ms": 60_000,
    }
    values.update(overrides)
    return FillObserverConfig(**values)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqliteEvidenceStore]:
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    instance.append(
        {
            "attempt_id": _ATTEMPT,
            "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
            "egress_result_kind": "ACK",
            "broker_execution_id": _ODNO,
            "trading_date": _DATE,
        },
        kind="EGRESS_RESULT_CONSUMED",
        record_class="EGRESS_RESULT_CONSUMED",
    )
    instance.append(
        {"send_seal": {"attempt_id": _ATTEMPT, "outbound_quantity": str(_QTY)}},
        kind="SEND_SEALED",
        record_class="SEND_SEALED",
    )
    yield instance
    instance.close()


def _filled_row() -> KisOrderRow:
    return KisOrderRow(
        odno=_ODNO,
        orgn_odno=None,
        ord_dt=_DATE,
        pdno=_INSTRUMENT,
        ord_qty=_QTY,
        tot_ccld_qty=_QTY,
        rmn_qty=Decimal(0),
        rjct_qty=Decimal(0),
        cancelled=False,
    )


class _SlowBroker:
    """``order_rows`` that holds the GET until :attr:`release` is set (or ``_SLOW_GET_S``
    passes), asking the caller's deadline predicate between "pages" like the real witness.
    """

    def __init__(self, rows: tuple[KisOrderRow, ...]) -> None:
        self.rows = rows
        self.release = threading.Event()
        self.started = threading.Event()
        self.threads: list[int] = []
        self.calls = 0
        self.aborted = 0

    def order_rows(
        self,
        scope: WitnessScope,
        *,
        inquiry_date: str | None = None,
        deadline_expired: Callable[[], bool] | None = None,
    ) -> tuple[str, tuple[KisOrderRow, ...]]:
        del scope
        self.calls += 1
        self.threads.append(threading.get_ident())
        self.started.set()
        give_up = time.monotonic() + _SLOW_GET_S
        while not self.release.wait(0.01):
            if deadline_expired is not None and deadline_expired():
                self.aborted += 1
                raise WitnessUnavailable("walk stopped by the caller's deadline")
            if time.monotonic() >= give_up:
                break
        return inquiry_date or _DATE, self.rows


class _Snapshots:
    """A :class:`~tos_runtime.posttrade.fill_fetch.SnapshotPrefetcher` that records which
    thread read and which thread was served."""

    def __init__(self) -> None:
        self.prefetch_threads: list[int] = []
        self.serving_threads: list[int] = []
        self.active: PrefetchedSnapshot | None = None

    def prefetch(
        self, scope: WitnessScope, *, today: str, abort: Callable[[], bool]
    ) -> WitnessSnapshot:
        del scope, today, abort
        self.prefetch_threads.append(threading.get_ident())
        return WitnessSnapshot(observed_at_generation=None, orders=())

    @contextmanager
    def serving(
        self,
        prefetched: PrefetchedSnapshot | None,
        *,
        max_age_ms: int,
        now_ms: Callable[[], int],
    ) -> Iterator[list[SnapshotUse]]:
        del max_age_ms, now_ms
        self.serving_threads.append(threading.get_ident())
        self.active = prefetched
        try:
            yield []
        finally:
            self.active = None


class _Engine:
    """``result_sink`` recording the thread it ran on and whether a snapshot was served."""

    def __init__(self, snapshots: _Snapshots | None = None) -> None:
        self.calls: list[tuple[EgressResultKind, int, bool]] = []
        self._snapshots = snapshots

    def __call__(self, payload: EgressResultPayload) -> ResultDisposition:
        served = self._snapshots is not None and self._snapshots.active is not None
        self.calls.append((payload.kind, threading.get_ident(), served))
        return ResultDisposition.APPLIED


def _observer(
    store: SqliteEvidenceStore,
    broker: _SlowBroker,
    engine: _Engine,
    *,
    snapshots: _Snapshots | None = None,
    engine_holds: bool = True,
    reproject: Callable[[EgressResultPayload], bool | None] = lambda _p: True,
    **config: Any,
) -> KisMockFillObserver:
    return KisMockFillObserver(
        config=_config(**config),
        orders=broker,
        evidence_store=store,
        result_sink=engine,
        reproject=reproject,
        release_committed=lambda _a: False,
        engine_holds=lambda _a: engine_holds,
        today=lambda: _DATE,
        monotonic=ProcessMonotonicSource(),
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        snapshots=snapshots,
    )


def _kinds(store: SqliteEvidenceStore) -> list[str]:
    return [
        r[0] for r in store.connection.execute("SELECT kind FROM entries ORDER BY seq")
    ]


def _poll_until_applied(observer: KisMockFillObserver, limit_s: float = 5.0) -> Any:
    deadline = time.monotonic() + limit_s
    while time.monotonic() < deadline:
        report = observer.poll_if_due()
        if report.polled:
            return report
        time.sleep(0.005)
    raise AssertionError("the FETCH result was never applied")


def _no_fetch_thread_alive() -> bool:
    return not [t for t in threading.enumerate() if t.name.startswith("tos-fill-fetch")]


# ===========================================================================
# §1 + §2 cadence and thread placement
# ===========================================================================


def test_a_slow_get_never_stretches_a_loop_pass(store: SqliteEvidenceStore) -> None:
    """Issue #950 acceptance: a broker GET held for seconds does not hold the loop. Every
    ``poll_if_due`` while it is in flight returns inside one pass's budget, and nothing is
    applied until the result is back. Mutation: run the FETCH inline (``poll_once`` from
    ``poll_if_due``) -> the first call blocks ~3 s -> red."""
    broker = _SlowBroker((_filled_row(),))
    engine = _Engine()
    observer = _observer(store, broker, engine)
    try:
        durations = []
        for _ in range(20):
            started = time.monotonic()
            report = observer.poll_if_due()
            durations.append(time.monotonic() - started)
            assert report.polled is False
            time.sleep(0.01)
        assert broker.started.is_set(), "the GET must actually be in flight"
        assert max(durations) < _PASS_BUDGET_S, durations
        assert engine.calls == []
        assert broker.calls == 1, "one FETCH in flight at a time"

        broker.release.set()
        report = _poll_until_applied(observer)
        assert [k for _a, k, _d in report.emitted] == [EgressResultKind.FULL_FILL]
    finally:
        observer.close()


def test_apply_runs_on_the_loop_thread_and_fetch_does_not(
    store: SqliteEvidenceStore,
) -> None:
    """Issue #950 acceptance: the GET ran on the FETCH worker; the engine feed and the
    observer's evidence row happened on the calling (loop) thread. Mutation: apply inside the
    worker -> the engine's recorded thread is the worker's -> red."""
    loop_thread = threading.get_ident()
    broker = _SlowBroker((_filled_row(),))
    broker.release.set()
    engine = _Engine()
    observer = _observer(store, broker, engine)
    try:
        observer.poll_if_due()
        _poll_until_applied(observer)
    finally:
        observer.close()

    assert broker.threads and all(t != loop_thread for t in broker.threads)
    assert [(kind, thread) for kind, thread, _s in engine.calls] == [
        (EgressResultKind.FULL_FILL, loop_thread)
    ]
    assert _kinds(store).count(FILL_OBSERVED_KIND) == 1


def test_a_due_finality_rerun_runs_on_the_loop_thread(
    store: SqliteEvidenceStore,
) -> None:
    """The ``_reproject_unreleased`` path (#949 r2 MEDIUM-1's 60 s term): the re-run itself —
    finality, release — runs on the loop thread, with its snapshot prefetched by the worker.
    """
    store.append(
        {
            "attempt_id": _ATTEMPT,
            "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
            "egress_result_kind": "FULL_FILL",
            "broker_execution_id": _ODNO,
            "trading_date": _DATE,
            "filled_quantity": str(_QTY),
            "remaining_quantity": "0",
        },
        kind="EGRESS_RESULT_CONSUMED",
        record_class="EGRESS_RESULT_CONSUMED",
    )
    loop_thread = threading.get_ident()
    snapshots = _Snapshots()
    reprojected: list[tuple[int, bool]] = []

    def _reproject(_payload: EgressResultPayload) -> bool:
        reprojected.append((threading.get_ident(), snapshots.active is not None))
        return True

    observer = _observer(
        store, _SlowBroker(()), _Engine(), snapshots=snapshots, reproject=_reproject
    )
    try:
        observer.poll_if_due()
        deadline = time.monotonic() + 5.0
        while not reprojected and time.monotonic() < deadline:
            observer.poll_if_due()
            time.sleep(0.005)
    finally:
        observer.close()

    assert reprojected == [(loop_thread, True)]
    assert snapshots.prefetch_threads and all(
        t != loop_thread for t in snapshots.prefetch_threads
    )


# ===========================================================================
# §3 the release path's broker read moves to FETCH
# ===========================================================================


def test_the_release_snapshot_is_read_on_fetch_and_served_on_the_loop(
    store: SqliteEvidenceStore,
) -> None:
    """A full fill reaches release reconciliation; its broker snapshot was read on the worker
    and is being served while the engine runs (so ``witness.observe`` there costs no network).
    Mutation: drop the prefetch -> ``served`` is False -> red."""
    loop_thread = threading.get_ident()
    broker = _SlowBroker((_filled_row(),))
    broker.release.set()
    snapshots = _Snapshots()
    engine = _Engine(snapshots)
    observer = _observer(store, broker, engine, snapshots=snapshots)
    try:
        observer.poll_if_due()
        _poll_until_applied(observer)
    finally:
        observer.close()

    assert engine.calls == [(EgressResultKind.FULL_FILL, loop_thread, True)]
    assert len(snapshots.prefetch_threads) == 1
    assert snapshots.prefetch_threads[0] != loop_thread
    assert snapshots.serving_threads == [loop_thread]


def test_no_snapshot_is_read_when_nothing_can_release(
    store: SqliteEvidenceStore,
) -> None:
    """A still-working order (nothing filled) reaches no release, so the worker does not pay
    for a balance read."""
    working = KisOrderRow(
        odno=_ODNO,
        orgn_odno=None,
        ord_dt=_DATE,
        pdno=_INSTRUMENT,
        ord_qty=_QTY,
        tot_ccld_qty=Decimal(0),
        rmn_qty=_QTY,
        rjct_qty=Decimal(0),
        cancelled=False,
    )
    broker = _SlowBroker((working,))
    broker.release.set()
    snapshots = _Snapshots()
    observer = _observer(store, broker, _Engine(snapshots), snapshots=snapshots)
    try:
        observer.poll_if_due()
        _poll_until_applied(observer)
    finally:
        observer.close()
    assert snapshots.prefetch_threads == []


# ===========================================================================
# §4 fail-closed paths are unchanged through the async split
# ===========================================================================


def test_engine_reservation_absent_still_holds_through_the_async_path(
    store: SqliteEvidenceStore,
) -> None:
    """#939: the engine holds no reservation -> nothing fed, one ABSENT row, recorded by the
    loop thread at APPLY."""
    broker = _SlowBroker((_filled_row(),))
    broker.release.set()
    engine = _Engine()
    observer = _observer(store, broker, engine, engine_holds=False)
    try:
        observer.poll_if_due()
        report = _poll_until_applied(observer)
    finally:
        observer.close()
    assert engine.calls == []
    assert report.held == ((_ATTEMPT, EgressResultKind.FULL_FILL),)
    assert _kinds(store).count(FILL_OBSERVER_ENGINE_RESERVATION_ABSENT_KIND) == 1


def test_a_read_cut_by_the_deadline_is_recorded_at_apply(
    store: SqliteEvidenceStore,
) -> None:
    """``poll_deadline_ms`` still bounds the FETCH's order reads, and the cut read is an
    absence recorded once by APPLY — never rows."""
    broker = _SlowBroker((_filled_row(),))
    engine = _Engine()
    observer = _observer(store, broker, engine, poll_deadline_ms=50)
    try:
        observer.poll_if_due()
        report = _poll_until_applied(observer)
    finally:
        observer.close()
    assert report.read_failed is True and report.emitted == ()
    assert broker.aborted == 1
    assert engine.calls == []
    assert _kinds(store).count(FILL_OBSERVER_READ_FAILED_KIND) == 1


# ===========================================================================
# §5 shutdown
# ===========================================================================


def test_close_stops_the_worker_and_drops_the_in_flight_fetch(
    store: SqliteEvidenceStore,
) -> None:
    """Issue #950 acceptance: a FETCH in flight at shutdown stops at its next page, the worker
    is joined (no orphan thread), and nothing it read is ever applied — not by ``close`` and
    not by a later ``poll_if_due``. Mutation: let ``close`` skip the join or keep the future ->
    a live ``tos-fill-fetch`` thread or an applied FULL_FILL -> red."""
    broker = _SlowBroker((_filled_row(),))
    engine = _Engine()
    observer = _observer(store, broker, engine)
    observer.poll_if_due()
    assert broker.started.wait(2.0)
    before = _kinds(store)

    started = time.monotonic()
    observer.close()
    assert time.monotonic() - started < 1.0, "close waited for the whole slow GET"
    assert _no_fetch_thread_alive()
    assert broker.aborted == 1

    broker.release.set()
    for _ in range(5):
        assert observer.poll_if_due().polled is False
    assert engine.calls == []
    assert _kinds(store) == before
    observer.close()  # idempotent
