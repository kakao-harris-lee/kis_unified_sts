"""15-minute high/low accessor for Setup C breakout."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from services.trading.indicator_engine import StreamingIndicatorEngine


def _feed_minute(engine, symbol, minute_idx, high, low, close):
    # one tick per minute; CandleAccumulator buckets by minute
    ts = datetime(2026, 6, 5, 9, 0, tzinfo=UTC) + timedelta(minutes=minute_idx)
    engine.on_tick(symbol, {"high": high, "low": low, "close": close, "volume": 1}, ts)


def test_recent_range_returns_max_high_min_low_over_window():
    eng = StreamingIndicatorEngine()
    # 20 one-minute candles; the last 15 span minutes 5..19
    for i in range(20):
        _feed_minute(eng, "A05", i, high=100 + i, low=50 + i, close=75 + i)
    rng = eng.get_recent_range("A05", minutes=15)
    assert rng is not None
    hi, lo = rng
    # last 15 closed candles → highs 105..119 (max 119-ish), lows 55..69 (min ~55)
    assert hi >= 118 and lo <= 56


def test_recent_range_none_when_no_candles():
    eng = StreamingIndicatorEngine()
    assert eng.get_recent_range("UNKNOWN", minutes=15) is None
