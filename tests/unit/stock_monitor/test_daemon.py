"""StockMonitorDaemon: entry->position, exit->trade(pnl), signal->signals; recovery; MTM."""

from __future__ import annotations

import json

import fakeredis
import fakeredis.aioredis
import pytest

import shared.streaming.trading_state as ts
from services.stock_monitor.daemon import StockMonitorDaemon
from shared.streaming.trading_state import TradingStatePublisher, TradingStateReader


def _enc(d: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode(): v.encode() for k, v in d.items()}


def _fill(role: str, side: str, price: str, code: str = "005930") -> dict[str, str]:
    return {
        "signal_id": f"sig-{code}",
        "order_id": f"VO-{role}",
        "symbol": code,
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


def _final(code: str = "005930") -> dict[str, str]:
    return {
        "signal_id": f"sig-{code}",
        "code": code,
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


@pytest.fixture()
def wired(monkeypatch):
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
        worker_id="test",
        fee_rate=0.003,
        status_interval=5.0,
    )
    return daemon, redis, TradingStateReader(asset_class="stock")


@pytest.mark.asyncio
async def test_signal_then_entry_then_exit(wired) -> None:
    daemon, redis, reader = wired
    await daemon.handle_signal(_enc(_final()))
    assert reader.get_signals()[0]["strategy"] == "vr_composite"

    await daemon.handle_fill(_enc(_fill("entry", "BUY", "71000.0")))
    positions = reader.get_positions()
    assert len(positions) == 1 and positions[0]["strategy"] == "vr_composite"

    await daemon.handle_fill(_enc(_fill("exit", "SELL", "73000.0")))
    assert reader.get_positions() == []
    trades = reader.get_trades()
    assert len(trades) == 1
    # pnl = (73000-71000)*10 - (71000+73000)*10*0.0015 = 20000 - 2160 = 17840
    assert round(trades[0]["pnl"], 0) == 17840.0
    assert trades[0]["strategy"] == "vr_composite"


@pytest.mark.asyncio
async def test_exit_without_entry_skips_trade(wired) -> None:
    daemon, redis, reader = wired
    await daemon.handle_fill(_enc(_fill("exit", "SELL", "73000.0")))
    assert reader.get_trades() == []


@pytest.mark.asyncio
async def test_recover_open_from_positions_hash(wired) -> None:
    daemon, redis, reader = wired
    await redis.hset(
        "trading:stock:positions",
        "005930",
        json.dumps(
            {
                "code": "005930",
                "entry_price": 71000.0,
                "quantity": 10,
                "opened_at_ms": 1_700_000_000_000,
                "state": "SURVIVAL",
                "signal_id": "sig-005930",
            }
        ),
    )
    await daemon.recover_open_positions()
    await daemon.handle_fill(_enc(_fill("exit", "SELL", "73000.0")))
    trades = reader.get_trades()
    assert len(trades) == 1 and trades[0]["entry_price"] == 71000.0


@pytest.mark.asyncio
async def test_recover_skips_foreign_records(wired) -> None:
    daemon, redis, reader = wired
    # orchestrator-style record: no opened_at_ms -> must be skipped
    await redis.hset(
        "trading:stock:positions",
        "uuid-1",
        json.dumps(
            {
                "id": "uuid-1",
                "code": "000660",
                "entry_price": 50000.0,
                "quantity": 5,
                "entry_time": "2026-06-06T00:00:00+00:00",
            }
        ),
    )
    await daemon.recover_open_positions()
    assert "000660" not in daemon._open


@pytest.mark.asyncio
async def test_mark_to_market(wired) -> None:
    daemon, redis, reader = wired
    await daemon.handle_signal(_enc(_final()))
    await daemon.handle_fill(_enc(_fill("entry", "BUY", "71000.0")))
    daemon.feed.prices["005930"] = {"close": 72000.0}
    await daemon.publish_status_and_mtm()
    pos = reader.get_positions()[0]
    assert pos["current_price"] == 72000.0
    assert pos["unrealized_pnl"] == (72000.0 - 71000.0) * 10


@pytest.mark.asyncio
async def test_mtm_survives_concurrent_mutation(wired) -> None:
    """A fill arriving mid-MTM (yielded on the price await) must not crash."""
    daemon, redis, reader = wired
    await daemon.handle_fill(_enc(_fill("entry", "BUY", "71000.0", code="005930")))
    await daemon.handle_fill(_enc(_fill("entry", "BUY", "50000.0", code="000660")))

    class _MutatingFeed:
        prices = {"005930": {"close": 72000.0}, "000660": {"close": 51000.0}}

        async def get_current_price(self, symbol: str) -> dict[str, float]:
            # Simulate a concurrent exit fill popping _open during iteration.
            daemon._open.pop("000660", None)
            return dict(self.prices.get(symbol, {}))

    daemon.feed = _MutatingFeed()
    # Iterates a snapshot -> no "dictionary changed size during iteration".
    await daemon.publish_status_and_mtm()
    assert "000660" not in daemon._open


@pytest.mark.asyncio
async def test_signal_meta_fifo_eviction(wired) -> None:
    """Pushing > signal_meta_max signals evicts the oldest (FIFO)."""
    daemon, redis, reader = wired
    daemon.signal_meta_max = 3
    for i in range(5):
        await daemon.handle_signal(_enc(_final(code=f"00000{i}")))
    assert len(daemon._signal_meta) == 3
    # oldest two evicted, newest three retained
    assert "sig-000000" not in daemon._signal_meta
    assert "sig-000001" not in daemon._signal_meta
    assert "sig-000004" in daemon._signal_meta


@pytest.mark.asyncio
async def test_entry_without_signal_meta_is_graceful(wired) -> None:
    """Entry fill with no prior signal -> position with empty strategy/name."""
    daemon, redis, reader = wired
    await daemon.handle_fill(_enc(_fill("entry", "BUY", "71000.0")))
    pos = reader.get_positions()[0]
    assert pos["strategy"] == ""
    assert pos["name"] == ""
    assert pos["entry_price"] == 71000.0
