"""Tests: WilliamsREntry genuine 15m timeframe contract.

Verifies that:
- Default (1m) config uses momentum_5m (backward compat)
- timeframe_minutes=15 requests momentum_15m + mtf_base_15m
- Default timeframe_minutes is 1
- The contract key (required_indicators) and the generate() read site
  resolve to the SAME _momentum_key (single source of truth — desync
  hazard guard) and generate() actually reads the tf-selected bundle
  with unchanged missing-bundle degradation.
"""
from datetime import datetime, timedelta, timezone

import pytest

from shared.strategy.base import EntryContext
from shared.strategy.entry.williams_r import WilliamsRConfig, WilliamsREntry


def test_default_is_1m_and_uses_momentum_5m():
    e = WilliamsREntry(WilliamsRConfig())
    req = list(e.required_indicators)
    assert "momentum_5m" in req
    assert not any(r.startswith("mtf_base_") for r in req)


def test_timeframe_15_requests_15m_bundles():
    e = WilliamsREntry(WilliamsRConfig(timeframe_minutes=15))
    req = list(e.required_indicators)
    assert "momentum_15m" in req
    assert "mtf_base_15m" in req
    assert "momentum_5m" not in req


def test_config_default_timeframe_is_one():
    assert WilliamsRConfig().timeframe_minutes == 1


def test_momentum_key_is_single_source_of_truth():
    """The declared contract key and the generate() read key MUST be the
    same _momentum_key — desync = silent permanent None from generate()."""
    e1 = WilliamsREntry(WilliamsRConfig())
    assert e1._momentum_key == "momentum_5m"
    assert e1._momentum_key in e1.required_indicators

    e15 = WilliamsREntry(WilliamsRConfig(timeframe_minutes=15))
    assert e15._momentum_key == "momentum_15m"
    assert e15._momentum_key in e15.required_indicators


def _ctx_15m(williams_r: float, *, minute: int, with_bundle: bool = True):
    """Minimal valid EntryContext for the tf=15 path (mirrors the real
    momentum_5m unit-test helper, but feeds the momentum_15m bundle)."""
    now = datetime(2026, 2, 25, 10, minute, tzinfo=timezone(timedelta(hours=9)))
    indicators = {
        "bb_middle": 49000,
        "volume": 1000,
        "volume_ma": 900,
    }
    if with_bundle:
        indicators["momentum_15m"] = {"williams_r": williams_r}
    return EntryContext(
        market_data={"code": "005930", "name": "삼성전자", "close": 50000},
        indicators=indicators,
        timestamp=now,
    )


@pytest.mark.asyncio
async def test_generate_reads_tf_selected_bundle():
    """generate() with timeframe_minutes=15 must read the momentum_15m
    bundle (proves the read site uses _momentum_key, not a hardcoded
    momentum_5m) and fire an oversold-reversal long."""
    e = WilliamsREntry(WilliamsRConfig(timeframe_minutes=15))

    # First call seeds prev %R (deep oversold) — no signal yet.
    r1 = await e.generate(_ctx_15m(-90.0, minute=20))
    assert r1 is None

    # Second call: %R reverses up above threshold → long entry signal.
    r2 = await e.generate(_ctx_15m(-75.0, minute=35))
    assert r2 is not None
    assert r2.metadata["signal_direction"] == "long"
    assert r2.metadata["williams_r"] == -75.0


@pytest.mark.asyncio
async def test_generate_missing_bundle_degrades_to_none():
    """Missing momentum_15m bundle (e.g. mid-warmup) → None, identical
    degradation to the 1m momentum_5m path."""
    e = WilliamsREntry(WilliamsRConfig(timeframe_minutes=15))
    result = await e.generate(_ctx_15m(-75.0, minute=20, with_bundle=False))
    assert result is None
