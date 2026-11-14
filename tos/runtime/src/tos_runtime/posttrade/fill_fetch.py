"""The fill observer's FETCH half: broker reads off the session loop's thread (issue #950)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import AbstractContextManager
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from tos_runtime.recon.ports import WitnessScope, WitnessSnapshot, WitnessUnavailable
from tos_runtime.recon.witness_kis import KisOrderRow
from tos_runtime.time.sources import MonotonicSource

__all__ = [
    "FetchPlan",
    "FetchResult",
    "FetchRunner",
    "HeldPositionSnapshot",
    "OrderRowsReader",
    "PrefetchedSnapshot",
    "SnapshotPrefetcher",
    "SnapshotRead",
    "SnapshotUse",
    "may_release",
    "odno_key",
    "run_fetch",
    "snapshot_key",
]

SnapshotKey = tuple[str, tuple[object, ...], frozenset[str]]


def snapshot_key(scope: WitnessScope) -> SnapshotKey:
    """The broker-relevant identity of ``scope`` (:data:`SnapshotKey`)."""
    return (scope.account, tuple(scope.instrument_keys), frozenset(scope.order_dates))


@dataclass(frozen=True)
class PrefetchedSnapshot:
    """A release-reconciliation snapshot read on the FETCH thread: the snapshot, or the"""

    key: SnapshotKey
    today: str
    outcome: WitnessSnapshot | WitnessUnavailable
    read_started_ms: int
    read_finished_ms: int
    first_request_ms: int | None = None


@dataclass(frozen=True)
class HeldPositionSnapshot:
    """A periodic CLOSE-position double observation read on the FETCH worker."""

    scope: WitnessScope | None
    today: str | None
    generation: int | None
    tip: tuple[int, int | None] | None
    token: int | None
    first: WitnessSnapshot | WitnessUnavailable
    confirmation: WitnessSnapshot | WitnessUnavailable | None
    first_balance_read_started_ms: int | None
    confirmation_balance_read_started_ms: int | None
    read_finished_ms: int


@dataclass(frozen=True)
class SnapshotRead:
    """What :meth:`SnapshotPrefetcher.prefetch` read, and when it started reading."""

    outcome: WitnessSnapshot | WitnessUnavailable
    first_request_ms: int | None
    age_origin_ms: int | None = None


@dataclass(frozen=True)
class SnapshotUse:
    """One reconciliation the serving side answered from a prefetched snapshot (``served``) or"""

    verdict: str
    snapshot: PrefetchedSnapshot
    age_ms: int
    max_age_ms: int
    reason: str | None = None

    def read_fields(self) -> dict[str, object]:
        """The read's evidence fields: its monotonic instants (age origin = ``read_started``,"""
        return {
            "read_started_monotonic_ms": self.snapshot.read_started_ms,
            "read_finished_monotonic_ms": self.snapshot.read_finished_ms,
            "first_request_monotonic_ms": self.snapshot.first_request_ms,
            "expiry_reason": self.reason,
        }


class SnapshotPrefetcher(Protocol):
    """The witness side of the prefetch (compose's ``DeferredKisWitness``)."""

    def prefetch(
        self, scope: WitnessScope, *, today: str, abort: Callable[[], bool]
    ) -> SnapshotRead:
        """Read ``scope``'s snapshot under ``today`` (FETCH thread); never raises."""
        ...

    def serving(
        self,
        prefetched: PrefetchedSnapshot | None,
        *,
        max_age_ms: int,
        now_ms: Callable[[], int],
    ) -> AbstractContextManager[list[SnapshotUse]]:
        """While open, an ``observe`` on THIS thread whose scope matches is answered from"""
        ...

    def serving_required(
        self,
        prefetched: PrefetchedSnapshot,
        *,
        expected_scope: WitnessScope,
        expected_today: str,
        max_age_ms: int,
        now_ms: Callable[[], int],
    ) -> AbstractContextManager[list[SnapshotUse]]:
        """Serve only this scope/date; mismatch, unknown date, or expiry must refuse rather"""
        ...


@dataclass(frozen=True)
class FetchPlan:
    """What one FETCH reads — built on the loop thread, read-only afterwards."""

    reads: tuple[tuple[str, WitnessScope], ...]
    targets: frozenset[tuple[str | None, str]]
    instrument: str
    deadline_ms: int
    snapshot_scope: WitnessScope | None
    today: str | None
    reproject_ids: tuple[str, ...]
    held_position_snapshot_due: bool = False
    held_position_scope: WitnessScope | None = None
    held_position_generation: int | None = None
    held_position_tip: tuple[int, int | None] | None = None
    held_position_token: int | None = None
    recovery_attempt_ids: tuple[str, ...] = ()
    evidence_seq_at_plan: int | None = None

    @property
    def risk_only(self) -> bool:
        """Whether the plan contains only optional CLOSE risk observation work."""
        return (
            self.held_position_snapshot_due
            and not self.reads
            and not self.reproject_ids
            and not self.recovery_attempt_ids
        )


@dataclass(frozen=True)
class FetchResult:
    """What one FETCH read: planned order rows, release snapshot, and optional CLOSE snapshot."""

    plan: FetchPlan
    reads: tuple[tuple[str, tuple[KisOrderRow, ...] | WitnessUnavailable], ...]
    snapshot: PrefetchedSnapshot | None
    held_position_snapshot: HeldPositionSnapshot | None = None


class OrderRowsReader(Protocol):
    """:meth:`~tos_runtime.recon.witness_kis.KisStockBrokerWitness.order_rows`."""

    def order_rows(
        self,
        scope: WitnessScope,
        *,
        inquiry_date: str | None = None,
        deadline_expired: Callable[[], bool] | None = None,
    ) -> tuple[str, tuple[KisOrderRow, ...]]: ...


def odno_key(raw: str | None) -> str | None:
    """Canonical comparison key for a KIS ODNO: whitespace and leading zeros dropped (a single"""
    text = (raw or "").strip()
    if not text or not (text.isascii() and text.isdigit()):
        return None
    key = text.lstrip("0")
    return key or None


def may_release(plan: FetchPlan, rows: tuple[KisOrderRow, ...]) -> bool:
    """Whether ``rows`` show a planned attempt fully filled — the one observation APPLY feeds to"""
    zero = Decimal(0)
    return any(
        (odno_key(r.odno), r.ord_dt or "") in plan.targets
        and r.pdno == plan.instrument
        and not r.cancelled
        and r.rmn_qty == zero
        and r.tot_ccld_qty is not None
        and r.tot_ccld_qty > zero
        for r in rows
    )


def _release_snapshot(
    plan: FetchPlan,
    *,
    releasing: bool,
    snapshots: SnapshotPrefetcher | None,
    monotonic: MonotonicSource,
    stop: Callable[[], bool],
) -> PrefetchedSnapshot | None:
    """Prefetch the existing release scope, retaining its established age fallback."""
    if (
        not releasing
        or snapshots is None
        or plan.snapshot_scope is None
        or plan.today is None
        or stop()
    ):
        return None
    called_ms = monotonic.now_ms()
    read = snapshots.prefetch(plan.snapshot_scope, today=plan.today, abort=stop)
    origin = (
        read.age_origin_ms if read.age_origin_ms is not None else read.first_request_ms
    )
    started = called_ms if origin is None else max(called_ms, origin)
    return PrefetchedSnapshot(
        key=snapshot_key(plan.snapshot_scope),
        today=plan.today,
        outcome=read.outcome,
        read_started_ms=started,
        read_finished_ms=monotonic.now_ms(),
        first_request_ms=read.first_request_ms,
    )


def _held_position_snapshot(
    plan: FetchPlan,
    *,
    snapshots: SnapshotPrefetcher | None,
    monotonic: MonotonicSource,
    stop: Callable[[], bool],
) -> HeldPositionSnapshot | None:
    """Read two complete risk-only observations or retain explicit failure evidence."""
    if not plan.held_position_snapshot_due:
        return None
    first: WitnessSnapshot | WitnessUnavailable
    confirmation: WitnessSnapshot | WitnessUnavailable | None = None
    first_started: int | None = None
    confirmation_started: int | None = None
    if plan.today is None:
        first = WitnessUnavailable("held-position snapshot has no trusted trading date")
    elif plan.held_position_generation is None:
        first = WitnessUnavailable(
            "held-position snapshot has no trusted RCL generation"
        )
    elif plan.held_position_scope is None:
        first = WitnessUnavailable("held-position snapshot scope is unavailable")
    elif snapshots is None:
        first = WitnessUnavailable("held-position snapshot reader is unavailable")
    elif stop():
        first = WitnessUnavailable("held-position snapshot fetch was stopped")
    else:
        first_read = snapshots.prefetch(
            plan.held_position_scope, today=plan.today, abort=stop
        )
        first = first_read.outcome
        first_started = first_read.age_origin_ms
        if (
            isinstance(first, WitnessSnapshot)
            and first.positions_complete
            and first.independent_of_evidence_store
            and first_started is not None
            and not stop()
        ):
            confirmation_read = snapshots.prefetch(
                plan.held_position_scope, today=plan.today, abort=stop
            )
            confirmation = confirmation_read.outcome
            confirmation_started = confirmation_read.age_origin_ms
    return HeldPositionSnapshot(
        scope=plan.held_position_scope,
        today=plan.today,
        generation=plan.held_position_generation,
        tip=plan.held_position_tip,
        token=plan.held_position_token,
        first=first,
        confirmation=confirmation,
        first_balance_read_started_ms=first_started,
        confirmation_balance_read_started_ms=confirmation_started,
        read_finished_ms=monotonic.now_ms(),
    )


def run_fetch(
    plan: FetchPlan,
    *,
    orders: OrderRowsReader,
    snapshots: SnapshotPrefetcher | None,
    monotonic: MonotonicSource,
    stop: Callable[[], bool],
) -> FetchResult:
    """Run ``plan``'s reads. Network only: no evidence written by this function, no engine."""

    def _expired() -> bool:
        return stop() or monotonic.now_ms() >= plan.deadline_ms

    reads: list[tuple[str, tuple[KisOrderRow, ...] | WitnessUnavailable]] = []
    releasing = bool(plan.reproject_ids or plan.recovery_attempt_ids)
    for date, scope in plan.reads:
        try:
            _date, rows = orders.order_rows(
                scope, inquiry_date=date, deadline_expired=_expired
            )
        except WitnessUnavailable as exc:
            reads.append((date, exc))
            continue
        reads.append((date, rows))
        releasing = releasing or may_release(plan, rows)
    held_position_snapshot = _held_position_snapshot(
        plan, snapshots=snapshots, monotonic=monotonic, stop=stop
    )
    snapshot = _release_snapshot(
        plan,
        releasing=releasing,
        snapshots=snapshots,
        monotonic=monotonic,
        stop=stop,
    )
    return FetchResult(
        plan=plan,
        reads=tuple(reads),
        snapshot=snapshot,
        held_position_snapshot=held_position_snapshot,
    )


class FetchRunner:
    """At most one FETCH in flight, on one worker thread (module docstring)."""

    def __init__(self, fetch: Callable[[FetchPlan, Callable[[], bool]], FetchResult]):
        self._fetch = fetch
        self._stop = threading.Event()
        self._executor: ThreadPoolExecutor | None = None
        self._future: Future[FetchResult] | None = None
        self._job_stop: threading.Event | None = None
        self._job_plan: FetchPlan | None = None
        self._job_cancelled = False

    @property
    def busy(self) -> bool:
        """A FETCH is still running; completed results wait for APPLY via :meth:`has_job`."""
        return self._future is not None and not self._future.done()

    @property
    def has_job(self) -> bool:
        """A submitted result remains untaken, even if the worker has finished."""
        return self._future is not None

    @property
    def current_plan(self) -> FetchPlan | None:
        """The submitted plan while its result is still waiting to be taken."""
        return self._job_plan

    def submit(self, plan: FetchPlan) -> None:
        """Start ``plan`` on the worker. Refused while one is in flight or after close."""
        if self._stop.is_set():
            raise RuntimeError("FetchRunner is closed")
        if self._future is not None:
            raise RuntimeError("a FETCH is already in flight")
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="tos-fill-fetch"
            )
        job_stop = threading.Event()
        self._job_stop = job_stop
        self._job_plan = plan
        self._job_cancelled = False
        self._future = self._executor.submit(
            self._fetch, plan, lambda: self._stop.is_set() or job_stop.is_set()
        )

    def cancel_risk_only(self) -> bool:
        """Cooperatively stop an obsolete risk-only read; never interrupt fill/recovery work."""
        if (
            not self.busy
            or self._future is None
            or self._job_plan is None
            or not self._job_plan.risk_only
            or self._job_stop is None
        ):
            return False
        self._job_cancelled = True
        self._job_stop.set()
        return True

    def take_done(self) -> FetchResult | None:
        """The finished FETCH's result (once), or ``None`` while none is finished. A FETCH that"""
        future = self._future
        if future is None or not future.done() or self._stop.is_set():
            return None
        self._future = None
        cancelled = self._job_cancelled
        self._job_stop = None
        self._job_plan = None
        self._job_cancelled = False
        result = future.result()
        return None if cancelled else result

    def close(self) -> None:
        """Stop and join the worker; an in-flight result is dropped, never applied."""
        self._stop.set()
        executor, self._executor, self._future = self._executor, None, None
        self._job_stop = None
        self._job_plan = None
        self._job_cancelled = False
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)
