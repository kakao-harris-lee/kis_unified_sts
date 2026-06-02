"""Unit tests for VRCompositeExit (daily VR + RSI + MA composite exit)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason
from shared.strategy.base import ExitContext
from shared.strategy.exit.vr_composite_exit import (
    VRCompositeExit,
    VRCompositeExitConfig,
)


def _minimal_config(**overrides) -> VRCompositeExitConfig:
    defaults = {
        "vr_period": 20,
        "vr_overheat_threshold": 300.0,
        "vr_extreme_overheat_threshold": 400.0,
        "rsi_period": 14,
        "rsi_overbought": 70.0,
        "ma_short": 5,
        "ma_mid": 20,
        "ma_long": 60,
        "hard_stop_pct": -0.07,
        "max_hold_days": 60,
        "show_warnings": False,
    }
    defaults.update(overrides)
    return VRCompositeExitConfig(**defaults)


def _position(
    *,
    entry_price: float = 100_000.0,
    entry_time: datetime | None = None,
) -> Position:
    return Position(
        id="pos_005930",
        code="005930",
        name="Samsung",
        side=PositionSide.LONG,
        quantity=10,
        entry_price=entry_price,
        entry_time=entry_time or datetime(2026, 5, 15, 10, 0, 0),
    )


def _overheated_series(length: int = 65):
    """Mostly ascending closes with occasional small dips.

    Produces VR well above 400 and RSI well above 70, triggering Rule 1.
    Includes a down day in the RSI seed window so the seeding division is well-defined.
    """
    # Down days at indices 5, 25, 45 keep VR denominator > 0 in every
    # 20-bar window and provide a non-zero loss in the RSI seed window (first 14).
    down_days = {5, 25, 45}
    closes = []
    price = 100.0
    for i in range(length):
        if i in down_days:
            price -= 0.5
        else:
            price += 1.0
        closes.append(price)
    volumes = [1_000] * length
    return closes, volumes


def _flat_series(length: int = 65, price: float = 100.0):
    """Alternating closes → no exit rule triggers."""
    closes = [price + (1.0 if i % 2 == 0 else -1.0) for i in range(length)]
    volumes = [1_000] * length
    return closes, volumes


def _context(
    position: Position,
    *,
    close: float,
    closes=None,
    volumes=None,
    ts: datetime | None = None,
) -> ExitContext:
    indicators = {}
    if closes is not None:
        indicators["daily_closes"] = closes
    if volumes is not None:
        indicators["daily_volumes"] = volumes
    return ExitContext(
        position=position,
        market_data={"close": close},
        indicators=indicators,
        timestamp=ts or datetime(2026, 5, 15, 10, 0, 0),
    )


@pytest.mark.asyncio
async def test_hard_stop_priority_zero():
    """profit_pct <= hard_stop_pct → STOP_LOSS at priority 1."""
    cfg = _minimal_config()
    strategy = VRCompositeExit(cfg)
    position = _position(entry_price=100_000.0)

    stop_close = 100_000.0 * (1.0 + cfg.hard_stop_pct)
    ctx = _context(position, close=stop_close)
    should_exit, signal = await strategy.should_exit(ctx)

    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS
    assert signal.priority == 1
    assert signal.metadata["trigger"] == "hard_stop"


@pytest.mark.asyncio
async def test_max_hold_days_triggers_time_cut():
    """hold_days >= max_hold_days → TIME_CUT."""
    cfg = _minimal_config(max_hold_days=10)
    strategy = VRCompositeExit(cfg)

    entry = datetime(2026, 5, 1, 10, 0, 0)
    position = _position(entry_price=100_000.0, entry_time=entry)
    ts = entry + timedelta(days=cfg.max_hold_days + 1)

    ctx = _context(position, close=100_500.0, ts=ts)
    should_exit, signal = await strategy.should_exit(ctx)
    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.TIME_CUT
    assert signal.metadata["trigger"] == "max_hold_days"


@pytest.mark.asyncio
async def test_strong_sell_when_extreme_overheat_and_overbought():
    """VR >= extreme_overheat + RSI >= overbought → INDICATOR_EXIT (rule 1)."""
    cfg = _minimal_config()
    strategy = VRCompositeExit(cfg)
    position = _position(entry_price=50.0)  # well below current close to avoid stops

    closes, volumes = _overheated_series()
    ctx = _context(position, close=closes[-1], closes=closes, volumes=volumes)

    should_exit, signal = await strategy.should_exit(ctx)
    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.INDICATOR_EXIT
    md = signal.metadata
    assert md["vr"] >= cfg.vr_extreme_overheat_threshold
    assert md["rsi"] >= cfg.rsi_overbought
    # Confidence must match one of the configured tiers.
    tiers = {
        cfg.confidence_strong_sell_1,
        cfg.confidence_strong_sell_2,
        cfg.confidence_sell_3,
        cfg.confidence_sell_4,
    }
    assert signal.confidence in tiers


@pytest.mark.asyncio
async def test_flat_series_no_exit_signal():
    """Flat alternating closes → no exit rule fires."""
    cfg = _minimal_config()
    strategy = VRCompositeExit(cfg)
    position = _position(entry_price=99.0)  # ensure no profit/stop trigger

    closes, volumes = _flat_series()
    ctx = _context(position, close=closes[-1], closes=closes, volumes=volumes)

    should_exit, signal = await strategy.should_exit(ctx)
    assert should_exit is False
    assert signal is None


@pytest.mark.asyncio
async def test_insufficient_history_returns_no_exit():
    """closes shorter than required → (False, None)."""
    cfg = _minimal_config()
    strategy = VRCompositeExit(cfg)
    position = _position(entry_price=50.0)

    short_closes = [100.0 + i for i in range(30)]  # < ma_long
    short_vols = [1_000] * 30
    ctx = _context(
        position, close=short_closes[-1], closes=short_closes, volumes=short_vols
    )

    should_exit, signal = await strategy.should_exit(ctx)
    assert should_exit is False
    assert signal is None


@pytest.mark.asyncio
async def test_missing_close_returns_no_exit():
    """close == 0 → (False, None)."""
    cfg = _minimal_config()
    strategy = VRCompositeExit(cfg)
    position = _position()

    ctx = ExitContext(
        position=position,
        market_data={"close": 0},
        indicators={},
        timestamp=datetime(2026, 5, 15, 10, 0, 0),
    )
    should_exit, signal = await strategy.should_exit(ctx)
    assert should_exit is False
    assert signal is None
