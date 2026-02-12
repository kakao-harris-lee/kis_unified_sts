"""Tests for MomentumDecayExit market_data contract."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from shared.models.position import Position, PositionSide, PositionState
from shared.strategy.base import ExitContext
from shared.strategy.exit.momentum_decay import MomentumDecayConfig, MomentumDecayExit


@pytest.mark.asyncio
async def test_momentum_decay_uses_code_mapped_snapshot_fields():
    strategy = MomentumDecayExit(MomentumDecayConfig())
    ts = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    position = Position(
        id="pos-1",
        code="005930",
        name="Samsung",
        side=PositionSide.LONG,
        quantity=1,
        entry_price=100.0,
        entry_time=ts - timedelta(days=1),
        current_price=120.0,
        highest_price=120.0,
        state=PositionState.SURVIVAL,
    )

    context = ExitContext(
        position=position,
        market_data={
            "005930": {
                "close": 117.0,             # 2.5% retracement from high 120
                "volume_velocity": -0.1,    # decay condition
                "vwap": 118.0,
            }
        },
        timestamp=ts,
    )

    should_exit, signal = await strategy.should_exit(context)

    assert should_exit is True
    assert signal is not None
    assert signal.reason.value in {"momentum_decay", "vwap_breakdown"}
