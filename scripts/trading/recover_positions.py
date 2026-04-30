#!/usr/bin/env python
"""Position recovery / reconciliation — Phase 5 Task 3.

On every order_router cold start, compare the live KIS broker's open
futures positions against the Redis snapshot at
``trading:futures:positions``. On any divergence, write a sentinel file
that ``services.order_router.main`` checks at startup and refuses to
operate until an operator clears it (parallels the kill-switch sentinel).

This is **mandatory** before live deployment: VirtualBroker is in-memory
and was always coherent with Redis by construction; the live KIS broker
maintains its own state and can drift (process kill mid-fill, manual KIS
order, partial cancel, etc.) — without reconciliation the daemon would
silently double-trade or trade against a stale view.

Sentinel file: ``/var/run/kis_position_recovery.tripped`` (configurable
via ``--sentinel-path``). Falls back to a project-local path when the
default isn't writable (phase-1 log-path lesson, commit 41b5e3c).

Operator clears via ``scripts/recover_positions_clear.sh`` after manual
reconciliation review.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger(__name__)

DEFAULT_SENTINEL_PATH = "/var/run/kis_position_recovery.tripped"
FALLBACK_SENTINEL_PATH = str(
    Path("/home/deploy/project/kis_unified_sts/logs/recovery") / "tripped"
)


@dataclass(frozen=True)
class _Position:
    symbol: str
    side: str  # "long" | "short"
    quantity: int

    @classmethod
    def from_redis_dict(cls, d: dict[str, Any]) -> _Position:
        side = str(d.get("side", "long")).lower()
        if side in ("buy", "BUY"):
            side = "long"
        elif side in ("sell", "SELL"):
            side = "short"
        return cls(
            symbol=str(d.get("symbol", d.get("code", ""))),
            side=side,
            quantity=int(d.get("quantity", 0)),
        )

    @classmethod
    def from_kis_dict(cls, d: dict[str, Any]) -> _Position:
        side_raw = str(d.get("side", "")).lower()
        # KIS futures balance encodes side as "1" (sell/short) or "2" (buy/long)
        # in some TR responses; the higher-level kis client normalizes to a string.
        if side_raw in ("buy", "long", "2"):
            side = "long"
        elif side_raw in ("sell", "short", "1"):
            side = "short"
        else:
            side = side_raw or "long"
        return cls(
            symbol=str(d.get("code", d.get("symbol", ""))),
            side=side,
            quantity=int(d.get("quantity", 0)),
        )


def reconcile(
    redis_positions: list[dict[str, Any]],
    broker_positions: list[dict[str, Any]],
) -> tuple[list[_Position], list[_Position], list[tuple[_Position, _Position]]]:
    """Compute (broker_only, redis_only, mismatched) divergence sets.

    - ``broker_only``: position exists at the broker, not in Redis (e.g.
      manual KIS order placed during downtime).
    - ``redis_only``: position exists in Redis, not at broker (e.g.
      broker auto-cancelled while daemon was offline).
    - ``mismatched``: same symbol on both sides, but quantity or side
      differs.
    """
    redis_pos = [_Position.from_redis_dict(d) for d in redis_positions]
    broker_pos = [_Position.from_kis_dict(d) for d in broker_positions]

    by_symbol_redis = {p.symbol: p for p in redis_pos}
    by_symbol_broker = {p.symbol: p for p in broker_pos}

    broker_only = [
        p for p in broker_pos if p.symbol not in by_symbol_redis and p.quantity > 0
    ]
    redis_only = [
        p for p in redis_pos if p.symbol not in by_symbol_broker and p.quantity > 0
    ]
    mismatched: list[tuple[_Position, _Position]] = []
    for sym, rp in by_symbol_redis.items():
        bp = by_symbol_broker.get(sym)
        if bp is None:
            continue
        if rp.side != bp.side or rp.quantity != bp.quantity:
            mismatched.append((rp, bp))

    return broker_only, redis_only, mismatched


def _resolve_sentinel_path(requested: str | None) -> Path:
    candidate = Path(requested) if requested else Path(DEFAULT_SENTINEL_PATH)
    try:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        # Test write-permission with a probe file
        probe = candidate.parent / ".kis_recovery_probe"
        probe.write_text("ok")
        probe.unlink()
        return candidate
    except (PermissionError, OSError):
        fallback = Path(FALLBACK_SENTINEL_PATH)
        fallback.parent.mkdir(parents=True, exist_ok=True)
        logger.warning(
            "Default sentinel path %s not writable; falling back to %s "
            "(phase-1 log-path lesson)",
            candidate,
            fallback,
        )
        return fallback


def write_sentinel(
    sentinel_path: Path,
    *,
    broker_only: list[_Position],
    redis_only: list[_Position],
    mismatched: list[tuple[_Position, _Position]],
) -> None:
    payload = {
        "broker_only": [p.__dict__ for p in broker_only],
        "redis_only": [p.__dict__ for p in redis_only],
        "mismatched": [
            {"redis": rp.__dict__, "broker": bp.__dict__} for rp, bp in mismatched
        ],
    }
    sentinel_path.write_text(json.dumps(payload, indent=2))
    logger.critical(
        "Recovery sentinel written to %s — order_router will refuse to start "
        "until cleared",
        sentinel_path,
    )


async def _fetch_redis_positions() -> list[dict[str, Any]]:
    from shared.streaming.trading_state import TradingStateReader

    return TradingStateReader("futures").get_positions()


async def _fetch_broker_positions() -> list[dict[str, Any]]:
    from shared.kis.auth import KISAuthConfig, KISAuthManager
    from shared.kis.client import KISClient

    auth_config = KISAuthConfig(
        app_key=os.environ.get("KIS_FUTURES_APP_KEY", ""),
        app_secret=os.environ.get("KIS_FUTURES_APP_SECRET", ""),
        is_real=os.environ.get("KIS_FUTURES_MARKET", "real").lower() == "real",
    )
    auth = KISAuthManager(auth_config)
    client = KISClient(config=auth_config, auth_manager=auth)
    try:
        positions = await client.get_futures_balance(
            account_no=os.environ.get("KIS_FUTURES_ACCOUNT_NO", "")
        )
    finally:
        await client.close()
    # Filter zero-quantity entries (closed positions still appear in some KIS responses)
    return [p for p in positions if int(p.get("quantity", 0)) > 0]


async def _send_telegram(summary: str) -> None:
    try:
        from shared.notification.telegram import TelegramNotifier

        notifier = TelegramNotifier(
            bot_token=os.environ.get("TELEGRAM_FUTURES_BOT_TOKEN", ""),
            chat_id=os.environ.get("TELEGRAM_FUTURES_CHAT_ID", ""),
        )
        await notifier.send_message(summary, is_critical=True)
    except Exception:
        logger.exception("Telegram alert failed")


async def _build_and_run(args: argparse.Namespace) -> int:
    redis_positions = await _fetch_redis_positions()
    logger.info("Redis reports %d open futures positions", len(redis_positions))
    try:
        broker_positions = await _fetch_broker_positions()
    except Exception:
        logger.exception("Broker query failed — refusing to start without confirmation")
        return 4
    logger.info("Broker reports %d open futures positions", len(broker_positions))

    broker_only, redis_only, mismatched = reconcile(redis_positions, broker_positions)
    if not broker_only and not redis_only and not mismatched:
        logger.info("Position state coherent — order_router may start.")
        return 0

    sentinel_path = _resolve_sentinel_path(args.sentinel_path)
    write_sentinel(
        sentinel_path,
        broker_only=broker_only,
        redis_only=redis_only,
        mismatched=mismatched,
    )

    summary_parts = ["POSITION RECOVERY: divergence detected — order_router blocked."]
    if broker_only:
        summary_parts.append(f"  broker-only: {len(broker_only)} positions")
        for p in broker_only:
            summary_parts.append(f"    {p.symbol} {p.side} qty={p.quantity}")
    if redis_only:
        summary_parts.append(f"  redis-only: {len(redis_only)} positions")
        for p in redis_only:
            summary_parts.append(f"    {p.symbol} {p.side} qty={p.quantity}")
    if mismatched:
        summary_parts.append(f"  mismatched: {len(mismatched)}")
        for rp, bp in mismatched:
            summary_parts.append(
                f"    {rp.symbol} redis={rp.side}/{rp.quantity} broker={bp.side}/{bp.quantity}"
            )
    summary = "\n".join(summary_parts)
    logger.warning("\n%s", summary)
    await _send_telegram(summary)
    return 3


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sentinel-path",
        default=None,
        help=f"Override sentinel file path (default: {DEFAULT_SENTINEL_PATH})",
    )
    args = parser.parse_args()
    return asyncio.run(_build_and_run(args))


if __name__ == "__main__":
    sys.exit(main())
