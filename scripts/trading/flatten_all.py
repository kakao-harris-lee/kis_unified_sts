#!/usr/bin/env python
"""Emergency flat-all — Phase 5 Task 4 / spec §6.2 step 1.

CLI entrypoint that closes every open futures position via market orders.
Required confirmation: ``--confirm`` flag (matches the project convention
referenced in `docs/plans/2026-04-20-futures-paradigm-phase5-rollout.md`
§6.2: "sts futures flatten-all --confirm").

Without ``--confirm`` the script prints a dry-run summary of what it
WOULD do and exits 0. With ``--confirm`` it actually issues market-close
orders by calling ``ForceCloseExecutor.close_for_kill_switch`` per
position — but only when ``--live`` also matches the resolved executor
trading mode (see below); a mismatch aborts before any KIS client is
constructed.

``--live`` (default off) must be given, together with ``--confirm``,
exactly when ``config/execution.yaml::execution.trading_mode`` (driven by
the ``TRADING_MODE`` env var — ``FUTURES_EXECUTOR_TRADING_MODE`` in
compose) resolves to something other than ``PAPER``. This is the SAME
trading-mode resolution ``OrderExecutor`` itself uses to decide whether an
order is simulated or sent to the real KIS futures endpoint
(``shared/execution/executor.py::_send_order``) — reused here rather than
re-derived. It is a different axis from ``KIS_FUTURES_MARKET``, which only
selects which KIS endpoint the (GET-only) balance read talks to; a paper
deployment routinely sets ``KIS_FUTURES_MARKET=real`` because KIS's mock
server serves no futures data at all, so that variable must never gate
real order placement.

Exit codes:
  - 0 — success (dry-run listed, or confirmed flatten with no failures).
  - 2 — configuration error: ``KIS_FUTURES_MARKET`` unset/unrecognized,
    ``--live``/``--confirm`` do not match the resolved trading mode,
    ``config/execution.yaml`` is missing/malformed, or the loaded section
    fails ``ExecutionConfig`` validation. No KIS client is constructed and
    no order is placed.
  - 5 — confirmed run completed but at least one position failed to flatten.

Designed for two callers:
  - operator: ``python -m scripts.trading.flatten_all --confirm`` during
    incident response (add ``--live`` only when trading_mode is not PAPER)
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

from pydantic import ValidationError

from shared.config.loader import ConfigError
from shared.exceptions import ConfigurationError

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
    confirm: bool,
) -> list[Any] | str:
    """Issue market-close for every position; return per-position OrderResults.

    Designed to be called either from CLI ``main`` (with the live KIS
    fetch) or from kill_switch's force_close_callback. The
    ``broker_positions`` list comes from ``KISClient.get_futures_balance``
    OR can be a pre-fetched snapshot (e.g. test fixture).

    ``confirm`` is keyword-only with no default — this in-process seam
    previously had no confirm gate at all (LEGACY-006 register gap), so a
    caller must decide explicitly rather than a default silently choosing
    "send real orders". When ``confirm`` is False, no order is placed
    (``force_close_executor`` is never invoked) and the dry-run summary
    string is returned instead of per-position results.
    """
    positions = _build_open_positions(broker_positions)
    if not confirm:
        return render_dry_run(positions)
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

    from shared.config.loader import ConfigLoader
    from shared.execution.config import ExecutionConfig, TradingMode
    from shared.execution.executor import OrderExecutor
    from shared.execution.fill_logger import FillLogger
    from shared.execution.force_close import ForceCloseExecutor
    from shared.execution.futures_instrument import resolve_futures_market_from_env
    from shared.execution.kis_futures_adapter import KISFuturesAdapter
    from shared.kis.auth import KISAuthConfig
    from shared.kis.client import KISClient
    from shared.kis.futures_feed import KISFuturesPriceFeed

    # Resolve the SAME trading-mode value OrderExecutor itself uses to decide
    # real vs simulated order placement (shared/execution/executor.py::
    # _send_order — anything other than PAPER sends a real KIS order; for
    # futures specifically, MOCK is routed to the real endpoint too since
    # KIS's mock server serves no futures order path at all). Reused, not
    # re-derived — this ExecutionConfig is also what OrderExecutor gets wired
    # with below when the run proceeds.
    execution_section = ConfigLoader.load("execution.yaml").get("execution", {})
    execution_config = ExecutionConfig(**execution_section)
    is_live_trading_mode = (
        execution_config.trading_mode.upper() != TradingMode.PAPER.value
    )

    # Sending real orders requires BOTH --confirm AND --live, and only when
    # --live matches the resolved trading_mode — no silent default in either
    # direction (CLAUDE.md: real futures order paths are policy-blocked; the
    # real account is never funded). This check runs before ANY KIS client
    # is constructed, including the GET-only balance read below — cheap and
    # first. KIS_FUTURES_MARKET is deliberately NOT part of this gate: it
    # only selects the market-DATA endpoint (a paper deployment routinely
    # sets it to "real" because KIS's mock server serves no futures data),
    # so keying real-order placement off it would abort every paper
    # --confirm run and teach the operator the wrong fix.
    if args.confirm and is_live_trading_mode != args.live:
        print(
            "ABORT: execution.yaml trading_mode resolves to "
            f"{execution_config.trading_mode!r} (env TRADING_MODE, mapped "
            f"from FUTURES_EXECUTOR_TRADING_MODE in compose) but "
            f"--live={args.live!r} was given. Sending real orders requires "
            "--confirm AND --live together, matching a non-PAPER "
            "trading_mode; refusing to proceed with a mismatched mode. No "
            "KIS client was constructed and no order was placed.",
            file=sys.stderr,
        )
        return 2

    # No silent default: an unset/unrecognized KIS_FUTURES_MARKET raises
    # ConfigurationError rather than resolving to the real endpoint. This
    # only selects the market-DATA endpoint for the balance read below —
    # real-order placement is gated by trading_mode above, not this.
    env_market = resolve_futures_market_from_env()
    is_real_data = env_market == "real"

    # Fetch broker positions. A real (is_real=True) client is only used for
    # this GET-only balance read here, which CLAUDE.md allows.
    auth_config = KISAuthConfig(
        app_key=os.environ.get("KIS_FUTURES_APP_KEY", ""),
        app_secret=os.environ.get("KIS_FUTURES_APP_SECRET", ""),
        is_real=is_real_data,
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

    # execution_config was already resolved above (for the live-mode gate) —
    # reused here rather than reloading/reconstructing it.
    order_executor = OrderExecutor(execution_config)
    await order_executor.initialize()

    feed = KISFuturesPriceFeed(config=auth_config)
    feed.update_symbols([p.symbol for p in positions])
    await feed.start()

    adapter = KISFuturesAdapter(order_executor=order_executor, futures_price_feed=feed)
    force_close = ForceCloseExecutor(kis_client=adapter, fill_logger=fill_logger)

    try:
        # confirm=True here — the trading_mode/--live real-order gate above
        # has already run, so it is safe for this seam to place orders.
        results = await flatten_all_async(
            broker_positions=broker_positions,
            force_close_executor=force_close,
            reason=args.reason,
            now_ms=int(time.time() * 1000),
            confirm=True,
        )
    finally:
        await fill_logger.flush()
        await feed.stop()
        await redis_client.aclose()

    assert isinstance(results, list)  # confirm=True never returns the str summary
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
        "--live",
        action="store_true",
        help="Confirms the operator intends real-money order placement. "
        "Off (paper) by default. Sending real orders requires BOTH "
        "--confirm AND --live, and only proceeds when this matches the "
        "resolved execution.yaml trading_mode (TRADING_MODE env / compose "
        "FUTURES_EXECUTOR_TRADING_MODE) — NOT the KIS_FUTURES_MARKET data "
        "endpoint, which is unrelated to real order placement.",
    )
    parser.add_argument(
        "--reason",
        default="operator_flatten_all",
        help="Reason recorded on each fill row (audit trail).",
    )
    args = parser.parse_args()
    try:
        return asyncio.run(_build_and_run(args))
    except (ConfigurationError, ConfigError, ValidationError) as e:
        # ConfigurationError: KIS_FUTURES_MARKET unset/unrecognized.
        # ConfigError (and its ConfigNotFoundError/ConfigValidationError
        # subclasses): ConfigLoader.load("execution.yaml") — the first
        # thing _build_and_run does, for the live-mode gate — hit a
        # missing or malformed file. ValidationError: the loaded section
        # failed ExecutionConfig's own pydantic validation (e.g. a
        # malformed account_no). All three are configuration problems, not
        # broker/order failures, so they share exit code 2 rather than
        # tracebacking with a bare exit code 1.
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
