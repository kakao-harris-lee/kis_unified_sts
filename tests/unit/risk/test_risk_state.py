# tests/unit/risk/test_risk_state.py
import fakeredis.aioredis
import pytest

from shared.risk.state import RiskStateStore


@pytest.mark.asyncio
async def test_state_defaults_are_zero():
    r = fakeredis.aioredis.FakeRedis()
    s = RiskStateStore(redis=r, asset_class="futures")
    snap = await s.load()
    assert snap.daily_pnl_krw == 0.0
    assert snap.consecutive_losses == 0
    assert snap.daily_trade_count == 0


@pytest.mark.asyncio
async def test_persist_then_load():
    r = fakeredis.aioredis.FakeRedis()
    s = RiskStateStore(redis=r, asset_class="futures")
    snap = await s.load()
    snap.consecutive_losses = 3
    snap.daily_trade_count = 2
    snap.daily_pnl_krw = -15000.0
    await s.save(snap)

    s2 = RiskStateStore(redis=r, asset_class="futures")
    reloaded = await s2.load()
    assert reloaded.consecutive_losses == 3
    assert reloaded.daily_trade_count == 2
    assert reloaded.daily_pnl_krw == -15000.0


@pytest.mark.asyncio
async def test_ttl_set_on_save():
    r = fakeredis.aioredis.FakeRedis()
    s = RiskStateStore(redis=r, asset_class="futures")
    snap = await s.load()
    snap.daily_trade_count = 1
    await s.save(snap)
    ttl = await r.ttl("risk:state:futures")
    assert 0 < ttl <= 86400
