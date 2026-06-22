"""Flag routing for the stock strategy daemon entrypoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import services.stock_strategy.main as m


def test_resolve_mode_default_off(monkeypatch):
    monkeypatch.delenv("STOCK_STRATEGY_DAEMON", raising=False)
    assert m._resolve_mode() == "off"


def test_resolve_mode_shadow(monkeypatch):
    monkeypatch.setenv("STOCK_STRATEGY_DAEMON", "shadow")
    assert m._resolve_mode() == "shadow"
    assert m._candidate_stream_for("shadow") == "signal.candidate.stock.shadow"
    assert m._candidate_stream_for("off") == "signal.candidate.stock"


def test_live_mode_is_active_and_unsuffixed() -> None:
    assert m._is_active_mode("live") is True
    assert m._candidate_stream_for("live") == "signal.candidate.stock"
    assert m._is_active_mode("off") is False


@pytest.mark.asyncio
async def test_build_prewarm_fn_calls_warmup_engine(monkeypatch):
    from services.stock_strategy import main as main_mod
    from shared.streaming.candle_warmup import StockPrewarmConfig, WarmupResult

    seen = {}

    async def _fake_warmup(engine, symbol, *, store, kis_client, config):
        seen["symbol"] = symbol
        seen["config"] = config
        return WarmupResult(120, 252, "parquet")

    monkeypatch.setattr(main_mod, "warmup_engine", _fake_warmup)
    fn = main_mod.build_prewarm_fn(
        engine=object(),
        store=object(),
        kis_client=object(),
        cfg=StockPrewarmConfig(rest_enabled=True),
    )
    res = await fn("000660")
    assert seen["symbol"] == "000660"
    assert seen["config"].rest_enabled is True
    assert res.source == "parquet"


# ---------------------------------------------------------------------------
# bear_override_config wiring tests (Component A gap fix)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daemon_receives_bear_override_config_when_enabled(monkeypatch):
    """When BearOverrideConfig.load() returns enabled=True, daemon gets non-None bear_override_config."""
    from services.stock_strategy import main as main_mod
    from shared.streaming.stock_bear_override import BearOverrideConfig

    monkeypatch.setenv("STOCK_STRATEGY_DAEMON", "shadow")

    captured = {}

    # Stub all heavy imports inside _build_and_run to avoid real I/O.
    fake_daemon_cls = MagicMock()
    fake_daemon_cls.return_value.run = AsyncMock()

    async def fake_aclose():
        pass

    fake_redis = MagicMock()
    fake_redis.aclose = fake_aclose

    with (
        patch("redis.asyncio.from_url", return_value=fake_redis),
        patch("services.stock_strategy.daemon.StockStrategyDaemon", fake_daemon_cls),
        patch(
            "services.stock_strategy.main.StockStrategyDaemon",
            fake_daemon_cls,
            create=True,
        ),
        patch(
            "shared.streaming.stock_bear_override.BearOverrideConfig.load",
            return_value=BearOverrideConfig(enabled=True),
        ),
        patch(
            "shared.streaming.stock_regime.StockRegimeConfig.load",
            return_value=MagicMock(enabled=False),
        ),
        patch(
            "shared.streaming.candle_warmup.StockPrewarmConfig.load",
            return_value=MagicMock(max_prewarm_per_cycle=5),
        ),
        patch(
            "shared.storage.config.StorageConfig.load_or_default",
            return_value=MagicMock(
                market_data=MagicMock(parquet=MagicMock(root="/tmp"))
            ),
        ),
        patch(
            "services.trading.strategy_manager.StrategyManager",
            return_value=MagicMock(
                required_indicators=[], set_indicator_engine=MagicMock()
            ),
        ),
        patch(
            "services.trading.indicator_engine.StreamingIndicatorEngine",
            return_value=MagicMock(),
        ),
        patch(
            "services.trading.stream_consumer_feed.StreamConsumerFeed",
            return_value=MagicMock(),
        ),
        patch(
            "shared.indicators.resolver.StreamingIndicatorResolver",
            return_value=MagicMock(),
        ),
        patch(
            "shared.storage.market_data_store.ParquetMarketDataStore",
            return_value=MagicMock(),
        ),
        patch(
            "shared.streaming.client.RedisClient.get_client",
            return_value=MagicMock(get=MagicMock(return_value=None)),
        ),
        patch("shared.kis.client.KISClient", return_value=MagicMock()),
        patch(
            "shared.indicators.contracts.IndicatorContract.from_required_keys",
            return_value=MagicMock(warmth_timeframe=None),
        ),
        patch("shared.config.loader.ConfigLoader.load", return_value={}),
        patch(
            "services.stock_strategy.universe.merge_screener_universe", return_value=[]
        ),
        patch(
            "services.stock_strategy.universe.parse_watchlist_codes", return_value=[]
        ),
        patch(
            "services.stock_strategy.main.build_prewarm_fn", return_value=AsyncMock()
        ),
    ):
        await main_mod._build_and_run()

    _, kwargs = fake_daemon_cls.call_args
    captured["bear_override_config"] = kwargs.get("bear_override_config")

    assert (
        captured["bear_override_config"] is not None
    ), "bear_override_config must be passed to StockStrategyDaemon when enabled=True"
    assert isinstance(captured["bear_override_config"], BearOverrideConfig)


@pytest.mark.asyncio
async def test_daemon_receives_none_bear_override_config_when_disabled(monkeypatch):
    """When BearOverrideConfig.load() returns enabled=False, daemon gets bear_override_config=None."""
    from services.stock_strategy import main as main_mod
    from shared.streaming.stock_bear_override import BearOverrideConfig

    monkeypatch.setenv("STOCK_STRATEGY_DAEMON", "shadow")

    captured = {}

    fake_daemon_cls = MagicMock()
    fake_daemon_cls.return_value.run = AsyncMock()

    async def fake_aclose():
        pass

    fake_redis = MagicMock()
    fake_redis.aclose = fake_aclose

    with (
        patch("redis.asyncio.from_url", return_value=fake_redis),
        patch("services.stock_strategy.daemon.StockStrategyDaemon", fake_daemon_cls),
        patch(
            "services.stock_strategy.main.StockStrategyDaemon",
            fake_daemon_cls,
            create=True,
        ),
        patch(
            "shared.streaming.stock_bear_override.BearOverrideConfig.load",
            return_value=BearOverrideConfig(enabled=False),
        ),
        patch(
            "shared.streaming.stock_regime.StockRegimeConfig.load",
            return_value=MagicMock(enabled=False),
        ),
        patch(
            "shared.streaming.candle_warmup.StockPrewarmConfig.load",
            return_value=MagicMock(max_prewarm_per_cycle=5),
        ),
        patch(
            "shared.storage.config.StorageConfig.load_or_default",
            return_value=MagicMock(
                market_data=MagicMock(parquet=MagicMock(root="/tmp"))
            ),
        ),
        patch(
            "services.trading.strategy_manager.StrategyManager",
            return_value=MagicMock(
                required_indicators=[], set_indicator_engine=MagicMock()
            ),
        ),
        patch(
            "services.trading.indicator_engine.StreamingIndicatorEngine",
            return_value=MagicMock(),
        ),
        patch(
            "services.trading.stream_consumer_feed.StreamConsumerFeed",
            return_value=MagicMock(),
        ),
        patch(
            "shared.indicators.resolver.StreamingIndicatorResolver",
            return_value=MagicMock(),
        ),
        patch(
            "shared.storage.market_data_store.ParquetMarketDataStore",
            return_value=MagicMock(),
        ),
        patch(
            "shared.streaming.client.RedisClient.get_client",
            return_value=MagicMock(get=MagicMock(return_value=None)),
        ),
        patch("shared.kis.client.KISClient", return_value=MagicMock()),
        patch(
            "shared.indicators.contracts.IndicatorContract.from_required_keys",
            return_value=MagicMock(warmth_timeframe=None),
        ),
        patch("shared.config.loader.ConfigLoader.load", return_value={}),
        patch(
            "services.stock_strategy.universe.merge_screener_universe", return_value=[]
        ),
        patch(
            "services.stock_strategy.universe.parse_watchlist_codes", return_value=[]
        ),
        patch(
            "services.stock_strategy.main.build_prewarm_fn", return_value=AsyncMock()
        ),
    ):
        await main_mod._build_and_run()

    _, kwargs = fake_daemon_cls.call_args
    captured["bear_override_config"] = kwargs.get("bear_override_config")

    assert (
        captured["bear_override_config"] is None
    ), "bear_override_config must be None when enabled=False"
