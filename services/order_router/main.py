"""Order-router consumer-group daemon.

Phase 4 Task 12 — reads filtered :class:`Signal`s from
``stream:signal.final``, places passive limit entries via
:class:`PassiveMaker`, and on fill registers a stop+target bracket via
:class:`PseudoOCO`. Fills are logged through :class:`FillLogger` (already
wired into PassiveMaker).

This is the only daemon that holds wallet authority — every other Phase 4
component reads/audits, but the order_router places real orders. The
kill_switch daemon (Task 13) writes a sentinel file on trigger; we honor
it by:

  1. **On startup**: refusing to enter the consume loop when the sentinel
     already exists — the previous trip has not been operator-cleared yet.
  2. **Per loop iteration**: re-checking the sentinel before each
     ``xreadgroup`` so a mid-session trip drains pre-trip messages without
     placing further orders.

Operator clears the sentinel via ``scripts/kill_switch_clear.sh`` before
the next start.

Error taxonomy:
- Parse error                   → XACK (poison-pill drop)
- PassiveMaker raises           → NO XACK (retry — beware of double-fill;
                                  see PR #134 review note on idempotency)
- PseudoOCO.register_bracket    → NO XACK (entry filled but bracket not
                                  registered → caller must reconcile)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta, timezone
from datetime import time as dt_time
from pathlib import Path
from typing import Any

from services.risk_filter.main import _signal_from_stream_fields
from shared.execution.contract_spec import ContractSpec
from shared.execution.live_mode_guard import LiveModeGuard
from shared.execution.passive_maker import PassiveMaker
from shared.execution.pseudo_oco import PseudoOCO
from shared.streaming.stage import StreamStage

logger = logging.getLogger(__name__)

# Phase 5 Gate-3 daily-trade counter lives in Redis under
# `order_router:daily_trades:YYYY-MM-DD` (KST date). Expires at the next
# KST midnight via TTL — restart-safe, multi-worker-safe (INCR is atomic).
_DAILY_TRADE_KEY_PREFIX = "order_router:daily_trades:"
_KST = timezone(timedelta(hours=9))


def _kst_date_key(now: datetime | None = None) -> str:
    """KST-date suffix for the daily-trade counter (e.g. ``2026-05-01``).

    The Phase 5 plan §2.3 daily-trade cap is "per trading day" by Korean
    convention. Using the KST date prevents 09:00–15:30 sessions from
    being split across UTC days.
    """
    ref = now or datetime.now(UTC)
    return ref.astimezone(_KST).date().isoformat()


def _seconds_until_next_kst_midnight(now: datetime | None = None) -> int:
    """TTL for the daily counter — wraps to 0 at next 00:00 KST.

    Caps at 86_400 just in case clock-skew makes the math return >24h.
    Floors at 60 so the counter never expires within the same minute.
    """
    ref = (now or datetime.now(UTC)).astimezone(_KST)
    next_midnight = datetime.combine(
        ref.date() + timedelta(days=1), dt_time.min, tzinfo=_KST
    )
    delta = int((next_midnight - ref).total_seconds())
    return max(60, min(delta, 86_400))


def _resolve_quantity(*, base_quantity: int, size_multiplier: float) -> int:
    """Scale ``base_quantity`` by ``size_multiplier``, floor at 1.

    Risk filter's :class:`ConsecutiveLossFilter` may emit
    ``size_multiplier=0.5`` to halve sizing after a losing streak. With
    ``base_quantity=1`` (current Phase 4 ladder), 0.5 rounds to 0; we floor
    at 1 contract because zero-sized orders are nonsensical and the filter's
    intent is "trade smaller", not "skip the trade" (which would have
    used ``passed=False``).
    """
    scaled = int(round(base_quantity * size_multiplier))
    return max(scaled, 1)


class OrderRouterDaemon(StreamStage):
    def __init__(
        self,
        *,
        redis: Any,
        passive_maker: PassiveMaker,
        pseudo_oco: PseudoOCO,
        contract_spec: ContractSpec,
        final_stream: str,
        consumer_group: str,
        worker_id: str,
        xread_block_ms: int,
        batch_size: int,
        passive_timeout_seconds: int,
        base_quantity: int = 1,
        kill_switch_sentinel_path: str | None = None,
        live_mode_guard: LiveModeGuard | None = None,
        locked_symbol: str | None = None,
    ) -> None:
        super().__init__(
            redis=redis,
            input_stream=final_stream,
            consumer_group=consumer_group,
            worker_id=worker_id,
            xread_block_ms=xread_block_ms,
            batch_size=batch_size,
            xreadgroup_error_sleep_seconds=0.5,
        )
        self.passive_maker = passive_maker
        self.pseudo_oco = pseudo_oco
        self.contract_spec = contract_spec
        self.passive_timeout_seconds = passive_timeout_seconds
        self.base_quantity = base_quantity
        self.sentinel_path = (
            Path(kill_switch_sentinel_path) if kill_switch_sentinel_path else None
        )
        self.live_mode_guard = live_mode_guard
        self.locked_symbol = locked_symbol
        self.refused_due_to_sentinel: bool = False
        self.live_suspended_count: int = 0
        # Phase 5 Gate-3 cap counters (observability + tests)
        self.symbol_lock_blocked_count: int = 0
        self.daily_trade_blocked_count: int = 0
        self.position_size_capped_count: int = 0

    def _sentinel_present(self) -> bool:
        return self.sentinel_path is not None and self.sentinel_path.exists()

    async def on_startup(self) -> None:
        # Startup guard: refuse to consume if the kill switch tripped previously
        # and an operator has not yet run scripts/kill_switch_clear.sh.
        if self._sentinel_present():
            self.refused_due_to_sentinel = True
            logger.critical(
                "Kill switch sentinel exists at %s — refusing to start. "
                "Run scripts/kill_switch_clear.sh after operator review.",
                self.sentinel_path,
            )
            self._stop.set()  # prevent the consume loop from running any iteration

    async def pre_iteration_gate(self) -> bool:
        # Per-iteration guard: a mid-session trip must drain pre-trip messages
        # without placing further orders.
        if self._sentinel_present():
            self.refused_due_to_sentinel = True
            logger.critical(
                "Kill switch sentinel appeared at %s during run; exiting.",
                self.sentinel_path,
            )
            return False
        return True

    async def handle_message(
        self, msg_id: bytes, fields: dict[bytes, bytes]  # noqa: ARG002
    ) -> bool:
        try:
            signal_id, signal = _signal_from_stream_fields(fields)
            size_multiplier = float(
                fields.get(b"size_multiplier", b"1.0").decode(errors="replace") or 1.0
            )
        except Exception:
            logger.exception("Unparseable final signal; ACK as poison-pill")
            return True  # poison-pill: consume

        quantity = _resolve_quantity(
            base_quantity=self.base_quantity, size_multiplier=size_multiplier
        )

        if (
            self.live_mode_guard is not None
            and await self.live_mode_guard.is_live_suspended(self.redis)
        ):
            self.live_suspended_count += 1
            logger.warning(
                "live_mode suspended; skipping signal_id=%s symbol=%s",
                signal_id,
                signal.symbol,
            )
            return True  # skip (consumed, no retry)

        guard = self.live_mode_guard

        if (
            guard is not None
            and guard.symbol_lock_enabled
            and self.locked_symbol is not None
            and signal.symbol != self.locked_symbol
        ):
            self.symbol_lock_blocked_count += 1
            logger.warning(
                "symbol_lock: signal.symbol=%s != locked=%s; skipping signal_id=%s",
                signal.symbol,
                self.locked_symbol,
                signal_id,
            )
            return True  # skip (consumed)

        if guard is not None and quantity > guard.max_position_size_contracts:
            self.position_size_capped_count += 1
            logger.warning(
                "position_size_cap: signal=%s quantity %d → %d (gate3)",
                signal_id,
                quantity,
                guard.max_position_size_contracts,
            )
            quantity = guard.max_position_size_contracts

        if guard is not None:
            counter_key = f"{_DAILY_TRADE_KEY_PREFIX}{_kst_date_key()}"
            try:
                count = await self.redis.incr(counter_key)
                if int(count) == 1:
                    await self.redis.expire(
                        counter_key, _seconds_until_next_kst_midnight()
                    )
            except Exception:
                logger.exception(
                    "daily_trade counter INCR failed; allowing signal_id=%s",
                    signal_id,
                )
            else:
                if int(count) > guard.max_daily_trades:
                    self.daily_trade_blocked_count += 1
                    logger.warning(
                        "daily_trade_cap: count=%d > max=%d; skipping signal_id=%s",
                        int(count),
                        guard.max_daily_trades,
                        signal_id,
                    )
                    return True  # cap hit: skip (consumed)

        try:
            result = await self.passive_maker.place_passive_limit_futures(
                signal=signal,
                signal_id=signal_id,
                quantity=quantity,
                spec=self.contract_spec,
                timeout_seconds=self.passive_timeout_seconds,
            )
        except Exception:
            logger.exception(
                "passive_maker raised signal_id=%s; leaving pending", signal_id
            )
            return False  # leave pending (no XACK)

        if not result.is_filled:
            logger.info(
                "passive limit not filled signal_id=%s reason=%s",
                signal_id,
                result.reason,
            )
            return True  # final state, consumed, no bracket

        try:
            from shared.execution.passive_maker import Fill

            fill = Fill(
                order_id=result.order_id or "",
                price=result.filled_price or 0.0,
                quantity=quantity,
                filled_at_ms=0,
            )
            await self.pseudo_oco.register_bracket(
                signal=signal,
                signal_id=signal_id,
                fill=fill,
                tick_size_points=self.contract_spec.tick_size_points,
            )
        except Exception:
            logger.exception(
                "OCO register failed signal_id=%s order_id=%s; leaving pending",
                signal_id,
                result.order_id,
            )
            return False  # leave pending

        return True  # success: consume


def _resolve_mode() -> str:
    """order_router execution mode: off (default) | paper | live.

    Anything other than ``paper``/``live`` (including unset or empty) resolves
    to the safety-critical default ``off`` so the helper always returns one of
    the three documented modes.
    """
    import os

    mode = os.getenv("FUTURES_ORDER_ROUTER", "off").strip().lower()
    return mode if mode in ("paper", "live") else "off"


def _final_stream_for(mode: str) -> str:
    """Final-signal stream the order_router consumes (F-1).

    paper → `.shadow` isolated stream (forms the shadow pipeline with
    risk_filter shadow); live → unsuffixed. Env-overridable.
    """
    import os

    base = "signal.final.futures.shadow" if mode == "paper" else "signal.final.futures"
    return os.getenv("FUTURES_FINAL_STREAM", base)


def _fill_stream_for(mode: str) -> str:
    """Fill stream FillLogger writes (F-1). paper → `.shadow`; live → unsuffixed."""
    import os

    base = "order.fill.futures.shadow" if mode == "paper" else "order.fill.futures"
    return os.getenv("FUTURES_FILL_STREAM", base)


async def _build_and_run() -> int:
    """Production entrypoint — wires KIS adapter + PassiveMaker + PseudoOCO.

    Phase 4 Task 17 (KIS adapter) + config loaders close the prior PR #135
    "EX_CONFIG stub" deferral. The kill_switch sentinel path is read from
    KillSwitchConfig so the order_router refuses to start under the same
    path the kill_switch daemon writes to.
    """
    import os
    import signal as signal_mod
    import socket

    import redis.asyncio as aioredis

    from services.kill_switch.config import KillSwitchConfig
    from services.order_router.config import Phase4ExecutionConfig
    from shared.collector.historical.futures import get_front_month_code
    from shared.config.loader import ConfigLoader
    from shared.execution.config import ExecutionConfig
    from shared.execution.contract_spec import (
        ContractSpecRegistry,
        resolve_contract_spec,
    )
    from shared.execution.executor import OrderExecutor
    from shared.execution.fill_logger import FillLogger
    from shared.execution.kis_futures_adapter import KISFuturesAdapter
    from shared.execution.live_mode_guard import LiveModeGuard
    from shared.execution.passive_maker import PassiveMaker
    from shared.execution.pseudo_oco import PseudoOCO
    from shared.kis.auth import KISAuthConfig
    from shared.kis.futures_feed import KISFuturesPriceFeed
    from shared.storage import SQLiteRuntimeLedger
    from shared.storage.config import StorageConfig

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url)

    mode = _resolve_mode()
    if mode not in ("paper", "live"):
        logger.info("FUTURES_ORDER_ROUTER=%s (off) — order_router inert, exiting", mode)
        await redis_client.aclose()
        return 0

    runtime_ledger = None
    storage_config = StorageConfig.load_or_default()
    if storage_config.runtime_storage.backend == "sqlite":
        runtime_ledger = SQLiteRuntimeLedger(storage_config.runtime_storage.sqlite)

    phase4_config = Phase4ExecutionConfig.from_yaml()
    kill_config = KillSwitchConfig.from_yaml()
    live_guard = LiveModeGuard.from_yaml()

    contract_specs = ContractSpecRegistry.from_yaml("config/execution.yaml")
    # Auto-detect front-month KOSPI200 mini contract — handles quarterly
    # rollover without code change (CLAUDE.md / MEMORY.md RL Symbol Policy).
    symbol = get_front_month_code(product="mini")
    spec = resolve_contract_spec(symbol, contract_specs)

    fill_logger = FillLogger(
        redis=redis_client,
        archive_client=None,
        stream=_fill_stream_for(mode),
        maxlen=phase4_config.final_stream_maxlen,
        batch_size=10,
        runtime_ledger=runtime_ledger,
        asset_class="futures",
    )

    # Feed is ALWAYS real (both paper AND live): KIS 모의투자 serves no futures
    # realtime feed, so the real WS is the only orderbook source. This drops the
    # old KIS_FUTURES_MARKET gating on the feed — paper mode simulates execution,
    # not data; live order placement remains gated by OrderExecutor.config.trading_mode.
    kis_auth = KISAuthConfig(
        app_key=os.environ.get("KIS_FUTURES_APP_KEY", ""),
        app_secret=os.environ.get("KIS_FUTURES_APP_SECRET", ""),
        is_real=True,
    )
    futures_feed = KISFuturesPriceFeed(config=kis_auth)
    futures_feed.update_symbols([symbol])
    await futures_feed.start()

    if mode == "paper":
        from shared.execution.paper_kis_futures_adapter import PaperKISFuturesAdapter

        kis_adapter: Any = PaperKISFuturesAdapter(futures_price_feed=futures_feed)
        guard_for_daemon = None  # paper places no real orders
        logger.info(
            "order_router PAPER mode — real orderbook, simulated fills, no real orders"
        )
    else:  # live
        execution_section = ConfigLoader.load("execution.yaml").get("execution", {})
        order_executor = OrderExecutor(ExecutionConfig(**execution_section))
        await order_executor.initialize()
        kis_adapter = KISFuturesAdapter(
            order_executor=order_executor,
            futures_price_feed=futures_feed,
        )
        guard_for_daemon = live_guard

    passive_maker = PassiveMaker(kis_client=kis_adapter, fill_logger=fill_logger)
    pseudo_oco = PseudoOCO(fill_logger=fill_logger)

    worker_id = f"order-router-{socket.gethostname()}-{os.getpid()}"
    daemon = OrderRouterDaemon(
        redis=redis_client,
        passive_maker=passive_maker,
        pseudo_oco=pseudo_oco,
        contract_spec=spec,
        final_stream=_final_stream_for(mode),
        consumer_group="order_router",
        worker_id=worker_id,
        xread_block_ms=phase4_config.xread_block_ms,
        batch_size=phase4_config.xread_batch_size,
        passive_timeout_seconds=phase4_config.passive_timeout_seconds,
        base_quantity=phase4_config.base_quantity,
        kill_switch_sentinel_path=kill_config.sentinel_path,
        live_mode_guard=guard_for_daemon,
        locked_symbol=symbol,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        await fill_logger.flush()
        await futures_feed.stop()
        await redis_client.aclose()
        if runtime_ledger is not None:
            runtime_ledger.close()
    return 0


def main() -> int:
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
