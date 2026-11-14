"""Post-ACK fill observer for the KIS 모의투자 stock order path (PR-3b, rescope plan §3 M2)."""

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
    HeldPositionSnapshot,
    OrderRowsReader,
    SnapshotPrefetcher,
    SnapshotUse,
    odno_key,
    run_fetch,
    snapshot_key,
)
from tos_runtime.posttrade.fill_observer_config import (
    FILL_OBSERVER_CONFIG_NAME,
    FillObserverConfig,
    FillObserverConfigError,
    load_fill_observer_config,
)
from tos_runtime.posttrade.fill_observer_plan import (
    build_fetch_plan,
    preempt_risk_only_fetch,
)
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
FILL_OBSERVER_RELEASE_SNAPSHOT_KIND = "FILL_OBSERVER_RELEASE_SNAPSHOT"

_CANCEL_REASONS = frozenset(
    {"cancelled_unfilled", "cancelled_after_fill", "derived_order_row"}
)

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


ResultSink = Callable[[EgressResultPayload], "ResultDisposition | None"]
Reprojector = Callable[[EgressResultPayload], "bool | None"]
ReleaseCommitted = Callable[[str], bool]
EngineHolds = Callable[[str], bool]
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
    released: bool = False
    stuck: bool = False
    held_terminal: bool = False
    absent_signatures: set[tuple[str, str | None, str | None]] = field(
        default_factory=set
    )
    sealed_quantity: Decimal | None = None


@dataclass(frozen=True)
class FillPollReport:
    """What one :meth:`KisMockFillObserver.poll_once` did."""

    polled: bool
    emitted: tuple[tuple[str, EgressResultKind, ResultDisposition | None], ...] = ()
    unattributed: tuple[str, ...] = ()
    read_failed: bool = False
    reprojected: tuple[tuple[str, bool | None], ...] = ()
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
    """Polls ``VTTC0081R`` for ACKed ODNOs and feeds what it reads to the engine (module"""

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
    snapshots: SnapshotPrefetcher | None = None
    held_position_tip: Callable[[], tuple[int, int | None] | None] | None = None
    held_position_eligible: Callable[[], bool] | None = None
    mark_held_position_pending: Callable[[WitnessScope | None], int | None] | None = (
        None
    )
    publish_held_position_snapshot: Callable[[HeldPositionSnapshot], None] | None = None
    pending_recovery_attempt_ids: Callable[[], tuple[str, ...]] | None = None
    resume_entry_discharge: Callable[[str], object] | None = None
    _last_poll_ms: int | None = field(default=None, init=False)
    _last_reproject_ms: dict[str, int] = field(default_factory=dict, init=False)
    _untrackable_recorded: set[str] = field(default_factory=set, init=False)
    _last_prior_day_read_ms: dict[str, int] = field(default_factory=dict, init=False)
    _first_pending_ms: dict[str, int] = field(default_factory=dict, init=False)
    _overdue_recorded: set[str] = field(default_factory=set, init=False)
    _last_read_failed: bool = field(default=False, init=False)
    _runner: FetchRunner | None = field(default=None, init=False)
    _closed: bool = field(default=False, init=False)
    _reread_now: bool = field(default=False, init=False)
    _expired_run: int = field(default=0, init=False)
    _expired_run_date: str | None = field(default=None, init=False)
    _last_held_position_poll_ms: int | None = field(default=None, init=False)
    _last_recovery_resume_ms: dict[str, int] = field(default_factory=dict, init=False)
    _preempted_for_fill: bool = field(default=False, init=False)

    def poll_if_due(self) -> FillPollReport:
        """The session loop's call (issue #950): never waits on the broker."""
        if self._closed:
            return FillPollReport(polled=False)
        if self._runner is None:
            self._runner = FetchRunner(self._fetch)
        done = self._runner.take_done()
        if done is not None:
            return self._apply(done)
        if self._runner.busy:
            if preempt_risk_only_fetch(self, self._runner):
                self._preempted_for_fill = True
            return FillPollReport(polled=False)
        if self._runner.has_job:
            return FillPollReport(polled=False)
        now = self.monotonic.now_ms()
        preempted_for_fill, self._preempted_for_fill = self._preempted_for_fill, False
        if (
            not preempted_for_fill
            and self._last_poll_ms is not None
            and now - self._last_poll_ms < self.config.poll_interval_ms
        ):
            return FillPollReport(polled=False)
        plan = self._plan()
        if plan is not None:
            self._runner.submit(plan)
        return FillPollReport(polled=False)

    def poll_once(self) -> FillPollReport:
        """One whole pass on the CALLING thread: plan, FETCH, APPLY — the same three steps"""
        plan = self._plan()
        if plan is None:
            return FillPollReport(polled=False)
        return self._apply(self._fetch(plan, lambda: False))

    def close(self) -> None:
        """Stop the FETCH worker with the session (issue #950): the in-flight read stops at its"""
        self._closed = True
        if self._runner is not None:
            self._runner.close()

    def _plan(self) -> FetchPlan | None:
        """Build the next worker plan from durable attempts and configured independent polls."""
        return build_fetch_plan(self)

    def _fetch(self, plan: FetchPlan, stop: Callable[[], bool]) -> FetchResult:
        """FETCH: :func:`~tos_runtime.posttrade.fill_fetch.run_fetch` over this observer's"""
        return run_fetch(
            plan,
            orders=self.orders,
            snapshots=self.snapshots,
            monotonic=self.monotonic,
            stop=stop,
        )

    def _apply(self, result: FetchResult) -> FillPollReport:
        """APPLY one FETCH's result, on the calling (loop) thread. The durable picture is"""
        if (
            result.held_position_snapshot is not None
            and self.publish_held_position_snapshot is not None
        ):
            self.publish_held_position_snapshot(result.held_position_snapshot)
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
        recovery_snapshot_matches = (
            result.snapshot is not None
            and result.plan.snapshot_scope is not None
            and result.plan.today is not None
            and result.snapshot.key == snapshot_key(result.plan.snapshot_scope)
            and result.snapshot.today == result.plan.today
            and self.today() == result.plan.today
        )
        with serving as uses:
            if recovery_snapshot_matches and self.resume_entry_discharge is not None:
                assert self.snapshots is not None
                assert result.snapshot is not None
                assert result.plan.snapshot_scope is not None
                assert result.plan.today is not None
                with self.snapshots.serving_required(
                    result.snapshot,
                    expected_scope=result.plan.snapshot_scope,
                    expected_today=result.plan.today,
                    max_age_ms=self.config.release_snapshot_max_age_ms,
                    now_ms=self.monotonic.now_ms,
                ) as recovery_uses:
                    for attempt_id in result.plan.recovery_attempt_ids:
                        self.resume_entry_discharge(attempt_id)
                uses.extend(recovery_uses)
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
        """One row per snapshot use (read instants, age, ``read_ok``, run so far). Only a run's"""
        for use in uses:
            read_ok = not isinstance(use.snapshot.outcome, WitnessUnavailable)
            if use.snapshot.today != self._expired_run_date:
                self._expired_run, self._expired_run_date = 0, use.snapshot.today
            expired = use.verdict == "expired"
            if expired:
                self._expired_run += 1
                self._reread_now |= self._expired_run == 1
            consecutive = self._expired_run
            if not expired and read_ok:
                self._expired_run = 0
            self._record(
                FILL_OBSERVER_RELEASE_SNAPSHOT_KIND,
                {
                    "verdict": use.verdict,
                    **use.read_fields(),
                    "age_ms": use.age_ms,
                    "max_age_ms": use.max_age_ms,
                    "trading_date": use.snapshot.today,
                    "read_ok": read_ok,
                    "consecutive_expired": consecutive,
                },
            )

    def _read_failed(
        self, date: str, attempts: list[_Tracked], exc: WitnessUnavailable
    ) -> None:
        """Record a failed read once per failure streak — and still run the overdue check: a"""
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
                self._last_reproject_ms[attempt.attempt_id] = self.monotonic.now_ms()
            disposition = self.result_sink(payload)
            emitted.append((attempt.attempt_id, payload.kind, disposition))
        return emitted

    def _hold_cancel(
        self, attempt: _Tracked, rows: tuple[KisOrderRow, ...], reason: str
    ) -> None:
        """One durable ``FILL_OBSERVER_CANCEL_UNSUPPORTED`` hold with what the broker showed"""
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
        """Record — once per distinct observation — what the broker showed for an attempt the"""
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
        """Attempts whose terminal result is recorded but whose release the RCL does not hold"""
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
                    and self._trackable(
                        attempt_id, row["broker_execution_id"], row.get("trading_date")
                    )
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

    def _trackable(self, attempt_id: str, odno: str, trading_date: Any) -> bool:
        """An ACK that cannot be joined to a broker row by ODNO is never tracked; one"""
        dated = isinstance(trading_date, str)
        if dated and odno_key(odno) is not None:
            return True
        if attempt_id not in self._untrackable_recorded:
            already = self.evidence_store.connection.execute(
                "SELECT COUNT(*) FROM entries WHERE kind = ? AND payload_json LIKE ?",
                (FILL_OBSERVER_ACK_UNTRACKABLE_KIND, f'%"{attempt_id}"%'),
            ).fetchone()[0]
            if not already:
                fields = {"attempt_id": attempt_id, "broker_execution_id": odno}
                fields["reason"] = "odno_no_digits" if dated else "no_trading_date"
                self._record(FILL_OBSERVER_ACK_UNTRACKABLE_KIND, fields)
            self._untrackable_recorded.add(attempt_id)
        return False

    def _apply_absent_rows(self, tracked: dict[str, _Tracked]) -> None:
        """An ``ENGINE_RESERVATION_ABSENT`` row holds only while the engine lacks the attempt"""
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ?",
            (FILL_OBSERVER_ENGINE_RESERVATION_ABSENT_KIND,),
        ).fetchall()
        for (payload_json,) in rows:
            row = json.loads(payload_json).get("payload", {})
            attempt = tracked.get(str(row.get("attempt_id")))
            if attempt is None or self.engine_holds(attempt.attempt_id):
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
            return self._cancel_marker(attempt), cancel_reason
        if len(mine) != 1:
            return self._unknown(attempt, "ambiguous_rows")
        if mine[0].pdno != self.instrument:
            return self._unknown(attempt, "instrument_mismatch")
        if (
            attempt.sealed_quantity is None
            or mine[0].ord_qty != attempt.sealed_quantity
        ):
            return self._unknown(attempt, "ordered_quantity_mismatch")
        kind, filled, remaining, reason = _fill_state(mine[0])
        if kind is None:
            return None, reason
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
        """Which ``_CANCEL_REASONS`` member the attributed rows show, or ``None``. Only rows"""
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
        """A ``CANCEL_ACK``-shaped marker the emit step routes to the cancel hold — it is never"""
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
        """One ``FILL_OBSERVER_OVERDUE`` row per attempt, ever: the wait clock is process-local,"""
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
    """``(kind, filled, remaining, reason)`` for one attributed row (module docstring's"""
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
