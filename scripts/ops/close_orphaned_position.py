"""One-shot paper close for an orphaned position left in a Redis positions hash.

Context (2026-06-10): the legacy stock orchestrator opened 에코프로(086520) on
2026-06-04 and wrote it to ``trading:stock:positions``. The M5d cutover disabled
the orchestrator (``STOCK_ORCHESTRATOR_ENABLED=false``) and the decoupled M4
daemons manage ``stock:daemon:positions`` only — so the position was orphaned:
no exit logic ran, and its Redis record went stale (current_price frozen at the
cutover while the stock kept falling).

This script performs a controlled paper close:
  1. reads the position record from the Redis hash,
  2. closes it at the given exit price (paper fill, round-trip fee applied),
  3. records the closed trade + a superseding ``is_open=0`` position snapshot
     in the SQLite RuntimeLedger (same payload shape as
     ``PositionTracker._trade_payload`` / ``_position_snapshot_payload``),
  4. HDELs the record from the Redis hash.

It deliberately does NOT touch ``risk:state:stock`` (RuntimeRiskState): the loss
accrued over days on a legacy-path position; folding it into M4-R's intraday
daily/weekly MDD counters would block the new pipeline's entries and distort
paper observation.

Usage:
    python scripts/ops/close_orphaned_position.py \
        --positions-key trading:stock:positions \
        --code 086520 --exit-price 105800 [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("close_orphaned_position")


def _build_trade_payload(rec: dict[str, Any], exit_price: float) -> dict[str, Any]:
    """Mirror PositionTracker._trade_payload for a LONG stock position."""
    entry_price = float(rec["entry_price"])
    quantity = int(rec["quantity"])
    pnl = (exit_price - entry_price) * quantity
    entry_time = datetime.fromisoformat(rec["entry_time"])
    exit_time = datetime.now(UTC)
    entry_notional = max(entry_price * quantity, 1e-9)
    return {
        "id": rec["id"],
        "trade_id": rec["id"],
        "idempotency_key": f"stock:{rec['id']}",
        "asset_class": "stock",
        "code": rec["code"],
        "symbol": rec["code"],
        "name": rec.get("name", ""),
        "side": rec.get("side", "long"),
        "strategy": rec.get("strategy", ""),
        "execution_venue": "KRX",
        "entry_time": entry_time,
        "entry_price": entry_price,
        "exit_time": exit_time,
        "exit_price": exit_price,
        "quantity": quantity,
        "pnl": pnl,
        "pnl_pct": (pnl / entry_notional) * 100.0,
        "hold_seconds": int((exit_time - entry_time).total_seconds()),
        "exit_reason": "manual_close",
        "exit_state": rec.get("state", "survival"),
        "commission": 0.0,
        "slippage": 0.0,
        "fee_rate": float(rec.get("fee_rate", 0.003)),
        "metadata": {
            "orphaned": True,
            "closed_by": "scripts/ops/close_orphaned_position.py",
            "note": "legacy orchestrator position orphaned by M5d cutover",
        },
    }


def _build_snapshot_payload(rec: dict[str, Any], exit_price: float) -> dict[str, Any]:
    """Mirror PositionTracker._position_snapshot_payload with is_open=0."""
    entry_price = float(rec["entry_price"])
    quantity = int(rec["quantity"])
    pnl = (exit_price - entry_price) * quantity
    return {
        "id": rec["id"],
        "position_id": rec["id"],
        "idempotency_key": f"stock:{rec['id']}",
        "asset_class": "stock",
        "code": rec["code"],
        "symbol": rec["code"],
        "name": rec.get("name", ""),
        "side": rec.get("side", "long"),
        "strategy": rec.get("strategy", ""),
        "quantity": quantity,
        "entry_time": datetime.fromisoformat(rec["entry_time"]),
        "entry_price": entry_price,
        "current_price": exit_price,
        "highest_price": float(rec.get("highest_price", entry_price)),
        "lowest_price": float(rec.get("lowest_price", entry_price)),
        "stop_price": float(rec.get("stop_price", 0.0)),
        "state": rec.get("state", "survival"),
        "is_open": 0,
        "exit_time": datetime.now(UTC),
        "exit_price": exit_price,
        "exit_reason": "manual_close",
        "pnl": pnl,
        "fee_rate": float(rec.get("fee_rate", 0.003)),
        "execution_venue": "KRX",
        "metadata": {"orphaned": True},
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--positions-key", default="trading:stock:positions")
    parser.add_argument("--code", required=True)
    parser.add_argument("--exit-price", type=float, required=True)
    parser.add_argument("--redis-url", default="redis://localhost:6379/1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import redis.asyncio as aioredis

    from shared.storage import SQLiteRuntimeLedger
    from shared.storage.config import StorageConfig

    redis_client = aioredis.from_url(args.redis_url)
    try:
        raw = await redis_client.hget(args.positions_key, args.code)
        if raw is None:
            # The orchestrator keyed this hash by position id, not code — scan.
            all_recs = await redis_client.hgetall(args.positions_key)
            field = None
            for k, v in all_recs.items():
                rec = json.loads(v)
                if rec.get("code") == args.code:
                    field, raw = k, v
                    break
            if raw is None:
                logger.error(
                    "no record for code=%s in %s", args.code, args.positions_key
                )
                return 1
        else:
            field = args.code

        rec = json.loads(raw)
        entry_price = float(rec["entry_price"])
        quantity = int(rec["quantity"])
        gross = (args.exit_price - entry_price) * quantity
        fee = (entry_price + args.exit_price) * quantity * (
            float(rec.get("fee_rate", 0.003)) / 2
        )
        logger.info(
            "closing %s (%s) qty=%d entry=%.1f exit=%.1f gross=%+.0f fee=%.0f net=%+.0f",
            rec.get("name", ""),
            rec["code"],
            quantity,
            entry_price,
            args.exit_price,
            gross,
            fee,
            gross - fee,
        )

        if args.dry_run:
            logger.info("dry-run: no writes performed")
            return 0

        storage_config = StorageConfig.load_or_default()
        ledger = SQLiteRuntimeLedger(storage_config.runtime_storage.sqlite)
        try:
            trade_id = ledger.record_trade(_build_trade_payload(rec, args.exit_price))
            ledger.record_position_snapshot(
                _build_snapshot_payload(rec, args.exit_price)
            )
            logger.info("ledger recorded trade id=%s + closing snapshot", trade_id)
        finally:
            ledger.close()

        if isinstance(field, (bytes, bytearray)):
            field = field.decode()
        removed = await redis_client.hdel(args.positions_key, field)
        logger.info("redis HDEL %s %s -> %d", args.positions_key, field, removed)
        return 0
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(asyncio.run(main()))
