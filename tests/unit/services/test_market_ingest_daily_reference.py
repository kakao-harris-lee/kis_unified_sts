"""market-ingest publishes the futures prev_close read-model.

After the F-9 cutover retires the orchestrator, this daemon is the only futures
process left holding KIS credentials, so its session-start REST prefetch is what
keeps Setup A from going blind. The publish must also follow a rollover: a
symbol change re-publishes for the new contract.
"""

from __future__ import annotations

import asyncio

import fakeredis
import pytest

from services.market_ingest.main import (
    MarketIngestDaemon,
    _build_daily_reference_prefetch,
)
from shared.streaming.daily_reference import read_futures_daily_reference

SYMBOL = "A05609"
NEXT_SYMBOL = "A05612"


class _KISClient:
    def __init__(self, prev_close=411.25, raises=False):
        self._prev_close = prev_close
        self._raises = raises
        self.calls: list[str] = []

    async def _get_futures_price(self, symbol):
        self.calls.append(symbol)
        if self._raises:
            raise ConnectionError("KIS unreachable")
        return {"price": 412.0, "prev_close": self._prev_close}


class _Feed:
    def __init__(self):
        self.callback = None

    def set_tick_callback(self, cb):
        self.callback = cb

    def update_symbols(self, symbols, *args, **kwargs):  # noqa: ARG002
        pass

    async def start(self):
        pass

    async def stop(self):
        pass

    def is_healthy(self) -> bool:
        return True


class _Publisher:
    def publish(self, asset, symbol, payload):
        pass

    def close(self, timeout: float = 2.0):  # noqa: ARG002
        pass


def _provider(values: list[list[str]]):
    state = {"i": 0}

    async def _p() -> list[str]:
        i = state["i"]
        if i < len(values):
            state["i"] = i + 1
            return values[i]
        return values[-1]

    return _p


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


async def test_prefetch_publishes_the_read_model(redis_client):
    kis = _KISClient(prev_close=411.25)
    prefetch = _build_daily_reference_prefetch(kis, redis_client)

    await prefetch([SYMBOL])

    payload = read_futures_daily_reference(redis_client, SYMBOL)
    assert payload is not None
    assert payload["prev_close"] == 411.25
    assert payload["source"] == "kis_rest"
    assert payload["producer"] == "market-ingest"
    assert kis.calls == [SYMBOL]


async def test_one_unreadable_symbol_does_not_stop_the_others(redis_client, caplog):
    class _PartialClient(_KISClient):
        async def _get_futures_price(self, symbol):
            self.calls.append(symbol)
            if symbol == SYMBOL:
                raise ConnectionError("KIS unreachable")
            return {"prev_close": 411.25}

    prefetch = _build_daily_reference_prefetch(_PartialClient(), redis_client)

    with caplog.at_level("WARNING"):
        await prefetch([SYMBOL, NEXT_SYMBOL])

    assert read_futures_daily_reference(redis_client, SYMBOL) is None
    assert read_futures_daily_reference(redis_client, NEXT_SYMBOL) is not None
    assert "prev_close prefetch failed" in caplog.text


async def test_a_zero_prev_close_warns_and_publishes_nothing(redis_client, caplog):
    prefetch = _build_daily_reference_prefetch(_KISClient(prev_close=0), redis_client)

    with caplog.at_level("WARNING"):
        await prefetch([SYMBOL])

    assert read_futures_daily_reference(redis_client, SYMBOL) is None
    assert "prev_close prefetch returned" in caplog.text


async def test_daemon_prefetches_at_start(redis_client):
    kis = _KISClient()
    daemon = MarketIngestDaemon(
        asset="futures",
        feed=_Feed(),
        publisher=_Publisher(),
        symbol_provider=_provider([[SYMBOL]]),
        refresh_interval_seconds=0.02,
        restart_on_symbol_change=True,
        daily_reference_prefetch=_build_daily_reference_prefetch(kis, redis_client),
    )

    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.05)
    await daemon.stop()
    await asyncio.wait_for(task, timeout=1.0)

    assert read_futures_daily_reference(redis_client, SYMBOL) is not None


async def test_daemon_republishes_on_a_contract_rollover(redis_client):
    kis = _KISClient()
    daemon = MarketIngestDaemon(
        asset="futures",
        feed=_Feed(),
        publisher=_Publisher(),
        symbol_provider=_provider([[SYMBOL], [NEXT_SYMBOL]]),
        refresh_interval_seconds=0.02,
        restart_on_symbol_change=True,
        daily_reference_prefetch=_build_daily_reference_prefetch(kis, redis_client),
    )

    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.12)
    await daemon.stop()
    await asyncio.wait_for(task, timeout=1.0)

    assert read_futures_daily_reference(redis_client, NEXT_SYMBOL) is not None


async def test_a_failing_prefetch_never_stops_the_ingest_loop(caplog):
    async def _boom(_symbols):
        raise RuntimeError("prefetch exploded")

    feed = _Feed()
    daemon = MarketIngestDaemon(
        asset="futures",
        feed=feed,
        publisher=_Publisher(),
        symbol_provider=_provider([[SYMBOL]]),
        refresh_interval_seconds=0.02,
        restart_on_symbol_change=True,
        daily_reference_prefetch=_boom,
    )

    with caplog.at_level("WARNING"):
        task = asyncio.create_task(daemon.run())
        await asyncio.sleep(0.05)
        await daemon.stop()
        await asyncio.wait_for(task, timeout=1.0)

    assert feed.callback is not None, "the daemon kept running and wired its feed"
    assert "daily_reference prefetch failed" in caplog.text


async def test_stock_ingest_has_no_prefetch_wired():
    """Stock has no prev_close read-model — the hook stays None (no-op)."""
    daemon = MarketIngestDaemon(
        asset="stock",
        feed=_Feed(),
        publisher=_Publisher(),
        symbol_provider=_provider([["005930"]]),
        refresh_interval_seconds=0.02,
    )
    assert daemon.daily_reference_prefetch is None
    await daemon._run_daily_reference_prefetch()  # no-op, must not raise
