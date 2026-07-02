"""Stock strategy daemon entrypoint (flag-gated, shadow-first).

Default-off: STOCK_STRATEGY_DAEMON env var must be set to ``shadow`` or ``live`` to
activate. Compose keeps the service profile-gated; no live impact on merge.

Flag routing:
  off (default / unset) — inert: log + close redis + return 0, no objects
                          constructed.
  shadow                — full wiring: StreamConsumerFeed + StreamingIndicatorEngine
                          + StrategyManager + StockStrategyDaemon, publishing to
                          signal.candidate.stock.shadow.
  live                  — same wiring, publishing to signal.candidate.stock.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any

from shared.config.runtime_defaults import redis_url_from_env
from shared.streaming.candle_warmup import StockPrewarmConfig, warmup_engine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prewarm factory — module-level so tests can monkeypatch `warmup_engine`
# ---------------------------------------------------------------------------


def build_prewarm_fn(*, engine, store, kis_client, cfg: StockPrewarmConfig):
    """Return an async ``prewarm_fn(symbol)`` bound to engine/store/kis_client/cfg."""

    async def _prewarm(symbol: str):
        return await warmup_engine(
            engine, symbol, store=store, kis_client=kis_client, config=cfg
        )

    return _prewarm


# ---------------------------------------------------------------------------
# Flag helpers — module-level so tests can import them directly
# ---------------------------------------------------------------------------


def _resolve_mode() -> str:
    """Return the daemon mode from the env var (default 'off')."""
    return os.getenv("STOCK_STRATEGY_DAEMON", "off").strip().lower()


def _is_active_mode(mode: str) -> bool:
    """Return True when the daemon should run."""
    return mode in {"shadow", "live"}


def _candidate_stream_for(mode: str) -> str:
    """Map a mode string to the Redis stream name for signal candidates.

    shadow → isolated shadow stream (not consumed by risk_filter).

    live → unsuffixed stream consumed by the live risk_filter pipeline.
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
    shadow/live: full wiring to mode-appropriate candidate stream.
    """
    import signal as signal_mod

    import redis.asyncio as aioredis

    redis_url = redis_url_from_env()
    redis_client = aioredis.from_url(redis_url)

    mode = _resolve_mode()

    if not _is_active_mode(mode):
        # off branch: completely inert — no engine, no feed, no manager.
        logger.info("STOCK_STRATEGY_DAEMON=%s (off) — daemon inert, exiting", mode)
        await redis_client.aclose()
        return 0

    # active mode: wire everything up.
    from services.stock_strategy.daemon import (
        LLMDiscoverySignalConfig,
        StockStrategyDaemon,
    )
    from services.stock_strategy.market_risk import MarketRiskGateWiringConfig
    from services.trading.indicator_engine import StreamingIndicatorEngine
    from services.trading.strategy_manager import StrategyManager
    from services.trading.stream_consumer_feed import StreamConsumerFeed
    from shared.config.loader import ConfigLoader
    from shared.indicators.contracts import IndicatorContract
    from shared.indicators.resolver import StreamingIndicatorResolver
    from shared.risk.market_risk_gate import MarketRiskGateConfig
    from shared.storage.config import StorageConfig
    from shared.storage.market_data_store import ParquetMarketDataStore
    from shared.streaming.client import RedisClient
    from shared.streaming.stock_bear_override import BearOverrideConfig
    from shared.streaming.stock_regime import StockRegimeConfig
    from shared.streaming.stock_signal_eval import StockSignalEvalConfig

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

    # Sync redis for universe reads (decode_responses=True so get() → str).
    sync_redis = RedisClient.get_client()
    watchlist_key = os.environ.get(
        "STOCK_WATCHLIST_KEY", "system:daily_watchlist:latest"
    )
    trade_targets_key = os.environ.get(
        "TRADE_TARGETS_LATEST_KEY", "system:trade_targets:latest"
    )
    effective_universe_key = os.environ.get(
        "STOCK_EFFECTIVE_UNIVERSE_KEY", "stock:universe:effective:latest"
    )
    overrides_key = os.environ.get(
        "STOCK_UNIVERSE_OVERRIDES_KEY", "stock:universe:overrides"
    )
    _max_symbols = int(os.environ.get("STOCK_MAX_SYMBOLS", "40"))

    from services.stock_strategy.universe import (
        build_effective_watchlist,
        parse_watchlist_codes,
    )

    def _watchlist_reader() -> Any:
        # Universe = managed effective entry universe when available, otherwise
        # daily-watchlist (scanner) ∪ trade_targets (screener) plus manual
        # include/exclude overrides. market-ingest reads the same effective key.
        return build_effective_watchlist(
            watchlist_raw=sync_redis.get(watchlist_key),
            trade_targets_raw=sync_redis.get(trade_targets_key),
            overrides_raw=sync_redis.get(overrides_key),
            effective_raw=sync_redis.get(effective_universe_key),
            max_symbols=_max_symbols,
        )

    # Build KIS client for prewarm REST tier (stock-specific real creds).
    from shared.kis import KISAuthConfig
    from shared.kis.client import KISClient

    kis_config = KISAuthConfig(
        app_key=os.environ.get("KIS_STOCK_APP_KEY", ""),
        app_secret=os.environ.get("KIS_STOCK_APP_SECRET", ""),
        is_real=os.environ.get("KIS_STOCK_MARKET", "mock").lower() == "real",
    )
    kis_client = KISClient(kis_config)

    prewarm_cfg = StockPrewarmConfig.load()
    prewarm_fn = build_prewarm_fn(
        engine=engine, store=store, kis_client=kis_client, cfg=prewarm_cfg
    )

    # Unified startup seed via prewarm_fn (same path as intraday prewarm).
    initial_codes = parse_watchlist_codes(_watchlist_reader(), max_symbols=_max_symbols)
    for sym in initial_codes:
        await prewarm_fn(sym)

    # Market-regime publisher for M4-X's bear exit (None when disabled).
    regime_config = StockRegimeConfig.load()
    if not regime_config.enabled:
        regime_config = None

    # Bear override config for M4-P entry override (None when disabled).
    bear_override_config = BearOverrideConfig.load()
    # The DailyScanner Redis key is owned by the bear-override config but is also
    # the source for the daily-indicator merge — capture it before the config is
    # nulled so the merge works even when the bear override itself is disabled.
    daily_indicators_key = bear_override_config.daily_indicators_key
    if not bear_override_config.enabled:
        bear_override_config = None

    # Per-(symbol, strategy) signal-eval observability (default ON). Read-only
    # telemetry → publishes the "why 0 signals" table to stock:daemon:signal_eval.
    signal_eval_config = StockSignalEvalConfig.load()
    llm_signal_config = LLMDiscoverySignalConfig.from_env()

    # Market-risk ENTRY gate (unified roadmap Phase 2C). The single
    # off/shadow/enforce switch is config/market_risk_gate.yaml::mode — no
    # M4-P-side on/off duplicate. Both configs are loaded ONCE here (never on
    # the hot path); the per-cycle Redis hash read happens inside the shared
    # evaluator through the sync client (the gate's contract is a sync
    # hgetall, which the async candidate-stream client cannot serve).
    market_risk_gate_config = MarketRiskGateConfig.load_or_default()
    market_risk_wiring = MarketRiskGateWiringConfig.load()

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
        regime_config=regime_config,
        bear_override_config=bear_override_config,
        daily_indicators_key=daily_indicators_key,
        signal_eval_config=signal_eval_config,
        llm_signal_config=llm_signal_config,
        market_risk_gate_config=market_risk_gate_config,
        market_risk_gate_redis=sync_redis,
        market_risk_wiring=market_risk_wiring,
        prewarm_fn=prewarm_fn,
        max_prewarm_per_cycle=prewarm_cfg.max_prewarm_per_cycle,
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
