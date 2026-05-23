"""Tests for ChandelierExit."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from shared.models.position import Position, PositionSide, PositionState
from shared.models.signal import ExitReason
from shared.strategy.base import ExitContext
from shared.strategy.exit.chandelier_exit import ChandelierExit, ChandelierExitConfig


def _make_position(entry_time: datetime) -> Position:
    return Position(
        id="test-pos-1",
        code="005930",
        name="Samsung Electronics",
        side=PositionSide.LONG,
        quantity=10,
        entry_price=10000.0,
        entry_time=entry_time,
        current_price=10000.0,
        highest_price=10000.0,
        lowest_price=10000.0,
        state=PositionState.SURVIVAL,
        strategy="pattern_pullback",
    )


def _make_exit() -> ChandelierExit:
    return ChandelierExit(
        ChandelierExitConfig(
            atr_multiplier=1000.0,
            take_profit_pct=0.0,
            max_hold_days=3,
        )
    )


@pytest.mark.asyncio
async def test_max_hold_handles_naive_entry_with_aware_context_time():
    entry_time = datetime(2026, 5, 1, 9, 30)
    context_time = datetime(2026, 5, 6, 9, 30, tzinfo=UTC)

    should_exit, signal = await _make_exit().should_exit(
        ExitContext(
            position=_make_position(entry_time),
            market_data={"close": 10000.0},
            timestamp=context_time,
        )
    )

    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.TIME_CUT


@pytest.mark.asyncio
async def test_max_hold_handles_aware_entry_with_naive_context_time():
    entry_time = datetime(2026, 5, 1, 9, 30, tzinfo=UTC)
    context_time = datetime(2026, 5, 6, 9, 30)

    should_exit, signal = await _make_exit().should_exit(
        ExitContext(
            position=_make_position(entry_time),
            market_data={"close": 10000.0},
            timestamp=context_time,
        )
    )

    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.TIME_CUT


@pytest.mark.asyncio
async def test_max_hold_clamps_negative_mixed_timezone_duration():
    entry_time = datetime(2026, 5, 6, 9, 30, tzinfo=UTC)
    context_time = datetime(2026, 5, 1, 9, 30)

    should_exit, signal = await _make_exit().should_exit(
        ExitContext(
            position=_make_position(entry_time),
            market_data={"close": 10000.0},
            timestamp=context_time,
        )
    )

    assert should_exit is False
    assert signal is None


@pytest.mark.asyncio
async def test_chandelier_uses_position_high_since_entry_before_rolling_high():
    position = _make_position(datetime(2026, 5, 1, 9, 30))
    position.highest_price = 10500.0

    should_exit, signal = await ChandelierExit(
        ChandelierExitConfig(atr_multiplier=3.0, max_hold_days=60)
    ).should_exit(
        ExitContext(
            position=position,
            market_data={
                "close": 10100.0,
                "atr": 100.0,
                "highest_high": 12000.0,
            },
            timestamp=datetime(2026, 5, 2, 9, 30),
        )
    )

    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.TRAILING_STOP
    assert signal.metadata["chandelier_stop"] == 10200.0
    assert signal.metadata["position_highest_high"] == 10500.0
    assert signal.metadata["indicator_highest_high"] == 12000.0


@pytest.mark.asyncio
async def test_chandelier_does_not_exit_from_pre_entry_rolling_high():
    position = _make_position(datetime(2026, 5, 1, 9, 30))
    position.highest_price = 10500.0

    should_exit, signal = await ChandelierExit(
        ChandelierExitConfig(atr_multiplier=3.0, max_hold_days=60)
    ).should_exit(
        ExitContext(
            position=position,
            market_data={
                "close": 10300.0,
                "atr": 100.0,
                "highest_high": 12000.0,
            },
            timestamp=datetime(2026, 5, 2, 9, 30),
        )
    )

    assert should_exit is False
    assert signal is None
