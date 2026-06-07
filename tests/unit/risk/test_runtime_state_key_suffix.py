"""F-1: RuntimeRiskState.key_suffix isolates shadow risk-state keys."""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from shared.risk.runtime_state import RuntimeRiskState


def _redis():
    return fakeredis.aioredis.FakeRedis()


def test_default_suffix_unchanged() -> None:
    rs = RuntimeRiskState(redis=_redis(), asset_class="futures")
    assert rs._risk_state._key == "risk:state:futures"
    assert rs._meta_key == "risk:state:futures:meta"


def test_shadow_suffix_isolates_keys() -> None:
    rs = RuntimeRiskState(redis=_redis(), asset_class="futures", key_suffix="shadow")
    assert rs._risk_state._key == "risk:state:futures:shadow"
    assert rs._meta_key == "risk:state:futures:shadow:meta"


def test_empty_suffix_is_noop() -> None:
    rs = RuntimeRiskState(redis=_redis(), asset_class="stock", key_suffix="")
    assert rs._risk_state._key == "risk:state:stock"
    assert rs._meta_key == "risk:state:stock:meta"


@pytest.mark.asyncio
async def test_shadow_writes_do_not_touch_live_key() -> None:
    redis = _redis()
    live = RuntimeRiskState(redis=redis, asset_class="futures")
    shadow = RuntimeRiskState(redis=redis, asset_class="futures", key_suffix="shadow")
    await shadow.record_trade(pnl_krw=-100_000.0)
    live_snap = await live.snapshot()
    shadow_snap = await shadow.snapshot()
    assert live_snap.daily_pnl_krw == 0.0  # live untouched
    assert shadow_snap.daily_pnl_krw == -100_000.0  # shadow accumulated
