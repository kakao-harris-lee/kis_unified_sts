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
  is never applied;
* §6 issue #971: a run of expired release snapshots gets ONE immediate re-read, then the
  ``finality_retry_interval_ms`` cadence — and a fresh snapshot ends the run.

Hermetic: no network at all — the broker is an in-process fake; the store is a ``tmp_path`` file.
"""

from __future__ import annotations

import json
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
    FILL_OBSERVER_RELEASE_SNAPSHOT_KIND,
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


# ===========================================================================
# §6 issue #971 — the immediate re-read after an expiry is once per run
# ===========================================================================

#: The tenant's values (``fill_observer.yaml``): 2 s age limit, 60 s finality re-run cadence.
_MAX_AGE_MS = 2_000
_RETRY_MS = 60_000
#: A broker whose balance + order snapshot read takes longer than the age limit, every time.
_SLOW_SNAPSHOT_MS = 2_500
#: One session-loop pass (``marketfeed.yaml`` poll_interval_ms 400 + allowance 100).
_PASS_MS = 500


class _ManualClock:
    """The observer's monotonic source; the fake broker advances it to model a slow read."""

    def __init__(self) -> None:
        self.ms = 1_000

    def now_ms(self) -> int:
        return self.ms


class _AgingSnapshots:
    """A prefetcher whose read takes ``read_ms`` of (fake) time, and a serving side that, like
    compose's ``DeferredKisWitness``, refuses a snapshot older than ``max_age_ms`` from its
    read's start (``expired``) and otherwise answers from it (``served``)."""

    def __init__(self, clock: _ManualClock, read_ms: int) -> None:
        self.clock = clock
        self.read_ms = read_ms
        self.reads = 0
        self._serving: tuple[PrefetchedSnapshot, int, list[SnapshotUse]] | None = None

    def prefetch(
        self, scope: WitnessScope, *, today: str, abort: Callable[[], bool]
    ) -> WitnessSnapshot:
        del scope, today, abort
        self.reads += 1
        self.clock.ms += self.read_ms
        return WitnessSnapshot(observed_at_generation=None, orders=())

    @contextmanager
    def serving(
        self,
        prefetched: PrefetchedSnapshot | None,
        *,
        max_age_ms: int,
        now_ms: Callable[[], int],
    ) -> Iterator[list[SnapshotUse]]:
        del now_ms
        uses: list[SnapshotUse] = []
        self._serving = None if prefetched is None else (prefetched, max_age_ms, uses)
        try:
            yield uses
        finally:
            self._serving = None

    def observe(self) -> bool:
        """The release reconciliation's read: ``True`` iff the snapshot was served (the
        release may proceed), ``False`` = refused as expired (the release HOLDS)."""
        assert self._serving is not None, "a re-run without a prefetched snapshot"
        prefetched, max_age_ms, uses = self._serving
        age = self.clock.ms - prefetched.read_started_ms
        verdict = "expired" if age > max_age_ms else "served"
        uses.append(SnapshotUse(verdict, prefetched, age, max_age_ms))
        return verdict == "served"


@pytest.fixture
def filled_store(store: SqliteEvidenceStore) -> SqliteEvidenceStore:
    """The ACK plus its recorded FULL_FILL: only the finality re-run is left to do."""
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
    return store


def _aging_observer(
    store: SqliteEvidenceStore, clock: _ManualClock, snapshots: _AgingSnapshots
) -> tuple[KisMockFillObserver, list[bool]]:
    """An observer whose finality re-run releases iff the reconciliation was served. The RCL
    never commits here, so the attempt stays re-projectable and the cadence is all we see.
    """
    outcomes: list[bool] = []

    def _reproject(_payload: EgressResultPayload) -> bool:
        outcomes.append(snapshots.observe())
        return outcomes[-1]

    observer = KisMockFillObserver(
        config=_config(
            finality_retry_interval_ms=_RETRY_MS,
            release_snapshot_max_age_ms=_MAX_AGE_MS,
        ),
        orders=_SlowBroker(()),
        evidence_store=store,
        result_sink=_Engine(),
        reproject=_reproject,
        release_committed=lambda _a: False,
        engine_holds=lambda _a: True,
        today=lambda: _DATE,
        monotonic=clock,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        snapshots=snapshots,
    )
    return observer, outcomes


def _run_passes(
    observer: KisMockFillObserver, clock: _ManualClock, until_ms: int
) -> None:
    """Session-loop passes on the fake clock: one plan/FETCH/APPLY attempt per pass."""
    while clock.ms < until_ms:
        observer.poll_once()
        clock.ms += _PASS_MS


def _run_until(
    observer: KisMockFillObserver, clock: _ManualClock, done: Callable[[], bool]
) -> None:
    """Passes until ``done`` — bounded at ten retry intervals, so a stalled cadence fails."""
    limit = clock.ms + 10 * _RETRY_MS
    while not done():
        assert clock.ms < limit, "no re-run within ten retry intervals"
        observer.poll_once()
        clock.ms += _PASS_MS


def _snapshot_rows(store: SqliteEvidenceStore) -> list[dict[str, Any]]:
    rows = store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq",
        (FILL_OBSERVER_RELEASE_SNAPSHOT_KIND,),
    ).fetchall()
    return [json.loads(r[0])["payload"] for r in rows]


def test_a_broker_slower_than_the_age_limit_is_re_read_once_then_at_the_retry_cadence(
    filled_store: SqliteEvidenceStore,
) -> None:
    """Issue #971's failing input: every snapshot read takes 2.5 s against a 2 s limit, so
    every snapshot expires and every release HOLDS. Over 10 simulated minutes the observer
    re-reads at once after the FIRST expiry only, then once per ``finality_retry_interval_ms``
    — not every 2-3 s. Mutation: set ``_reread_now`` on every expiry (the #969 behaviour) ->
    ~200 reads and rows -> red.
    """
    clock = _ManualClock()
    snapshots = _AgingSnapshots(clock, _SLOW_SNAPSHOT_MS)
    observer, outcomes = _aging_observer(filled_store, clock, snapshots)
    duration_ms = 10 * 60_000

    _run_passes(observer, clock, clock.ms + duration_ms)

    # The first due re-run, the one immediate re-read, then one per retry interval.
    bound = 2 + duration_ms // _RETRY_MS
    assert 2 <= snapshots.reads <= bound, snapshots.reads
    rows = _snapshot_rows(filled_store)
    assert len(rows) == snapshots.reads
    # Release decisions are unchanged: every expired snapshot held, none released.
    assert outcomes == [False] * snapshots.reads
    assert {r["verdict"] for r in rows} == {"expired"}
    assert [r["consecutive_expired"] for r in rows] == list(
        range(1, snapshots.reads + 1)
    )
    # The immediate re-read happened (one pass later), and the rest kept the cadence.
    starts = [r["read_started_monotonic_ms"] for r in rows]
    assert starts[1] - starts[0] < _RETRY_MS
    assert all(b - a >= _RETRY_MS for a, b in zip(starts[1:], starts[2:]))


def test_a_fresh_snapshot_after_a_run_releases_and_resets_the_run(
    filled_store: SqliteEvidenceStore,
) -> None:
    """A run of expiries ends when a snapshot is served fresh: that re-run releases, its row
    carries the length of the run it ended, and the NEXT expiry gets its own immediate re-read
    again. Mutation: never reset the run -> the post-reset expiry waits 60 s -> red."""
    clock = _ManualClock()
    snapshots = _AgingSnapshots(clock, _SLOW_SNAPSHOT_MS)
    observer, outcomes = _aging_observer(filled_store, clock, snapshots)

    # A run of three: first, immediate re-read, one retry interval later.
    _run_until(observer, clock, lambda: len(outcomes) == 3)
    assert outcomes == [False, False, False]

    # The broker recovers: the next due re-run is served and releases.
    snapshots.read_ms = 100
    _run_until(observer, clock, lambda: len(outcomes) == 4)
    assert outcomes[3] is True
    served = _snapshot_rows(filled_store)[-1]
    assert served["verdict"] == "served"
    assert served["consecutive_expired"] == 3

    # Slow again (the RCL never committed here, so re-runs continue): a NEW run, and its first
    # expiry is re-read at once — within a few passes, not a retry interval.
    snapshots.read_ms = _SLOW_SNAPSHOT_MS
    _run_until(observer, clock, lambda: len(outcomes) == 5)
    expired_at = clock.ms
    _run_until(observer, clock, lambda: len(outcomes) == 6)
    assert clock.ms - expired_at < _RETRY_MS // 10
    assert outcomes[4:] == [False, False]
    tail = _snapshot_rows(filled_store)[-2:]
    assert [r["verdict"] for r in tail] == ["expired", "expired"]
    assert [r["consecutive_expired"] for r in tail] == [1, 2]
