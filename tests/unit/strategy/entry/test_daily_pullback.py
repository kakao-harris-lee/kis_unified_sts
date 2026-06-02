"""Unit tests for DailyPullbackEntry (stock daily pullback)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from shared.models.signal import SignalType
from shared.strategy.base import EntryContext
from shared.strategy.entry.daily_pullback import (
    DailyPullbackConfig,
    DailyPullbackEntry,
)


def _minimal_config(**overrides) -> DailyPullbackConfig:
    """Minimal config matching the YAML contract; overrides are applied last."""
    defaults = {
        "sma_long_period": 200,
        "sma_short_period": 20,
        "sma_mid_period": 60,
        "rsi_period": 5,
        "rsi_oversold": 45.0,
        "require_mid_trend": True,
        "mid_trend_lookback": 5,
        "stop_loss_pct": 7.0,
        "signal_cooldown_days": 0,  # disabled for most tests
        "confidence_base": 0.6,
        "min_confidence": 0.0,
    }
    defaults.update(overrides)
    return DailyPullbackConfig(**defaults)


def _context(
    *,
    close: float,
    sma_200: float,
    sma_20: float,
    rsi_5: float,
    sma_60: float = 0.0,
    sma_60_prev: float = 0.0,
    code: str = "005930",
    timestamp: datetime | None = None,
) -> EntryContext:
    return EntryContext(
        market_data={"code": code, "name": "Samsung", "close": close},
        indicators={
            "sma_200": sma_200,
            "sma_20": sma_20,
            "sma_60": sma_60,
            "sma_60_prev": sma_60_prev,
            "rsi_5": rsi_5,
        },
        timestamp=timestamp or datetime(2026, 5, 15, 10, 0, 0),
    )


@pytest.mark.asyncio
async def test_happy_path_emits_long_signal_with_metadata():
    """All four conditions met → long ENTRY signal with stop_loss + metadata."""
    cfg = _minimal_config(require_mid_trend=False)
    strategy = DailyPullbackEntry(cfg)

    ctx = _context(
        close=70_000,
        sma_200=65_000,  # close > sma_200 → uptrend
        sma_20=71_000,  # close <= sma_20 → pullback
        rsi_5=30.0,  # below rsi_oversold → oversold
    )

    signal = await strategy.generate(ctx)

    assert signal is not None
    assert signal.signal_type == SignalType.ENTRY
    assert signal.strategy == "daily_pullback"
    assert signal.confidence > 0
    assert signal.metadata["signal_direction"] == "long"
    assert signal.metadata["trigger"] == "pullback_to_sma20"
    # stop_loss derived from config, no magic number in test
    expected_stop = 70_000 * (1.0 - cfg.stop_loss_pct / 100.0)
    assert signal.metadata["stop_loss"] == pytest.approx(expected_stop)


@pytest.mark.asyncio
async def test_rsi_threshold_just_above_blocks_signal():
    """RSI at or above rsi_oversold → no signal (threshold edge)."""
    cfg = _minimal_config(require_mid_trend=False)
    strategy = DailyPullbackEntry(cfg)

    ctx_block = _context(
        close=70_000,
        sma_200=65_000,
        sma_20=71_000,
        rsi_5=cfg.rsi_oversold,  # NOT strictly less than threshold
    )
    assert await strategy.generate(ctx_block) is None

    # Just below threshold → signal emitted
    ctx_pass = _context(
        close=70_000,
        sma_200=65_000,
        sma_20=71_000,
        rsi_5=cfg.rsi_oversold - 0.1,
    )
    assert await strategy.generate(ctx_pass) is not None


@pytest.mark.asyncio
async def test_long_trend_filter_blocks_when_below_sma200():
    """close <= SMA(200) → no signal (long-trend filter)."""
    cfg = _minimal_config(require_mid_trend=False)
    strategy = DailyPullbackEntry(cfg)

    ctx = _context(close=60_000, sma_200=65_000, sma_20=71_000, rsi_5=30.0)
    assert await strategy.generate(ctx) is None


@pytest.mark.asyncio
async def test_pullback_filter_blocks_when_above_sma20():
    """close > SMA(20) → not in pullback → no signal."""
    cfg = _minimal_config(require_mid_trend=False)
    strategy = DailyPullbackEntry(cfg)

    ctx = _context(close=72_000, sma_200=65_000, sma_20=71_000, rsi_5=30.0)
    assert await strategy.generate(ctx) is None


@pytest.mark.asyncio
async def test_mid_trend_filter_blocks_when_sma60_falling():
    """require_mid_trend=True and SMA(60) declining → no signal."""
    cfg = _minimal_config(require_mid_trend=True)
    strategy = DailyPullbackEntry(cfg)

    ctx = _context(
        close=70_000,
        sma_200=65_000,
        sma_20=71_000,
        rsi_5=30.0,
        sma_60=67_000,
        sma_60_prev=68_000,  # falling
    )
    assert await strategy.generate(ctx) is None


@pytest.mark.asyncio
async def test_cooldown_blocks_repeat_signal_within_window():
    """Within signal_cooldown_days, a second call for the same code returns None."""
    cooldown = 5
    cfg = _minimal_config(require_mid_trend=False, signal_cooldown_days=cooldown)
    strategy = DailyPullbackEntry(cfg)

    base_ts = datetime(2026, 5, 15, 10, 0, 0)
    first = await strategy.generate(
        _context(
            close=70_000,
            sma_200=65_000,
            sma_20=71_000,
            rsi_5=30.0,
            timestamp=base_ts,
        )
    )
    assert first is not None

    # Same code, within cooldown → blocked
    next_within = await strategy.generate(
        _context(
            close=70_000,
            sma_200=65_000,
            sma_20=71_000,
            rsi_5=30.0,
            timestamp=base_ts + timedelta(days=cooldown - 1),
        )
    )
    assert next_within is None

    # After cooldown → allowed
    after = await strategy.generate(
        _context(
            close=70_000,
            sma_200=65_000,
            sma_20=71_000,
            rsi_5=30.0,
            timestamp=base_ts + timedelta(days=cooldown + 1),
        )
    )
    assert after is not None


@pytest.mark.asyncio
async def test_missing_market_data_returns_none():
    """Empty market data / missing code → no signal, no crash."""
    cfg = _minimal_config(require_mid_trend=False)
    strategy = DailyPullbackEntry(cfg)

    empty_ctx = EntryContext(
        market_data={},
        indicators={},
        timestamp=datetime(2026, 5, 15, 10, 0, 0),
    )
    assert await strategy.generate(empty_ctx) is None


def test_required_indicators_advertises_contract():
    """Strategy exposes required_indicators for upstream orchestration."""
    strategy = DailyPullbackEntry(_minimal_config())
    required = strategy.required_indicators
    for key in ("sma_200", "sma_20", "sma_60", "rsi_5"):
        assert key in required
