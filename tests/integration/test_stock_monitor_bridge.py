"""e2e: daemon shadow streams -> StockMonitorDaemon -> dashboard :shadow keys (read-back)."""

from __future__ import annotations

import fakeredis
import fakeredis.aioredis
import pytest

import shared.streaming.trading_state as ts
from services.stock_monitor.daemon import StockMonitorDaemon
from shared.streaming.trading_state import TradingStatePublisher, TradingStateReader


def _enc(d: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode(): v.encode() for k, v in d.items()}


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
async def test_bridge_publishes_dashboard_state_in_shadow_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = fakeredis.FakeServer()
    redis = fakeredis.aioredis.FakeRedis(server=server, db=1)
    sync = fakeredis.FakeStrictRedis(server=server, db=1)
    monkeypatch.setattr(ts, "_get_redis", lambda: sync)
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "shadow")

    daemon = StockMonitorDaemon(
        redis=redis,
        feed=_FakeFeed(),
        publisher=TradingStatePublisher(asset_class="stock"),
        alert_sink=None,
        positions_key="trading:stock:positions",
        fill_stream="order.fill.stock.shadow",
        signal_stream="signal.final.stock.shadow",
        consumer_group="stock_monitor",
        worker_id="e2e",
        fee_rate=0.003,
        status_interval=5.0,
    )

    def _fill(role: str, side: str, price: str) -> dict[bytes, bytes]:
        return _enc(
            {
                "signal_id": "sig-1",
                "order_id": f"VO-{role}",
                "symbol": "005930",
                "side": side,
                "order_type": "market",
                "requested_price": price,
                "filled_price": price,
                "tick_size_points": "0.0",
                "slippage_ticks": "0.0",
                "quantity": "10",
                "requested_at_ms": "1700000000000",
                "filled_at_ms": "1700000000000",
                "latency_ms": "0",
                "venue": "KRX",
                "trade_role": role,
                "broker_error_code": "",
            }
        )

    final = _enc(
        {
            "signal_id": "sig-1",
            "code": "005930",
            "name": "삼성전자",
            "strategy": "vr_composite",
            "direction": "long",
            "price": "71000.0",
            "quantity": "10",
            "confidence": "0.62",
            "generated_at_ms": "1700000000000",
            "metadata_json": "{}",
            "size_multiplier": "1.0",
            "filtered_at_ms": "1700000000000",
        }
    )

    reader = TradingStateReader(asset_class="stock")

    await daemon.handle_signal(final)
    await daemon.handle_fill(_fill("entry", "BUY", "71000.0"))
    open_positions = reader.get_positions()
    assert len(open_positions) == 1 and open_positions[0]["code"] == "005930"
    assert open_positions[0]["strategy"] == "vr_composite"  # signal correlation worked
    await daemon.handle_fill(_fill("exit", "SELL", "73000.0"))

    signals = reader.get_signals()
    assert len(signals) == 1  # no accidental double-publish
    assert signals[0]["strategy"] == "vr_composite"
    assert reader.get_positions() == []  # opened then closed
    trades = reader.get_trades()
    assert len(trades) == 1 and trades[0]["symbol"] == "005930"
    assert round(trades[0]["pnl"], 0) == 17840.0

    # the live (no-suffix) keys are untouched -> orchestrator's dashboard is safe
    assert sync.exists("trading:stock:trades") == 0
    assert sync.exists("trading:stock:trades:shadow") == 1
