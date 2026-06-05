"""FuturesContextProvider — builds MarketContext from engine + macro + events."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from services.decision_engine.context_provider import FuturesContextProvider
from shared.decision.context import MarketContext, ScheduledEvent


class _FakeEngine:
    def __init__(self, *, warm=True, atr=2.0, price=352.0, rng=(360.0, 340.0)):
        self._warm, self._atr, self._price, self._rng = warm, atr, price, rng

    def is_warm(self, _symbol):
        return self._warm

    def get_indicators(self, _symbol):
        return {"close": self._price, "atr": self._atr}

    def get_recent_range(self, _symbol, _minutes=15):
        return self._rng


class _FakeDailyRef:
    def __init__(self):
        self.observed = []

    def prev_close(self):
        return 350.0

    def today_open(self):
        return 351.0

    def observe(self, *, price, now):
        self.observed.append((price, now))


class _Macro:
    sp500_change_pct = 0.8


@pytest.mark.asyncio
async def test_builds_market_context_when_warm():
    ev = [ScheduledEvent("e1", "FOMC", datetime(2026, 6, 5, 9, 5, tzinfo=UTC), 1)]
    p = FuturesContextProvider(
        engine=_FakeEngine(),
        daily_ref=_FakeDailyRef(),
        symbol="A05",
        macro_reader=lambda: _Macro(),
        events_provider=lambda: ev,
        now_fn=lambda: datetime(2026, 6, 5, 9, 10, tzinfo=UTC),
    )
    ctx = await p()
    assert isinstance(ctx, MarketContext)
    assert ctx.symbol == "A05"
    assert ctx.current_price == 352.0
    assert ctx.atr_14 == 2.0
    assert ctx.prev_close == 350.0 and ctx.today_open == 351.0
    assert ctx.last_15min_high == 360.0 and ctx.last_15min_low == 340.0
    assert ctx.macro_overnight.sp500_change_pct == 0.8
    assert ctx.scheduled_events == ev
    # unused fields defaulted, not crashing
    assert ctx.current_spread_ticks == 0.0


@pytest.mark.asyncio
async def test_returns_none_until_warm():
    p = FuturesContextProvider(
        engine=_FakeEngine(warm=False),
        daily_ref=_FakeDailyRef(),
        symbol="A05",
        macro_reader=lambda: None,
        events_provider=lambda: [],
        now_fn=lambda: datetime(2026, 6, 5, 9, 10, tzinfo=UTC),
    )
    assert await p() is None


@pytest.mark.asyncio
async def test_observes_price_for_today_open():
    ref = _FakeDailyRef()
    p = FuturesContextProvider(
        engine=_FakeEngine(price=352.0),
        daily_ref=ref,
        symbol="A05",
        macro_reader=lambda: None,
        events_provider=lambda: [],
        now_fn=lambda: datetime(2026, 6, 5, 9, 10, tzinfo=UTC),
    )
    await p()
    assert ref.observed and ref.observed[0][0] == 352.0
