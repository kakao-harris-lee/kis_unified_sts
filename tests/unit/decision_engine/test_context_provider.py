"""FuturesContextProvider — builds MarketContext from engine + macro + events."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from services.decision_engine.context_provider import FuturesContextProvider
from shared.decision.context import MarketContext, ScheduledEvent


class _FakeEngine:
    """Fake engine whose contract matches the REAL StreamingIndicatorEngine:
    - get_indicators returns bb/rsi/atr/vwap/... (NO 'close' key)
    - get_last_price returns the price separately
    """

    def __init__(self, *, warm=True, atr=2.0, price=352.0, rng=(360.0, 340.0)):
        self._warm, self._atr, self._price, self._rng = warm, atr, price, rng

    def is_warm(self, _symbol):
        return self._warm

    def get_last_price(self, _symbol):
        return self._price if self._price > 0 else None

    def get_indicators(self, _symbol):
        # Real engine returns bb/rsi/atr/vwap/etc — no 'close' key.
        return {"atr": self._atr}

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


class _FakeDailyRefOrderProbe:
    """Daily ref that proves observe() is called BEFORE prev_close() is read.

    prev_close() returns a real value only after observe() has been called;
    before that it returns 0.0 so an ordering bug would surface as 0.0 in
    the built context.
    """

    def __init__(self):
        self._observed = False

    def observe(self, *, price, now):  # noqa: ARG002
        self._observed = True

    def prev_close(self):
        return 350.0 if self._observed else 0.0

    def today_open(self):
        return 351.0 if self._observed else 0.0


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
    assert ctx.current_spread_ticks == 1.0  # F-4 canonical default
    assert ctx.vwap == ctx.current_price  # F-4: vwap defaults to current_price
    assert ctx.atr_90th_percentile == ctx.atr_14 * 1.5  # F-4 default


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


@pytest.mark.asyncio
async def test_observe_called_before_prev_close_read():
    """observe() must run before prev_close() is read — ordering invariant."""
    ref = _FakeDailyRefOrderProbe()
    p = FuturesContextProvider(
        engine=_FakeEngine(price=352.0),
        daily_ref=ref,
        symbol="A05",
        macro_reader=lambda: None,
        events_provider=lambda: [],
        now_fn=lambda: datetime(2026, 6, 5, 9, 10, tzinfo=UTC),
    )
    ctx = await p()
    assert ctx is not None
    # If ordering is wrong prev_close returns 0.0 and the context would still
    # be built (0.0 is a valid float for the field), but the value would be wrong.
    assert ctx.prev_close == 350.0
    assert ctx.today_open == 351.0


@pytest.mark.asyncio
async def test_returns_none_when_price_zero():
    """get_last_price returning 0.0 / None must yield None from provider."""
    p = FuturesContextProvider(
        engine=_FakeEngine(price=0.0),
        daily_ref=_FakeDailyRef(),
        symbol="A05",
        macro_reader=lambda: None,
        events_provider=lambda: [],
        now_fn=lambda: datetime(2026, 6, 5, 9, 10, tzinfo=UTC),
    )
    assert await p() is None


@pytest.mark.asyncio
async def test_macro_reader_exception_yields_none_macro():
    """macro_reader raising must not crash; macro_overnight should be None."""

    def _bad_macro():
        raise RuntimeError("redis down")

    p = FuturesContextProvider(
        engine=_FakeEngine(),
        daily_ref=_FakeDailyRef(),
        symbol="A05",
        macro_reader=_bad_macro,
        events_provider=lambda: [],
        now_fn=lambda: datetime(2026, 6, 5, 9, 10, tzinfo=UTC),
    )
    ctx = await p()
    assert ctx is not None
    assert ctx.macro_overnight is None


@pytest.mark.asyncio
async def test_events_provider_exception_yields_empty_events():
    """events_provider raising must not crash; scheduled_events should be []."""

    def _bad_events():
        raise OSError("yaml missing")

    p = FuturesContextProvider(
        engine=_FakeEngine(),
        daily_ref=_FakeDailyRef(),
        symbol="A05",
        macro_reader=lambda: None,
        events_provider=_bad_events,
        now_fn=lambda: datetime(2026, 6, 5, 9, 10, tzinfo=UTC),
    )
    ctx = await p()
    assert ctx is not None
    assert ctx.scheduled_events == []


# ---------------------------------------------------------------------------
# Bug C: atr_14 == 0 (stale engine) must suppress the context
# ---------------------------------------------------------------------------


class _FakeEngineStaleIndicators:
    """Engine that is warm (enough candles) but returns empty indicators.

    This simulates the staleness case: get_indicators() returns {} when the
    last tick was >180 s ago, even though is_warm() stays True.
    """

    def is_warm(self, _symbol):
        return True

    def get_last_price(self, _symbol):
        return 352.0

    def get_indicators(self, _symbol):
        # Stale: no indicators available (atr absent)
        return {}

    def get_recent_range(self, _symbol, _minutes=15):
        return (360.0, 340.0)


@pytest.mark.asyncio
async def test_returns_none_when_atr_is_zero_or_absent():
    """Bug C regression: warm engine with stale/absent ATR must return None.

    Without a valid ATR, stop-loss distances become zero (degenerate signal).
    The provider must suppress the context rather than emit a broken one.
    """
    p = FuturesContextProvider(
        engine=_FakeEngineStaleIndicators(),
        daily_ref=_FakeDailyRef(),
        symbol="A05",
        macro_reader=lambda: None,
        events_provider=lambda: [],
        now_fn=lambda: datetime(2026, 6, 5, 9, 10, tzinfo=UTC),
    )
    result = await p()
    assert (
        result is None
    ), "Provider must return None when ATR is 0 / absent (stale engine)"
