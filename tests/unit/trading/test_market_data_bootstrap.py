"""Owner tests for market-data bootstrap helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


def _config(asset_class: str = "stock") -> SimpleNamespace:
    return SimpleNamespace(
        asset_class=asset_class,
        symbols=["005930"],
        enable_telegram=False,
        telegram_token=None,
        telegram_chat_id=None,
    )


def test_init_price_feeds_stock_stream_returns_stream_feed(monkeypatch) -> None:
    from services.trading.market_data_bootstrap import init_price_feeds
    from services.trading.stream_consumer_feed import StreamConsumerFeed

    fake_redis = object()
    monkeypatch.setenv("STOCK_MARKET_DATA_SOURCE", "stream")
    monkeypatch.setattr("redis.asyncio.from_url", lambda _url: fake_redis)

    result = init_price_feeds(
        config=_config("stock"),
        kis_client=object(),
        kis_config=object(),
    )

    assert isinstance(result.stream_consumer_feed, StreamConsumerFeed)
    assert result.data_source is result.stream_consumer_feed
    assert result.stream_redis is fake_redis
    assert result.stock_price_feed is None
    assert result.futures_price_feed is None


def test_init_price_feeds_stock_websocket_returns_stock_feed(monkeypatch) -> None:
    from services.trading.market_data_bootstrap import init_price_feeds

    fake_feed = object()
    monkeypatch.delenv("STOCK_MARKET_DATA_SOURCE", raising=False)
    monkeypatch.setattr(
        "shared.kis.stock_feed.KISStockPriceFeed",
        lambda config=None: fake_feed,
    )

    result = init_price_feeds(
        config=_config("stock"),
        kis_client=object(),
        kis_config=object(),
    )

    assert result.data_source is fake_feed
    assert result.stock_price_feed is fake_feed
    assert result.stream_consumer_feed is None


def test_init_price_feeds_futures_ignores_stock_stream_flag(monkeypatch) -> None:
    from services.trading.market_data_bootstrap import init_price_feeds

    fake_feed = object()
    monkeypatch.setenv("STOCK_MARKET_DATA_SOURCE", "stream")
    monkeypatch.setattr(
        "shared.kis.futures_feed.KISFuturesPriceFeed",
        lambda config=None: fake_feed,
    )

    result = init_price_feeds(
        config=_config("futures"),
        kis_client=object(),
        kis_config=object(),
    )

    assert result.data_source is fake_feed
    assert result.futures_price_feed is fake_feed
    assert result.stream_consumer_feed is None
    assert result.stream_redis is None


def test_init_data_provider_returns_provider_and_failover_flag(monkeypatch) -> None:
    from services.trading import market_data_bootstrap as bootstrap
    from services.trading.market_data_bootstrap import init_data_provider

    class FakeMarketDataProvider:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    monkeypatch.setattr(bootstrap, "MarketDataProvider", FakeMarketDataProvider)
    monkeypatch.setattr(
        bootstrap.ConfigLoader,
        "load",
        lambda _name: {
            "data_provider": {
                "cache_ttl_websocket": 1.5,
                "batch_size": 7,
                "fetch_timeout_seconds": 3.0,
            },
            "failover": {
                "enabled": True,
                "health_check_interval_seconds": 11.0,
                "staleness_threshold_seconds": 22.0,
            },
        },
    )

    data_source = object()
    result = init_data_provider(
        config=_config("stock"),
        kis_client=object(),
        data_source=data_source,
    )

    assert result.failover_enabled is True
    assert result.provider.kwargs["data_source"] is data_source
    provider_config = result.provider.kwargs["config"]
    assert provider_config.cache_ttl_seconds == 1.5
    assert provider_config.batch_size == 7
    assert provider_config.fetch_timeout_seconds == 3.0
    assert provider_config.health_check_interval_seconds == 11.0
    assert provider_config.staleness_threshold_seconds == 22.0


def test_init_tick_stream_publisher_skips_when_stream_feed_is_active() -> None:
    from services.trading.market_data_bootstrap import init_tick_stream_publisher

    result = init_tick_stream_publisher(stream_consumer_feed=object())

    assert result.publisher is None
