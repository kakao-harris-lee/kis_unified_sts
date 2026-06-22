"""Stock exit daemon entrypoint (flag-gated, shadow-first, default-off).

off (default): inert — log + close redis + return 0, constructing nothing.
shadow/live:   full wiring to mode-appropriate order.fill.stock stream.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket

logger = logging.getLogger(__name__)


def _resolve_mode() -> str:
    """Return the daemon mode from the env var (default 'off')."""
    return os.getenv("STOCK_EXIT_DAEMON", "off").strip().lower()


def _is_active_mode(mode: str) -> bool:
    """Return True when the daemon should run."""
    return mode in {"shadow", "live"}


def _fill_stream_for(mode: str) -> str:
    """shadow -> suffixed exit-fill stream; live -> unsuffixed."""
    return "order.fill.stock.shadow" if mode == "shadow" else "order.fill.stock"


async def _build_and_run() -> int:
    import signal as signal_mod

    import redis.asyncio as aioredis

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url)

    mode = _resolve_mode()
    if not _is_active_mode(mode):
        logger.info("STOCK_EXIT_DAEMON=%s (off) — daemon inert, exiting", mode)
        await redis_client.aclose()
        return 0

    from services.stock_exit.daemon import StockExitDaemon
    from services.trading.stream_consumer_feed import StreamConsumerFeed
    from shared.config.loader import ConfigLoader
    from shared.execution.fill_logger import FillLogger
    from shared.paper.broker import VirtualBroker
    from shared.risk.runtime_state import RuntimeRiskState
    from shared.storage import SQLiteRuntimeLedger
    from shared.storage.config import StorageConfig
    from shared.strategy.exit.three_stage import ThreeStageExit, ThreeStageExitConfig
    from shared.streaming.stock_bear_override import BearOverrideConfig
    from shared.streaming.stock_keys import stock_daemon_positions_key
    from shared.streaming.stock_regime import StockRegimeConfig

    raw = ConfigLoader.load("stock_exit.yaml").get("stock_exit", {})
    exit_strategy = ThreeStageExit(ThreeStageExitConfig.from_dict(raw))

    tick_stream = os.environ.get("STOCK_TICK_STREAM", "market:ticks")
    feed = StreamConsumerFeed(redis=redis_client, stream=tick_stream)

    fill_stream = os.environ.get("STOCK_FILL_STREAM", _fill_stream_for(mode))
    positions_key = stock_daemon_positions_key()
    interval = float(os.environ.get("STOCK_EXIT_INTERVAL", "5"))

    runtime_ledger = None
    storage_config = StorageConfig.load_or_default()
    if storage_config.runtime_storage.backend == "sqlite":
        runtime_ledger = SQLiteRuntimeLedger(storage_config.runtime_storage.sqlite)

    fill_logger = FillLogger(
        redis=redis_client,
        archive_client=None,
        stream=fill_stream,
        maxlen=10_000,
        batch_size=10,
        runtime_ledger=runtime_ledger,
        asset_class="stock",
    )
    slippage_rate = float(os.environ.get("STOCK_PAPER_SLIPPAGE_RATE", "0.0001"))
    broker = VirtualBroker(slippage_rate=slippage_rate)
    runtime_state = RuntimeRiskState(redis=redis_client, asset_class="stock")

    # Regime consumer for bear exit (None when disabled → market_state=None).
    regime_config = StockRegimeConfig.load()
    if not regime_config.enabled:
        regime_config = None

    # Bear override consumer (None-equivalent when disabled → override=∅).
    bear_override_config = BearOverrideConfig.load()
    if not bear_override_config.enabled:
        bear_override_config = None

    daemon = StockExitDaemon(
        redis=redis_client,
        feed=feed,
        exit_strategy=exit_strategy,
        broker=broker,
        fill_logger=fill_logger,
        runtime_state=runtime_state,
        positions_key=positions_key,
        interval_seconds=interval,
        regime_config=regime_config,
        runtime_ledger=runtime_ledger,
        bear_override_config=bear_override_config,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    worker_id = f"stock-exit-{socket.gethostname()}-{os.getpid()}"
    logger.info(
        "stock exit daemon starting worker=%s interval=%.1fs", worker_id, interval
    )
    try:
        await daemon.run()
    finally:
        await fill_logger.flush()
        await redis_client.aclose()
        if runtime_ledger is not None:
            runtime_ledger.close()
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
