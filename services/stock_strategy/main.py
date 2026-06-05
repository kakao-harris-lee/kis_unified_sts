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
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Flag helpers — module-level so tests can import them directly
# ---------------------------------------------------------------------------


def _resolve_mode() -> str:
    """Return the daemon mode from the env var (default 'off')."""
    return os.getenv("STOCK_STRATEGY_DAEMON", "off").strip().lower()


def _candidate_stream_for(mode: str) -> str:
    """Map a mode string to the Redis stream name for signal candidates.

    shadow → isolated shadow stream (not consumed by risk_filter); any other
    value (off) → the real candidate stream.
    """
    return (
        "signal.candidate.stock.shadow"
        if mode == "shadow"
        else "signal.candidate.stock"
    )


# ---------------------------------------------------------------------------
# Parquet warmup helper
# ---------------------------------------------------------------------------


def _warmup_engine_from_parquet(
    engine: Any, store: Any, symbol: str, lookback_minutes: int = 240
) -> None:
    """Seed the engine's 1-min candles from parquet so it is warm at startup.

    Best-effort: on any read error the engine simply warms from live ticks.

    Mirrors services/decision_engine/main.py with asset_class="stock".
    ParquetMarketDataStore orders ASC; a bare limit=N would return the OLDEST N
    bars, so we fetch with a recency bound then take the tail (fixed in #414).
    """
    start_bound = (datetime.now(UTC) - timedelta(days=5)).date().isoformat()
    try:
        df = store.get_minute_bars(symbol, start=start_bound)
    except Exception:
        logger.warning(
            "parquet warmup read failed for %s; warming from live ticks", symbol
        )
        return
    if df is None or len(df) == 0:
        return
    df = df.iloc[-lookback_minutes:]
    candles = [
        {
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": float(r.get("volume", 0) or 0),
        }
        for _, r in df.iterrows()
    ]
    engine.seed_candles(symbol, candles)


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
    from shared.indicators.resolver import StreamingIndicatorResolver
    from shared.storage.config import StorageConfig
    from shared.storage.market_data_store import ParquetMarketDataStore
    from shared.streaming.client import RedisClient

    candidate_stream = _candidate_stream_for(mode)

    engine = StreamingIndicatorEngine()

    # Cold-start warmup from parquet (best-effort, stock asset class).
    store = ParquetMarketDataStore(
        StorageConfig.load_or_default().market_data.parquet.root,
        asset_class="stock",
    )

    manager = StrategyManager(asset_class="stock", indicator_engine=engine)
    manager.set_indicator_engine(engine)
    resolver = StreamingIndicatorResolver(
        engine=engine,
        required_keys=tuple(manager.required_indicators),
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
            _warmup_engine_from_parquet(engine, store, sym)

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
