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
import contextlib
import logging
from pathlib import Path
from typing import Any

from services.risk_filter.main import _signal_from_stream_fields
from shared.execution.contract_spec import ContractSpec
from shared.execution.live_mode_guard import LiveModeGuard
from shared.execution.passive_maker import PassiveMaker
from shared.execution.pseudo_oco import PseudoOCO

logger = logging.getLogger(__name__)


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


class OrderRouterDaemon:
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
    ) -> None:
        self.redis = redis
        self.passive_maker = passive_maker
        self.pseudo_oco = pseudo_oco
        self.contract_spec = contract_spec
        self.final_stream = final_stream
        self.consumer_group = consumer_group
        self.worker_id = worker_id
        self.xread_block_ms = xread_block_ms
        self.batch_size = batch_size
        self.passive_timeout_seconds = passive_timeout_seconds
        self.base_quantity = base_quantity
        self.sentinel_path = (
            Path(kill_switch_sentinel_path) if kill_switch_sentinel_path else None
        )
        self.live_mode_guard = live_mode_guard
        self._stop = asyncio.Event()
        self.refused_due_to_sentinel: bool = False
        self.live_suspended_count: int = 0

    def _sentinel_present(self) -> bool:
        return self.sentinel_path is not None and self.sentinel_path.exists()

    async def run(self) -> None:
        # Startup guard: refuse to consume if the kill switch tripped previously
        # and an operator has not yet run scripts/kill_switch_clear.sh.
        if self._sentinel_present():
            self.refused_due_to_sentinel = True
            logger.critical(
                "Kill switch sentinel exists at %s — refusing to start. "
                "Run scripts/kill_switch_clear.sh after operator review.",
                self.sentinel_path,
            )
            return

        with contextlib.suppress(Exception):
            await self.redis.xgroup_create(
                self.final_stream, self.consumer_group, id="0", mkstream=True
            )

        while not self._stop.is_set():
            # Per-iteration guard: a mid-session trip must drain pre-trip
            # messages without placing further orders.
            if self._sentinel_present():
                self.refused_due_to_sentinel = True
                logger.critical(
                    "Kill switch sentinel appeared at %s during run; exiting.",
                    self.sentinel_path,
                )
                return

            try:
                messages = await self.redis.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.worker_id,
                    streams={self.final_stream: ">"},
                    count=self.batch_size,
                    block=self.xread_block_ms,
                )
            except Exception:
                logger.exception("xreadgroup error; sleeping 0.5s")
                await asyncio.sleep(0.5)
                continue

            if not messages:
                await asyncio.sleep(0)
                continue

            for _stream, msgs in messages:
                for msg_id, data in msgs:
                    await self._process(msg_id, data)

    async def stop(self) -> None:
        self._stop.set()

    async def _process(self, msg_id: bytes, fields: dict[bytes, bytes]) -> None:
        try:
            signal_id, signal = _signal_from_stream_fields(fields)
            size_multiplier = float(
                fields.get(b"size_multiplier", b"1.0").decode(errors="replace") or 1.0
            )
        except Exception:
            logger.exception("Unparseable final signal; ACK as poison-pill")
            await self.redis.xack(self.final_stream, self.consumer_group, msg_id)
            return

        quantity = _resolve_quantity(
            base_quantity=self.base_quantity, size_multiplier=size_multiplier
        )

        # Live-mode guard (Phase 5 Task 5): consult BEFORE submitting the
        # order. Suspended → XACK as skip (no retry; the signal is consumed).
        # Disabled-by-default config makes this a no-op until Gate 2 flips
        # `futures_live.enabled: true`.
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
            await self.redis.xack(self.final_stream, self.consumer_group, msg_id)
            return

        # Place passive limit + log fill
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
            return

        if not result.is_filled:
            # Missed (timeout/cancel) — final state, ACK and drop. The signal
            # is consumed; no bracket to register, no retry.
            logger.info(
                "passive limit not filled signal_id=%s reason=%s",
                signal_id,
                result.reason,
            )
            await self.redis.xack(self.final_stream, self.consumer_group, msg_id)
            return

        # Register bracket on the entry fill
        try:
            from shared.execution.passive_maker import Fill

            fill = Fill(
                order_id=result.order_id or "",
                price=result.filled_price or 0.0,
                quantity=quantity,
                filled_at_ms=0,  # bracket cares about handle state, not entry timestamp
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
            return

        await self.redis.xack(self.final_stream, self.consumer_group, msg_id)


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
    from shared.db.client import AsyncClickHouseClient
    from shared.db.config import ClickHouseConfig
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

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url)

    ch_config = ClickHouseConfig.from_env(database="kospi")
    ch_client = AsyncClickHouseClient(ch_config)
    await ch_client.connect()

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
        ch_client=ch_client,
        stream="stream:order.fill",
        maxlen=phase4_config.final_stream_maxlen,
        ch_batch_size=10,  # spec §5.2 — kept here as a buffer-tuning constant
    )

    # ExecutionConfig is a plain Pydantic BaseModel (not ServiceConfigBase),
    # so we go through ConfigLoader → constructor manually.
    execution_section = ConfigLoader.load("execution.yaml").get("execution", {})
    execution_config = ExecutionConfig(**execution_section)
    order_executor = OrderExecutor(execution_config)
    await order_executor.initialize()

    # Futures-side KIS auth — this is the order-placement account.
    kis_auth = KISAuthConfig(
        app_key=os.environ.get("KIS_FUTURES_APP_KEY", ""),
        app_secret=os.environ.get("KIS_FUTURES_APP_SECRET", ""),
        is_real=os.environ.get("KIS_FUTURES_MARKET", "real").lower() == "real",
    )
    futures_feed = KISFuturesPriceFeed(config=kis_auth)
    futures_feed.update_symbols([symbol])
    await futures_feed.start()

    kis_adapter = KISFuturesAdapter(
        order_executor=order_executor,
        futures_price_feed=futures_feed,
    )

    passive_maker = PassiveMaker(kis_client=kis_adapter, fill_logger=fill_logger)
    pseudo_oco = PseudoOCO(fill_logger=fill_logger)

    worker_id = f"order-router-{socket.gethostname()}-{os.getpid()}"
    daemon = OrderRouterDaemon(
        redis=redis_client,
        passive_maker=passive_maker,
        pseudo_oco=pseudo_oco,
        contract_spec=spec,
        final_stream="stream:signal.final",
        consumer_group="order_router",
        worker_id=worker_id,
        xread_block_ms=phase4_config.xread_block_ms,
        batch_size=phase4_config.xread_batch_size,
        passive_timeout_seconds=phase4_config.passive_timeout_seconds,
        base_quantity=phase4_config.base_quantity,
        kill_switch_sentinel_path=kill_config.sentinel_path,
        live_mode_guard=live_guard,
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
        await ch_client.close()
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
