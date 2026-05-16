"""Tests for the technical consensus stock entry strategy."""

from datetime import UTC, datetime, timedelta

import pytest

from shared.strategy.base import EntryContext
from shared.strategy.entry.technical_consensus import (
    TechnicalConsensusEntry,
    TechnicalConsensusEntryConfig,
)


def _context(**indicators):
    data = {"code": "005930", "name": "Samsung", "close": 70000.0}
    return EntryContext(
        market_data=data,
        indicators=indicators,
        timestamp=datetime(2026, 5, 15, 0, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_generates_entry_when_core_votes_overlap():
    entry = TechnicalConsensusEntry(
        TechnicalConsensusEntryConfig(
            min_entry_votes=2,
            min_entry_core_votes=2,
            include_trend_vote=False,
            include_volume_vote=False,
            min_confidence=0.70,
            confidence_base=0.70,
        )
    )

    signal = await entry.generate(
        _context(
            prev_williams_r=-90.0,
            williams_r=-60.0,
            prev_rsi=30.0,
            rsi=42.0,
            prev_macd_hist=-1.0,
            macd_hist=-0.5,
        )
    )

    assert signal is not None
    assert signal.strategy == "technical_consensus"
    assert signal.metadata["signal_direction"] == "long"
    assert signal.metadata["technical_consensus"]["entry_core_vote_count"] == 2


@pytest.mark.asyncio
async def test_requires_minimum_core_votes():
    entry = TechnicalConsensusEntry(
        TechnicalConsensusEntryConfig(
            min_entry_votes=2,
            min_entry_core_votes=2,
            include_trend_vote=True,
            include_volume_vote=False,
            min_confidence=0.70,
            confidence_base=0.70,
        )
    )

    signal = await entry.generate(
        _context(
            prev_williams_r=-90.0,
            williams_r=-60.0,
            prev_rsi=50.0,
            rsi=52.0,
            prev_macd_hist=-1.0,
            macd_hist=-0.5,
            ma20=69000.0,
        )
    )

    assert signal is None


@pytest.mark.asyncio
async def test_signal_cooldown_blocks_same_symbol():
    entry = TechnicalConsensusEntry(
        TechnicalConsensusEntryConfig(
            min_entry_votes=2,
            min_entry_core_votes=2,
            include_trend_vote=False,
            include_volume_vote=False,
            signal_cooldown_days=3,
            min_confidence=0.70,
            confidence_base=0.70,
        )
    )

    ctx = _context(
        prev_williams_r=-90.0,
        williams_r=-60.0,
        prev_rsi=30.0,
        rsi=42.0,
        prev_macd_hist=-1.0,
        macd_hist=-0.5,
    )
    first = await entry.generate(ctx)
    second_ctx = _context(
        prev_williams_r=-90.0,
        williams_r=-60.0,
        prev_rsi=30.0,
        rsi=42.0,
        prev_macd_hist=-1.0,
        macd_hist=-0.5,
    )
    second_ctx.timestamp = ctx.timestamp + timedelta(days=1)

    assert first is not None
    assert await entry.generate(second_ctx) is None
