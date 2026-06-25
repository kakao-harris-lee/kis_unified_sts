"""Integration tests for shared entry gates in mean reversion and Williams %R."""

from __future__ import annotations

from datetime import datetime
from types import ModuleType
from zoneinfo import ZoneInfo

import pytest

from shared.strategy.base import EntryContext
from shared.strategy.entry import gates as entry_gates
from shared.strategy.entry import mean_reversion as mean_reversion_module
from shared.strategy.entry import williams_r as williams_r_module
from shared.strategy.entry.mean_reversion import MeanReversionConfig, MeanReversionEntry
from shared.strategy.entry.williams_r import WilliamsRConfig, WilliamsREntry

KST = ZoneInfo("Asia/Seoul")


def _kst(hour: int, minute: int) -> datetime:
    return datetime(2026, 6, 25, hour, minute, tzinfo=KST)


def _expected_window(
    *,
    skip_market_open_minutes: int = 0,
    skip_market_close_minutes: int = 0,
) -> entry_gates.MarketSessionWindow:
    return entry_gates.MarketSessionWindow(
        market_open_hour=9,
        market_open_minute=0,
        market_close_hour=15,
        market_close_minute=15,
        skip_market_open_minutes=skip_market_open_minutes,
        skip_market_close_minutes=skip_market_close_minutes,
    )


def _record_session_gate_calls(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
) -> list[tuple[datetime, entry_gates.MarketSessionWindow]]:
    calls: list[tuple[datetime, entry_gates.MarketSessionWindow]] = []

    def wrapped(timestamp: datetime, window: entry_gates.MarketSessionWindow) -> bool:
        calls.append((timestamp, window))
        return entry_gates.is_in_entry_session(timestamp, window)

    monkeypatch.setattr(module, "is_in_entry_session", wrapped, raising=False)
    return calls


def _record_cooldown_gate_calls(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
) -> list[tuple[datetime, datetime | None, float]]:
    calls: list[tuple[datetime, datetime | None, float]] = []

    def wrapped(
        *,
        now: datetime,
        last_signal_at: datetime | None,
        cooldown_seconds: float,
    ) -> bool:
        calls.append((now, last_signal_at, cooldown_seconds))
        return entry_gates.cooldown_elapsed(
            now=now,
            last_signal_at=last_signal_at,
            cooldown_seconds=cooldown_seconds,
        )

    monkeypatch.setattr(module, "cooldown_elapsed", wrapped, raising=False)
    return calls


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


@pytest.mark.asyncio
async def test_mean_reversion_blocks_during_open_skip_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record_session_gate_calls(monkeypatch, mean_reversion_module)
    entry = MeanReversionEntry(MeanReversionConfig(skip_market_open_minutes=30))

    signal = await entry.generate(_mean_context(_kst(9, 10)))

    assert signal is None
    assert calls == [(_kst(9, 10), _expected_window(skip_market_open_minutes=30))]


@pytest.mark.asyncio
async def test_mean_reversion_blocks_during_close_skip_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record_session_gate_calls(monkeypatch, mean_reversion_module)
    entry = MeanReversionEntry(MeanReversionConfig(skip_market_close_minutes=15))

    signal = await entry.generate(_mean_context(_kst(15, 5)))

    assert signal is None
    assert calls == [(_kst(15, 5), _expected_window(skip_market_close_minutes=15))]


@pytest.mark.asyncio
async def test_mean_reversion_cooldown_blocks_second_same_symbol_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record_cooldown_gate_calls(monkeypatch, mean_reversion_module)
    entry = MeanReversionEntry(MeanReversionConfig(signal_cooldown_seconds=300))

    first = await entry.generate(_mean_context(_kst(10, 0)))
    second = await entry.generate(_mean_context(_kst(10, 4)))

    assert first is not None
    assert second is None
    assert calls[-1] == (_kst(10, 4), _kst(10, 0), 300)


@pytest.mark.asyncio
async def test_williams_r_blocks_during_open_skip_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record_session_gate_calls(monkeypatch, williams_r_module)
    entry = WilliamsREntry(
        WilliamsRConfig(
            skip_market_open_minutes=30,
            skip_market_close_minutes=0,
            signal_cooldown_seconds=0,
        )
    )
    entry._prev_williams_r["005930"] = -90.0

    signal = await entry.generate(_williams_context(_kst(9, 10)))

    assert signal is None
    assert calls == [(_kst(9, 10), _expected_window(skip_market_open_minutes=30))]


@pytest.mark.asyncio
async def test_williams_r_blocks_during_close_skip_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record_session_gate_calls(monkeypatch, williams_r_module)
    entry = WilliamsREntry(
        WilliamsRConfig(
            skip_market_open_minutes=0,
            skip_market_close_minutes=15,
            signal_cooldown_seconds=0,
        )
    )
    entry._prev_williams_r["005930"] = -90.0

    signal = await entry.generate(_williams_context(_kst(15, 5)))

    assert signal is None
    assert calls == [(_kst(15, 5), _expected_window(skip_market_close_minutes=15))]


@pytest.mark.asyncio
async def test_williams_r_cooldown_blocks_second_same_symbol_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record_cooldown_gate_calls(monkeypatch, williams_r_module)
    entry = WilliamsREntry(
        WilliamsRConfig(
            skip_market_open_minutes=0,
            skip_market_close_minutes=0,
            signal_cooldown_seconds=300,
        )
    )

    await entry.generate(_williams_context(_kst(10, 0), williams_r=-90.0))
    first = await entry.generate(_williams_context(_kst(10, 5), williams_r=-75.0))
    entry._prev_williams_r["005930"] = -90.0
    second = await entry.generate(_williams_context(_kst(10, 8), williams_r=-75.0))

    assert first is not None
    assert second is None
    assert calls[-1] == (_kst(10, 8), _kst(10, 5), 300)
