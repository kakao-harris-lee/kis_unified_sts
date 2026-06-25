"""Hermetic tests for the trend-day trailing exit (long/short symmetric)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason
from shared.strategy.base import ExitContext
from shared.strategy.exit.trend_trail_exit import (
    TrendTrailExit,
    TrendTrailExitConfig,
)

KST = timezone(timedelta(hours=9))


def _exit(**overrides) -> TrendTrailExit:
    base = {
        "stop_atr_mult": 1.5,
        "breakeven_activation_atr": 1.0,
        "trail_activation_atr": 1.5,
        "trail_atr_mult": 2.0,
        "eod_flatten_enabled": True,
        "eod_flatten_hour": 15,
        "eod_flatten_minute": 15,
    }
    base.update(overrides)
    return TrendTrailExit(TrendTrailExitConfig(**base))


def _pos(
    side: PositionSide, entry: float, *, highest=0.0, lowest=float("inf"), atr=1.0
) -> Position:
    return Position(
        id="bt_101S6000",
        code="101S6000",
        name="KOSPI200",
        side=side,
        quantity=1,
        entry_price=entry,
        entry_time=datetime(2026, 1, 5, 10, 0, tzinfo=KST),
        current_price=entry,
        highest_price=highest,
        lowest_price=lowest,
        metadata={"entry_atr": atr},
    )


def _ctx(position, close, *, hour=11, minute=0) -> ExitContext:
    return ExitContext(
        position=position,
        market_data={"close": close, "atr": 1.0},
        indicators={"atr": 1.0},
        timestamp=datetime(2026, 1, 5, hour, minute, tzinfo=KST),
    )


# --- Hard stop ---------------------------------------------------------------


async def test_long_hard_stop():
    ex = _exit()
    pos = _pos(PositionSide.LONG, entry=600.0, atr=1.0)  # stop = 600 - 1.5 = 598.5
    should, sig = await ex.should_exit(_ctx(pos, close=598.4))
    assert should and sig.reason == ExitReason.STOP_LOSS
    assert sig.metadata["exit_type"] == "hard_stop"


async def test_short_hard_stop():
    ex = _exit()
    pos = _pos(PositionSide.SHORT, entry=600.0, atr=1.0)  # stop = 600 + 1.5 = 601.5
    should, sig = await ex.should_exit(_ctx(pos, close=601.6))
    assert should and sig.reason == ExitReason.STOP_LOSS


async def test_long_no_exit_inside_stop():
    ex = _exit()
    pos = _pos(PositionSide.LONG, entry=600.0, highest=600.5, atr=1.0)
    should, sig = await ex.should_exit(_ctx(pos, close=599.5))
    assert not should and sig is None


# --- Trailing stop -----------------------------------------------------------


async def test_long_trailing_stop_after_runup():
    ex = _exit()
    # Ran up to 605 (in_favor=5 ATR > trail_activation 1.5), now drops.
    # trail_stop = best(605) - 2.0*ATR(1) = 603. Breakeven floor = 600.
    pos = _pos(PositionSide.LONG, entry=600.0, highest=605.0, atr=1.0)
    should, sig = await ex.should_exit(_ctx(pos, close=602.9))
    assert should and sig.reason == ExitReason.TRAILING_STOP
    assert sig.metadata["trail_stop"] == pytest.approx(603.0)


async def test_short_trailing_stop_after_rundown():
    ex = _exit()
    # Ran down to 595 (in_favor=5 ATR), now bounces.
    # trail_stop = best(595) + 2.0 = 597. Breakeven cap = 600.
    pos = _pos(PositionSide.SHORT, entry=600.0, lowest=595.0, atr=1.0)
    should, sig = await ex.should_exit(_ctx(pos, close=597.1))
    assert should and sig.reason == ExitReason.TRAILING_STOP
    assert sig.metadata["trail_stop"] == pytest.approx(597.0)


async def test_trailing_not_active_before_activation():
    ex = _exit()
    # Only +1 ATR in favor (< trail_activation 1.5) → trailing not armed.
    pos = _pos(PositionSide.LONG, entry=600.0, highest=601.0, atr=1.0)
    should, sig = await ex.should_exit(_ctx(pos, close=600.2))
    assert not should


async def test_breakeven_floor_caps_long_trail_above_entry():
    ex = _exit(trail_atr_mult=10.0)  # huge trail dist would put stop far below entry
    # best=602 (in_favor 2 ATR ≥ trail 1.5 and ≥ breakeven 1.0).
    # raw trail_stop = 602 - 10 = 592, but breakeven floor lifts it to entry 600.
    pos = _pos(PositionSide.LONG, entry=600.0, highest=602.0, atr=1.0)
    should, sig = await ex.should_exit(_ctx(pos, close=599.9))
    assert should and sig.metadata["trail_stop"] == pytest.approx(600.0)


# --- EOD flatten -------------------------------------------------------------


async def test_eod_flatten_long():
    ex = _exit()
    pos = _pos(PositionSide.LONG, entry=600.0, highest=600.2, atr=1.0)
    should, sig = await ex.should_exit(_ctx(pos, close=600.1, hour=15, minute=15))
    assert should and sig.reason == ExitReason.EOD_CLOSE


async def test_eod_flatten_disabled():
    ex = _exit(eod_flatten_enabled=False)
    pos = _pos(PositionSide.LONG, entry=600.0, highest=600.2, atr=1.0)
    should, sig = await ex.should_exit(_ctx(pos, close=600.1, hour=15, minute=30))
    assert not should


async def test_hard_stop_takes_priority_over_eod():
    ex = _exit()
    pos = _pos(PositionSide.LONG, entry=600.0, atr=1.0)
    # At/after EOD AND below hard stop → hard stop (priority 1) wins.
    should, sig = await ex.should_exit(_ctx(pos, close=598.0, hour=15, minute=20))
    assert should and sig.reason == ExitReason.STOP_LOSS


def test_config_validation_rejects_bad_trail():
    with pytest.raises(AssertionError):
        TrendTrailExit(TrendTrailExitConfig(trail_atr_mult=0.0))
