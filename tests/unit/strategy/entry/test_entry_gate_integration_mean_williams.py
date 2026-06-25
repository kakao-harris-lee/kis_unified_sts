"""Integration tests for shared entry gates in mean reversion and Williams %R."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from shared.strategy.base import EntryContext
from shared.strategy.entry.mean_reversion import MeanReversionConfig, MeanReversionEntry
from shared.strategy.entry.williams_r import WilliamsRConfig, WilliamsREntry

KST = ZoneInfo("Asia/Seoul")


def _kst(hour: int, minute: int) -> datetime:
    return datetime(2026, 6, 25, hour, minute, tzinfo=KST)


def _mean_context(timestamp: datetime, *, code: str = "005930") -> EntryContext:
    return EntryContext(
        market_data={
            "code": code,
            "name": "Samsung Electronics",
            "close": 365.0,
            "bb_lower": 366.0,
            "bb_upper": 374.0,
            "bb_middle": 370.0,
            "rsi": 25.0,
        },
        timestamp=timestamp,
    )


def _mean_entry(**overrides) -> MeanReversionEntry:
    defaults = {
        "signal_cooldown_seconds": 0,
        "skip_market_open_minutes": 0,
        "skip_market_close_minutes": 0,
    }
    defaults.update(overrides)
    return MeanReversionEntry(MeanReversionConfig(**defaults))


def _williams_context(
    timestamp: datetime,
    *,
    code: str = "005930",
    williams_r: float = -75.0,
) -> EntryContext:
    return EntryContext(
        market_data={"code": code, "name": "Samsung Electronics", "close": 50_000.0},
        indicators={
            "bb_middle": 49_000.0,
            "rvol": 1.5,
            "momentum_5m": {"williams_r": williams_r},
        },
        timestamp=timestamp,
    )


def _williams_entry(**overrides) -> WilliamsREntry:
    defaults = {
        "signal_cooldown_seconds": 0,
        "skip_market_open_minutes": 0,
        "skip_market_close_minutes": 0,
    }
    defaults.update(overrides)
    return WilliamsREntry(WilliamsRConfig(**defaults))


def _seed_williams_reversal(entry: WilliamsREntry, code: str = "005930") -> None:
    entry._prev_williams_r[code] = -90.0


def _assert_long_signal(signal, *, code: str) -> None:
    assert signal is not None
    assert signal.code == code
    assert signal.metadata["signal_direction"] == "long"


@pytest.mark.asyncio
async def test_mean_reversion_blocks_inside_open_skip_and_allows_at_cutoff(
) -> None:
    entry = _mean_entry(skip_market_open_minutes=30)

    blocked = await entry.generate(_mean_context(_kst(9, 29)))
    allowed = await entry.generate(_mean_context(_kst(9, 30)))

    assert blocked is None
    _assert_long_signal(allowed, code="005930")


@pytest.mark.asyncio
async def test_mean_reversion_blocks_during_close_skip_window() -> None:
    entry = _mean_entry(skip_market_close_minutes=15)

    signal = await entry.generate(_mean_context(_kst(15, 0)))

    assert signal is None


@pytest.mark.asyncio
async def test_mean_reversion_cooldown_blocks_second_same_symbol_signal() -> None:
    entry = _mean_entry(signal_cooldown_seconds=300)

    first = await entry.generate(_mean_context(_kst(10, 0)))
    second = await entry.generate(_mean_context(_kst(10, 4)))

    _assert_long_signal(first, code="005930")
    assert second is None


@pytest.mark.asyncio
async def test_mean_reversion_cooldown_allows_different_symbol() -> None:
    entry = _mean_entry(signal_cooldown_seconds=300)

    first = await entry.generate(_mean_context(_kst(10, 0), code="005930"))
    second = await entry.generate(_mean_context(_kst(10, 4), code="000660"))

    _assert_long_signal(first, code="005930")
    _assert_long_signal(second, code="000660")


@pytest.mark.asyncio
async def test_williams_r_blocks_inside_open_skip_and_allows_at_cutoff(
) -> None:
    entry = _williams_entry(skip_market_open_minutes=30)
    _seed_williams_reversal(entry)

    blocked = await entry.generate(_williams_context(_kst(9, 29)))
    allowed = await entry.generate(_williams_context(_kst(9, 30)))

    assert blocked is None
    _assert_long_signal(allowed, code="005930")


@pytest.mark.asyncio
async def test_williams_r_blocks_during_close_skip_window() -> None:
    entry = _williams_entry(skip_market_close_minutes=15)
    _seed_williams_reversal(entry)

    signal = await entry.generate(_williams_context(_kst(15, 0)))

    assert signal is None


@pytest.mark.asyncio
async def test_williams_r_cooldown_blocks_second_same_symbol_signal() -> None:
    entry = _williams_entry(signal_cooldown_seconds=300)
    _seed_williams_reversal(entry)

    first = await entry.generate(_williams_context(_kst(10, 0)))
    _seed_williams_reversal(entry)
    second = await entry.generate(_williams_context(_kst(10, 4)))

    _assert_long_signal(first, code="005930")
    assert second is None


@pytest.mark.asyncio
async def test_williams_r_cooldown_allows_different_symbol() -> None:
    entry = _williams_entry(signal_cooldown_seconds=300)
    _seed_williams_reversal(entry, code="005930")
    _seed_williams_reversal(entry, code="000660")

    first = await entry.generate(_williams_context(_kst(10, 0), code="005930"))
    second = await entry.generate(_williams_context(_kst(10, 4), code="000660"))

    _assert_long_signal(first, code="005930")
    _assert_long_signal(second, code="000660")
