"""The fill observer's FETCH half: broker reads off the session loop's thread (issue #950).

:class:`~tos_runtime.posttrade.fill_observer.KisMockFillObserver` is split in two:

* **FETCH** (this module) — network only. One :class:`FetchPlan` (built on the loop thread from
  durable evidence) is run by :func:`run_fetch`: the ``VTTC0081R`` order reads for the planned
  dates and, when the release path will need it, the release reconciliation's broker snapshot.
  A separately scoped stock held-position observation may also be requested by cadence, even
  when there are no ACK reads. It touches no engine, no RCL, and no observer state; what it
  produces is a :class:`FetchResult`, data only.
* **APPLY** (the observer) — everything else, on the loop thread only: classifying rows, every
  observer evidence row, feeding the engine, finality, release, re-projection.

**Why the release snapshot is fetched here** (#949 review round 2 MEDIUM-1). A terminal fill fed
to the engine runs finality -> the release consumer -> ``ReconciliationService.reconcile`` ->
``witness.observe``: a balance walk plus an order walk per date, on the loop thread, with no
deadline. FETCH reads that snapshot ahead of time — when a read row looks like a full fill
(:func:`may_release`) or a finality re-run is due — and APPLY serves it to the reconciliation
(:class:`SnapshotPrefetcher.serving`). The reconciliation itself is unchanged: same scope, same
judgement, same fail-closed outcome for an unavailable read; only the instant the broker was read
moves. **That instant is bounded** (#969 review r1 HIGH): a snapshot older than
``release_snapshot_max_age_ms`` (from its read's start) is not served — an order that appeared at
the broker since (an orphan, which must block the release) could be missing from it — so that
release HOLDS and the observer records the snapshot's real read instants and age. The first
expiry in a run of consecutive expiries schedules a fresh worker read at once; later ones wait
``finality_retry_interval_ms`` like any other finality re-run (#971 / PR #978). Expiry never
falls back to a live read on the loop. **The age starts at the balance read's first pacer
grant** (issue #970, review-979 r1 HIGH), not before: every request on the app key is paced, so
queueing in the pacer is not broker-state age, and the witness reads the closed earlier days'
order walks BEFORE the balance and today's walk last — the window covers everything that can
still change (``KisStockBrokerWitness.observe``'s read-order note; :class:`SnapshotRead`). An
expiry records whether the read's own window outran the limit (:class:`SnapshotUse`).
**Not moved**: a reconciliation whose scope the prefetch did not
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
    #: Monotonic instants the read started and finished (#969 review r1 HIGH). The age the
    #: serving side checks is measured from the START — the balance read's first pacer grant
    #: (:class:`SnapshotRead`), the earliest moment the state that can still change was read.
    read_started_ms: int
    read_finished_ms: int
    #: The grant of the read's very first request — earlier than ``read_started_ms`` by the
    #: closed days' order walks. Recorded, not aged from. ``None``: unknown (nothing sent, or
    #: built by hand).
    first_request_ms: int | None = None


@dataclass(frozen=True)
class HeldPositionSnapshot:
    """A periodic CLOSE-position double observation read on the FETCH worker.

    ``scope`` is the risk-only scope actually passed to ``prefetch`` (account and exactly one
    instrument, with no historical order dates). ``first_balance_read_started_ms`` and
    ``confirmation_balance_read_started_ms`` are the raw grants returned by
    :attr:`SnapshotRead.age_origin_ms`; unlike the release snapshot's compatibility timestamp,
    they are deliberately left ``None`` when the witness did not record a balance grant. Both
    raw samples and grants are retained for the cache's independent strict comparison.
    """

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
    """What :meth:`SnapshotPrefetcher.prefetch` read, and when it started reading.

    Attributes:
        outcome: The snapshot, or the unavailability the read ended in.
        first_request_ms: The monotonic grant instant of the read's FIRST broker request (the
            app key pacer's slot, issue #970). ``None`` when the read sent nothing.
        age_origin_ms: The grant of the BALANCE read's first request — the age origin
            (review-979 r1 HIGH). The witness reads closed earlier days first, then the balance,
            then today; everything that can still change is read from here on
            (``KisStockBrokerWitness.observe``'s read-order note). Release snapshots retain their
            compatibility fallback; CLOSE proof uses this raw field and refuses ``None``.
    """

    outcome: WitnessSnapshot | WitnessUnavailable
    first_request_ms: int | None
    age_origin_ms: int | None = None


@dataclass(frozen=True)
class SnapshotUse:
    """One reconciliation the serving side answered from a prefetched snapshot (``served``) or
    refused because it was older than the limit (``expired``) — APPLY records each."""

    verdict: str
    snapshot: PrefetchedSnapshot
    age_ms: int
    max_age_ms: int
    #: Why an ``expired`` one expired: ``read_span_exceeds_max_age`` (the read's own window,
    #: balance grant to last request, is longer than the limit — it can never be served) or
    #: ``aged_before_apply``. ``None`` when served.
    reason: str | None = None

    def read_fields(self) -> dict[str, object]:
        """The read's evidence fields: its monotonic instants (age origin = ``read_started``,
        the first request of all, the end) and the expiry reason."""
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
        """While open, an ``observe`` on THIS thread whose scope matches is answered from
        ``prefetched`` — or, past ``max_age_ms``, refused as unavailable (a HOLD, never a live
        read). Yields the list each such answer is appended to (APPLY)."""
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
        """Serve only this scope/date; mismatch, unknown date, or expiry must refuse rather
        than fall through to a live broker read on the session-loop thread."""
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
        held_position_snapshot_due: Whether this plan includes a cadence-due CLOSE snapshot
            request. It remains true when date/scope is unavailable so APPLY can invalidate an
            older proof rather than silently leave it usable.
        held_position_scope: Optional, one-instrument risk-only scope to fetch for CLOSE proof.
            It is independent of order reads and is fetched even when ``reads`` is empty.
        held_position_generation: RCL sequence captured when the held-position plan was built;
            ``None`` means the observation cannot prove a position.
        held_position_tip: Atomic ``(writer_epoch, last_seq)`` captured with the generation; the
            cache compares both to reject an epoch change even when sequence numbers match.
        held_position_token: The held-position cache's pending token, captured before FETCH; an
            older worker result cannot overwrite a newer cache request.
        recovery_attempt_ids: Close attempts whose entry discharge should be resumed from the
            release-scope snapshot; never resumed by a live read on the session loop.
        evidence_seq_at_plan: Durable evidence tail captured before planning. The loop uses it to
            preempt a risk-only FETCH if a new ACK arrives while its broker read is in flight.
    """

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
    # Release reconciliation keeps its existing fallback for snapshots whose witness did not
    # report the balance grant; that compatibility rule is not used by CLOSE risk proof.
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
        # A first failure, incomplete position list, non-independent source, or missing balance
        # grant cannot establish a comparable sample, so do not spend another paced read.
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
    """Run ``plan``'s reads. Network only: no evidence written by this function, no engine.

    Each order read gets one predicate — the plan's deadline OR ``stop`` — which the witness
    asks before every page, so a shutdown ends a walk at its next page. The snapshot read gets
    ``stop`` only: a time deadline on it would turn a slow-but-working broker into a held
    release (``witness_kis.order_rows``'s own note), which this split does not change.
    """

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
    # Do not reuse the release read for CLOSE proof: its scope may contain historical order
    # dates, while the risk proof binds one instrument and one RCL generation. Run the double
    # observation first so the release/recovery snapshot is the final broker read before APPLY;
    # otherwise two paced CLOSE reads can make that single-use snapshot stale before it is served.
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
        """The finished FETCH's result (once), or ``None`` while none is finished. A FETCH that
        raised re-raises here, on the loop thread — the observer's bookkeeping failed, and the
        loop's own rule is that such a failure propagates."""
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
