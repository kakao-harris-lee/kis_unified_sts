"""Recover the trading date a dateless ACK row never carried, from the broker's own order rows."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.fill_fetch import odno_key
from tos_runtime.recon.witness_kis import KisOrderRow

__all__ = [
    "AMBIGUOUS",
    "AckDateScan",
    "FILL_OBSERVER_ACK_DATE_RECOVERY_KIND",
    "NO_MATCH",
    "RECOVERED",
    "UndatedAck",
    "recorded_outcomes",
    "recovered_trading_dates",
    "resolve_ack_dates",
]

FILL_OBSERVER_ACK_DATE_RECOVERY_KIND = "FILL_OBSERVER_ACK_DATE_RECOVERY"

RECOVERED = "recovered"
NO_MATCH = "no_match"
AMBIGUOUS = "ambiguous"

UndatedAck = tuple[str, str]

ClaimedOrderDays = frozenset[tuple[str, str, str]]

Recorder = Callable[[str, dict[str, Any]], None]


@dataclass
class AckDateScan:
    """One in-progress window scan: the dates to read, who is being looked up, what came back."""

    window: tuple[str, ...] = ()
    targets: tuple[UndatedAck, ...] = ()
    rows: dict[str, tuple[KisOrderRow, ...]] = field(default_factory=dict)

    @property
    def active(self) -> bool:
        """Whether a window is open — one date per FETCH until every date has answered."""
        return bool(self.window)

    def start(self, window: tuple[str, ...], targets: tuple[UndatedAck, ...]) -> None:
        """Anchor a window so later passes read the same dates even as ``today`` advances."""
        self.window, self.targets, self.rows = window, targets, {}

    def clear(self) -> None:
        """Abandon the scan — a failed read leaves no verdict; the cadence retries the whole set."""
        self.window, self.targets, self.rows = (), (), {}

    def next_date(self) -> str | None:
        """The next window date with no rows yet, or ``None`` when the window is complete."""
        for date in self.window:
            if date not in self.rows:
                return date
        return None

    def record(self, date: str, rows: tuple[KisOrderRow, ...]) -> bool:
        """Keep one date's rows; ``True`` once every window date has answered."""
        if date not in self.window:
            return False
        self.rows[date] = rows
        return self.next_date() is None


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


def recorded_outcomes(store: SqliteEvidenceStore) -> set[tuple[str, str, str | None]]:
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


def _matched_dates(
    scan: AckDateScan,
    *,
    attempt_id: str,
    odno: str,
    instrument: str,
    sealed_quantity: Decimal | None,
    claimed: ClaimedOrderDays,
) -> list[str]:
    """Window dates whose rows carry an order this attempt could own (module docstring's four"""
    key = odno_key(odno)
    if key is None or sealed_quantity is None:
        return []
    taken = {
        (claimed_key, date)
        for claimed_key, date, owner in claimed
        if owner != attempt_id
    }
    dates = {
        date
        for date, rows in scan.rows.items()
        if (key, date) not in taken
        for row in rows
        if row.pdno == instrument
        and odno_key(row.odno) == key
        and row.ord_qty == sealed_quantity
    }
    return sorted(dates)


def resolve_ack_dates(
    scan: AckDateScan,
    *,
    instrument: str,
    sealed: Mapping[str, Decimal | None],
    claimed: ClaimedOrderDays,
    evidence_store: SqliteEvidenceStore,
    record: Recorder,
) -> bool:
    """Judge a COMPLETE window and record one verdict per target; ``True`` if any was recovered."""
    scanned = sorted(scan.rows)
    already = recorded_outcomes(evidence_store)
    recovered_any = False
    for attempt_id, odno in scan.targets:
        dates = _matched_dates(
            scan,
            attempt_id=attempt_id,
            odno=odno,
            instrument=instrument,
            sealed_quantity=sealed.get(attempt_id),
            claimed=claimed,
        )
        if len(dates) == 1:
            outcome, trading_date = RECOVERED, dates[0]
            recovered_any = True
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
    return recovered_any
