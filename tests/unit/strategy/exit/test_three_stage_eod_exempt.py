"""eod_exempt_maximize: MAXIMIZE positions skip EOD_CLOSE; others still close."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason
from shared.strategy.exit.three_stage import ThreeStageExit, ThreeStageExitConfig

# 15:30 KST = 06:30 UTC (after the 15:15 eod_close_time).
_EOD_NOW = datetime(2026, 6, 9, 6, 30, tzinfo=UTC)


def _pos(entry: float = 10000.0) -> Position:
    return Position(
        id="p1",
        code="005930",
        name="",
        side=PositionSide.LONG,
        quantity=10,
        entry_price=entry,
    )


@pytest.mark.asyncio
async def test_maximize_exempt_from_eod_when_flag_set() -> None:
    strat = ThreeStageExit(
        ThreeStageExitConfig(eod_exempt_maximize=True, enable_bear_exit=False)
    )
    # +5% -> MAXIMIZE; price at the high so trailing stop is NOT hit.
    md = {"005930": {"close": 10500.0}}
    with patch(
        "shared.strategy.exit.three_stage.is_trading_day_kst", return_value=True
    ):
        sig = await strat._check_position(
            position=_pos(), market_data=md, market_state=None, now=_EOD_NOW
        )
    # MAXIMIZE exempt -> no EOD_CLOSE; at-high -> no trailing -> held (None).
    assert sig is None or sig.reason != ExitReason.EOD_CLOSE


@pytest.mark.asyncio
async def test_survival_still_eod_closed_with_flag() -> None:
    strat = ThreeStageExit(
        ThreeStageExitConfig(eod_exempt_maximize=True, enable_bear_exit=False)
    )
    md = {"005930": {"close": 10050.0}}  # +0.5% -> SURVIVAL
    with patch(
        "shared.strategy.exit.three_stage.is_trading_day_kst", return_value=True
    ):
        sig = await strat._check_position(
            position=_pos(), market_data=md, market_state=None, now=_EOD_NOW
        )
    assert sig is not None and sig.reason == ExitReason.EOD_CLOSE


@pytest.mark.asyncio
async def test_maximize_eod_closed_when_flag_default_false() -> None:
    # Backward-compat: default False -> MAXIMIZE is still force-closed at EOD.
    strat = ThreeStageExit(ThreeStageExitConfig(enable_bear_exit=False))
    md = {"005930": {"close": 10500.0}}  # +5% -> MAXIMIZE
    with patch(
        "shared.strategy.exit.three_stage.is_trading_day_kst", return_value=True
    ):
        sig = await strat._check_position(
            position=_pos(), market_data=md, market_state=None, now=_EOD_NOW
        )
    assert sig is not None and sig.reason == ExitReason.EOD_CLOSE
