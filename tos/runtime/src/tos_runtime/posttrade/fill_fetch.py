"""The fill observer's FETCH half: broker reads off the session loop's thread (issue #950).

:class:`~tos_runtime.posttrade.fill_observer.KisMockFillObserver` is split in two:

* **FETCH** (this module) — network only. One :class:`FetchPlan` (built on the loop thread from
  durable evidence) is run by :func:`run_fetch`: the ``VTTC0081R`` order reads for the planned
  dates and, when the release path will need it, the release reconciliation's broker snapshot.
  It touches no engine, no RCL, and no observer state; what it produces is a
  :class:`FetchResult`, data only.
* **APPLY** (the observer) — everything else, on the loop thread only: classifying rows, every
  observer evidence row, feeding the engine, finality, release, re-projection.

**Why the release snapshot is fetched here** (#949 review round 2 MEDIUM-1). A terminal fill fed
to the engine runs finality -> the release consumer -> ``ReconciliationService.reconcile`` ->
``witness.observe``: a balance walk plus an order walk per date, on the loop thread, with no
deadline. FETCH reads that snapshot ahead of time — when a read row looks like a full fill
(:func:`may_release`) or a finality re-run is due — and APPLY serves it to the reconciliation
(:class:`SnapshotPrefetcher.serving`). The reconciliation itself is unchanged: same scope, same
judgement, same fail-closed outcome for an unavailable read; only the instant the broker was read
moves, by at most one loop pass. **Not moved**: a reconciliation whose scope the prefetch did not
anticipate (its key or trading date differs) falls back to the live read, exactly as before #950
— bounded by ``witness_request_timeout_s`` per page, as #949 left it.

**One FETCH at a time, stopped with the session.** :class:`FetchRunner` runs at most one plan on
one worker thread. :meth:`FetchRunner.close` stops it: the in-flight read stops at its next page
(the stop flag is part of every read's deadline predicate), the worker is joined, and the result
is dropped — a FETCH in flight at shutdown never reaches APPLY.

Firewall: stdlib + ``tos_runtime.recon`` + ``tos_runtime.time`` only.
"""

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
    "OrderRowsReader",
    "PrefetchedSnapshot",
    "SnapshotPrefetcher",
    "may_release",
    "odno_key",
    "run_fetch",
    "snapshot_key",
]

#: ``(account, instrument keys, order dates)`` — what a broker snapshot depends on. The KIS
#: witness never filters by attempt id and ``as_of_generation`` is not a broker input, so two
#: scopes with the same key read the same broker state.
SnapshotKey = tuple[str, tuple[object, ...], frozenset[str]]


def snapshot_key(scope: WitnessScope) -> SnapshotKey:
    """The broker-relevant identity of ``scope`` (:data:`SnapshotKey`)."""
    return (scope.account, tuple(scope.instrument_keys), frozenset(scope.order_dates))


@dataclass(frozen=True)
class PrefetchedSnapshot:
    """A release-reconciliation snapshot read on the FETCH thread: the snapshot, or the
    :class:`~tos_runtime.recon.ports.WitnessUnavailable` the read ended in (served as the same
    raise — an unavailable read stays a hold, never a guess)."""

    key: SnapshotKey
    today: str
    outcome: WitnessSnapshot | WitnessUnavailable


class SnapshotPrefetcher(Protocol):
    """The witness side of the prefetch (compose's ``DeferredKisWitness``)."""

    def prefetch(
        self, scope: WitnessScope, *, today: str, abort: Callable[[], bool]
    ) -> PrefetchedSnapshot:
        """Read ``scope``'s snapshot under ``today`` (FETCH thread); never raises."""
        ...

    def serving(
        self, prefetched: PrefetchedSnapshot | None
    ) -> AbstractContextManager[None]:
        """While open, an ``observe`` on THIS thread whose scope matches is answered from
        ``prefetched`` instead of the network (APPLY)."""
        ...


@dataclass(frozen=True)
class FetchPlan:
    """What one FETCH reads — built on the loop thread, read-only afterwards.

    Attributes:
        reads: ``(date, scope)`` per order inquiry; ``scope.attempt_ids`` names the attempts the
            date is read for (APPLY attributes against exactly those).
        targets: ``(odno_key, date)`` of every planned attempt — :func:`may_release`'s input.
        instrument: The observer's instrument.
        deadline_ms: The order reads' shared deadline (``poll_deadline_ms`` from the plan's start,
            on the injected monotonic clock).
        snapshot_scope: The release reconciliation's scope, or ``None`` when there is no trusted
            trading date (the live read then refuses on its own, without a network call).
        today: The trusted trading date the snapshot is read under.
        reproject_ids: Attempts whose finality re-run is due — a snapshot is always fetched for
            them.
    """

    reads: tuple[tuple[str, WitnessScope], ...]
    targets: frozenset[tuple[str | None, str]]
    instrument: str
    deadline_ms: int
    snapshot_scope: WitnessScope | None
    today: str | None
    reproject_ids: tuple[str, ...]


@dataclass(frozen=True)
class FetchResult:
    """What one FETCH read: each planned date's rows or its unavailability, and the snapshot."""

    plan: FetchPlan
    reads: tuple[tuple[str, tuple[KisOrderRow, ...] | WitnessUnavailable], ...]
    snapshot: PrefetchedSnapshot | None


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
    """Canonical comparison key for a KIS ODNO: whitespace and leading zeros dropped (a single
    ``"0"`` kept); ``None`` for an absent, all-zero, or non-ASCII-digit value — a value that is
    not an order number never matches one (``tools/broker_probes/probes_order.py::odno_key``
    measured why both sides must be canonicalized)."""
    text = (raw or "").strip()
    if not text or not (text.isascii() and text.isdigit()):
        return None
    key = text.lstrip("0")
    return key or None


def may_release(plan: FetchPlan, rows: tuple[KisOrderRow, ...]) -> bool:
    """Whether ``rows`` show a planned attempt fully filled — the one observation APPLY feeds to
    the engine as ``FULL_FILL``, i.e. the one that reaches the release reconciliation. A loose
    superset is harmless (an unused snapshot); a miss only means the live read, as before #950.
    """
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


def run_fetch(
    plan: FetchPlan,
    *,
    orders: OrderRowsReader,
    snapshots: SnapshotPrefetcher | None,
    monotonic: MonotonicSource,
    stop: Callable[[], bool],
) -> FetchResult:
    """Run ``plan``'s reads. Network only: no evidence written by this function, no engine.

    Each order read gets one predicate — the plan's deadline OR ``stop`` — which the witness
    asks before every page, so a shutdown ends a walk at its next page. The snapshot read gets
    ``stop`` only: a time deadline on it would turn a slow-but-working broker into a held
    release (``witness_kis.order_rows``'s own note), which this split does not change.
    """

    def _expired() -> bool:
        return stop() or monotonic.now_ms() >= plan.deadline_ms

    reads: list[tuple[str, tuple[KisOrderRow, ...] | WitnessUnavailable]] = []
    releasing = bool(plan.reproject_ids)
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
    snapshot = None
    if (
        releasing
        and snapshots is not None
        and plan.snapshot_scope is not None
        and plan.today is not None
        and not stop()
    ):
        snapshot = snapshots.prefetch(plan.snapshot_scope, today=plan.today, abort=stop)
    return FetchResult(plan=plan, reads=tuple(reads), snapshot=snapshot)


class FetchRunner:
    """At most one FETCH in flight, on one worker thread (module docstring)."""

    def __init__(self, fetch: Callable[[FetchPlan, Callable[[], bool]], FetchResult]):
        self._fetch = fetch
        self._stop = threading.Event()
        self._executor: ThreadPoolExecutor | None = None
        self._future: Future[FetchResult] | None = None

    @property
    def busy(self) -> bool:
        """A FETCH is in flight (submitted, not yet taken)."""
        return self._future is not None and not self._future.done()

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
        self._future = self._executor.submit(self._fetch, plan, self._stop.is_set)

    def take_done(self) -> FetchResult | None:
        """The finished FETCH's result (once), or ``None`` while none is finished. A FETCH that
        raised re-raises here, on the loop thread — the observer's bookkeeping failed, and the
        loop's own rule is that such a failure propagates."""
        future = self._future
        if future is None or not future.done() or self._stop.is_set():
            return None
        self._future = None
        return future.result()

    def close(self) -> None:
        """Stop and join the worker; an in-flight result is dropped, never applied."""
        self._stop.set()
        executor, self._executor, self._future = self._executor, None, None
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)
