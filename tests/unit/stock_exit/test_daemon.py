"""StockExitDaemon: stop-loss -> SELL + HDEL + record_loss + exit fill; not-filled -> no close."""

from __future__ import annotations

import json

import fakeredis.aioredis
import pytest

from services.stock_exit.daemon import StockExitDaemon
from shared.execution.fill_logger import FillLogger
from shared.paper.broker import VirtualBroker
from shared.risk.runtime_state import RuntimeRiskState
from shared.strategy.exit.three_stage import ThreeStageExit, ThreeStageExitConfig


def _seed_record(code: str = "005930", entry: float = 71000.0) -> dict[str, object]:
    return {
        "code": code,
        "entry_price": entry,
        "quantity": 10,
        "opened_at_ms": 1_700_000_000_000,
        "state": "SURVIVAL",
        "signal_id": f"sig-{code}",
    }


class _FakeFeed:
    """Minimal price-feed stand-in: a settable price cache."""

    def __init__(self) -> None:
        self.prices: dict[str, dict[str, float]] = {}

    def update_symbols(self, symbols: list[str]) -> None:
        pass

    async def get_current_price(self, symbol: str) -> dict[str, float]:
        return dict(self.prices.get(symbol, {}))

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


def _build_daemon(redis, *, broker=None, fill_logger=None) -> StockExitDaemon:
    return StockExitDaemon(
        redis=redis,
        feed=_FakeFeed(),
        exit_strategy=ThreeStageExit(
            ThreeStageExitConfig(enable_bear_exit=False, eod_exempt_maximize=True)
        ),
        broker=broker or VirtualBroker(slippage_rate=0.0001),
        fill_logger=fill_logger
        or FillLogger(
            redis=redis,
            stream="order.fill.stock.shadow",
            maxlen=1000,
            asset_class="stock",
        ),
        runtime_state=RuntimeRiskState(redis=redis, asset_class="stock"),
        positions_key="trading:stock:positions",
        interval_seconds=1.0,
    )


@pytest.mark.asyncio
async def test_stop_loss_sells_closes_and_records_loss() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    daemon.feed.prices["005930"] = {"close": 69580.0}  # -2% -> STOP_LOSS

    await daemon.run_cycle()

    assert not await redis.hexists("trading:stock:positions", "005930")
    fills = await redis.xrange("order.fill.stock.shadow")
    assert len(fills) == 1
    assert fills[0][1][b"side"] == b"SELL"
    assert fills[0][1][b"trade_role"] == b"exit"
    snap = await daemon.runtime_state.snapshot()
    assert snap.daily_pnl_krw < 0
    assert snap.consecutive_losses == 1


@pytest.mark.asyncio
async def test_no_price_no_action() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    await daemon.run_cycle()
    assert await redis.hexists("trading:stock:positions", "005930")
    assert await redis.xrange("order.fill.stock.shadow") == []


@pytest.mark.asyncio
async def test_unfilled_sell_does_not_close() -> None:
    redis = fakeredis.aioredis.FakeRedis()

    class _UnfilledBroker:
        async def submit_order(self, **_):
            class _O:
                filled = False
                rejection_reason = "no_fill"
                fill_price = None
                order_id = ""

            return _O()

    daemon = _build_daemon(redis, broker=_UnfilledBroker())
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    daemon.feed.prices["005930"] = {"close": 69580.0}
    await daemon.run_cycle()
    assert await redis.hexists("trading:stock:positions", "005930")
    assert await redis.xrange("order.fill.stock.shadow") == []


@pytest.mark.asyncio
async def test_high_water_persisted() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    # Use a late eod_close_hour so EOD check never fires during test runs,
    # regardless of wall-clock time.
    daemon = StockExitDaemon(
        redis=redis,
        feed=_FakeFeed(),
        exit_strategy=ThreeStageExit(
            ThreeStageExitConfig(
                enable_bear_exit=False,
                eod_exempt_maximize=True,
                eod_close_hour=23,
                eod_close_minute=59,
                time_cut_minutes=99999,
            )
        ),
        broker=VirtualBroker(slippage_rate=0.0001),
        fill_logger=FillLogger(
            redis=redis,
            stream="order.fill.stock.shadow",
            maxlen=1000,
            asset_class="stock",
        ),
        runtime_state=RuntimeRiskState(redis=redis, asset_class="stock"),
        positions_key="trading:stock:positions",
        interval_seconds=1.0,
    )
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    daemon.feed.prices["005930"] = {"close": 72000.0}  # +1.4% -> SURVIVAL, no exit
    await daemon.run_cycle()
    rec = json.loads(await redis.hget("trading:stock:positions", "005930"))
    assert rec["high_water"] == 72000.0
