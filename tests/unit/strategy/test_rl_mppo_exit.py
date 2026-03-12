"""Unit tests for RLMPPOExit."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason
from shared.strategy.base import ExitContext
from shared.strategy.exit.rl_mppo_exit import RLMPPOExit, RLMPPOExitConfig


KST = timezone(timedelta(hours=9))


def _make_position(
    *,
    side: PositionSide = PositionSide.SHORT,
    entry_price: float = 100.0,
    current_price: float = 101.0,
    entry_time: datetime | None = None,
) -> Position:
    if entry_time is None:
        entry_time = datetime(2026, 3, 12, 10, 0, 0, tzinfo=KST)
    return Position(
        id="pos-1",
        code="A05603",
        name="KOSPI200 Mini",
        side=side,
        quantity=1,
        entry_price=entry_price,
        entry_time=entry_time,
        current_price=current_price,
    )


def _make_exit_strategy(config: RLMPPOExitConfig | None = None) -> RLMPPOExit:
    strategy = RLMPPOExit(config or RLMPPOExitConfig())
    strategy._load_model = lambda: SimpleNamespace(predict=lambda *_args, **_kwargs: (3, None))
    strategy._build_observation = lambda _position, _context: np.zeros(31, dtype=np.float32)
    return strategy


@pytest.mark.asyncio
async def test_should_exit_blocks_rl_exit_before_min_hold(monkeypatch):
    strategy = _make_exit_strategy(
        RLMPPOExitConfig(min_hold_seconds=60, backtest_min_hold_seconds=0)
    )
    monkeypatch.setattr(
        "shared.strategy.exit.rl_mppo_exit.get_action_confidence",
        lambda *_args, **_kwargs: 0.95,
    )

    now = datetime(2026, 3, 12, 10, 0, 20, tzinfo=KST)
    position = _make_position(entry_time=now - timedelta(seconds=20))
    context = ExitContext(
        position=position,
        market_data={"last_price": 101.0},
        timestamp=now,
        metadata={"is_backtest": False},
    )

    should_exit, signal = await strategy.should_exit(context)

    assert should_exit is False
    assert signal is None


@pytest.mark.asyncio
async def test_should_exit_allows_rl_exit_after_min_hold(monkeypatch):
    strategy = _make_exit_strategy(
        RLMPPOExitConfig(min_hold_seconds=60, backtest_min_hold_seconds=0)
    )
    monkeypatch.setattr(
        "shared.strategy.exit.rl_mppo_exit.get_action_confidence",
        lambda *_args, **_kwargs: 0.95,
    )

    now = datetime(2026, 3, 12, 10, 2, 0, tzinfo=KST)
    position = _make_position(entry_time=now - timedelta(seconds=90))
    context = ExitContext(
        position=position,
        market_data={"last_price": 101.0},
        timestamp=now,
        metadata={"is_backtest": False},
    )

    should_exit, signal = await strategy.should_exit(context)

    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.RL_EXIT


@pytest.mark.asyncio
async def test_should_exit_uses_backtest_min_hold_override(monkeypatch):
    strategy = _make_exit_strategy(
        RLMPPOExitConfig(min_hold_seconds=60, backtest_min_hold_seconds=0)
    )
    monkeypatch.setattr(
        "shared.strategy.exit.rl_mppo_exit.get_action_confidence",
        lambda *_args, **_kwargs: 0.95,
    )

    now = datetime(2026, 3, 12, 10, 0, 10, tzinfo=KST)
    position = _make_position(entry_time=now - timedelta(seconds=10))
    context = ExitContext(
        position=position,
        market_data={"last_price": 101.0},
        timestamp=now,
        metadata={"is_backtest": True},
    )

    should_exit, signal = await strategy.should_exit(context)

    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.RL_EXIT


@pytest.mark.asyncio
async def test_hard_stop_bypasses_min_hold(monkeypatch):
    strategy = _make_exit_strategy(
        RLMPPOExitConfig(min_hold_seconds=60, backtest_min_hold_seconds=0, hard_stop_pct=-0.03)
    )
    monkeypatch.setattr(
        "shared.strategy.exit.rl_mppo_exit.get_action_confidence",
        lambda *_args, **_kwargs: 0.95,
    )

    now = datetime(2026, 3, 12, 10, 0, 5, tzinfo=KST)
    position = _make_position(
        side=PositionSide.LONG,
        entry_price=100.0,
        current_price=96.0,
        entry_time=now - timedelta(seconds=5),
    )
    context = ExitContext(
        position=position,
        market_data={"last_price": 96.0},
        timestamp=now,
        metadata={"is_backtest": False},
    )

    should_exit, signal = await strategy.should_exit(context)

    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS
