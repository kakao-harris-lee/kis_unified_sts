"""M1c: STOCK_MARKET_DATA_SOURCE flag routing in the orchestrator."""

from __future__ import annotations

import pytest

from services.trading.orchestrator import TradingConfig, TradingOrchestrator
from services.trading.stream_consumer_feed import StreamConsumerFeed


def test_init_price_feeds_stream_branch_builds_stream_consumer_feed(monkeypatch):
    monkeypatch.setenv("STOCK_MARKET_DATA_SOURCE", "stream")
    orch = TradingOrchestrator(TradingConfig.stock())
    orch._kis_client = object()  # truthy → bypass the early return
    data_source = orch._init_price_feeds(object())  # truthy kis_config
    assert isinstance(data_source, StreamConsumerFeed)
    assert orch._stream_consumer_feed is data_source
    assert orch._stock_price_feed is None  # no KIS WebSocket feed
    assert orch._stream_redis is not None


def _fake_stock_feed(config=None):
    return object()


def _fake_futures_feed(config=None):
    return object()


def test_init_price_feeds_default_is_websocket(monkeypatch):
    monkeypatch.delenv("STOCK_MARKET_DATA_SOURCE", raising=False)
    monkeypatch.setattr("shared.kis.stock_feed.KISStockPriceFeed", _fake_stock_feed)
    orch = TradingOrchestrator(TradingConfig.stock())
    orch._kis_client = object()
    data_source = orch._init_price_feeds(object())
    assert orch._stream_consumer_feed is None
    assert orch._stock_price_feed is data_source  # KIS feed path taken


def test_init_price_feeds_futures_ignores_stock_flag(monkeypatch):
    monkeypatch.setenv("STOCK_MARKET_DATA_SOURCE", "stream")
    monkeypatch.setattr(
        "shared.kis.futures_feed.KISFuturesPriceFeed", _fake_futures_feed
    )
    orch = TradingOrchestrator(TradingConfig.futures())
    orch._kis_client = object()
    data_source = orch._init_price_feeds(object())
    assert orch._stream_consumer_feed is None  # flag is stock-only
    assert orch._futures_price_feed is data_source


def test_stream_attrs_declared_after_construction():
    orch = TradingOrchestrator(TradingConfig.stock())
    assert orch._stream_consumer_feed is None
    assert orch._stream_redis is None


def test_tick_stream_publisher_skipped_on_stream_path():
    orch = TradingOrchestrator(TradingConfig.stock())
    orch._stream_consumer_feed = object()  # simulate active stream feed
    orch._init_tick_stream_publisher()
    assert orch._tick_stream_publisher is None


def test_tick_stream_publisher_built_on_websocket_path(monkeypatch):
    monkeypatch.setenv("MONITOR_TICK_STREAM_ENABLED", "false")  # config says disabled
    orch = TradingOrchestrator(TradingConfig.stock())
    orch._stream_consumer_feed = None
    orch._init_tick_stream_publisher()  # takes the normal (non-skip) path
    assert orch._tick_stream_publisher is None  # disabled-by-env, but path executed


class _RecordingFeed:
    """Stand-in for a stock feed that records its tick callback."""

    def __init__(self) -> None:
        self.callback = None

    def set_tick_callback(self, callback) -> None:
        self.callback = callback


def test_init_indicator_engine_wires_callback_to_stream_feed():
    orch = TradingOrchestrator(TradingConfig.stock())
    # Minimal state the wiring block reads at top level:
    orch._strategy_manager = None
    orch._stock_price_feed = None
    orch._futures_price_feed = None
    fake = _RecordingFeed()
    orch._stream_consumer_feed = fake

    orch._init_indicator_engine()

    assert fake.callback is not None  # _on_stock_tick bound to the stream feed
    assert callable(fake.callback)


def test_init_indicator_engine_wires_callback_to_ws_feed_when_present():
    orch = TradingOrchestrator(TradingConfig.stock())
    orch._strategy_manager = None
    orch._futures_price_feed = None
    orch._stream_consumer_feed = None
    fake = _RecordingFeed()
    orch._stock_price_feed = fake

    orch._init_indicator_engine()

    assert fake.callback is not None  # WS path unchanged


class _FakeStreamFeed:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.symbols = None

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    def update_symbols(self, symbols) -> None:
        self.symbols = list(symbols)


class _FakeAsyncRedis:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_start_stream_consumer_feed_starts_and_subscribes():
    orch = TradingOrchestrator(TradingConfig.stock())
    orch.config.symbols = ["005930", "000660"]
    fake = _FakeStreamFeed()
    orch._stream_consumer_feed = fake
    await orch._start_stream_consumer_feed()
    assert fake.started is True
    assert fake.symbols == ["005930", "000660"]


@pytest.mark.asyncio
async def test_stop_stream_consumer_feed_stops_and_closes_redis():
    orch = TradingOrchestrator(TradingConfig.stock())
    fake = _FakeStreamFeed()
    redis = _FakeAsyncRedis()
    orch._stream_consumer_feed = fake
    orch._stream_redis = redis
    await orch._stop_stream_consumer_feed()
    assert fake.stopped is True
    assert redis.closed is True
    assert orch._stream_redis is None


@pytest.mark.asyncio
async def test_stream_feed_helpers_noop_when_absent():
    orch = TradingOrchestrator(TradingConfig.stock())
    orch._stream_consumer_feed = None
    orch._stream_redis = None
    await orch._start_stream_consumer_feed()  # no raise
    await orch._stop_stream_consumer_feed()  # no raise
