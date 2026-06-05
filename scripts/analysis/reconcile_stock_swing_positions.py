#!/usr/bin/env python3
"""Reconcile RuntimeLedger stock swing open rows against Redis runtime positions.

Default mode is a dry-run. With ``--apply``, the script appends closed position
snapshots into RuntimeLedger for positions that exist in durable storage but no
longer exist in Redis runtime state.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@dataclass(frozen=True)
class SwingOpenPosition:
    id: str
    code: str
    name: str
    entry_date: datetime
    entry_price: float
    quantity: int
    strategy: str
    execution_venue: str
    stop_loss_price: float
    high_since_entry: float
    current_state: str
    side: str
    fee_rate: float
    updated_at: datetime


@dataclass(frozen=True)
class RedisOpenPosition:
    id: str
    code: str


@dataclass(frozen=True)
class ReconciliationCandidate:
    position: SwingOpenPosition
    age_days: int
    reason: str


def _coerce_datetime(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw
    return datetime.fromisoformat(str(raw))


def _coerce_aware(raw: datetime) -> datetime:
    if raw.tzinfo is None:
        return raw.replace(tzinfo=UTC)
    return raw.astimezone(UTC)


def _position_from_row(row: tuple[Any, ...]) -> SwingOpenPosition:
    return SwingOpenPosition(
        id=str(row[0]),
        code=str(row[1]),
        name=str(row[2]),
        entry_date=_coerce_datetime(row[3]),
        entry_price=float(row[4] or 0.0),
        quantity=int(row[5] or 0),
        strategy=str(row[6] or ""),
        execution_venue=str(row[7] or "KRX"),
        stop_loss_price=float(row[8] or 0.0),
        high_since_entry=float(row[9] or row[4] or 0.0),
        current_state=str(row[10] or "survival"),
        side=str(row[11] or "long"),
        fee_rate=float(row[12] or 0.0),
        updated_at=_coerce_datetime(row[13]),
    )


def _position_from_ledger_row(row: dict[str, Any]) -> SwingOpenPosition:
    entry = row.get("entry_time") or row.get("entry_date") or datetime.now(UTC)
    updated = row.get("snapshot_time") or row.get("updated_at") or entry
    entry_price = float(row.get("entry_price") or 0.0)
    return SwingOpenPosition(
        id=str(row.get("position_id") or row.get("id") or ""),
        code=str(row.get("symbol") or row.get("code") or ""),
        name=str(row.get("name") or ""),
        entry_date=_coerce_datetime(entry),
        entry_price=entry_price,
        quantity=int(row.get("quantity") or 0),
        strategy=str(row.get("strategy") or ""),
        execution_venue=str(row.get("venue") or "KRX"),
        stop_loss_price=float(
            row.get("stop_price") or row.get("stop_loss_price") or 0.0
        ),
        high_since_entry=float(row.get("high_since_entry") or entry_price),
        current_state=str(row.get("state") or row.get("current_state") or "survival"),
        side=str(row.get("side") or "long"),
        fee_rate=float(row.get("fee_rate") or 0.0),
        updated_at=_coerce_datetime(updated),
    )


def _redis_position_from_payload(payload: dict[str, Any]) -> RedisOpenPosition:
    return RedisOpenPosition(
        id=str(payload.get("id") or ""),
        code=str(payload.get("code") or ""),
    )


def plan_reconciliation(
    ledger_positions: list[SwingOpenPosition],
    redis_positions: list[RedisOpenPosition],
    *,
    now: datetime,
    min_age_days: int,
    code_filter: set[str] | None = None,
    id_filter: set[str] | None = None,
) -> list[ReconciliationCandidate]:
    """Return ledger-only open positions safe enough to close by replacement."""
    redis_ids = {p.id for p in redis_positions if p.id}
    redis_codes = {p.code for p in redis_positions if p.code}
    now_utc = _coerce_aware(now)

    candidates: list[ReconciliationCandidate] = []
    for position in ledger_positions:
        if code_filter and position.code not in code_filter:
            continue
        if id_filter and position.id not in id_filter:
            continue

        if position.id in redis_ids:
            continue
        if position.code in redis_codes:
            continue

        age_days = max(
            0, (now_utc.date() - _coerce_aware(position.entry_date).date()).days
        )
        if age_days < min_age_days:
            continue

        candidates.append(
            ReconciliationCandidate(
                position=position,
                age_days=age_days,
                reason="redis_absent_id_and_code",
            )
        )

    return candidates


def close_replacement_row(
    candidate: ReconciliationCandidate,
    *,
    closed_at: datetime,
    exit_reason: str,
) -> dict[str, Any]:
    position = candidate.position
    return {
        "id": position.id,
        "position_id": position.id,
        "asset_class": "stock",
        "symbol": position.code,
        "name": position.name,
        "entry_time": position.entry_date.isoformat(),
        "entry_price": position.entry_price,
        "quantity": position.quantity,
        "strategy": position.strategy,
        "venue": position.execution_venue or "KRX",
        "stop_price": position.stop_loss_price,
        "high_since_entry": position.high_since_entry,
        "state": position.current_state,
        "is_open": 0,
        "exit_time": closed_at.isoformat(),
        "exit_price": position.entry_price,
        "exit_reason": exit_reason,
        "pnl": 0.0,
        "side": position.side or "long",
        "fee_rate": position.fee_rate,
        "snapshot_time": closed_at.isoformat(),
    }


def fetch_runtime_ledger_open_positions(ledger: Any) -> list[SwingOpenPosition]:
    return [
        _position_from_ledger_row(row)
        for row in ledger.load_open_positions(asset_class="stock")
    ]


def fetch_redis_open_positions() -> list[RedisOpenPosition]:
    from shared.streaming.trading_state import TradingStateReader

    reader = TradingStateReader("stock")
    payloads = reader.get_positions() or []
    return [
        _redis_position_from_payload(payload)
        for payload in payloads
        if isinstance(payload, dict)
    ]


def apply_replacements(
    ledger: Any,
    candidates: list[ReconciliationCandidate],
    *,
    closed_at: datetime,
    exit_reason: str,
) -> int:
    if not candidates:
        return 0
    snapshots = [
        close_replacement_row(
            candidate,
            closed_at=closed_at,
            exit_reason=exit_reason,
        )
        for candidate in candidates
    ]
    for snapshot in snapshots:
        ledger.record_position_snapshot(snapshot)
    return len(snapshots)


def _candidate_payload(candidate: ReconciliationCandidate) -> dict[str, Any]:
    payload = asdict(candidate)
    position = payload["position"]
    for key in ("entry_date", "updated_at"):
        position[key] = position[key].isoformat()
    return payload


def _parse_csv(raw: str) -> set[str]:
    return {item.strip() for item in raw.split(",") if item.strip()}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Insert closed replacement rows. Omit for dry-run.",
    )
    parser.add_argument(
        "--min-age-days",
        type=int,
        default=1,
        help="Only reconcile ledger-only open positions at least this old.",
    )
    parser.add_argument("--code", default="", help="Comma-separated code filter.")
    parser.add_argument("--id", default="", help="Comma-separated position id filter.")
    parser.add_argument(
        "--exit-reason",
        default="reconciled_redis_absent",
        help="Exit reason stored in replacement rows when --apply is used.",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Print machine-readable reconciliation result.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    from shared.storage import SQLiteRuntimeLedger, StorageConfig

    storage_config = StorageConfig.load_or_default()
    ledger = SQLiteRuntimeLedger(storage_config.runtime_storage.sqlite)
    try:
        ledger_positions = fetch_runtime_ledger_open_positions(ledger)
        redis_positions = fetch_redis_open_positions()
        candidates = plan_reconciliation(
            ledger_positions,
            redis_positions,
            now=datetime.now(UTC),
            min_age_days=max(0, int(args.min_age_days)),
            code_filter=_parse_csv(args.code) or None,
            id_filter=_parse_csv(args.id) or None,
        )

        applied = 0
        if args.apply:
            applied = apply_replacements(
                ledger,
                candidates,
                closed_at=datetime.now(UTC).replace(tzinfo=None),
                exit_reason=str(args.exit_reason),
            )

        result = {
            "mode": "apply" if args.apply else "dry_run",
            "ledger_open_positions": len(ledger_positions),
            "redis_open_positions": len(redis_positions),
            "candidate_count": len(candidates),
            "applied_count": applied,
            "candidates": [_candidate_payload(candidate) for candidate in candidates],
        }
        if args.print_json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(
                f"{result['mode']}: candidates={len(candidates)} "
                f"applied={applied} ledger_open={len(ledger_positions)} "
                f"redis_open={len(redis_positions)}"
            )
            for candidate in candidates:
                position = candidate.position
                print(
                    f"- {position.id} {position.code} {position.name} "
                    f"strategy={position.strategy} age_days={candidate.age_days} "
                    f"reason={candidate.reason}"
                )
        return 0
    finally:
        ledger.close()


if __name__ == "__main__":
    raise SystemExit(main())
