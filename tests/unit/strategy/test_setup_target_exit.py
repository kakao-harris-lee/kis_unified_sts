"""Unit tests for SetupTargetExit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from shared.config import ConfigLoader
from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason
from shared.strategy.base import ExitContext
from shared.strategy.exit.setup_target_exit import (
    SetupTargetExit,
    SetupTargetExitConfig,
)


def _position(
    *,
    side: PositionSide,
    entry_price: float = 100.0,
    stop_price: float = 0.0,
    take_profit: float = 0.0,
) -> Position:
    return Position(
        id="pos-1",
        code="A05603",
        name="KOSPI200 Mini",
        side=side,
        quantity=1,
        entry_price=entry_price,
        entry_time=datetime.now(UTC) - timedelta(minutes=20),
        current_price=entry_price,
        stop_price=stop_price,
        metadata={"take_profit": take_profit},
    )


@pytest.mark.asyncio
async def test_long_exits_at_setup_stop():
    exit_strategy = SetupTargetExit(SetupTargetExitConfig(eod_close_enabled=False))
    position = _position(side=PositionSide.LONG, stop_price=98.0, take_profit=104.0)
    context = ExitContext(position=position, market_data={"close": 97.9})

    fired, signal = await exit_strategy.should_exit(context)

    assert fired is True
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS
    assert signal.priority == 1


@pytest.mark.asyncio
async def test_long_exits_at_setup_target():
    exit_strategy = SetupTargetExit(SetupTargetExitConfig(eod_close_enabled=False))
    position = _position(side=PositionSide.LONG, stop_price=98.0, take_profit=104.0)
    context = ExitContext(position=position, market_data={"close": 104.1})

    fired, signal = await exit_strategy.should_exit(context)

    assert fired is True
    assert signal is not None
    assert signal.reason == ExitReason.TARGET_REACHED
    assert signal.priority == 2


@pytest.mark.asyncio
async def test_short_uses_inverted_stop_and_target():
    exit_strategy = SetupTargetExit(SetupTargetExitConfig(eod_close_enabled=False))
    position = _position(side=PositionSide.SHORT, stop_price=102.0, take_profit=96.0)

    fired, signal = await exit_strategy.should_exit(
        ExitContext(position=position, market_data={"close": 95.9})
    )
    assert fired is True
    assert signal is not None
    assert signal.reason == ExitReason.TARGET_REACHED

    fired, signal = await exit_strategy.should_exit(
        ExitContext(position=position, market_data={"close": 102.1})
    )
    assert fired is True
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS


def test_setup_a_config_uses_setup_target_exit():
    config = ConfigLoader.load_strategy("futures", "setup_a_gap_reversion")

    assert config["strategy"]["exit"]["type"] == "setup_target_exit"
