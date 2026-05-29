"""Unit tests for MeanReversionExit (BB middle target + ATR stop)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason
from shared.strategy.base import ExitContext, MarketStateAdapter
from shared.strategy.exit.mean_reversion_exit import (
    MeanReversionExit,
    MeanReversionExitConfig,
)


def _minimal_config(**overrides) -> MeanReversionExitConfig:
    defaults = {
        "atr_stop_multiplier": 2.0,
        "max_stop_loss_pct": -0.03,
        "target_bb_middle": True,
        "time_cut_minutes": 120,
        "eod_close_hour": 15,
        "eod_close_minute": 15,
        "enable_bear_exit": True,
        "fee_rate": 0.003,
    }
    defaults.update(overrides)
    return MeanReversionExitConfig(**defaults)


def _position(
    *,
    entry_price: float = 100_000.0,
    entry_time: datetime | None = None,
    side: PositionSide = PositionSide.LONG,
) -> Position:
    return Position(
        id="pos_005930",
        code="005930",
        name="Samsung",
        side=side,
        quantity=10,
        entry_price=entry_price,
        entry_time=entry_time or datetime(2026, 5, 15, 9, 30, 0),
    )


def _context(
    position: Position,
    *,
    close: float,
    bb_middle: float = 0.0,
    atr: float = 0.0,
    ts: datetime | None = None,
    market_state=None,
    is_backtest: bool = True,  # default: bypass EOD/calendar coupling
) -> ExitContext:
    return ExitContext(
        position=position,
        market_data={"close": close, "bb_middle": bb_middle, "atr": atr},
        indicators={"close": close, "bb_middle": bb_middle, "atr": atr},
        timestamp=ts or datetime(2026, 5, 15, 10, 0, 0),
        market_state=market_state,
        metadata={"is_backtest": is_backtest},
    )


@pytest.mark.asyncio
async def test_bb_middle_target_triggers_exit_for_long():
    """LONG position, close >= bb_middle → TARGET_REACHED exit."""
    cfg = _minimal_config()
    strategy = MeanReversionExit(cfg)
    position = _position(entry_price=100_000.0)

    ctx = _context(position, close=102_000.0, bb_middle=102_000.0)
    should_exit, signal = await strategy.should_exit(ctx)

    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.TARGET_REACHED
    assert signal.metadata["target"] == "bb_middle"


@pytest.mark.asyncio
async def test_bb_middle_just_below_does_not_trigger():
    """close just below bb_middle → no target exit (threshold edge)."""
    cfg = _minimal_config()
    strategy = MeanReversionExit(cfg)
    position = _position(entry_price=100_000.0)

    ctx = _context(position, close=101_999.0, bb_middle=102_000.0, atr=0)
    should_exit, signal = await strategy.should_exit(ctx)
    assert should_exit is False
    assert signal is None


@pytest.mark.asyncio
async def test_hard_stop_caps_at_max_stop_loss_pct():
    """profit_pct <= max_stop_loss_pct → STOP_LOSS exit with cap applied."""
    cfg = _minimal_config()
    strategy = MeanReversionExit(cfg)
    position = _position(entry_price=100_000.0)

    # -4% loss exceeds the -3% cap.
    capped_close = 100_000.0 * (1 + cfg.max_stop_loss_pct - 0.01)
    ctx = _context(position, close=capped_close, bb_middle=0, atr=0)

    should_exit, signal = await strategy.should_exit(ctx)
    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS
    assert signal.metadata["stop_pct"] == cfg.max_stop_loss_pct


@pytest.mark.asyncio
async def test_time_cut_fires_when_held_too_long_without_profit():
    """holding_minutes >= time_cut_minutes and profit <= fee_rate → TIME_CUT."""
    cfg = _minimal_config(time_cut_minutes=30)
    strategy = MeanReversionExit(cfg)

    entry_time = datetime(2026, 5, 15, 9, 0, 0)
    position = _position(entry_price=100_000.0, entry_time=entry_time)

    # 31 minutes later, ~0 profit.
    ts = entry_time + timedelta(minutes=cfg.time_cut_minutes + 1)
    ctx = _context(position, close=100_010.0, bb_middle=0, atr=0, ts=ts)

    should_exit, signal = await strategy.should_exit(ctx)
    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.TIME_CUT


@pytest.mark.asyncio
async def test_bear_market_exit_when_enabled():
    """BEAR regime + enable_bear_exit → BEAR_EXIT."""
    cfg = _minimal_config(enable_bear_exit=True)
    strategy = MeanReversionExit(cfg)
    position = _position(entry_price=100_000.0)

    ctx = _context(
        position,
        close=100_500.0,
        bb_middle=0,
        atr=0,
        market_state=MarketStateAdapter("BEAR"),
    )
    should_exit, signal = await strategy.should_exit(ctx)
    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.BEAR_EXIT


@pytest.mark.asyncio
async def test_holds_when_within_band_and_under_stop():
    """No target, no stop, no time, no bear → no exit."""
    cfg = _minimal_config(time_cut_minutes=120)
    strategy = MeanReversionExit(cfg)
    position = _position(entry_price=100_000.0)

    ctx = _context(position, close=100_500.0, bb_middle=102_000.0, atr=0)
    should_exit, signal = await strategy.should_exit(ctx)
    assert should_exit is False
    assert signal is None


@pytest.mark.asyncio
async def test_missing_price_returns_no_exit():
    """No current price available → (False, None), no crash."""
    cfg = _minimal_config()
    strategy = MeanReversionExit(cfg)
    position = _position(entry_price=100_000.0)
    # Make sure position has no current_price fallback.
    position.current_price = 0.0

    ctx = ExitContext(
        position=position,
        market_data={},
        indicators={},
        timestamp=datetime(2026, 5, 15, 10, 0, 0),
        metadata={"is_backtest": True},
    )
    should_exit, signal = await strategy.should_exit(ctx)
    assert should_exit is False
    assert signal is None
