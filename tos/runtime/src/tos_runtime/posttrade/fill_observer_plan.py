"""Build the fill observer's asynchronous broker-read plan on the session-loop thread.

The observer itself owns the evidence classifications and APPLY mutations. This helper only
gathers due work, records its monotonic scheduling state, and returns immutable FETCH inputs.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol

from tos.engine.records import InstrumentKey

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.fill_fetch import (
    FetchPlan,
    HeldPositionSnapshot,
    odno_key,
)
from tos_runtime.posttrade.fill_observer_config import FillObserverConfig
from tos_runtime.recon.evidence_reader import SqliteEvidenceReceiptReader
from tos_runtime.recon.ports import WitnessScope, WitnessUnavailable
from tos_runtime.time.sources import MonotonicSource

__all__ = [
    "build_fetch_plan",
    "due_recovery_attempts",
    "preempt_risk_only_fetch",
    "release_scope",
]


class _PlanSource(Protocol):
    """The observer fields and read-only helpers needed to plan one FETCH."""

    config: FillObserverConfig
    evidence_store: SqliteEvidenceStore
    monotonic: MonotonicSource
    account: str
    instrument: str

    @property
    def today(self) -> Callable[[], str | None]: ...

    held_position_tip: Callable[[], tuple[int, int | None] | None] | None
    held_position_eligible: Callable[[], bool] | None
    mark_held_position_pending: Callable[[WitnessScope | None], int | None] | None
    publish_held_position_snapshot: Callable[[HeldPositionSnapshot], None] | None
    pending_recovery_attempt_ids: Callable[[], tuple[str, ...]] | None
    resume_entry_discharge: Callable[[str], object] | None
    _last_poll_ms: int | None
    _last_held_position_poll_ms: int | None
    _last_prior_day_read_ms: dict[str, int]
    _last_recovery_resume_ms: dict[str, int]

    def _tracked_attempts(self) -> dict[str, Any]: ...

    def _due_reprojects(self, tracked: dict[str, Any]) -> tuple[str, ...]: ...


class _RiskFetchRunner(Protocol):
    @property
    def current_plan(self) -> FetchPlan | None: ...

    def cancel_risk_only(self) -> bool: ...


def due_recovery_attempts(source: _PlanSource, now: int) -> tuple[str, ...]:
    """Close attempts whose deferred entry discharge is due at the retry cadence."""
    if (
        source.pending_recovery_attempt_ids is None
        or source.resume_entry_discharge is None
    ):
        return ()
    try:
        attempt_ids = source.pending_recovery_attempt_ids()
    except Exception:  # noqa: BLE001 -- a failed scan cannot create recovery authority
        return ()
    normalized = sorted(
        {
            attempt_id
            for attempt_id in attempt_ids
            if isinstance(attempt_id, str) and attempt_id
        }
    )
    due: list[str] = []
    for attempt_id in normalized:
        last = source._last_recovery_resume_ms.get(attempt_id)
        if last is not None and now - last < source.config.finality_retry_interval_ms:
            continue
        source._last_recovery_resume_ms[attempt_id] = now
        due.append(attempt_id)
    return tuple(due)


def due_attempt_read(source: _PlanSource, attempt: Any, now: int) -> bool:
    """Today's ACKs are read each poll; prior dates follow their configured cadence."""
    today = source.today()
    if today is None or attempt.trading_date >= today:
        return True
    last = source._last_prior_day_read_ms.get(attempt.attempt_id)
    if last is not None and now - last < source.config.prior_day_poll_interval_ms:
        return False
    source._last_prior_day_read_ms[attempt.attempt_id] = now
    return True


def preempt_risk_only_fetch(source: _PlanSource, runner: _RiskFetchRunner) -> bool:
    """Cancel optional position reads when a matching ACK arrived after the plan watermark."""
    plan = runner.current_plan
    if plan is None or not plan.risk_only:
        return False
    if plan.evidence_seq_at_plan is None:
        return runner.cancel_risk_only()
    try:
        rows = source.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? AND seq > ? "
            "ORDER BY seq ASC",
            ("EGRESS_RESULT_CONSUMED", plan.evidence_seq_at_plan),
        ).fetchall()
        for (payload_json,) in rows:
            row = json.loads(payload_json).get("payload", {})
            key = row.get("instrument_key") or {}
            if (
                row.get("egress_result_kind") == "ACK"
                and key.get("account") == source.account
                and key.get("instrument") == source.instrument
            ):
                return runner.cancel_risk_only()
    except Exception:  # noqa: BLE001 -- uncertain new work cancels optional FETCH
        return runner.cancel_risk_only()
    return False


def _held_position_is_eligible(source: _PlanSource) -> bool:
    """Only poll positions when the RCL grants a current CLOSE-observation purpose."""
    if source.held_position_eligible is None:
        return False
    try:
        return source.held_position_eligible() is True
    except Exception:  # noqa: BLE001 -- unknown RCL state is not polling authority
        return False


def release_scope(source: _PlanSource) -> WitnessScope:
    """The release/recovery consumer's scope: account, instrument, all receipt dates."""
    instrument_key = InstrumentKey(account=source.account, instrument=source.instrument)
    try:
        receipts = SqliteEvidenceReceiptReader(source.evidence_store).receipts(
            WitnessScope(account=source.account, instrument_keys=(instrument_key,))
        )
    except WitnessUnavailable:
        receipts = ()
    dates = {
        receipt.trading_date for receipt in receipts if receipt.trading_date is not None
    }
    return WitnessScope(
        account=source.account,
        instrument_keys=(instrument_key,),
        order_dates=tuple(sorted(dates)),
    )


def _held_position_request(
    source: _PlanSource,
    *,
    due: bool,
    today: str | None,
    instrument_key: InstrumentKey,
) -> tuple[WitnessScope | None, int | None, tuple[int, int | None] | None, int | None]:
    """Capture the atomic RCL tip and invalidate/mark the one-use cache before FETCH."""
    raw_tip = (
        None
        if not due or source.held_position_tip is None
        else source.held_position_tip()
    )
    tip = (
        raw_tip
        if isinstance(raw_tip, tuple)
        and len(raw_tip) == 2
        and isinstance(raw_tip[0], int)
        and not isinstance(raw_tip[0], bool)
        and raw_tip[0] >= 0
        and (
            raw_tip[1] is None
            or (
                isinstance(raw_tip[1], int)
                and not isinstance(raw_tip[1], bool)
                and raw_tip[1] >= 0
            )
        )
        else None
    )
    generation = None if tip is None else tip[1]
    scope = (
        WitnessScope(
            account=source.account,
            instrument_keys=(instrument_key,),
            as_of_generation=generation,
            order_dates=(),
        )
        if due and today is not None and generation is not None
        else None
    )
    token = (
        None
        if not due or source.mark_held_position_pending is None
        else source.mark_held_position_pending(scope)
    )
    return scope, generation, tip, token


def _evidence_seq(source: _PlanSource) -> int | None:
    """Capture a durable watermark for cooperative risk-only FETCH preemption."""
    try:
        row = source.evidence_store.connection.execute(
            "SELECT COALESCE(MAX(seq), -1) FROM entries"
        ).fetchone()
    except Exception:  # noqa: BLE001 -- unknown watermark means preemption fails closed
        return None
    value = None if row is None else row[0]
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def build_fetch_plan(source: _PlanSource) -> FetchPlan | None:
    """Build one immutable FETCH plan from due ACK, recovery, and CLOSE-proof work."""
    evidence_seq_at_plan = _evidence_seq(source)
    tracked = source._tracked_attempts()
    reproject_ids = source._due_reprojects(tracked)
    now = source.monotonic.now_ms()
    pending = [
        attempt
        for attempt in tracked.values()
        if not attempt.terminal and due_attempt_read(source, attempt, now)
    ]
    recovery_ids = due_recovery_attempts(source, now)
    fill_work_due = bool(pending or reproject_ids or recovery_ids)
    held_interval = source.config.held_position_poll_interval_ms
    held_position_due = (
        not fill_work_due
        and source.publish_held_position_snapshot is not None
        and source.mark_held_position_pending is not None
        and held_interval is not None
        and (
            source._last_held_position_poll_ms is None
            or now - source._last_held_position_poll_ms >= held_interval
        )
        and _held_position_is_eligible(source)
    )
    if not pending and not reproject_ids and not held_position_due and not recovery_ids:
        return None
    if pending:
        source._last_poll_ms = now
    if held_position_due:
        # Mark at planning, not completion: a slow FETCH cannot enqueue another read.
        source._last_held_position_poll_ms = now

    instrument_key = InstrumentKey(account=source.account, instrument=source.instrument)
    reads = tuple(
        (
            date,
            WitnessScope(
                account=source.account,
                instrument_keys=(instrument_key,),
                attempt_ids=tuple(
                    attempt.attempt_id
                    for attempt in pending
                    if attempt.trading_date == date
                ),
                order_dates=(date,),
            ),
        )
        for date in sorted({attempt.trading_date for attempt in pending})
    )
    today = source.today()
    position_scope, generation, tip, position_token = _held_position_request(
        source,
        due=held_position_due,
        today=today,
        instrument_key=instrument_key,
    )
    release_scope_needed = bool(pending or reproject_ids or recovery_ids)
    return FetchPlan(
        reads=reads,
        targets=frozenset(
            (odno_key(attempt.odno), attempt.trading_date) for attempt in pending
        ),
        instrument=source.instrument,
        deadline_ms=now + source.config.poll_deadline_ms,
        snapshot_scope=(
            release_scope(source)
            if today is not None and release_scope_needed
            else None
        ),
        today=today,
        reproject_ids=reproject_ids,
        held_position_snapshot_due=held_position_due,
        held_position_scope=position_scope,
        held_position_generation=generation,
        held_position_tip=tip,
        held_position_token=position_token,
        recovery_attempt_ids=recovery_ids,
        evidence_seq_at_plan=evidence_seq_at_plan,
    )
