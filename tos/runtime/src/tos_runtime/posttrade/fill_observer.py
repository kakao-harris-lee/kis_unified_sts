"""Post-ACK fill observer for the KIS 모의투자 stock order path (PR-3b, rescope plan §3 M2).

``KisMockTransport`` maps an order reply to ``ACK``/``REJECT``/``UNKNOWN``/``TIMEOUT`` only; what
happens to an ACKed order afterwards is only visible on 주식일별주문체결조회 (``VTTC0081R``, GET,
mock host). This module polls that TR for the ODNOs this runtime holds an ACK for, and turns what
it reads into ``PARTIAL_FILL``/``FULL_FILL``/``CANCEL_ACK``/``UNKNOWN`` results for the engine's
normal result path (``EGRESS_RESULT`` through the durable inbox, then finality and release).

**What it tracks comes from durable evidence, not memory.** An attempt is tracked when an
``EGRESS_RESULT_CONSUMED`` row records its ``ACK`` with an ODNO and a trading date. What was already
reported is the latest recorded result for that attempt, so a restart re-derives the same picture
and an execution observed twice is reported once.

**Two separate "done"s (PR-3b review HIGH 1).** The broker side is done when a terminal result
(``FULL_FILL``/``CANCEL_ACK``/``EXPIRED``/``REJECT``) is recorded — the observer stops reading the
broker for it. The capacity side is done only when the RCL holds the attempt's release command
(:func:`~tos_runtime.posttrade.release_consumer.release_command_id`). Between the two — the process
died after the engine consumed the result but before finality ran, or reconciliation / the RCL CAS
refused the release — the observer re-runs finality from the recorded result every
``finality_retry_interval_ms`` (``reproject``), never re-feeding the fill to the engine, until the
release commits.

**Only an engine that holds the reservation is fed (found while fixing review HIGH 1).** The
engine's in-memory reservation projection is not rebuilt on boot (``engine/driver.py``: "no ledger
rebuild; Phase 5 / J3"). A result fed after a restart for a pre-restart attempt is refused as an
orphan by the live engine, but the NEXT boot's replay — which does rebuild the reservation from
the inbox — re-derives it as applied and refuses the boot (``EngineReplayDiverged``). So when the
engine does not hold this attempt's reservation, nothing is enqueued: one
``FILL_OBSERVER_ENGINE_RESERVATION_ABSENT`` row records what the broker showed, the reservation
stays held (fail closed — no release, so no double release), and a terminal observation stops
the polling. Releasing it is the ledger-rebuild work (issue #944), not this module's.

**Each ACK is read under its own trading date (review MEDIUM).** VTTC0081R takes the date, so an
ACK from an earlier day — the runtime was down across the KST date boundary — is still read, and
reconciled, under its ``ord_dt``; a read that fails is recorded, and the attempt still goes
overdue. Nothing is skipped silently.

**Attribution.** A row belongs to an attempt only when its ``odno`` equals the ACK's ODNO (both
sides canonicalized: whitespace and leading zeros dropped, ASCII digits only — measured
encodings differ, ``tools/broker_probes/probes_order.py::odno_key``) AND its ``ord_dt`` equals the
ACK's trading date (a KIS ODNO is a per-day sequence). The emitted result carries the ACK's ODNO
and date verbatim, so every receipt of the attempt names one broker order. A row that matches no
ACK this runtime recorded is recorded as ``FILL_OBSERVER_UNATTRIBUTED_ORDER`` and never enqueued —
and the release reconciliation then sees it as an orphan broker order, which blocks release.

**Fail closed.** A row that does not name this attempt's instrument (``pdno``; review HIGH 2 — the
witness refuses such a read outright as well), a row whose ``ord_qty`` is not the attempt's sealed quantity
(``SEND_SEALED``), whose quantities do not parse or do not add up (``tot_ccld_qty + rmn_qty !=
ord_qty``), a rejected quantity, two rows for one ODNO, or a filled quantity smaller than one
already reported → ``UNKNOWN`` (the engine quarantines). Never a guessed fill. No row for the ODNO
yet is not evidence of anything: nothing is emitted, and after ``overdue_after_ms`` one
``FILL_OBSERVER_OVERDUE`` row is recorded — a warning; reading continues.

**Cancels are held, not released (Codex r2 HIGH 1, scope narrowed by the operator).** Any cancel
— ``cncl_yn=Y`` on the order's row, or a separate row whose ``orgn_odno`` is the order — gets one
durable ``FILL_OBSERVER_CANCEL_UNSUPPORTED`` row with the observed rows; nothing is fed to the
engine or released, and polling stops. The cancel → non-execution proof → release path waits for a
모의 cancel probe to measure the real row shape.

GET only, mock host only: the reads go through
:meth:`~tos_runtime.recon.witness_kis.KisStockBrokerWitness.order_rows`, whose host and TR id are
sealed at load (mock ``V``-prefixed TR, the order transport's own mock host). This module never
sends anything to a broker.

**FETCH / APPLY (issue #950).** :meth:`KisMockFillObserver.poll_if_due` — the session loop's
call — never waits on the broker: the reads run on one worker thread
(:mod:`tos_runtime.posttrade.fill_fetch`, which also prefetches the release reconciliation's
broker snapshot) and everything else above runs on the loop thread when the result comes back.
:meth:`KisMockFillObserver.poll_once` runs the same steps back to back on the calling thread.

Firewall: stdlib + ``tos.engine`` + ``tos_runtime.*`` only.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from tos.engine.records import EgressResultPayload, InstrumentKey
from tos.engine.vocabulary import EgressResultKind, ResultDisposition

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.fill_fetch import (
    FetchPlan,
    FetchResult,
    FetchRunner,
    OrderRowsReader,
    SnapshotPrefetcher,
    SnapshotUse,
    odno_key,
    run_fetch,
)
from tos_runtime.posttrade.fill_observer_config import (
    FILL_OBSERVER_CONFIG_NAME,
    FillObserverConfig,
    FillObserverConfigError,
    load_fill_observer_config,
)
from tos_runtime.recon.evidence_reader import SqliteEvidenceReceiptReader
from tos_runtime.recon.ports import WitnessScope, WitnessUnavailable
from tos_runtime.recon.witness_kis import KisOrderRow
from tos_runtime.time.sources import MonotonicSource

__all__ = [
    "FILL_OBSERVED_KIND",
    "FILL_OBSERVER_CANCEL_UNSUPPORTED_KIND",
    "FILL_OBSERVER_CONFIG_NAME",
    "FILL_OBSERVER_ACK_UNTRACKABLE_KIND",
    "FILL_OBSERVER_ENGINE_RESERVATION_ABSENT_KIND",
    "FILL_OBSERVER_FINALITY_STUCK_KIND",
    "FILL_OBSERVER_OVERDUE_KIND",
    "FILL_OBSERVER_READ_FAILED_KIND",
    "FILL_OBSERVER_RELEASE_SNAPSHOT_KIND",
    "FILL_OBSERVER_UNATTRIBUTED_KIND",
    "FillObserverConfig",
    "FillObserverConfigError",
    "FillPollReport",
    "KisMockFillObserver",
    "load_fill_observer_config",
    "odno_key",
]

FILL_OBSERVED_KIND = "FILL_OBSERVED"
FILL_OBSERVER_UNATTRIBUTED_KIND = "FILL_OBSERVER_UNATTRIBUTED_ORDER"
FILL_OBSERVER_READ_FAILED_KIND = "FILL_OBSERVER_READ_FAILED"
FILL_OBSERVER_OVERDUE_KIND = "FILL_OBSERVER_OVERDUE"
FILL_OBSERVER_ENGINE_RESERVATION_ABSENT_KIND = "FILL_OBSERVER_ENGINE_RESERVATION_ABSENT"
FILL_OBSERVER_ACK_UNTRACKABLE_KIND = "FILL_OBSERVER_ACK_UNTRACKABLE"
FILL_OBSERVER_FINALITY_STUCK_KIND = "FILL_OBSERVER_FINALITY_STUCK"
FILL_OBSERVER_CANCEL_UNSUPPORTED_KIND = "FILL_OBSERVER_CANCEL_UNSUPPORTED"
#: One per reconciliation answered from (``served``) or refused by the age limit of
#: (``expired``) a prefetched release snapshot — its real read instants and age (#969 r1 HIGH).
FILL_OBSERVER_RELEASE_SNAPSHOT_KIND = "FILL_OBSERVER_RELEASE_SNAPSHOT"

#: Classifier reasons that are a cancel (Codex r2 HIGH 1, operator-narrowed scope): an unfilled
#: cancel, a cancel after a partial fill, and a separate row whose ``orgn_odno`` points at the
#: order (how a KIS cancel/modify most likely arrives — unmeasured on 모의). The cancel →
#: non-execution proof → release path is NOT built in PR-3b: such an attempt gets one durable
#: ``FILL_OBSERVER_CANCEL_UNSUPPORTED`` hold with the observed rows — nothing is fed to the engine,
#: nothing released, no retry — until a 모의 cancel probe measures the real row shape (issue #948).
_CANCEL_REASONS = frozenset(
    {"cancelled_unfilled", "cancelled_after_fill", "derived_order_row"}
)

#: Release hold reasons a finality re-run cannot change (PR-3b r2 claim 1): the re-run stops and
#: one ``FILL_OBSERVER_FINALITY_STUCK`` row names the reason. Every other hold — reconciliation
#: unavailable or not corroborated, an RCL CAS/state refusal — is retried until it commits.
_PERMANENT_HOLD_REASONS = frozenset(
    {
        "NO_WITNESS",
        "PROOF_NOT_RELOADED",
        "NON_EXECUTION_PROOF_UNPRODUCIBLE",
        "PROOF_NOT_TRANSFERABLE",
        "PROOF_NOT_CURRENT",
        "NO_RESERVATION",
    }
)

_RESULT_KINDS = ("EGRESS_RESULT_CONSUMED", "RESULT_UNMATCHED")
_TERMINAL_KINDS = frozenset(
    {
        EgressResultKind.FULL_FILL,
        EgressResultKind.CANCEL_ACK,
        EgressResultKind.EXPIRED,
        EgressResultKind.REJECT,
    }
)


#: Feeds one result into the engine and returns its disposition (compose supplies it).
ResultSink = Callable[[EgressResultPayload], "ResultDisposition | None"]
#: Re-runs finality for an already-recorded terminal result; ``True`` iff the RCL committed.
Reprojector = Callable[[EgressResultPayload], "bool | None"]
#: Whether the RCL holds ``attempt_id``'s release command.
ReleaseCommitted = Callable[[str], bool]
#: Whether the live engine holds ``attempt_id``'s reservation (module docstring).
EngineHolds = Callable[[str], bool]
#: Today's trusted KST trading date (``YYYYMMDD``), or ``None`` when untrusted.
TradingDate = Callable[[], "str | None"]


@dataclass
class _Tracked:
    """One ACKed attempt as durable evidence describes it."""

    attempt_id: str
    instrument_key: InstrumentKey
    odno: str
    trading_date: str
    last_kind: EgressResultKind = EgressResultKind.ACK
    last_filled: Decimal | None = None
    last_remaining: Decimal | None = None
    max_filled: Decimal = Decimal("0")
    terminal: bool = False
    #: The RCL holds this attempt's release command (capacity side done).
    released: bool = False
    #: A finality re-run hit a permanent hold; recorded once, never re-run again.
    stuck: bool = False
    #: Terminal by a HOLD, not by an engine receipt — the engine held no reservation for it, or
    #: the broker showed a cancel — so never re-projected (there is no receipt to project from).
    held_terminal: bool = False
    #: ``(kind, filled, remaining)`` already recorded as ``ENGINE_RESERVATION_ABSENT``.
    absent_signatures: set[tuple[str, str | None, str | None]] = field(
        default_factory=set
    )
    #: ``SEND_SEALED.send_seal.outbound_quantity`` — what was actually put on the wire.
    sealed_quantity: Decimal | None = None


@dataclass(frozen=True)
class FillPollReport:
    """What one :meth:`KisMockFillObserver.poll_once` did."""

    polled: bool
    emitted: tuple[tuple[str, EgressResultKind, ResultDisposition | None], ...] = ()
    unattributed: tuple[str, ...] = ()
    read_failed: bool = False
    #: ``(attempt_id, rcl_released)`` for every finality re-run this poll made.
    reprojected: tuple[tuple[str, bool | None], ...] = ()
    #: ``(attempt_id, kind)`` observed but NOT fed: the engine holds no such reservation.
    held: tuple[tuple[str, EgressResultKind], ...] = ()


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


@dataclass
class KisMockFillObserver:
    """Polls ``VTTC0081R`` for ACKed ODNOs and feeds what it reads to the engine (module
    docstring)."""

    config: FillObserverConfig
    orders: OrderRowsReader
    evidence_store: SqliteEvidenceStore
    result_sink: ResultSink
    reproject: Reprojector
    release_committed: ReleaseCommitted
    engine_holds: EngineHolds
    today: TradingDate
    monotonic: MonotonicSource
    account: str
    instrument: str
    #: The release reconciliation's snapshot prefetch (``fill_fetch`` module docstring);
    #: ``None`` = no prefetch, the release path reads the broker live.
    snapshots: SnapshotPrefetcher | None = None
    _last_poll_ms: int | None = field(default=None, init=False)
    _last_reproject_ms: dict[str, int] = field(default_factory=dict, init=False)
    _untrackable_recorded: set[str] = field(default_factory=set, init=False)
    _last_prior_day_read_ms: dict[str, int] = field(default_factory=dict, init=False)
    _first_pending_ms: dict[str, int] = field(default_factory=dict, init=False)
    _overdue_recorded: set[str] = field(default_factory=set, init=False)
    _last_read_failed: bool = field(default=False, init=False)
    _runner: FetchRunner | None = field(default=None, init=False)
    _closed: bool = field(default=False, init=False)
    #: An expired release snapshot was refused: the next plan re-runs finality at once, with a
    #: fresh worker read, instead of after ``finality_retry_interval_ms``.
    _reread_now: bool = field(default=False, init=False)

    # -- entry points --------------------------------------------------------------------

    def poll_if_due(self) -> FillPollReport:
        """The session loop's call (issue #950): never waits on the broker.

        Per pass, in order: a FETCH that has finished is APPLIED here, on this (the loop's)
        thread, and its report returned; a FETCH still in flight means nothing more this pass;
        otherwise, once ``poll_interval_ms`` has passed since the last poll, the next
        :class:`~tos_runtime.posttrade.fill_fetch.FetchPlan` is built from durable evidence and
        handed to the FETCH worker. Only the broker reads leave this thread — every evidence
        row, every engine call, finality and release stay on it. After :meth:`close` this does
        nothing at all.
        """
        if self._closed:
            return FillPollReport(polled=False)
        if self._runner is None:
            self._runner = FetchRunner(self._fetch)
        done = self._runner.take_done()
        if done is not None:
            return self._apply(done)
        if self._runner.busy:
            return FillPollReport(polled=False)
        now = self.monotonic.now_ms()
        if (
            self._last_poll_ms is not None
            and now - self._last_poll_ms < self.config.poll_interval_ms
        ):
            return FillPollReport(polled=False)
        plan = self._plan()
        if plan is not None:
            self._runner.submit(plan)
        return FillPollReport(polled=False)

    def poll_once(self) -> FillPollReport:
        """One whole pass on the CALLING thread: plan, FETCH, APPLY — the same three steps
        :meth:`poll_if_due` spreads over two threads, run back to back. No GET at all when no
        ACKed attempt is outstanding on the broker side and no finality re-run is due.

        **The read phase is bounded by ``poll_deadline_ms``** (#949 review HIGH). The deadline
        is fixed when the plan is built and handed to every order read; the WITNESS asks it
        before each page of each date's walk — page 0 included, so a date whose turn comes too
        late costs nothing. Once it is past, nothing further is read and whatever was not read
        is ``WitnessUnavailable`` — recorded once, fail-closed, retried at the next due poll. It
        can never turn into a partial row list. A request already in flight is bounded by
        ``witness_request_timeout_s``.
        """
        plan = self._plan()
        if plan is None:
            return FillPollReport(polled=False)
        return self._apply(self._fetch(plan, lambda: False))

    def close(self) -> None:
        """Stop the FETCH worker with the session (issue #950): the in-flight read stops at its
        next page, the worker is joined, and its result is dropped — never applied. Idempotent;
        :meth:`poll_if_due` is a no-op afterwards."""
        self._closed = True
        if self._runner is not None:
            self._runner.close()

    # -- plan (loop thread) / FETCH (worker) / APPLY (loop thread) ------------------------

    def _plan(self) -> FetchPlan | None:
        """What the next FETCH reads, from durable evidence: the dates of attempts still open on
        the broker side, plus the finality re-runs that are due. ``None`` when there is neither.
        """
        tracked = self._tracked_attempts()
        reproject_ids = self._due_reprojects(tracked)
        pending = [t for t in tracked.values() if not t.terminal and self._due(t)]
        if not pending and not reproject_ids:
            return None
        now = self.monotonic.now_ms()
        if pending:
            self._last_poll_ms = now
        instrument_key = InstrumentKey(account=self.account, instrument=self.instrument)
        reads = tuple(
            (
                date,
                WitnessScope(
                    account=self.account,
                    instrument_keys=(instrument_key,),
                    attempt_ids=tuple(
                        t.attempt_id for t in pending if t.trading_date == date
                    ),
                    order_dates=(date,),
                ),
            )
            for date in sorted({t.trading_date for t in pending})
        )
        today = self.today()
        return FetchPlan(
            reads=reads,
            targets=frozenset((odno_key(t.odno), t.trading_date) for t in pending),
            instrument=self.instrument,
            deadline_ms=now + self.config.poll_deadline_ms,
            snapshot_scope=None if today is None else self._release_scope(),
            today=today,
            reproject_ids=reproject_ids,
        )

    def _release_scope(self) -> WitnessScope:
        """The scope the release consumer's reconciliation will ask the witness for
        (``release_consumer._reconcile``: this account/instrument, every recorded receipt's
        trading date) — what the snapshot is prefetched under. A scope that turns out different
        is not served; the live read answers it (``fill_fetch`` module docstring)."""
        instrument_key = InstrumentKey(account=self.account, instrument=self.instrument)
        try:
            receipts = SqliteEvidenceReceiptReader(self.evidence_store).receipts(
                WitnessScope(account=self.account, instrument_keys=(instrument_key,))
            )
        except WitnessUnavailable:
            receipts = ()
        dates = {r.trading_date for r in receipts if r.trading_date is not None}
        return WitnessScope(
            account=self.account,
            instrument_keys=(instrument_key,),
            order_dates=tuple(sorted(dates)),
        )

    def _fetch(self, plan: FetchPlan, stop: Callable[[], bool]) -> FetchResult:
        """FETCH: :func:`~tos_runtime.posttrade.fill_fetch.run_fetch` over this observer's
        witness — network only, no observer state touched."""
        return run_fetch(
            plan,
            orders=self.orders,
            snapshots=self.snapshots,
            monotonic=self.monotonic,
            stop=stop,
        )

    def _apply(self, result: FetchResult) -> FillPollReport:
        """APPLY one FETCH's result, on the calling (loop) thread. The durable picture is
        re-derived first, so an attempt that turned terminal since the plan is left alone. The
        prefetched snapshot is served to every reconciliation this APPLY triggers."""
        tracked = self._tracked_attempts()
        emitted: list[tuple[str, EgressResultKind, ResultDisposition | None]] = []
        held: list[tuple[str, EgressResultKind]] = []
        unattributed: list[str] = []
        read_failed = False
        uses: list[SnapshotUse] = []
        serving = (
            self.snapshots.serving(
                result.snapshot,
                max_age_ms=self.config.release_snapshot_max_age_ms,
                now_ms=self.monotonic.now_ms,
            )
            if self.snapshots is not None
            else nullcontext(uses)
        )
        with serving as uses:
            reprojected = self._reproject_unreleased(tracked, result.plan.reproject_ids)
            planned = dict(result.plan.reads)
            for date, outcome in result.reads:
                on_date = [
                    tracked[a]
                    for a in planned[date].attempt_ids
                    if a in tracked and not tracked[a].terminal
                ]
                if isinstance(outcome, WitnessUnavailable):
                    self._read_failed(date, on_date, outcome)
                    read_failed = True
                    continue
                unattributed.extend(self._flag_unattributed(outcome, tracked))
                emitted.extend(self._emit(on_date, outcome, held))
        self._record_snapshot_uses(uses)
        if result.reads and not read_failed:
            self._last_read_failed = False
        return FillPollReport(
            polled=bool(result.reads),
            emitted=tuple(emitted),
            unattributed=tuple(unattributed),
            read_failed=read_failed,
            reprojected=reprojected,
            held=tuple(held),
        )

    def _record_snapshot_uses(self, uses: list[SnapshotUse]) -> None:
        """One row per reconciliation the prefetched snapshot answered or was refused for, with
        the read's real monotonic instants and its age; an expiry schedules a fresh read.
        """
        for use in uses:
            self._record(
                FILL_OBSERVER_RELEASE_SNAPSHOT_KIND,
                {
                    "verdict": use.verdict,
                    "read_started_monotonic_ms": use.snapshot.read_started_ms,
                    "read_finished_monotonic_ms": use.snapshot.read_finished_ms,
                    "age_ms": use.age_ms,
                    "max_age_ms": use.max_age_ms,
                    "trading_date": use.snapshot.today,
                },
            )
            if use.verdict == "expired":
                self._reread_now = True

    def _due(self, attempt: _Tracked) -> bool:
        """Today's ACKs are read every poll. An unresolved ACK from an EARLIER trading day is
        re-read under its own date at ``prior_day_poll_interval_ms`` (Codex r2 MEDIUM): an
        overdue row is a warning, not an end — the attempt is only done on a terminal broker
        result (or a recorded hold)."""
        today = self.today()
        if today is None or attempt.trading_date >= today:
            return True
        now = self.monotonic.now_ms()
        last = self._last_prior_day_read_ms.get(attempt.attempt_id)
        if last is not None and now - last < self.config.prior_day_poll_interval_ms:
            return False
        self._last_prior_day_read_ms[attempt.attempt_id] = now
        return True

    def _read_failed(
        self, date: str, attempts: list[_Tracked], exc: WitnessUnavailable
    ) -> None:
        """Record a failed read once per failure streak — and still run the overdue check: a
        read that keeps failing must surface, never go quiet."""
        if not self._last_read_failed:
            self._record(
                FILL_OBSERVER_READ_FAILED_KIND,
                {"inquiry_date": date, "reason": str(exc)[:200]},
            )
        self._last_read_failed = True
        for attempt in attempts:
            self._check_overdue(attempt)

    def _emit(
        self,
        attempts: list[_Tracked],
        rows: tuple[KisOrderRow, ...],
        held: list[tuple[str, EgressResultKind]],
    ) -> list[tuple[str, EgressResultKind, ResultDisposition | None]]:
        emitted = []
        for attempt in attempts:
            payload, reason = self._classify(attempt, rows)
            if payload is None:
                self._check_overdue(attempt)
                continue
            if reason in _CANCEL_REASONS:
                self._hold_cancel(attempt, rows, reason)
                held.append((attempt.attempt_id, payload.kind))
                continue
            if not self.engine_holds(attempt.attempt_id):
                self._hold_absent(attempt, payload, reason)
                held.append((attempt.attempt_id, payload.kind))
                continue
            self._record(
                FILL_OBSERVED_KIND,
                {
                    "attempt_id": attempt.attempt_id,
                    "broker_execution_id": attempt.odno,
                    "trading_date": attempt.trading_date,
                    "kind": payload.kind.value,
                    "filled_quantity": _text(payload.filled_quantity),
                    "remaining_quantity": _text(payload.remaining_quantity),
                    "reason": reason,
                },
            )
            if payload.kind in _TERMINAL_KINDS:
                # The sink runs finality right now; the retry clock starts here, not at zero.
                self._last_reproject_ms[attempt.attempt_id] = self.monotonic.now_ms()
            disposition = self.result_sink(payload)
            emitted.append((attempt.attempt_id, payload.kind, disposition))
        return emitted

    def _hold_cancel(
        self, attempt: _Tracked, rows: tuple[KisOrderRow, ...], reason: str
    ) -> None:
        """One durable ``FILL_OBSERVER_CANCEL_UNSUPPORTED`` hold with what the broker showed
        (the ``_CANCEL_REASONS`` note): the reservation stays held, polling stops."""
        key = odno_key(attempt.odno)
        observed = [
            {
                "odno": r.odno,
                "orgn_odno": r.orgn_odno,
                "ord_dt": r.ord_dt,
                "ord_qty": _text(r.ord_qty),
                "tot_ccld_qty": _text(r.tot_ccld_qty),
                "rmn_qty": _text(r.rmn_qty),
                "rjct_qty": _text(r.rjct_qty),
                "cancelled": r.cancelled,
            }
            for r in rows
            if r.ord_dt == attempt.trading_date
            and key in (odno_key(r.odno), odno_key(r.orgn_odno))
        ]
        self._record(
            FILL_OBSERVER_CANCEL_UNSUPPORTED_KIND,
            {
                "attempt_id": attempt.attempt_id,
                "broker_execution_id": attempt.odno,
                "trading_date": attempt.trading_date,
                "reason": reason,
                "observed_rows": observed,
            },
        )
        attempt.terminal = True
        attempt.held_terminal = True

    def _hold_absent(
        self, attempt: _Tracked, payload: EgressResultPayload, reason: str
    ) -> None:
        """Record — once per distinct observation — what the broker showed for an attempt the
        engine does not hold (module docstring). Nothing is enqueued, nothing released.
        """
        signature = (
            payload.kind.value,
            _text(payload.filled_quantity),
            _text(payload.remaining_quantity),
        )
        if signature in attempt.absent_signatures:
            return
        self._record(
            FILL_OBSERVER_ENGINE_RESERVATION_ABSENT_KIND,
            {
                "attempt_id": attempt.attempt_id,
                "broker_execution_id": attempt.odno,
                "trading_date": attempt.trading_date,
                "kind": signature[0],
                "filled_quantity": signature[1],
                "remaining_quantity": signature[2],
                "reason": reason,
            },
        )
        attempt.absent_signatures.add(signature)

    def _due_reprojects(self, tracked: dict[str, _Tracked]) -> tuple[str, ...]:
        """Attempts whose terminal result is recorded but whose release the RCL does not hold
        yet, and whose ``finality_retry_interval_ms`` has passed (module docstring "Two
        separate 'done's"). Their clock starts at planning, so a FETCH in flight is not
        re-planned for them."""
        now = self.monotonic.now_ms()
        reread_now, self._reread_now = self._reread_now, False
        due = []
        for attempt in tracked.values():
            if not _reprojectable(attempt):
                continue
            last = self._last_reproject_ms.get(attempt.attempt_id)
            if (
                not reread_now
                and last is not None
                and now - last < self.config.finality_retry_interval_ms
            ):
                continue
            self._last_reproject_ms[attempt.attempt_id] = now
            due.append(attempt.attempt_id)
        return tuple(due)

    def _reproject_unreleased(
        self, tracked: dict[str, _Tracked], attempt_ids: tuple[str, ...]
    ) -> tuple[tuple[str, bool | None], ...]:
        """APPLY: re-run finality for the planned attempts that still need it."""
        done = []
        for attempt_id in attempt_ids:
            attempt = tracked.get(attempt_id)
            if attempt is None or not _reprojectable(attempt):
                continue
            payload = self._payload(
                attempt, attempt.last_kind, attempt.last_filled, attempt.last_remaining
            )
            released = self.reproject(payload)
            done.append((attempt.attempt_id, released))
            if not released:
                self._stop_if_permanent(attempt)
        return tuple(done)

    def _stop_if_permanent(self, attempt: _Tracked) -> None:
        """r2 claim 1: never re-run forever on a hold no re-run can change."""
        row = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = 'CAPACITY_RELEASE_HELD' "
            "AND payload_json LIKE ? ORDER BY seq DESC LIMIT 1",
            (f'%"{attempt.attempt_id}"%',),
        ).fetchone()
        reason = None if row is None else json.loads(row[0])["payload"].get("reason")
        if reason in _PERMANENT_HOLD_REASONS:
            self._record(
                FILL_OBSERVER_FINALITY_STUCK_KIND,
                {
                    "attempt_id": attempt.attempt_id,
                    "broker_execution_id": attempt.odno,
                    "hold_reason": reason,
                },
            )
            attempt.stuck = True

    # -- durable picture -------------------------------------------------------------------

    def _tracked_attempts(self) -> dict[str, _Tracked]:
        placeholders = ",".join("?" for _ in _RESULT_KINDS)
        rows = self.evidence_store.connection.execute(
            f"SELECT kind, payload_json FROM entries WHERE kind IN ({placeholders}) "
            "ORDER BY seq ASC",
            _RESULT_KINDS,
        ).fetchall()
        tracked: dict[str, _Tracked] = {}
        for evidence_kind, payload_json in rows:
            row = json.loads(payload_json).get("payload", {})
            key = row.get("instrument_key") or {}
            if key.get("account") != self.account or key.get("instrument") != (
                self.instrument
            ):
                continue
            attempt_id = row.get("attempt_id")
            try:
                kind = EgressResultKind(row.get("egress_result_kind"))
            except ValueError:
                continue
            if not isinstance(attempt_id, str):
                continue
            if attempt_id not in tracked:
                if (
                    evidence_kind == "EGRESS_RESULT_CONSUMED"
                    and kind is EgressResultKind.ACK
                    and isinstance(row.get("broker_execution_id"), str)
                    and isinstance(row.get("trading_date"), str)
                    and self._trackable(attempt_id, row["broker_execution_id"])
                ):
                    tracked[attempt_id] = _Tracked(
                        attempt_id=attempt_id,
                        instrument_key=InstrumentKey(
                            account=self.account, instrument=self.instrument
                        ),
                        odno=row["broker_execution_id"],
                        trading_date=row["trading_date"],
                    )
                continue
            attempt = tracked[attempt_id]
            filled = _decimal(row.get("filled_quantity"))
            attempt.last_kind = kind
            attempt.last_filled = filled
            attempt.last_remaining = _decimal(row.get("remaining_quantity"))
            if filled is not None and filled > attempt.max_filled:
                attempt.max_filled = filled
            if kind in _TERMINAL_KINDS:
                attempt.terminal = True
        for attempt_id, quantity in self._sealed_quantities().items():
            if attempt_id in tracked:
                tracked[attempt_id].sealed_quantity = quantity
        self._apply_absent_rows(tracked)
        stuck = {
            str(json.loads(row[0]).get("payload", {}).get("attempt_id"))
            for row in self.evidence_store.connection.execute(
                "SELECT payload_json FROM entries WHERE kind = ?",
                (FILL_OBSERVER_FINALITY_STUCK_KIND,),
            )
        }
        for attempt in tracked.values():
            attempt.stuck = attempt.attempt_id in stuck
            if attempt.terminal:
                attempt.released = self.release_committed(attempt.attempt_id)
        return tracked

    def _trackable(self, attempt_id: str, odno: str) -> bool:
        """An ACK whose ODNO has no usable digits (``odno_key`` is ``None`` — e.g. all zeros)
        would match every row that also has none (Claude review LOW 3). It is never tracked;
        one ``FILL_OBSERVER_ACK_UNTRACKABLE`` row says so, so the reservation's hold is visible.
        """
        if odno_key(odno) is not None:
            return True
        if attempt_id not in self._untrackable_recorded:
            already = self.evidence_store.connection.execute(
                "SELECT COUNT(*) FROM entries WHERE kind = ? AND payload_json LIKE ?",
                (FILL_OBSERVER_ACK_UNTRACKABLE_KIND, f'%"{attempt_id}"%'),
            ).fetchone()[0]
            if not already:
                self._record(
                    FILL_OBSERVER_ACK_UNTRACKABLE_KIND,
                    {"attempt_id": attempt_id, "broker_execution_id": odno},
                )
            self._untrackable_recorded.add(attempt_id)
        return False

    def _apply_absent_rows(self, tracked: dict[str, _Tracked]) -> None:
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ?",
            (FILL_OBSERVER_ENGINE_RESERVATION_ABSENT_KIND,),
        ).fetchall()
        for (payload_json,) in rows:
            row = json.loads(payload_json).get("payload", {})
            attempt = tracked.get(str(row.get("attempt_id")))
            if attempt is None:
                continue
            attempt.absent_signatures.add(
                (
                    str(row.get("kind")),
                    row.get("filled_quantity"),
                    row.get("remaining_quantity"),
                )
            )
            if row.get("kind") in {k.value for k in _TERMINAL_KINDS} and not (
                attempt.terminal
            ):
                attempt.terminal = True
                attempt.held_terminal = True
        for (payload_json,) in self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ?",
            (FILL_OBSERVER_CANCEL_UNSUPPORTED_KIND,),
        ):
            attempt = tracked.get(
                str(json.loads(payload_json).get("payload", {}).get("attempt_id"))
            )
            if attempt is not None and not attempt.released:
                attempt.terminal = True
                attempt.held_terminal = True

    def _sealed_quantities(self) -> dict[str, Decimal | None]:
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = 'SEND_SEALED'"
        ).fetchall()
        sealed: dict[str, Decimal | None] = {}
        for (payload_json,) in rows:
            seal = json.loads(payload_json).get("payload", {}).get("send_seal") or {}
            attempt_id = seal.get("attempt_id")
            if isinstance(attempt_id, str):
                sealed[attempt_id] = _decimal(seal.get("outbound_quantity"))
        return sealed

    def _flag_unattributed(
        self, rows: tuple[KisOrderRow, ...], tracked: dict[str, _Tracked]
    ) -> tuple[str, ...]:
        known = {(odno_key(t.odno), t.trading_date) for t in tracked.values()}
        already = self._recorded_unattributed()
        flagged = []
        for row in rows:
            identity = (odno_key(row.odno), row.ord_dt)
            if identity in known or (odno_key(row.orgn_odno), row.ord_dt) in known:
                continue
            label = f"{row.odno}@{row.ord_dt}"
            if label not in already:
                self._record(
                    FILL_OBSERVER_UNATTRIBUTED_KIND,
                    {
                        "broker_execution_id": row.odno,
                        "order_date": row.ord_dt,
                        "instrument": row.pdno,
                        "tot_ccld_qty": _text(row.tot_ccld_qty),
                    },
                )
                already.add(label)
            flagged.append(label)
        return tuple(flagged)

    def _recorded_unattributed(self) -> set[str]:
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ?",
            (FILL_OBSERVER_UNATTRIBUTED_KIND,),
        ).fetchall()
        labels = set()
        for (payload_json,) in rows:
            row = json.loads(payload_json).get("payload", {})
            labels.add(f"{row.get('broker_execution_id')}@{row.get('order_date')}")
        return labels

    # -- one attempt -------------------------------------------------------------------

    def _classify(
        self, attempt: _Tracked, rows: tuple[KisOrderRow, ...]
    ) -> tuple[EgressResultPayload | None, str]:
        """The result to emit for ``attempt``, or ``None`` (nothing new / not visible yet)."""
        key = odno_key(attempt.odno)
        mine = [
            r
            for r in rows
            if odno_key(r.odno) == key and r.ord_dt == attempt.trading_date
        ]
        derived = [
            r
            for r in rows
            if odno_key(r.orgn_odno) == key and r.ord_dt == attempt.trading_date
        ]
        if not mine and not derived:
            return None, "not_visible"
        cancel_reason = self._cancel_reason(mine, derived)
        if cancel_reason is not None:
            # Codex r3 MEDIUM: an attributed cancel is decided FIRST — before the ambiguity
            # check and before the UNKNOWN de-duplication, either of which used to swallow it
            # (a derived-only cancel read as "ambiguous"; a cancel after an earlier UNKNOWN
            # produced no payload at all, so no hold was ever recorded).
            return self._cancel_marker(attempt), cancel_reason
        if len(mine) != 1:
            return self._unknown(attempt, "ambiguous_rows")
        if mine[0].pdno != self.instrument:
            # Review HIGH 2: the ODNO and date say "ours", the instrument does not — a row for
            # another symbol (or naming none) never proves this attempt's fill.
            return self._unknown(attempt, "instrument_mismatch")
        if (
            attempt.sealed_quantity is None
            or mine[0].ord_qty != attempt.sealed_quantity
        ):
            # The row's 주문수량 must be what this attempt sealed and sent — otherwise it is not
            # this order as we know it, whatever its number says.
            return self._unknown(attempt, "ordered_quantity_mismatch")
        kind, filled, remaining, reason = _fill_state(mine[0])
        if kind is None:
            return None, reason  # still working, nothing executed yet
        if kind is EgressResultKind.UNKNOWN:
            return self._unknown(attempt, reason)
        if filled is not None and filled < attempt.max_filled:
            return self._unknown(attempt, "fill_regressed")
        if (kind, filled, remaining) == (
            attempt.last_kind,
            attempt.last_filled,
            attempt.last_remaining,
        ):
            return None, "already_reported"
        return self._payload(attempt, kind, filled, remaining), reason

    def _cancel_reason(
        self, mine: list[KisOrderRow], derived: list[KisOrderRow]
    ) -> str | None:
        """Which ``_CANCEL_REASONS`` member the attributed rows show, or ``None``. Only rows
        naming this attempt's instrument count — a row for another symbol is never a cancel of
        this order (it stays the instrument-mismatch path)."""
        ours = [r for r in mine if r.pdno == self.instrument]
        cancelled = [r for r in ours if r.cancelled]
        if any(r.pdno == self.instrument for r in derived):
            return "derived_order_row"
        if not cancelled:
            return None
        filled = [r.tot_ccld_qty for r in cancelled]
        if all(q is not None and q == 0 for q in filled):
            return "cancelled_unfilled"
        return "cancelled_after_fill"

    def _cancel_marker(self, attempt: _Tracked) -> EgressResultPayload:
        """A ``CANCEL_ACK``-shaped marker the emit step routes to the cancel hold — it is never
        fed to the engine."""
        return self._payload(attempt, EgressResultKind.CANCEL_ACK, None, None)

    def _unknown(
        self, attempt: _Tracked, reason: str
    ) -> tuple[EgressResultPayload | None, str]:
        if attempt.last_kind is EgressResultKind.UNKNOWN:
            return None, "already_reported"
        return self._payload(attempt, EgressResultKind.UNKNOWN, None, None), reason

    @staticmethod
    def _payload(
        attempt: _Tracked,
        kind: EgressResultKind,
        filled: Decimal | None,
        remaining: Decimal | None,
    ) -> EgressResultPayload:
        return EgressResultPayload(
            instrument_key=attempt.instrument_key,
            attempt_id=attempt.attempt_id,
            kind=kind,
            filled_quantity=filled,
            remaining_quantity=remaining,
            broker_execution_id=attempt.odno,
            trading_date=attempt.trading_date,
        )

    def _check_overdue(self, attempt: _Tracked) -> None:
        """One ``FILL_OBSERVER_OVERDUE`` row per attempt, ever: the wait clock is process-local,
        the "already recorded" check is durable."""
        now = self.monotonic.now_ms()
        first = self._first_pending_ms.setdefault(attempt.attempt_id, now)
        if now - first < self.config.overdue_after_ms:
            return
        if attempt.attempt_id not in self._overdue_recorded:
            self._overdue_recorded |= self._recorded_overdue()
        if attempt.attempt_id not in self._overdue_recorded:
            self._record(
                FILL_OBSERVER_OVERDUE_KIND,
                {
                    "attempt_id": attempt.attempt_id,
                    "broker_execution_id": attempt.odno,
                    "trading_date": attempt.trading_date,
                    "waited_ms": now - first,
                },
            )
            self._overdue_recorded.add(attempt.attempt_id)

    def _recorded_overdue(self) -> set[str]:
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ?",
            (FILL_OBSERVER_OVERDUE_KIND,),
        ).fetchall()
        return {
            str(json.loads(payload_json).get("payload", {}).get("attempt_id"))
            for (payload_json,) in rows
        }

    def _record(self, kind: str, fields: dict[str, Any]) -> None:
        self.evidence_store.append(fields, kind=kind, record_class=kind)


def _reprojectable(attempt: _Tracked) -> bool:
    """Terminal by an engine receipt, not released, not held, not stuck."""
    return (
        attempt.terminal
        and not attempt.released
        and not attempt.held_terminal
        and not attempt.stuck
    )


def _fill_state(
    row: KisOrderRow,
) -> tuple[EgressResultKind | None, Decimal | None, Decimal | None, str]:
    """``(kind, filled, remaining, reason)`` for one attributed row (module docstring's
    fail-closed list). ``kind is None`` means the order is still working with nothing executed.
    """
    ordered, filled, remaining = row.ord_qty, row.tot_ccld_qty, row.rmn_qty
    if ordered is None or filled is None or remaining is None:
        return EgressResultKind.UNKNOWN, None, None, "quantity_unparseable"
    if row.rjct_qty is not None and row.rjct_qty > 0:
        return EgressResultKind.UNKNOWN, None, None, "rejected_quantity"
    if row.cancelled:
        if filled == 0:
            return EgressResultKind.CANCEL_ACK, None, None, "cancelled_unfilled"
        return EgressResultKind.UNKNOWN, None, None, "cancelled_after_fill"
    if filled < 0 or remaining < 0 or filled + remaining != ordered:
        return EgressResultKind.UNKNOWN, None, None, "quantity_inconsistent"
    if filled == 0:
        return None, None, None, "working"
    if remaining == 0:
        return EgressResultKind.FULL_FILL, filled, remaining, "filled"
    return EgressResultKind.PARTIAL_FILL, filled, remaining, "partially_filled"


def _text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")
