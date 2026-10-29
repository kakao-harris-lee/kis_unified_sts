"""Periodic CLOSE-position reads stay on the fill observer's single FETCH worker."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from tos.engine.records import InstrumentKey
from tos_runtime.compose._broker_posttrade_wiring import DeferredKisWitness
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.fill_fetch import (
    FetchPlan,
    FetchResult,
    FetchRunner,
    HeldPositionSnapshot,
    PrefetchedSnapshot,
    SnapshotRead,
    run_fetch,
    snapshot_key,
)
from tos_runtime.posttrade.fill_observer import FillObserverConfig, KisMockFillObserver
from tos_runtime.recon.ports import WitnessScope, WitnessSnapshot, WitnessUnavailable
from tos_runtime.time.sources import ProcessMonotonicSource

from ..evidence.conftest import FixedKeyProvider

_ACCOUNT = "5000000001"
_INSTRUMENT = "005930"
_TODAY = "20261029"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqliteEvidenceStore]:
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    yield instance
    instance.close()


class _NoOrders:
    def __init__(self) -> None:
        self.calls = 0

    def order_rows(
        self,
        scope: WitnessScope,
        *,
        inquiry_date: str | None = None,
        deadline_expired: Callable[[], bool] | None = None,
    ) -> tuple[str, tuple[Any, ...]]:
        del scope, inquiry_date, deadline_expired
        self.calls += 1
        raise AssertionError("an empty ACK set must not issue an order inquiry")


class _Snapshots:
    def __init__(
        self,
        *,
        age_origin_ms: int | None = 120,
        outcome: WitnessSnapshot | WitnessUnavailable | None = None,
        block: bool = False,
    ) -> None:
        self.age_origin_ms = age_origin_ms
        self.outcome = outcome or WitnessSnapshot(
            observed_at_generation=None,
            orders=(),
            positions=((_INSTRUMENT, Decimal(3)),),
            positions_complete=True,
            provenance="kis-mock-stock",
            independent_of_evidence_store=True,
        )
        self.block = block
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0
        self.active_reads = 0
        self.max_active_reads = 0
        self.prefetch_threads: list[int] = []
        self.active: PrefetchedSnapshot | None = None
        self.strict_required = False

    def prefetch(
        self, scope: WitnessScope, *, today: str, abort: Callable[[], bool]
    ) -> SnapshotRead:
        del today, abort
        self.calls += 1
        self.active_reads += 1
        self.max_active_reads = max(self.max_active_reads, self.active_reads)
        self.prefetch_threads.append(threading.get_ident())
        self.started.set()
        try:
            if self.block:
                assert self.release.wait(
                    2.0
                ), "test did not release the fake broker read"
            outcome = self.outcome
            if isinstance(outcome, WitnessSnapshot):
                outcome = WitnessSnapshot(
                    observed_at_generation=scope.as_of_generation,
                    orders=outcome.orders,
                    positions=outcome.positions,
                    positions_complete=outcome.positions_complete,
                    provenance=outcome.provenance,
                    independent_of_evidence_store=outcome.independent_of_evidence_store,
                )
            return SnapshotRead(
                outcome=outcome,
                first_request_ms=100,
                age_origin_ms=self.age_origin_ms,
            )
        finally:
            self.active_reads -= 1

    @contextmanager
    def serving(
        self,
        prefetched: PrefetchedSnapshot | None,
        *,
        max_age_ms: int,
        now_ms: Callable[[], int],
    ) -> Iterator[list[Any]]:
        del max_age_ms, now_ms
        self.active = prefetched
        try:
            yield []
        finally:
            self.active = None

    @contextmanager
    def serving_required(
        self,
        prefetched: PrefetchedSnapshot,
        *,
        expected_scope: WitnessScope,
        expected_today: str,
        max_age_ms: int,
        now_ms: Callable[[], int],
    ) -> Iterator[list[Any]]:
        del max_age_ms, now_ms
        assert prefetched.key == snapshot_key(expected_scope)
        assert prefetched.today == expected_today
        self.active = prefetched
        self.strict_required = True
        try:
            yield []
        finally:
            self.strict_required = False
            self.active = None


class _PacedSnapshots(_Snapshots):
    """Two broker requests per observation, separated by a 2s app-key pacer."""

    def __init__(self, clock: Any) -> None:
        super().__init__(age_origin_ms=None)
        self.clock = clock
        self.scopes: list[WitnessScope] = []
        self.release_age_ms: int | None = None

    def prefetch(
        self, scope: WitnessScope, *, today: str, abort: Callable[[], bool]
    ) -> SnapshotRead:
        del today, abort
        start = self.clock.now_ms()
        self.calls += 1
        self.active_reads += 1
        self.max_active_reads = max(self.max_active_reads, self.active_reads)
        self.prefetch_threads.append(threading.get_ident())
        self.scopes.append(scope)
        self.started.set()
        try:
            # A balance grant, then a second request after the 2s app-key pacing interval.
            self.clock.ms += 4_000
            return SnapshotRead(
                outcome=WitnessSnapshot(
                    observed_at_generation=scope.as_of_generation,
                    orders=(),
                    positions=((_INSTRUMENT, Decimal(3)),),
                    positions_complete=True,
                    provenance="kis-mock-stock",
                    independent_of_evidence_store=True,
                ),
                first_request_ms=start,
                age_origin_ms=start,
            )
        finally:
            self.active_reads -= 1

    @contextmanager
    def serving_required(
        self,
        prefetched: PrefetchedSnapshot,
        *,
        expected_scope: WitnessScope,
        expected_today: str,
        max_age_ms: int,
        now_ms: Callable[[], int],
    ) -> Iterator[list[Any]]:
        assert prefetched.key == snapshot_key(expected_scope)
        assert prefetched.today == expected_today
        self.release_age_ms = now_ms() - prefetched.read_started_ms
        assert (
            self.release_age_ms <= max_age_ms
        ), "release snapshot expired before APPLY"
        self.active = prefetched
        self.strict_required = True
        try:
            yield []
        finally:
            self.strict_required = False
            self.active = None


class _CancellableSnapshots(_Snapshots):
    def __init__(self) -> None:
        super().__init__(age_origin_ms=100)
        self.aborted = threading.Event()

    def prefetch(
        self, scope: WitnessScope, *, today: str, abort: Callable[[], bool]
    ) -> SnapshotRead:
        del today
        self.calls += 1
        self.active_reads += 1
        self.max_active_reads = max(self.max_active_reads, self.active_reads)
        self.prefetch_threads.append(threading.get_ident())
        self.started.set()
        try:
            while not self.release.wait(0.002):
                if abort():
                    self.aborted.set()
                    return SnapshotRead(
                        outcome=WitnessUnavailable("risk-only fetch preempted"),
                        first_request_ms=None,
                        age_origin_ms=None,
                    )
            return SnapshotRead(
                outcome=WitnessSnapshot(
                    observed_at_generation=scope.as_of_generation,
                    orders=(),
                    positions=((_INSTRUMENT, Decimal(3)),),
                    positions_complete=True,
                    provenance="kis-mock-stock",
                    independent_of_evidence_store=True,
                ),
                first_request_ms=100,
                age_origin_ms=100,
            )
        finally:
            self.active_reads -= 1


class _EmptyOrders:
    def __init__(self) -> None:
        self.scopes: list[WitnessScope] = []

    def order_rows(
        self,
        scope: WitnessScope,
        *,
        inquiry_date: str | None = None,
        deadline_expired: Callable[[], bool] | None = None,
    ) -> tuple[str, tuple[Any, ...]]:
        del deadline_expired
        self.scopes.append(scope)
        return inquiry_date or _TODAY, ()


class _ManualClock:
    def __init__(self) -> None:
        self.ms = 1_000

    def now_ms(self) -> int:
        return self.ms


def _config(*, held_interval_ms: int | None = 60_000) -> FillObserverConfig:
    return FillObserverConfig(
        witness_fields={},
        poll_interval_ms=3_000,
        overdue_after_ms=600_000,
        finality_retry_interval_ms=60_000,
        prior_day_poll_interval_ms=600_000,
        poll_deadline_ms=1_500,
        witness_request_timeout_s=2.0,
        release_snapshot_max_age_ms=6_000,
        held_position_poll_interval_ms=held_interval_ms,
        held_position_max_age_ms=6_000 if held_interval_ms is not None else None,
    )


def _observer(
    store: SqliteEvidenceStore,
    snapshots: _Snapshots,
    *,
    publish: Callable[[HeldPositionSnapshot], None] | None = None,
    tip: tuple[int, int | None] | None = (7, 41),
    held_interval_ms: int | None = 60_000,
    pending_recovery: Callable[[], tuple[str, ...]] | None = None,
    resume_recovery: Callable[[str], object] | None = None,
    monotonic: Any | None = None,
    eligible: Callable[[], bool] | None = None,
) -> tuple[KisMockFillObserver, _NoOrders, list[WitnessScope | None]]:
    orders = _NoOrders()
    pending_scopes: list[WitnessScope | None] = []

    def _mark_pending(scope: WitnessScope | None) -> int:
        pending_scopes.append(scope)
        return 23

    observer = KisMockFillObserver(
        config=_config(held_interval_ms=held_interval_ms),
        orders=orders,
        evidence_store=store,
        result_sink=lambda _payload: None,
        reproject=lambda _payload: True,
        release_committed=lambda _attempt_id: False,
        engine_holds=lambda _attempt_id: True,
        today=lambda: _TODAY,
        monotonic=monotonic or ProcessMonotonicSource(),
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        snapshots=snapshots,
        held_position_tip=(lambda: tip) if publish is not None else None,
        held_position_eligible=(
            (eligible if eligible is not None else lambda: True)
            if publish is not None
            else None
        ),
        mark_held_position_pending=(_mark_pending if publish is not None else None),
        publish_held_position_snapshot=publish,
        pending_recovery_attempt_ids=pending_recovery,
        resume_entry_discharge=resume_recovery,
    )
    return observer, orders, pending_scopes


def _poll_until(observer: KisMockFillObserver, predicate: Callable[[], bool]) -> None:
    deadline = time.monotonic() + 2.0
    while not predicate() and time.monotonic() < deadline:
        observer.poll_if_due()
        time.sleep(0.002)
    assert predicate(), "the worker result was not applied"


def test_periodic_snapshot_runs_off_loop_without_any_ack_or_order_read(
    store: SqliteEvidenceStore,
) -> None:
    """No tracked ACK is required, and a busy worker prevents concurrent fetches."""
    snapshots = _Snapshots(age_origin_ms=120, block=True)
    published: list[HeldPositionSnapshot] = []
    loop_thread = threading.get_ident()
    observer, orders, pending_scopes = _observer(
        store, snapshots, publish=lambda snapshot: published.append(snapshot)
    )
    try:
        observer.poll_if_due()
        assert snapshots.started.wait(1.0)
        assert pending_scopes == [
            WitnessScope(
                account=_ACCOUNT,
                instrument_keys=(
                    InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT),
                ),
                as_of_generation=41,
                order_dates=(),
            )
        ]
        for _ in range(5):
            observer.poll_if_due()
        assert snapshots.calls == 1
        assert snapshots.max_active_reads == 1
        assert orders.calls == 0
        assert published == []

        snapshots.release.set()
        _poll_until(observer, lambda: bool(published))
        result = published[0]
        assert snapshots.prefetch_threads[0] != loop_thread
        assert threading.get_ident() == loop_thread
        assert result.scope == pending_scopes[0]
        assert result.tip == (7, 41)
        assert result.generation == 41
        assert result.token == 23
        # A first-request timestamp must never stand in for the balance grant.
        assert isinstance(result.first, WitnessSnapshot)
        assert isinstance(result.confirmation, WitnessSnapshot)
        assert result.first == result.confirmation
        assert result.first_balance_read_started_ms == 120
        assert result.confirmation_balance_read_started_ms == 120
        assert snapshots.calls == 2
        observer.poll_if_due()
        assert snapshots.calls == 2
    finally:
        snapshots.release.set()
        observer.close()


def test_missing_tip_invalidates_without_network_and_publishes_failure(
    store: SqliteEvidenceStore,
) -> None:
    snapshots = _Snapshots()
    published: list[HeldPositionSnapshot] = []
    observer, orders, pending_scopes = _observer(
        store,
        snapshots,
        publish=lambda snapshot: published.append(snapshot),
        tip=None,
    )
    try:
        observer.poll_if_due()
        _poll_until(observer, lambda: bool(published))
        assert pending_scopes == [None]
        assert isinstance(published[0].first, WitnessUnavailable)
        assert published[0].tip is None
        assert snapshots.calls == 0
        assert orders.calls == 0
    finally:
        observer.close()


def test_ineligible_rcl_scope_does_not_mark_cache_or_fetch_position(
    store: SqliteEvidenceStore,
) -> None:
    snapshots = _Snapshots()
    published: list[HeldPositionSnapshot] = []
    observer, orders, pending_scopes = _observer(
        store,
        snapshots,
        publish=published.append,
        eligible=lambda: False,
    )
    try:
        observer.poll_if_due()
        assert snapshots.calls == 0
        assert pending_scopes == []
        assert published == []
        assert orders.calls == 0
    finally:
        observer.close()


def test_missing_balance_grant_never_falls_back_to_first_request_or_starts_confirmation(
    store: SqliteEvidenceStore,
) -> None:
    snapshots = _Snapshots(age_origin_ms=None)
    published: list[HeldPositionSnapshot] = []
    observer, orders, _ = _observer(
        store, snapshots, publish=lambda snapshot: published.append(snapshot)
    )
    try:
        observer.poll_if_due()
        _poll_until(observer, lambda: bool(published))
        sample = published[0]
        assert isinstance(sample.first, WitnessSnapshot)
        assert sample.confirmation is None
        assert sample.first_balance_read_started_ms is None
        assert snapshots.calls == 1
        assert orders.calls == 0
    finally:
        observer.close()


def test_recovery_resume_uses_only_the_prefetched_release_snapshot(
    store: SqliteEvidenceStore,
) -> None:
    snapshots = _Snapshots()
    observed: list[tuple[str, bool, int]] = []
    loop_thread = threading.get_ident()
    observer, orders, _ = _observer(
        store,
        snapshots,
        held_interval_ms=None,
        pending_recovery=lambda: ("close-attempt",),
        resume_recovery=lambda attempt_id: observed.append(
            (
                attempt_id,
                snapshots.active is not None and snapshots.strict_required,
                threading.get_ident(),
            )
        ),
    )
    try:
        observer.poll_if_due()
        _poll_until(observer, lambda: bool(observed))
        assert observed == [("close-attempt", True, loop_thread)]
        assert len(snapshots.prefetch_threads) == 1
        assert snapshots.prefetch_threads[0] != loop_thread
        assert orders.calls == 0
        # The configured retry cadence prevents a second recovery plan on every loop pass.
        observer.poll_if_due()
        assert len(snapshots.prefetch_threads) == 1
    finally:
        observer.close()


def test_paced_held_pair_runs_before_recovery_snapshot_and_keeps_it_fresh(
    store: SqliteEvidenceStore,
) -> None:
    """The held double read costs two 2s pacer gaps; recovery must receive the final read."""
    clock = _ManualClock()
    snapshots = _PacedSnapshots(clock)
    published: list[HeldPositionSnapshot] = []
    resumed: list[tuple[str, bool, int]] = []
    loop_thread = threading.get_ident()
    observer, orders, _ = _observer(
        store,
        snapshots,
        publish=published.append,
        held_interval_ms=None,
        resume_recovery=lambda attempt_id: resumed.append(
            (
                attempt_id,
                snapshots.active is not None and snapshots.strict_required,
                threading.get_ident(),
            )
        ),
        monotonic=clock,
    )
    instrument_key = InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT)
    risk_scope = WitnessScope(
        account=_ACCOUNT,
        instrument_keys=(instrument_key,),
        as_of_generation=41,
        order_dates=(),
    )
    release_scope = WitnessScope(
        account=_ACCOUNT,
        instrument_keys=(instrument_key,),
        order_dates=(),
    )
    plan = FetchPlan(
        reads=(),
        targets=frozenset(),
        instrument=_INSTRUMENT,
        deadline_ms=10**9,
        snapshot_scope=release_scope,
        today=_TODAY,
        reproject_ids=(),
        held_position_snapshot_due=True,
        held_position_scope=risk_scope,
        held_position_generation=41,
        held_position_tip=(7, 41),
        held_position_token=23,
        recovery_attempt_ids=("close-attempt",),
    )
    try:
        result = run_fetch(
            plan,
            orders=orders,
            snapshots=snapshots,
            monotonic=clock,
            stop=lambda: False,
        )
        observer._apply(result)

        assert len(snapshots.scopes) == 3
        assert [scope.as_of_generation for scope in snapshots.scopes] == [41, 41, None]
        assert snapshots.release_age_ms == 4_000
        assert resumed == [("close-attempt", True, loop_thread)]
        assert len(published) == 1
        assert orders.calls == 0
    finally:
        observer.close()


def test_new_ack_preempts_inflight_risk_only_fetch_and_gets_worker_priority(
    store: SqliteEvidenceStore,
) -> None:
    snapshots = _CancellableSnapshots()
    published: list[HeldPositionSnapshot] = []
    observer, _unused_orders, pending_scopes = _observer(
        store,
        snapshots,
        publish=published.append,
        held_interval_ms=0,
    )
    orders = _EmptyOrders()
    observer.orders = orders
    try:
        observer.poll_if_due()
        assert snapshots.started.wait(1.0)
        active_plan = observer._runner.current_plan if observer._runner else None
        assert active_plan is not None and active_plan.risk_only

        attempt_id = "new-ack"
        store.append(
            {
                "attempt_id": attempt_id,
                "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
                "egress_result_kind": "ACK",
                "broker_execution_id": "0000098765",
                "trading_date": _TODAY,
            },
            kind="EGRESS_RESULT_CONSUMED",
            record_class="EGRESS_RESULT_CONSUMED",
        )
        store.append(
            {"send_seal": {"attempt_id": attempt_id, "outbound_quantity": "3"}},
            kind="SEND_SEALED",
            record_class="SEND_SEALED",
        )
        observer.poll_if_due()
        assert snapshots.aborted.wait(1.0), "new ACK did not cancel risk-only FETCH"
        _poll_until(observer, lambda: bool(orders.scopes))

        assert snapshots.aborted.is_set()
        assert snapshots.calls == 1
        assert published == []
        assert len(pending_scopes) == 1
        assert len(orders.scopes) == 1
        assert orders.scopes[0].attempt_ids == (attempt_id,)
        assert orders.scopes[0].order_dates == (_TODAY,)
    finally:
        snapshots.release.set()
        observer.close()


def test_completed_fetch_remains_busy_until_apply_takes_its_result() -> None:
    plan = FetchPlan(
        reads=(),
        targets=frozenset(),
        instrument=_INSTRUMENT,
        deadline_ms=1,
        snapshot_scope=None,
        today=None,
        reproject_ids=(),
    )
    runner = FetchRunner(
        lambda submitted, _stop: FetchResult(plan=submitted, reads=(), snapshot=None)
    )
    try:
        runner.submit(plan)
        assert runner._future is not None
        result = runner._future.result(timeout=1.0)
        assert not runner.busy
        assert runner.has_job
        with pytest.raises(RuntimeError, match="already in flight"):
            runner.submit(plan)
        assert runner.take_done() is result
        assert not runner.busy
    finally:
        runner.close()


@pytest.mark.parametrize(
    ("current_date", "prefetched_order_dates"),
    [(None, ()), ("20261030", ()), (_TODAY, ("20261028",))],
)
def test_required_recovery_snapshot_refuses_scope_or_date_change_without_live_fallback(
    current_date: str | None,
    prefetched_order_dates: tuple[str, ...],
) -> None:
    class _LiveWitness:
        calls = 0

        def observe(self, scope: WitnessScope) -> WitnessSnapshot:
            del scope
            self.calls += 1
            return WitnessSnapshot(observed_at_generation=None, orders=())

    scope = WitnessScope(
        account=_ACCOUNT,
        instrument_keys=(InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT),),
        order_dates=(),
    )
    live = _LiveWitness()
    witness = DeferredKisWitness(lambda: current_date)
    witness.inner = live  # type: ignore[assignment]
    prefetched_scope = WitnessScope(
        account=_ACCOUNT,
        instrument_keys=(InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT),),
        order_dates=prefetched_order_dates,
    )
    prefetched = PrefetchedSnapshot(
        key=snapshot_key(prefetched_scope),
        today=_TODAY,
        outcome=WitnessSnapshot(observed_at_generation=None, orders=()),
        read_started_ms=0,
        read_finished_ms=0,
    )
    with witness.serving_required(
        prefetched,
        expected_scope=scope,
        expected_today=_TODAY,
        max_age_ms=100,
        now_ms=lambda: 0,
    ):
        with pytest.raises(WitnessUnavailable, match="required prefetched snapshot"):
            witness.observe(scope)
    assert live.calls == 0
