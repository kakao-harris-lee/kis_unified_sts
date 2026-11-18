"""Recover the trading date a dateless ACK row never carried, from the broker's own order rows.

Issue #1096 (incident 2026-11-13): one ``EGRESS_RESULT_CONSUMED`` ACK row was written without a
``trading_date`` key, so :meth:`KisMockFillObserver._trackable` dropped it from the tracked set on
every boot, its entry reservation stayed ``COMMITTED_UNBOUND`` forever, and the ARE limit stayed
saturated. #1074 stamps the date on NEW ACKs; evidence is append-only, so the row already written
can only be repaired by asking the broker. This module does that, GET-only: it scans a bounded,
configured window of the tenant's own trading dates in 주식일별주문체결조회 for the ACK's ODNO and,
when EXACTLY ONE date carries it, records the date so the next pass tracks the attempt normally.
Zero matches or more than one keep the existing fail-closed refusal.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.fill_fetch import odno_key
from tos_runtime.recon.ports import WitnessUnavailable
from tos_runtime.recon.witness_kis import KisOrderRow

__all__ = [
    "AMBIGUOUS",
    "FILL_OBSERVER_ACK_DATE_RECOVERY_KIND",
    "NO_MATCH",
    "RECOVERED",
    "UndatedAck",
    "apply_ack_date_scan",
    "recorded_outcomes",
    "recovered_trading_dates",
]

FILL_OBSERVER_ACK_DATE_RECOVERY_KIND = "FILL_OBSERVER_ACK_DATE_RECOVERY"

RECOVERED = "recovered"
NO_MATCH = "no_match"
AMBIGUOUS = "ambiguous"

#: One dateless ACK the scan looks for: ``(attempt_id, broker_execution_id)``.
UndatedAck = tuple[str, str]

AckDateRead = tuple[str, "tuple[KisOrderRow, ...] | WitnessUnavailable"]
Recorder = Callable[[str, dict[str, Any]], None]


def _payloads(store: SqliteEvidenceStore) -> list[dict[str, Any]]:
    rows = store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
        (FILL_OBSERVER_ACK_DATE_RECOVERY_KIND,),
    ).fetchall()
    payloads: list[dict[str, Any]] = []
    for (payload_json,) in rows:
        payload = json.loads(payload_json).get("payload", {})
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def recovered_trading_dates(store: SqliteEvidenceStore) -> dict[str, str]:
    """``attempt_id -> trading_date`` for every ACK a completed scan resolved to one date."""
    recovered: dict[str, str] = {}
    for payload in _payloads(store):
        attempt_id = payload.get("attempt_id")
        trading_date = payload.get("trading_date")
        if (
            payload.get("outcome") == RECOVERED
            and isinstance(attempt_id, str)
            and isinstance(trading_date, str)
        ):
            recovered[attempt_id] = trading_date
    return recovered


def recorded_outcomes(
    store: SqliteEvidenceStore,
) -> set[tuple[str, str, str | None]]:
    """The ``(attempt_id, outcome, trading_date)`` signatures already on durable record."""
    signatures: set[tuple[str, str, str | None]] = set()
    for payload in _payloads(store):
        attempt_id = payload.get("attempt_id")
        outcome = payload.get("outcome")
        trading_date = payload.get("trading_date")
        if isinstance(attempt_id, str) and isinstance(outcome, str):
            signatures.add(
                (
                    attempt_id,
                    outcome,
                    trading_date if isinstance(trading_date, str) else None,
                )
            )
    return signatures


def _rows_by_date(
    reads: tuple[AckDateRead, ...],
) -> dict[str, tuple[KisOrderRow, ...]] | None:
    """Every scanned date's rows, or ``None`` if ANY date failed to read (fail-closed: a window
    with a hole cannot tell "this ODNO is on no other date" from "we did not look")."""
    rows_by_date: dict[str, tuple[KisOrderRow, ...]] = {}
    for date, outcome in reads:
        if isinstance(outcome, WitnessUnavailable):
            return None
        rows_by_date[date] = outcome
    return rows_by_date or None


def _matched_dates(
    rows_by_date: dict[str, tuple[KisOrderRow, ...]], odno: str, instrument: str
) -> list[str]:
    key = odno_key(odno)
    return sorted(
        {
            date
            for date, rows in rows_by_date.items()
            for row in rows
            if row.pdno == instrument and odno_key(row.odno) == key
        }
    )


def apply_ack_date_scan(
    reads: tuple[AckDateRead, ...],
    targets: tuple[UndatedAck, ...],
    *,
    instrument: str,
    evidence_store: SqliteEvidenceStore,
    record: Recorder,
) -> None:
    """Decide each scanned ACK's trading date and record the verdict once per distinct outcome."""
    if not targets:
        return
    rows_by_date = _rows_by_date(reads)
    if rows_by_date is None:
        return
    scanned = sorted(rows_by_date)
    already = recorded_outcomes(evidence_store)
    for attempt_id, odno in targets:
        dates = _matched_dates(rows_by_date, odno, instrument)
        if len(dates) == 1:
            outcome, trading_date = RECOVERED, dates[0]
        elif not dates:
            outcome, trading_date = NO_MATCH, None
        else:
            outcome, trading_date = AMBIGUOUS, None
        signature = (attempt_id, outcome, trading_date)
        if signature in already:
            continue
        record(
            FILL_OBSERVER_ACK_DATE_RECOVERY_KIND,
            {
                "attempt_id": attempt_id,
                "broker_execution_id": odno,
                "outcome": outcome,
                "trading_date": trading_date,
                "scanned_dates": scanned,
                "matched_dates": dates,
            },
        )
        already.add(signature)
