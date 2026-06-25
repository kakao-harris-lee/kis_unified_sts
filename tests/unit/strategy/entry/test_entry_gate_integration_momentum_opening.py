"""Entry gate integration regressions for momentum and opening surge strategies."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from shared.strategy.base import EntryContext
from shared.strategy.entry.momentum_breakout import (
    MomentumBreakoutConfig,
    MomentumBreakoutEntry,
)
from shared.strategy.entry.opening_volume_surge import (
    OpeningVolumeSurgeConfig,
    OpeningVolumeSurgeEntry,
)

KST = ZoneInfo("Asia/Seoul")


def _kst(hour: int, minute: int) -> datetime:
    return datetime(2026, 6, 25, hour, minute, tzinfo=KST)


def _momentum_strategy(
    *,
    skip_market_open_minutes: int = 30,
    skip_market_close_minutes: int = 15,
    signal_cooldown_seconds: int = 600,
) -> MomentumBreakoutEntry:
    return MomentumBreakoutEntry(
        MomentumBreakoutConfig(
            breakout_buffer_pct=0.1,
            rvol_threshold=1.5,
            volume_threshold=1.0,
            min_atr_cost_ratio=2.0,
            round_trip_cost=0.005,
            skip_market_open_minutes=skip_market_open_minutes,
            skip_market_close_minutes=skip_market_close_minutes,
            signal_cooldown_seconds=signal_cooldown_seconds,
        )
    )


def _momentum_context(timestamp: datetime, *, close: float = 101.0) -> EntryContext:
    return EntryContext(
        market_data={
            "code": "005930",
            "name": "Samsung",
            "close": close,
            "high": max(close, 102.0),
            "high_5": 100.0,
            "rvol": 2.0,
            "volume": 200_000,
            "volume_ma": 100_000,
            "atr": 2.0,
        },
        timestamp=timestamp,
        metadata={
            "daily_watchlist": {"strategies": {"momentum_breakout": ["005930"]}}
        },
    )


def _opening_strategy(
    *,
    only_first_minutes: int = 0,
    entry_cutoff_hour: int = -1,
    entry_cutoff_minute: int = 0,
) -> OpeningVolumeSurgeEntry:
    return OpeningVolumeSurgeEntry(
        OpeningVolumeSurgeConfig(
            only_first_minutes=only_first_minutes,
            market_open_hour=9,
            market_open_minute=0,
            volume_multiplier=1.0,
            min_change_pct=1.0,
            require_above_open=True,
            min_range_position=0.0,
            min_day_range_pct=0.0,
            entry_cutoff_hour=entry_cutoff_hour,
            entry_cutoff_minute=entry_cutoff_minute,
        )
    )


def _opening_context(timestamp: datetime) -> EntryContext:
    return EntryContext(
        market_data={
            "code": "005930",
            "name": "Samsung",
            "volume": 150_000,
            "prev_day_volume": 100_000,
            "rvol": 2.0,
            "close": 101.0,
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "change_pct": 2.0,
        },
        timestamp=timestamp,
    )


@pytest.mark.asyncio
async def test_momentum_breakout_respects_open_skip_window() -> None:
    strategy = _momentum_strategy(skip_market_open_minutes=30)

    assert await strategy.generate(_momentum_context(_kst(9, 29))) is None
    assert await strategy.generate(_momentum_context(_kst(9, 30))) is not None


@pytest.mark.asyncio
async def test_momentum_breakout_respects_close_skip_window() -> None:
    strategy = _momentum_strategy(
        skip_market_close_minutes=15,
        signal_cooldown_seconds=0,
    )

    assert await strategy.generate(_momentum_context(_kst(14, 59))) is not None
    assert await strategy.generate(_momentum_context(_kst(15, 0))) is None


@pytest.mark.asyncio
async def test_momentum_breakout_respects_cooldown() -> None:
    strategy = _momentum_strategy(signal_cooldown_seconds=600)

    assert await strategy.generate(_momentum_context(_kst(10, 0))) is not None
    assert (
        await strategy.generate(_momentum_context(_kst(10, 5), close=102.0)) is None
    )


@pytest.mark.asyncio
async def test_opening_volume_surge_blocks_before_market_open() -> None:
    strategy = _opening_strategy()

    assert await strategy.generate(_opening_context(_kst(8, 59))) is None
    assert await strategy.generate(_opening_context(_kst(9, 0))) is not None


@pytest.mark.asyncio
async def test_opening_volume_surge_preserves_only_first_minutes() -> None:
    strategy = _opening_strategy(only_first_minutes=5)

    assert await strategy.generate(_opening_context(_kst(9, 5))) is not None
    assert await strategy.generate(_opening_context(_kst(9, 6))) is None


@pytest.mark.asyncio
async def test_opening_volume_surge_preserves_entry_cutoff() -> None:
    strategy = _opening_strategy(entry_cutoff_hour=9, entry_cutoff_minute=10)

    assert await strategy.generate(_opening_context(_kst(9, 10))) is not None
    assert await strategy.generate(_opening_context(_kst(9, 11))) is None
