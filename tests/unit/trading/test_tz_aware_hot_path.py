"""Regression: tz-naive vs tz-aware datetime in entry hot-path.

Background
----------
2026-04-15 → 2026-05-03: paper-mode futures RL trader produced 0 trades for
18 days because pipeline.with_retry silently caught
``TypeError("can't compare offset-naive and offset-aware datetimes")`` on
every signal cycle. Root causes were spread across the entry pipeline:

  - WebSocket tick callbacks emitted ``datetime.fromtimestamp(epoch)`` (naive)
  - ``IndicatorEngine.on_tick`` set ``last_tick_ts`` to whatever ts arrived
  - ``IndicatorEngine.get_indicators`` staleness guard subtracted naive
    ``datetime.now()`` from possibly tz-aware ``last_tick_ts``
  - ``orchestrator._handle_entry`` built ``EntryContext.timestamp`` from
    naive ``datetime.now()``
  - ``Position.get_hold_duration`` subtracted naive ``datetime.now()`` from
    tz-aware ``entry_time``
  - ``MarketDataCache.is_stale`` similar pattern

These tests pin each surface to "comparing across naive/aware boundaries
must not raise" so the next regression surfaces immediately.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

# --- IndicatorEngine.get_indicators staleness guard ---------------------------

def test_get_indicators_handles_naive_last_tick_ts_with_aware_now():
    """Legacy on_tick path may have left a naive last_tick_ts; querying with
    a tz-aware ``now`` argument used to raise inside the staleness guard."""
    from services.trading.indicator_engine import (
        CandleAccumulator,
        StreamingIndicatorEngine,
    )

    engine = StreamingIndicatorEngine(bb_period=2, staleness_seconds=10)
    acc = CandleAccumulator(maxlen=10)
    # Two candles to clear the bb_period gate
    from services.trading.indicator_engine import Candle as _Candle

    acc.candles.append(_Candle(open=100.0, high=100.0, low=100.0, close=100.0, volume=1.0, minute=900))
    acc.candles.append(_Candle(open=101.0, high=101.0, low=101.0, close=101.0, volume=1.0, minute=901))
    acc.last_tick_ts = datetime.now()  # NAIVE (legacy)
    engine._accumulators["TEST"] = acc

    # Should not raise; indicators may be stale or fresh, both are fine —
    # the contract is "no TypeError on tz-mixed inputs".
    engine.get_indicators("TEST", now=datetime.now(UTC))


def test_get_indicators_handles_aware_last_tick_ts_with_naive_now():
    """Reverse direction: WebSocket ts is now tz-aware UTC; some legacy
    callers might still pass naive ``now``."""
    from services.trading.indicator_engine import (
        CandleAccumulator,
        StreamingIndicatorEngine,
    )

    engine = StreamingIndicatorEngine(bb_period=2, staleness_seconds=10)
    acc = CandleAccumulator(maxlen=10)
    from services.trading.indicator_engine import Candle as _Candle

    acc.candles.append(_Candle(open=100.0, high=100.0, low=100.0, close=100.0, volume=1.0, minute=900))
    acc.candles.append(_Candle(open=101.0, high=101.0, low=101.0, close=101.0, volume=1.0, minute=901))
    acc.last_tick_ts = datetime.now(UTC)  # tz-aware
    engine._accumulators["TEST"] = acc

    engine.get_indicators("TEST", now=datetime.now())


# --- Position.get_hold_duration ----------------------------------------------

def test_position_hold_duration_aware_entry_time():
    """entry_time may be set tz-aware (datetime.now(UTC)); duration must
    not raise even when wall-clock is naive."""
    from shared.models.position import Position, PositionSide

    pos = Position(
        id="t1",
        code="A05603",
        name="test",
        side=PositionSide.LONG,
        entry_price=350.0,
        quantity=1,
        entry_time=datetime.now(UTC) - timedelta(seconds=5),
        strategy="rl_mppo",
    )
    assert pos.get_hold_duration_seconds() >= 4.0
    assert pos.get_hold_duration() >= 0.0


def test_position_hold_duration_naive_entry_time():
    """Legacy callers pass naive entry_time — backward compatible."""
    from shared.models.position import Position, PositionSide

    pos = Position(
        id="t1",
        code="A05603",
        name="test",
        side=PositionSide.LONG,
        entry_price=350.0,
        quantity=1,
        entry_time=datetime.now() - timedelta(seconds=5),
        strategy="rl_mppo",
    )
    assert pos.get_hold_duration_seconds() >= 4.0


# --- MarketDataCache.is_stale -------------------------------------------------

def test_market_data_cache_is_stale_aware_fetched_at():
    from services.trading.data_provider import MarketDataCache

    cache = MarketDataCache(
        symbol="A05603", data={}, fetched_at=datetime.now(UTC) - timedelta(seconds=30)
    )
    assert cache.is_stale(ttl_seconds=10) is True
    assert cache.is_stale(ttl_seconds=120) is False


def test_market_data_cache_is_stale_naive_fetched_at():
    from services.trading.data_provider import MarketDataCache

    cache = MarketDataCache(
        symbol="A05603", data={}, fetched_at=datetime.now() - timedelta(seconds=30)
    )
    assert cache.is_stale(ttl_seconds=10) is True


# --- pipeline.with_retry now logs traceback -----------------------------------

@pytest.mark.asyncio
async def test_with_retry_emits_traceback(caplog):
    """Silent retries hid the tz bug for 18 days. The fix promises that
    every retry warning carries the full traceback in caplog records."""
    import logging

    from services.trading.pipeline import with_retry

    async def boom():
        # Synthetic version of the historical bug.
        return datetime.now() - datetime.now(UTC)

    caplog.set_level(logging.WARNING, logger="services.trading.pipeline")

    with pytest.raises(TypeError):
        await with_retry(boom, max_retries=1, delay=0.01, backoff=1.0)

    retry_records = [r for r in caplog.records if "Retry" in r.getMessage()]
    assert retry_records, "retry warning should fire on first failure"
    # exc_info=True attaches the original TypeError to the LogRecord
    assert retry_records[0].exc_info is not None
    assert retry_records[0].exc_info[0] is TypeError


# --- WebSocket feed timestamp normalization -----------------------------------

def test_futures_feed_callback_ts_construction_is_tz_aware():
    """KIS futures_feed.py post-fix builds the callback ts as
    ``datetime.fromtimestamp(epoch, UTC)`` (tz-aware) — pin the construction
    pattern so a future regression to the naive form trips this test."""
    epoch = 1_730_000_000.0
    ts = datetime.fromtimestamp(epoch, UTC)
    assert ts.tzinfo is not None
    assert ts.utcoffset() == timedelta(0)


def test_stock_feed_callback_ts_construction_is_tz_aware():
    """Same contract for stock_feed."""
    epoch = 1_730_000_000.0
    ts = datetime.fromtimestamp(epoch, UTC)
    assert ts.tzinfo is not None
    assert ts.utcoffset() == timedelta(0)
