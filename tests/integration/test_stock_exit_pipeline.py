"""e2e: M4-O-style open position -> M4-X exit -> close + PnL feedback + re-entry freed."""

from __future__ import annotations

import json

import fakeredis
import fakeredis.aioredis
import pytest

from services.stock_exit.daemon import StockExitDaemon
from shared.execution.fill_logger import FillLogger
from shared.paper.broker import VirtualBroker
from shared.risk.runtime_state import RuntimeRiskState
from shared.strategy.exit.three_stage import ThreeStageExit, ThreeStageExitConfig


class _FakeFeed:
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


@pytest.mark.asyncio
async def test_open_exit_close_and_reentry_freed() -> None:
    server = fakeredis.FakeServer()
    redis = fakeredis.aioredis.FakeRedis(server=server, db=1)
    sync_redis = fakeredis.FakeStrictRedis(server=server, db=1)
    positions_key = "trading:stock:positions"

    # M4-O opened position (its exact record schema, uppercase state).
    await redis.hset(
        positions_key,
        "005930",
        json.dumps(
            {
                "code": "005930",
                "entry_price": 71000.0,
                "quantity": 10,
                # 2023-11 UTC — deliberately old so holding >> time_cut
                "opened_at_ms": 1_700_000_000_000,
                "state": "SURVIVAL",
                "signal_id": "sig-1",
            }
        ),
    )

    # M4-R OpenPositionFilter provider sees the open position (re-entry blocked).
    def _has_open_position(code: str) -> bool:
        return bool(sync_redis.hexists(positions_key, code))

    assert _has_open_position("005930") is True

    feed = _FakeFeed()
    feed.prices["005930"] = {"close": 69580.0}  # -2% -> STOP_LOSS

    daemon = StockExitDaemon(
        redis=redis,
        feed=feed,
        exit_strategy=ThreeStageExit(
            ThreeStageExitConfig(enable_bear_exit=False, eod_exempt_maximize=True)
        ),
        broker=VirtualBroker(slippage_rate=0.0001),
        fill_logger=FillLogger(
            redis=redis,
            stream="order.fill.stock.shadow",
            maxlen=1000,
            asset_class="stock",
        ),
        runtime_state=RuntimeRiskState(redis=redis, asset_class="stock"),
        positions_key=positions_key,
        interval_seconds=1.0,
    )

    await daemon.run_cycle()

    # Exit fill published.
    fills = await redis.xrange("order.fill.stock.shadow")
    assert len(fills) == 1 and fills[0][1][b"trade_role"] == b"exit"
    assert fills[0][1][b"side"] == b"SELL"
    # Position closed -> re-entry freed (M4-R provider now returns False).
    assert _has_open_position("005930") is False
    # Realized loss fed to the shared risk state M4-R reads.
    snap = await RuntimeRiskState(redis=redis, asset_class="stock").snapshot()
    assert snap.daily_pnl_krw < 0
    assert snap.consecutive_losses == 1
    assert snap.daily_trade_count == 1
