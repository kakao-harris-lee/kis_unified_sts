"""Tests for TrendContinuationVWAPEntry."""

from datetime import datetime, timedelta, timezone

import pytest

from shared.strategy.base import EntryContext
from shared.strategy.entry.trend_continuation_vwap import (
    TrendContinuationVWAPConfig,
    TrendContinuationVWAPEntry,
)

KST = timezone(timedelta(hours=9))


def _context(**overrides) -> EntryContext:
    indicators = {
        "open": 100.0,
        "vwap": 100.0,
        "rvol": 1.8,
        "volume": 180_000,
        "volume_ma": 100_000,
        "daily_close": 120.0,
        "daily_sma_20": 110.0,
        "daily_sma_60": 100.0,
        "daily_sma_60_prev": 99.0,
        "daily_rsi_5": 65.0,
        "daily_volume_ratio": 1.4,
    }
    indicators.update(overrides.pop("indicators", {}))
    market_data = {
        "code": "005930",
        "name": "Samsung",
        "close": overrides.pop("close", 101.0),
    }
    market_data.update(overrides.pop("market_data", {}))
    metadata = {"regime": overrides.pop("regime", "BULL_STRONG")}
    metadata.update(overrides.pop("metadata", {}))
    return EntryContext(
        market_data=market_data,
        indicators=indicators,
        timestamp=overrides.pop("timestamp", datetime(2026, 5, 22, 10, 30, tzinfo=KST)),
        metadata=metadata,
    )


@pytest.fixture
def entry() -> TrendContinuationVWAPEntry:
    return TrendContinuationVWAPEntry(
        TrendContinuationVWAPConfig(signal_cooldown_seconds=0)
    )


@pytest.mark.asyncio
async def test_generates_signal_on_daily_trend_and_vwap_reclaim(entry):
    signal = await entry.generate(_context())

    assert signal is not None
    assert signal.strategy == "trend_continuation_vwap"
    assert signal.metadata["signal_direction"] == "long"
    assert signal.metadata["trigger"] == "vwap_reclaim"


@pytest.mark.asyncio
async def test_rejects_blocked_regime(entry):
    signal = await entry.generate(_context(regime="SIDEWAYS_DOWN"))

    assert signal is None


@pytest.mark.asyncio
async def test_rejects_missing_daily_trend(entry):
    signal = await entry.generate(
        _context(indicators={"daily_close": 98.0, "daily_sma_20": 110.0})
    )

    assert signal is None


@pytest.mark.asyncio
async def test_rejects_weak_vwap_reclaim(entry):
    signal = await entry.generate(_context(close=100.01))

    assert signal is None


@pytest.mark.asyncio
async def test_rejects_low_rvol(entry):
    signal = await entry.generate(_context(indicators={"rvol": 1.1}))

    assert signal is None
