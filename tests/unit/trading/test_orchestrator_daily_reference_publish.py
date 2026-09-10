"""The session-start prev_close prefetch must also publish the read-model.

The orchestrator is the only futures process holding KIS credentials before the
F-9 cutover, so its one REST call per symbol is the sole source of prev_close
for the decoupled decision-engine (whose parquet daily bars never carried the
trading symbol). These tests pin the publish at that seam and pin that a Redis
failure cannot reach the trading path.
"""

from __future__ import annotations

import fakeredis
import pytest

from services.trading.orchestrator import TradingConfig, TradingOrchestrator
from shared.streaming.daily_reference import read_futures_daily_reference

SYMBOL = "A05609"


class _KISClient:
    """Stands in for KISClient — only the futures current-price call is used."""

    def __init__(self, prev_close=411.25, raises=False):
        self._prev_close = prev_close
        self._raises = raises
        self.calls: list[str] = []

    async def _get_futures_price(self, symbol):
        self.calls.append(symbol)
        if self._raises:
            raise ConnectionError("KIS unreachable")
        return {"price": 412.0, "prev_close": self._prev_close}


def _orchestrator(kis_client, symbols=(SYMBOL,)) -> TradingOrchestrator:
    orch = object.__new__(TradingOrchestrator)
    orch.config = TradingConfig(
        asset_class="futures",
        strategy_name="setup_a_gap_reversion",
        symbols=list(symbols),
        initial_capital=10_000_000,
        paper_trading=True,
    )
    orch._kis_client = kis_client
    orch._futures_daily_reference = {}
    return orch


@pytest.fixture
def redis_client(monkeypatch):
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        "shared.streaming.client.RedisClient.get_client", staticmethod(lambda: client)
    )
    return client


async def test_prefetch_caches_and_publishes_the_read_model(redis_client):
    orch = _orchestrator(_KISClient(prev_close=411.25))

    await orch._prefetch_futures_daily_reference()

    # Unchanged local behavior: the in-process cache Setup A already read.
    assert orch._futures_daily_reference == {SYMBOL: {"prev_close": 411.25}}
    # New: the same number, visible to the credential-less decision-engine.
    payload = read_futures_daily_reference(redis_client, SYMBOL)
    assert payload is not None
    assert payload["prev_close"] == 411.25
    assert payload["source"] == "kis_rest"
    assert payload["producer"] == "trader-futures"


async def test_a_rest_failure_publishes_nothing_and_does_not_raise(redis_client):
    orch = _orchestrator(_KISClient(raises=True))

    await orch._prefetch_futures_daily_reference()

    assert orch._futures_daily_reference == {}
    assert read_futures_daily_reference(redis_client, SYMBOL) is None


async def test_a_zero_prev_close_is_neither_cached_nor_published(redis_client):
    orch = _orchestrator(_KISClient(prev_close=0))

    await orch._prefetch_futures_daily_reference()

    assert orch._futures_daily_reference == {}
    assert read_futures_daily_reference(redis_client, SYMBOL) is None


async def test_a_redis_outage_still_caches_prev_close_for_the_trading_path(
    monkeypatch, caplog
):
    """Publishing is additive: the orchestrator's own Setup A must not lose
    prev_close because Redis is down."""

    def _boom():
        raise ConnectionError("redis down")

    monkeypatch.setattr(
        "shared.streaming.client.RedisClient.get_client", staticmethod(_boom)
    )
    orch = _orchestrator(_KISClient(prev_close=411.25))

    with caplog.at_level("WARNING"):
        await orch._prefetch_futures_daily_reference()

    assert orch._futures_daily_reference == {SYMBOL: {"prev_close": 411.25}}
    assert "read-model publish failed" in caplog.text


async def test_every_configured_symbol_is_published(redis_client):
    orch = _orchestrator(_KISClient(prev_close=411.25), symbols=("A05609", "A01609"))

    await orch._prefetch_futures_daily_reference()

    for symbol in ("A05609", "A01609"):
        payload = read_futures_daily_reference(redis_client, symbol)
        assert payload is not None, symbol
        assert payload["prev_close"] == 411.25
