"""Unit tests for VRCompositeEntry (daily VR + RSI + MA composite)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from shared.models.signal import SignalType
from shared.strategy.base import EntryContext
from shared.strategy.entry.vr_composite import (
    VRCompositeConfig,
    VRCompositeEntry,
)


def _minimal_config(**overrides) -> VRCompositeConfig:
    """Config matching the YAML contract."""
    defaults = {
        "vr_period": 20,
        "vr_bottom_threshold": 60.0,
        "vr_depression_threshold": 70.0,
        "rsi_period": 14,
        "rsi_oversold": 30.0,
        "rsi_weak_oversold": 35.0,
        "rsi_neutral_upper": 50.0,
        "ma_short": 5,
        "ma_mid": 20,
        "ma_long": 60,
        "signal_cooldown_days": 0,  # disabled for most tests
        "show_warnings": False,
    }
    defaults.update(overrides)
    return VRCompositeConfig(**defaults)


def _declining_series(length: int = 65, start: float = 100.0, end: float = 40.0):
    """Monotonically declining closes + heavier-on-down volumes.

    Produces VR ≈ 0 (all changes down) and RSI ≈ 0 (no gains),
    deterministically satisfying VR <= 60 and RSI <= 30.
    """
    step = (start - end) / (length - 1)
    closes = [start - step * i for i in range(length)]
    volumes = [1_000] * length
    return closes, volumes


def _flat_series(length: int = 65, price: float = 100.0):
    """Alternating up/down ticks → VR ~100, RSI ~50, no buy rule fires."""
    closes = []
    for i in range(length):
        closes.append(price + (1.0 if i % 2 == 0 else -1.0))
    volumes = [1_000] * length
    return closes, volumes


def _context(closes, volumes, *, code: str = "005930", ts: datetime | None = None):
    return EntryContext(
        market_data={"code": code, "name": "Samsung"},
        indicators={"daily_closes": closes, "daily_volumes": volumes},
        timestamp=ts or datetime(2026, 5, 15, 10, 0, 0),
    )


@pytest.mark.asyncio
async def test_happy_path_strong_buy_emits_signal():
    """Long downtrend → VR<=bottom + RSI<=oversold → BUY signal."""
    cfg = _minimal_config()
    strategy = VRCompositeEntry(cfg)

    closes, volumes = _declining_series()
    signal = await strategy.generate(_context(closes, volumes))

    assert signal is not None
    assert signal.signal_type == SignalType.ENTRY
    assert signal.strategy == "vr_composite"
    assert signal.confidence > 0
    # Confidence must match one of the configured tiers (no magic numbers).
    tiers = {
        cfg.confidence_strong_buy_1,
        cfg.confidence_strong_buy_2,
        cfg.confidence_buy_3,
        cfg.confidence_buy_4,
        cfg.confidence_buy_5,
    }
    assert signal.confidence in tiers
    md = signal.metadata
    assert md["vr"] <= cfg.vr_depression_threshold
    assert md["rsi"] <= cfg.rsi_weak_oversold
    assert md["strategy_type"] == "daily"
    assert "reasons" in md


@pytest.mark.asyncio
async def test_flat_series_yields_no_signal():
    """VR≈100 and RSI≈50 → no entry rule satisfied."""
    cfg = _minimal_config()
    strategy = VRCompositeEntry(cfg)

    closes, volumes = _flat_series()
    assert await strategy.generate(_context(closes, volumes)) is None


@pytest.mark.asyncio
async def test_insufficient_history_returns_none():
    """closes shorter than vr_period + ma_long requirement → None, no crash."""
    cfg = _minimal_config()
    strategy = VRCompositeEntry(cfg)

    closes, volumes = _declining_series(length=30)  # < ma_long (60)
    assert await strategy.generate(_context(closes, volumes)) is None


@pytest.mark.asyncio
async def test_missing_series_returns_none():
    """No daily_closes / daily_volumes provided → None, no crash."""
    strategy = VRCompositeEntry(_minimal_config())

    ctx = EntryContext(
        market_data={"code": "005930"},
        indicators={},
        timestamp=datetime(2026, 5, 15, 10, 0, 0),
    )
    assert await strategy.generate(ctx) is None


@pytest.mark.asyncio
async def test_cooldown_blocks_repeat_signal_within_window():
    """Within signal_cooldown_days, repeat signals are suppressed."""
    cooldown = 3
    cfg = _minimal_config(signal_cooldown_days=cooldown)
    strategy = VRCompositeEntry(cfg)

    closes, volumes = _declining_series()
    base = datetime(2026, 5, 15, 10, 0, 0)

    first = await strategy.generate(_context(closes, volumes, ts=base))
    assert first is not None

    blocked = await strategy.generate(
        _context(closes, volumes, ts=base + timedelta(days=cooldown - 1))
    )
    assert blocked is None

    after = await strategy.generate(
        _context(closes, volumes, ts=base + timedelta(days=cooldown + 1))
    )
    assert after is not None


@pytest.mark.asyncio
async def test_missing_code_returns_none():
    """Empty code → None (input validation)."""
    strategy = VRCompositeEntry(_minimal_config())
    closes, volumes = _declining_series()
    ctx = EntryContext(
        market_data={"code": ""},
        indicators={"daily_closes": closes, "daily_volumes": volumes},
        timestamp=datetime(2026, 5, 15, 10, 0, 0),
    )
    assert await strategy.generate(ctx) is None


def test_required_indicators_lists_daily_series():
    strategy = VRCompositeEntry(_minimal_config())
    required = strategy.required_indicators
    assert "daily_closes" in required
    assert "daily_volumes" in required
