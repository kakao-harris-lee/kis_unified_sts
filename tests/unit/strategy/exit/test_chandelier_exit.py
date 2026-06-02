"""Unit tests for ChandelierExit (daily trailing stop)."""

from __future__ import annotations

from datetime import datetime

import pytest

from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason
from shared.strategy.base import ExitContext
from shared.strategy.exit.chandelier_exit import (
    ChandelierExit,
    ChandelierExitConfig,
)


def _minimal_config(**overrides) -> ChandelierExitConfig:
    defaults = {
        "atr_period": 22,
        "atr_multiplier": 3.0,
        "lookback_period": 22,
        "hard_stop_pct": -0.07,
        "take_profit_pct": 0.0,
        "max_hold_days": 60,
        "default_exit_confidence": 0.85,
    }
    defaults.update(overrides)
    return ChandelierExitConfig(**defaults)


def _position(
    *,
    entry_price: float = 70_000.0,
    entry_time: datetime | None = None,
    code: str = "005930",
) -> Position:
    return Position(
        id=f"pos_{code}",
        code=code,
        name="Samsung",
        side=PositionSide.LONG,
        quantity=10,
        entry_price=entry_price,
        entry_time=entry_time or datetime(2026, 5, 14, 10, 0, 0),
    )


def _context(
    position: Position,
    *,
    close: float,
    atr: float = 0.0,
    highest_high: float = 0.0,
    holding_days: int = 0,
    ts: datetime | None = None,
) -> ExitContext:
    return ExitContext(
        position=position,
        market_data={"close": close},
        indicators={
            "atr": atr,
            "highest_high": highest_high,
            "holding_days": holding_days,
        },
        timestamp=ts or datetime(2026, 5, 15, 10, 0, 0),
    )


@pytest.mark.asyncio
async def test_hard_stop_triggers_at_threshold():
    """Loss <= hard_stop_pct → STOP_LOSS exit (priority 1)."""
    cfg = _minimal_config()
    strategy = ChandelierExit(cfg)
    position = _position(entry_price=100_000.0)

    # profit_pct = -7% exactly = hard_stop_pct
    stop_price = 100_000.0 * (1.0 + cfg.hard_stop_pct)
    ctx = _context(position, close=stop_price, atr=500, highest_high=110_000)

    should_exit, signal = await strategy.should_exit(ctx)

    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS
    assert signal.priority == 1
    assert signal.metadata["exit_type"] == "hard_stop"


@pytest.mark.asyncio
async def test_hard_stop_just_above_threshold_no_exit():
    """Loss just above hard_stop_pct → no hard-stop (threshold edge)."""
    cfg = _minimal_config()
    strategy = ChandelierExit(cfg)
    position = _position(entry_price=100_000.0)

    # profit_pct just above hard_stop_pct (e.g., -6.99%)
    above = 100_000.0 * (1.0 + cfg.hard_stop_pct + 0.001)
    # ChandelierExit uses position.highest_price (use_position_high_since_entry
    # default=True, and Position.__post_init__ seeds it to entry_price). Align
    # it with the non-triggering trailing high so chandelier_stop stays below
    # close and no trailing exit fires.
    position.highest_price = above + 10
    # Provide non-triggering trailing (close above chandelier_stop).
    ctx = _context(position, close=above, atr=100, highest_high=above + 10)

    should_exit, signal = await strategy.should_exit(ctx)
    assert should_exit is False
    assert signal is None


@pytest.mark.asyncio
async def test_chandelier_trailing_stop_triggers():
    """close < highest_high - ATR×multiplier → TRAILING_STOP exit."""
    cfg = _minimal_config(atr_multiplier=3.0)
    strategy = ChandelierExit(cfg)
    position = _position(entry_price=100_000.0)

    highest_high = 110_000.0
    atr = 1_000.0
    chandelier_stop = highest_high - atr * cfg.atr_multiplier  # = 107_000

    # ChandelierExit prefers position.highest_price (use_position_high_since_entry
    # default=True); set the post-entry high under test so the indicator path
    # and the position path agree on chandelier_stop.
    position.highest_price = highest_high

    ctx = _context(
        position,
        close=chandelier_stop - 100,  # below stop
        atr=atr,
        highest_high=highest_high,
    )
    should_exit, signal = await strategy.should_exit(ctx)

    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.TRAILING_STOP
    assert signal.metadata["exit_type"] == "chandelier"
    assert signal.metadata["chandelier_stop"] == pytest.approx(chandelier_stop)


@pytest.mark.asyncio
async def test_chandelier_above_stop_no_exit():
    """close above chandelier_stop → no exit (trailing edge)."""
    cfg = _minimal_config()
    strategy = ChandelierExit(cfg)
    position = _position(entry_price=100_000.0)

    highest_high = 110_000.0
    atr = 1_000.0
    chandelier_stop = highest_high - atr * cfg.atr_multiplier

    # ChandelierExit prefers position.highest_price (use_position_high_since_entry
    # default=True); set the post-entry high under test.
    position.highest_price = highest_high

    ctx = _context(
        position,
        close=chandelier_stop + 100,  # above stop
        atr=atr,
        highest_high=highest_high,
    )
    should_exit, signal = await strategy.should_exit(ctx)
    assert should_exit is False
    assert signal is None


@pytest.mark.asyncio
async def test_max_hold_days_triggers_time_cut():
    """holding_days >= max_hold_days → TIME_CUT exit."""
    cfg = _minimal_config(max_hold_days=10)
    strategy = ChandelierExit(cfg)
    position = _position(entry_price=100_000.0)

    ctx = _context(
        position,
        close=100_500.0,  # small profit, no hard stop
        atr=0,
        highest_high=0,
        holding_days=cfg.max_hold_days,
    )
    should_exit, signal = await strategy.should_exit(ctx)
    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.TIME_CUT
    assert signal.metadata["holding_days"] == cfg.max_hold_days


@pytest.mark.asyncio
async def test_take_profit_fires_when_enabled():
    """take_profit_pct > 0 and profit >= threshold → TARGET_REACHED."""
    cfg = _minimal_config(take_profit_pct=0.10)
    strategy = ChandelierExit(cfg)
    position = _position(entry_price=100_000.0)

    target_close = 100_000.0 * (1 + cfg.take_profit_pct)
    ctx = _context(position, close=target_close, atr=0, highest_high=0)
    should_exit, signal = await strategy.should_exit(ctx)

    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.TARGET_REACHED
    assert signal.metadata["exit_type"] == "take_profit"


@pytest.mark.asyncio
async def test_missing_close_returns_no_exit():
    """Missing close price → (False, None), no crash."""
    cfg = _minimal_config()
    strategy = ChandelierExit(cfg)
    position = _position()

    ctx = ExitContext(
        position=position,
        market_data={},
        indicators={},
        timestamp=datetime(2026, 5, 15, 10, 0, 0),
    )
    should_exit, signal = await strategy.should_exit(ctx)
    assert should_exit is False
    assert signal is None
