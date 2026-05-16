#!/usr/bin/env python3
"""Reconcile ClickHouse stock swing open rows against Redis runtime positions.

Default mode is a dry-run. With ``--apply``, the script inserts closed
replacement rows into ``market.swing_positions`` for ClickHouse-only positions.
The table uses ReplacingMergeTree(updated_at), so inserting a newer row with the
same (code, entry_date, id) key is enough to make ``FINAL`` reads show closed.
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

from scripts.analysis.stock_paper_daily_verification import (  # noqa: E402
    _build_clickhouse_client,
    _load_config,
    _load_repo_env,
    _validate_identifier,
)


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


def _redis_position_from_payload(payload: dict[str, Any]) -> RedisOpenPosition:
    return RedisOpenPosition(
        id=str(payload.get("id") or ""),
        code=str(payload.get("code") or ""),
    )


def plan_reconciliation(
    clickhouse_positions: list[SwingOpenPosition],
    redis_positions: list[RedisOpenPosition],
    *,
    now: datetime,
    min_age_days: int,
    code_filter: set[str] | None = None,
    id_filter: set[str] | None = None,
) -> list[ReconciliationCandidate]:
    """Return ClickHouse-only open positions safe enough to close by replacement."""
    redis_ids = {p.id for p in redis_positions if p.id}
    redis_codes = {p.code for p in redis_positions if p.code}
    now_utc = _coerce_aware(now)

    candidates: list[ReconciliationCandidate] = []
    for position in clickhouse_positions:
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
) -> tuple[Any, ...]:
    position = candidate.position
    return (
        position.id,
        position.code,
        position.name,
        position.entry_date,
        position.entry_price,
        position.quantity,
        position.strategy,
        position.execution_venue or "KRX",
        position.stop_loss_price,
        position.high_since_entry,
        position.current_state,
        0,
        closed_at,
        position.entry_price,
        exit_reason,
        0.0,
        position.side or "long",
        position.fee_rate,
    )


def _ensure_execution_venue_column(client: Any, database: str, table: str) -> None:
    client.execute(
        f"ALTER TABLE {database}.{table} "
        "ADD COLUMN IF NOT EXISTS execution_venue String DEFAULT 'KRX' AFTER strategy"
    )


def fetch_clickhouse_open_positions(
    client: Any, database: str, table: str
) -> list[SwingOpenPosition]:
    rows = client.execute(f"""
        SELECT
            id,
            code,
            name,
            entry_date,
            entry_price,
            quantity,
            strategy,
            execution_venue,
            stop_loss_price,
            high_since_entry,
            current_state,
            side,
            fee_rate,
            updated_at
        FROM {database}.{table} FINAL
        WHERE is_open = 1
        ORDER BY entry_date ASC, code ASC, id ASC
        """)
    return [_position_from_row(row) for row in rows]


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
    client: Any,
    database: str,
    table: str,
    candidates: list[ReconciliationCandidate],
    *,
    closed_at: datetime,
    exit_reason: str,
) -> int:
    if not candidates:
        return 0
    rows = [
        close_replacement_row(
            candidate,
            closed_at=closed_at,
            exit_reason=exit_reason,
        )
        for candidate in candidates
    ]
    client.execute(
        f"""
        INSERT INTO {database}.{table}
        (id, code, name, entry_date, entry_price, quantity, strategy,
         execution_venue, stop_loss_price, high_since_entry, current_state,
         is_open, exit_date, exit_price, exit_reason, pnl, side, fee_rate)
        VALUES
        """,
        rows,
    )
    return len(rows)


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
        help="Only reconcile ClickHouse-only open rows at least this old.",
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
    _load_repo_env()
    config = _load_config()
    database = _validate_identifier(config.clickhouse_database, label="database")
    table = _validate_identifier(config.clickhouse_position_table, label="table")
    client = _build_clickhouse_client(database)
    try:
        _ensure_execution_venue_column(client, database, table)
        clickhouse_positions = fetch_clickhouse_open_positions(client, database, table)
        redis_positions = fetch_redis_open_positions()
        candidates = plan_reconciliation(
            clickhouse_positions,
            redis_positions,
            now=datetime.now(UTC),
            min_age_days=max(0, int(args.min_age_days)),
            code_filter=_parse_csv(args.code) or None,
            id_filter=_parse_csv(args.id) or None,
        )

        applied = 0
        if args.apply:
            applied = apply_replacements(
                client,
                database,
                table,
                candidates,
                closed_at=datetime.now(UTC).replace(tzinfo=None),
                exit_reason=str(args.exit_reason),
            )

        result = {
            "mode": "apply" if args.apply else "dry_run",
            "clickhouse_open_positions": len(clickhouse_positions),
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
                f"applied={applied} ch_open={len(clickhouse_positions)} "
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
        client.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
