"""Stock strategy daemon entrypoint (flag-gated, shadow-first).

Default-off: STOCK_STRATEGY_DAEMON env var must be set to ``shadow`` to
activate.  The systemd unit ships disabled; no live impact on merge.

Flag routing:
  off (default / unset) — inert: log + close redis + return 0, no objects
                          constructed.
  shadow                — full wiring: StreamConsumerFeed + StreamingIndicatorEngine
                          + StrategyManager + StockStrategyDaemon, publishing to
                          signal.candidate.stock.shadow.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any

from shared.streaming.parquet_warmup import warmup_engine_from_parquet

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Flag helpers — module-level so tests can import them directly
# ---------------------------------------------------------------------------


def _resolve_mode() -> str:
    """Return the daemon mode from the env var (default 'off')."""
    return os.getenv("STOCK_STRATEGY_DAEMON", "off").strip().lower()


def _candidate_stream_for(mode: str) -> str:
    """Map a mode string to the Redis stream name for signal candidates.

    shadow → isolated shadow stream (not consumed by risk_filter).

    Note: the ``else`` branch returns the live candidate stream.  The current
    ``off`` path never reaches this function (``_build_and_run`` returns early
    before calling it), so this return value is reserved for a future live
    cutover — the point at which ``STOCK_STRATEGY_DAEMON=live`` (or similar)
    will route signals into the real risk_filter pipeline.
    """
    return (
        "signal.candidate.stock.shadow"
        if mode == "shadow"
        else "signal.candidate.stock"
    )


# ---------------------------------------------------------------------------
# Production entrypoint
# ---------------------------------------------------------------------------


async def _build_and_run() -> int:
    """Flag-gated production entrypoint.

    off / unset: inert — log and return 0, constructing NONE of the
                 engine/feed/manager objects.
    shadow:      full wiring to signal.candidate.stock.shadow.
    """
    import signal as signal_mod

    import redis.asyncio as aioredis

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url)

    mode = _resolve_mode()

    if mode != "shadow":
        # off branch: completely inert — no engine, no feed, no manager.
        logger.info("STOCK_STRATEGY_DAEMON=%s (off) — daemon inert, exiting", mode)
        await redis_client.aclose()
        return 0

    # shadow mode: wire everything up.
    from services.stock_strategy.daemon import StockStrategyDaemon
    from services.trading.indicator_engine import StreamingIndicatorEngine
    from services.trading.strategy_manager import StrategyManager
    from services.trading.stream_consumer_feed import StreamConsumerFeed
    from shared.config.loader import ConfigLoader
    from shared.indicators.contracts import IndicatorContract
    from shared.indicators.resolver import StreamingIndicatorResolver
    from shared.storage.config import StorageConfig
    from shared.storage.market_data_store import ParquetMarketDataStore
    from shared.streaming.client import RedisClient

    candidate_stream = _candidate_stream_for(mode)

    # Build StrategyManager FIRST (no engine arg) so we can read
    # required_indicators to compute the correct MTF warmth gate.
    manager = StrategyManager(asset_class="stock")

    # Read MTF / staleness config from streaming.yaml, mirroring
    # TradingOrchestrator._init_indicator_engine.
    try:
        _ie_cfg = ConfigLoader.load("streaming.yaml").get("indicator_engine", {})
        staleness_seconds = float(_ie_cfg.get("staleness_seconds", 180.0))
        mtf_timeframes = _ie_cfg.get("mtf_timeframes", None)
        mtf_maxlen = int(_ie_cfg.get("mtf_maxlen", 250))
    except Exception:
        staleness_seconds = 180.0
        mtf_timeframes = None
        mtf_maxlen = 250

    # Warmth gate must reflect what the *strategy* needs, not the broad
    # streaming.yaml accumulation set — mirrors orchestrator logic.
    try:
        contract = IndicatorContract.from_required_keys(
            tuple(manager.required_indicators)
        )
        mtf_warmth_timeframe: int | None = contract.warmth_timeframe
    except Exception:
        mtf_warmth_timeframe = None

    engine = StreamingIndicatorEngine(
        mtf_timeframes=mtf_timeframes,
        mtf_maxlen=mtf_maxlen,
        staleness_seconds=staleness_seconds,
        mtf_warmth_timeframe=mtf_warmth_timeframe,
    )

    # Wire engine into manager (single call — no double-set).
    manager.set_indicator_engine(engine)

    resolver = StreamingIndicatorResolver(
        engine=engine,
        required_keys=tuple(manager.required_indicators),
    )

    # Cold-start warmup from parquet (best-effort, stock asset class).
    store = ParquetMarketDataStore(
        StorageConfig.load_or_default().market_data.parquet.root,
        asset_class="stock",
    )

    tick_stream = os.environ.get("STOCK_TICK_STREAM", "market:ticks")
    feed = StreamConsumerFeed(
        redis=redis_client,
        stream=tick_stream,
        indicator_engine=engine,
    )

    # Sync redis for watchlist reads (decode_responses=True so get() → str).
    sync_redis = RedisClient.get_client()
    watchlist_key = os.environ.get(
        "STOCK_WATCHLIST_KEY", "system:daily_watchlist:latest"
    )

    def _watchlist_reader() -> Any:
        return sync_redis.get(watchlist_key)

    # Seed parquet warmup for any symbol already in the watchlist.
    initial_raw = _watchlist_reader()
    if initial_raw:
        from services.stock_strategy.universe import parse_watchlist_codes

        initial_codes = parse_watchlist_codes(
            initial_raw,
            max_symbols=int(os.environ.get("STOCK_MAX_SYMBOLS", "40")),
        )
        for sym in initial_codes:
            warmup_engine_from_parquet(engine, store, sym)

    daemon = StockStrategyDaemon(
        redis=redis_client,
        feed=feed,
        engine=engine,
        resolver=resolver,
        manager=manager,
        candidate_stream=candidate_stream,
        candidate_maxlen=10_000,
        now_fn=lambda: datetime.now(UTC),
        max_symbols=int(os.environ.get("STOCK_MAX_SYMBOLS", "40")),
        watchlist_reader=_watchlist_reader,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        await redis_client.aclose()
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
