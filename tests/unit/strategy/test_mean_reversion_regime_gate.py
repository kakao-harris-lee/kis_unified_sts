import datetime as dt
from unittest.mock import MagicMock

import pytest


def _ctx_long_trigger():
    """Build a context that triggers the LONG entry path.

    Uses a fixed KST market-hours timestamp (10:00 KST = 01:00 UTC) to
    avoid time-fragile failures when the test runs before 09:00 KST.
    """
    from zoneinfo import ZoneInfo

    from shared.strategy.base import EntryContext

    _KST = ZoneInfo("Asia/Seoul")
    today_kst = dt.datetime.now(_KST).date()
    ts = dt.datetime(
        today_kst.year, today_kst.month, today_kst.day, 10, 0, 0, tzinfo=_KST
    )
    return EntryContext(
        market_data={"code": "futures", "name": "futures", "close": 100.0},
        indicators={
            "bb_lower": 100.0,
            "bb_upper": 200.0,
            "bb_middle": 150.0,
            "rsi": 25.0,
            "volume": 1000,
            "volume_ma": 500,
            "atr": 2.0,
        },
        timestamp=ts,
    )


def _cfg_gate():
    from shared.strategy.gates.regime_gate import GateConfig

    return GateConfig(
        regime_percentile_max=60.0,
        impact_score_max=70,
        event_window_minutes=15,
        require_overnight_us_direction=False,
        permissive_on_missing=True,
    )


def _stub_infra(monkeypatch, module):
    from shared.streaming.client import RedisClient

    monkeypatch.setattr(
        RedisClient, "get_client", classmethod(lambda _cls: MagicMock())
    )


def test_gate_cfg_none_default():
    """gate_cfg defaults to None on MeanReversionEntry."""
    from shared.strategy.entry.mean_reversion import (
        MeanReversionConfig,
        MeanReversionEntry,
    )

    entry = MeanReversionEntry(MeanReversionConfig(allow_short=False))
    assert entry._gate_cfg is None


def test_gate_cfg_stored_when_passed():
    """gate_cfg kwarg is stored on the entry."""
    from shared.strategy.entry.mean_reversion import (
        MeanReversionConfig,
        MeanReversionEntry,
    )

    cfg = _cfg_gate()
    entry = MeanReversionEntry(MeanReversionConfig(allow_short=False), gate_cfg=cfg)
    assert entry._gate_cfg is cfg


@pytest.mark.asyncio
async def test_regime_gate_blocks_long_returns_none(monkeypatch):
    from shared.strategy.entry import mean_reversion as mr

    cfg = mr.MeanReversionConfig(allow_short=False, regime_filter=False)
    entry = mr.MeanReversionEntry(cfg, gate_cfg=_cfg_gate())
    _stub_infra(monkeypatch, mr)
    monkeypatch.setattr(mr, "apply_regime_gate", lambda **_kw: True)  # block
    result = await entry.generate(_ctx_long_trigger())
    assert result is None


@pytest.mark.asyncio
async def test_regime_gate_allows_long_returns_signal(monkeypatch):
    from shared.strategy.entry import mean_reversion as mr

    cfg = mr.MeanReversionConfig(allow_short=False, regime_filter=False)
    entry = mr.MeanReversionEntry(cfg, gate_cfg=_cfg_gate())
    _stub_infra(monkeypatch, mr)
    monkeypatch.setattr(mr, "apply_regime_gate", lambda **_kw: False)  # allow
    result = await entry.generate(_ctx_long_trigger())
    assert result is not None
    assert result.metadata["signal_direction"] == "long"


@pytest.mark.asyncio
async def test_gate_degrades_permissive_when_redis_unavailable(monkeypatch):
    """When Redis client construction raises, the gate hook short-circuits
    PERMISSIVE and the signal passes through."""
    from shared.strategy.entry import mean_reversion as mr
    from shared.streaming.client import RedisClient

    entry = mr.MeanReversionEntry(
        mr.MeanReversionConfig(allow_short=False, regime_filter=False),
        gate_cfg=_cfg_gate(),
    )
    monkeypatch.setattr(
        RedisClient,
        "get_client",
        classmethod(lambda _cls: (_ for _ in ()).throw(RuntimeError("redis down"))),
    )
    gate_called = []
    monkeypatch.setattr(
        mr, "apply_regime_gate", lambda **kw: gate_called.append(kw) or False
    )
    result = await entry.generate(_ctx_long_trigger())
    assert result is not None
    assert gate_called == []
