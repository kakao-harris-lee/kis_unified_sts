"""Tests for TechnicalConsensusExit."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason
from shared.strategy.base import ExitContext
from shared.strategy.exit.technical_consensus_exit import (
    TechnicalConsensusExit,
    TechnicalConsensusExitConfig,
)

KST = timezone(timedelta(hours=9))


def _make_position(
    *,
    entry_price: float = 10000.0,
    current_price: float = 10500.0,
    highest_price: float = 11000.0,
) -> Position:
    position = Position(
        id="pos-1",
        code="005930",
        name="삼성전자",
        side=PositionSide.LONG,
        quantity=10,
        entry_price=entry_price,
        current_price=current_price,
        entry_time=datetime(2026, 5, 15, 9, 30, tzinfo=KST),
    )
    position.highest_price = highest_price
    return position


@pytest.mark.asyncio
async def test_consensus_exit_triggers_on_two_or_more_votes():
    strategy = TechnicalConsensusExit(
        TechnicalConsensusExitConfig(min_exit_votes=2, include_volume_vote=False)
    )
    position = _make_position()
    context = ExitContext(
        position=position,
        market_data={"close": 10500.0},
        indicators={
            "prev_williams_r": -8.0,
            "williams_r": -42.0,
            "prev_rsi": 74.0,
            "rsi": 58.0,
            "prev_macd_hist": 0.3,
            "macd_hist": -0.1,
            "ma20": 10600.0,
        },
        timestamp=datetime(2026, 5, 15, 13, 30, tzinfo=KST),
    )

    should_exit, signal = await strategy.should_exit(context)

    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.INDICATOR_EXIT
    assert signal.strategy == "technical_consensus_exit"
    assert signal.metadata["technical_consensus"]["exit_vote_count"] >= 2


@pytest.mark.asyncio
async def test_consensus_exit_does_not_force_eod_by_default():
    strategy = TechnicalConsensusExit(
        TechnicalConsensusExitConfig(min_exit_votes=2, include_volume_vote=False)
    )
    position = _make_position(current_price=10300.0, highest_price=10300.0)
    context = ExitContext(
        position=position,
        market_data={"close": 10300.0},
        indicators={
            "prev_williams_r": -50.0,
            "williams_r": -45.0,
            "prev_rsi": 50.0,
            "rsi": 52.0,
            "prev_macd_hist": 0.1,
            "macd_hist": 0.2,
            "ma20": 10000.0,
        },
        timestamp=datetime(2026, 5, 15, 15, 25, tzinfo=KST),
    )

    should_exit, signal = await strategy.should_exit(context)

    assert should_exit is False
    assert signal is None


@pytest.mark.asyncio
async def test_consensus_exit_keeps_hard_stop_safety_net():
    strategy = TechnicalConsensusExit(TechnicalConsensusExitConfig(hard_stop_pct=-0.07))
    position = _make_position(entry_price=10000.0, current_price=9000.0)
    context = ExitContext(
        position=position,
        market_data={"close": 9000.0},
        indicators={},
        timestamp=datetime(2026, 5, 15, 10, 0, tzinfo=KST),
    )

    should_exit, signal = await strategy.should_exit(context)

    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS
