"""15-minute high/low accessor for Setup C breakout."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared.indicators.streaming.engine import StreamingIndicatorEngine


def _feed_minute(engine, symbol, minute_idx, high, low, close):
    ts = datetime(2026, 6, 5, 9, 0, tzinfo=UTC) + timedelta(minutes=minute_idx)
    engine.on_tick(symbol, {"high": high, "low": low, "close": close, "volume": 1}, ts)


def test_recent_range_returns_max_high_min_low_over_window():
    eng = StreamingIndicatorEngine()
    for i in range(20):
        _feed_minute(eng, "A05", i, high=100 + i, low=50 + i, close=75 + i)
    rng = eng.get_recent_range("A05", minutes=15)
    assert rng is not None
    hi, lo = rng
    assert hi >= 118 and lo <= 56


def test_recent_range_none_when_no_candles():
    eng = StreamingIndicatorEngine()
    assert eng.get_recent_range("UNKNOWN", minutes=15) is None


def test_get_last_price_returns_most_recent_close():
    """get_last_price returns the in-progress candle's close (latest tick)."""
    eng = StreamingIndicatorEngine()
    for i in range(5):
        _feed_minute(eng, "A05", i, high=100 + i, low=99 + i, close=100 + i)
    ts = datetime(2026, 6, 5, 9, 5, tzinfo=UTC)
    eng.on_tick("A05", {"high": 110, "low": 108, "close": 109.5, "volume": 1}, ts)
    price = eng.get_last_price("A05")
    assert price == 109.5


def test_get_last_price_none_for_unknown_symbol():
    eng = StreamingIndicatorEngine()
    assert eng.get_last_price("UNKNOWN") is None
