#!/usr/bin/env python
"""Emergency flat-all — Phase 5 Task 4 / spec §6.2 step 1.

CLI entrypoint that closes every open futures position via market orders.
Required confirmation: ``--confirm`` flag (matches the project convention
referenced in `docs/plans/2026-04-20-futures-paradigm-phase5-rollout.md`
§6.2: "sts futures flatten-all --confirm").

Without ``--confirm`` the script prints a dry-run summary of what it
WOULD do and exits 0. With ``--confirm`` it actually issues market-close
orders by calling ``ForceCloseExecutor.close_for_kill_switch`` per
position.

Designed for two callers:
  - operator: ``python -m scripts.trading.flatten_all --confirm`` during
    incident response
  - kill_switch daemon's ``force_close_callback``: in-process function call
    via ``flatten_all_async()``
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger(__name__)


def _build_open_positions(broker_positions: list[dict[str, Any]]):
    """Convert KIS futures balance entries to OpenPosition.

    Pure-functional helper extracted for unit testability — the live
    KIS query happens elsewhere.
    """
    from shared.execution.contract_spec import (
        ContractSpecRegistry,
        resolve_contract_spec,
    )
    from shared.execution.force_close import OpenPosition

    registry = ContractSpecRegistry.from_yaml("config/execution.yaml")

    positions: list[OpenPosition] = []
    for p in broker_positions:
        qty = int(p.get("quantity", 0))
        if qty <= 0:
            continue
        symbol = str(p.get("code", p.get("symbol", "")))
        if not symbol:
            continue
        side_raw = str(p.get("side", "")).lower()
        if side_raw in ("buy", "long", "2"):
            direction = "long"
        elif side_raw in ("sell", "short", "1"):
            direction = "short"
        else:
            logger.warning("unknown side %r for %s — skipping", side_raw, symbol)
            continue
        try:
            spec = resolve_contract_spec(symbol, registry)
        except ValueError:
            logger.warning("no contract spec for symbol %s — skipping", symbol)
            continue
        positions.append(
            OpenPosition(
                signal_id=f"flatten-{symbol}",
                symbol=symbol,
                direction=direction,
                quantity=qty,
                entry_price=float(p.get("avg_price", 0.0)),
                tick_size_points=spec.tick_size_points,
            )
        )
    return positions


def render_dry_run(positions: list) -> str:
    if not positions:
        return "DRY-RUN: no open positions; nothing to flatten."
    lines = [f"DRY-RUN: would flatten {len(positions)} position(s):"]
    for p in positions:
        lines.append(
            f"  {p.symbol} {p.direction} qty={p.quantity} "
            f"entry={p.entry_price:.2f} tick={p.tick_size_points}"
        )
    lines.append("\nRe-run with --confirm to actually issue market-close orders.")
    return "\n".join(lines)


async def flatten_all_async(
    *,
    broker_positions: list[dict[str, Any]],
    force_close_executor: Any,
    reason: str,
    now_ms: int,
) -> list[Any]:
    """Issue market-close for every position; return per-position OrderResults.

    Designed to be called either from CLI ``main`` (with the live KIS
    fetch) or from kill_switch's force_close_callback. The
    ``broker_positions`` list comes from ``KISClient.get_futures_balance``
    OR can be a pre-fetched snapshot (e.g. test fixture).
    """
    positions = _build_open_positions(broker_positions)
    results = []
    for pos in positions:
        try:
            result = await force_close_executor.close_for_kill_switch(
                position=pos, reason=reason, now_ms=now_ms
            )
            results.append((pos, result))
        except Exception:
            logger.exception("flatten failed for %s", pos.symbol)
            results.append((pos, None))
    return results


def render_confirmed_summary(results: list) -> str:
    if not results:
        return "CONFIRMED: no positions to flatten."
    lines = [f"CONFIRMED: issued {len(results)} market-close order(s):"]
    for pos, result in results:
        status = "FAILED" if result is None else result.state.value.upper()
        lines.append(f"  {pos.symbol} {pos.direction} qty={pos.quantity}: {status}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI runner
# ---------------------------------------------------------------------------


async def _build_and_run(args: argparse.Namespace) -> int:
    import time

    import redis.asyncio as aioredis

    from shared.execution.config import ExecutionConfig
    from shared.execution.executor import OrderExecutor
    from shared.execution.fill_logger import FillLogger
    from shared.execution.force_close import ForceCloseExecutor
    from shared.execution.kis_futures_adapter import KISFuturesAdapter
    from shared.kis.auth import KISAuthConfig
    from shared.kis.client import KISClient
    from shared.kis.futures_feed import KISFuturesPriceFeed

    # Fetch broker positions
    auth_config = KISAuthConfig(
        app_key=os.environ.get("KIS_FUTURES_APP_KEY", ""),
        app_secret=os.environ.get("KIS_FUTURES_APP_SECRET", ""),
        is_real=os.environ.get("KIS_FUTURES_MARKET", "real").lower() == "real",
    )
    # KISClient builds/reuses its own KISAuthManager singleton from config
    # (KISAuthManager.get_instance(config)); it takes config only.
    kis_client = KISClient(config=auth_config)
    try:
        broker_positions = await kis_client.get_futures_balance(
            account_no=os.environ.get("KIS_FUTURES_ACCOUNT_NO", "")
        )
    finally:
        await kis_client.close()

    positions = _build_open_positions(broker_positions)

    if not args.confirm:
        print(render_dry_run(positions))
        return 0

    if not positions:
        print("CONFIRMED: no positions to flatten.")
        return 0

    # Wire executors
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url)

    fill_logger = FillLogger(redis=redis_client, archive_client=None)

    # ConfigLoader path matches services.order_router.main wiring
    from shared.config.loader import ConfigLoader

    execution_section = ConfigLoader.load("execution.yaml").get("execution", {})
    execution_config = ExecutionConfig(**execution_section)
    order_executor = OrderExecutor(execution_config)
    await order_executor.initialize()

    feed = KISFuturesPriceFeed(config=auth_config)
    feed.update_symbols([p.symbol for p in positions])
    await feed.start()

    adapter = KISFuturesAdapter(order_executor=order_executor, futures_price_feed=feed)
    force_close = ForceCloseExecutor(kis_client=adapter, fill_logger=fill_logger)

    try:
        results = await flatten_all_async(
            broker_positions=broker_positions,
            force_close_executor=force_close,
            reason=args.reason,
            now_ms=int(time.time() * 1000),
        )
    finally:
        await fill_logger.flush()
        await feed.stop()
        await redis_client.aclose()

    print(render_confirmed_summary(results))
    fail_count = sum(1 for _, r in results if r is None or not r.is_filled)
    return 0 if fail_count == 0 else 5


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required to actually issue market-close orders. Without this, "
        "the script prints a dry-run summary and exits 0.",
    )
    parser.add_argument(
        "--reason",
        default="operator_flatten_all",
        help="Reason recorded on each fill row (audit trail).",
    )
    args = parser.parse_args()
    return asyncio.run(_build_and_run(args))


if __name__ == "__main__":
    sys.exit(main())
