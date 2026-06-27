"""Test EMA indicator additions to StreamingIndicatorEngine."""

from datetime import datetime, timedelta

from services.trading.indicator_engine import StreamingIndicatorEngine


def _feed_candles(engine: StreamingIndicatorEngine, symbol: str, prices: list[float]):
    """Feed a list of close prices as synthetic candles."""
    base = datetime(2026, 3, 2, 9, 0, 0)
    for i, price in enumerate(prices):
        tick_time = base + timedelta(minutes=i)
        engine.on_tick(
            symbol,
            {"close": price, "high": price * 1.005, "low": price * 0.995,
             "open": price, "volume": 10000 + i},
            tick_time,
        )
        # Advance to next minute to finalize candle
        engine.on_tick(
            symbol,
            {"close": price, "high": price * 1.005, "low": price * 0.995,
             "open": price, "volume": 10000 + i},
            tick_time + timedelta(seconds=61),
        )


def test_ema_values_present_after_warmup():
    """EMA 5/20/60 absolute values appear in indicators after sufficient candles."""
    engine = StreamingIndicatorEngine(bb_period=20, staleness_seconds=0)
    prices = [50000 + i * 10 for i in range(65)]
    _feed_candles(engine, "005930", prices)

    indicators = engine.get_indicators("005930")
    assert indicators is not None
    assert "ema_5" in indicators
    assert "ema_20" in indicators
    assert "ema_60" in indicators
    assert indicators["ema_5"] > 0
    assert indicators["ema_20"] > 0
    assert indicators["ema_60"] > 0


def test_ema_aligned_true_in_uptrend():
    """ema_aligned is True when EMA5 > EMA20 > EMA60 (uptrend)."""
    engine = StreamingIndicatorEngine(bb_period=20, staleness_seconds=0)
    prices = [50000 + i * 50 for i in range(65)]
    _feed_candles(engine, "005930", prices)

    indicators = engine.get_indicators("005930")
    assert indicators is not None
    assert indicators.get("ema_aligned") is True
    assert indicators["ema_5"] > indicators["ema_20"] > indicators["ema_60"]


def test_ema_aligned_false_in_downtrend():
    """ema_aligned is False when prices are falling."""
    engine = StreamingIndicatorEngine(bb_period=20, staleness_seconds=0)
    prices = [55000 - i * 50 for i in range(65)]
    _feed_candles(engine, "005930", prices)

    indicators = engine.get_indicators("005930")
    assert indicators is not None
    assert indicators.get("ema_aligned") is False


def test_ema_60_zero_when_insufficient_candles():
    """ema_60 is 0 when fewer than 60 candles available."""
    engine = StreamingIndicatorEngine(bb_period=20, staleness_seconds=0)
    prices = [50000 + i * 10 for i in range(25)]
    _feed_candles(engine, "005930", prices)

    indicators = engine.get_indicators("005930")
    assert indicators is not None
    assert indicators["ema_5"] > 0
    assert indicators["ema_20"] > 0
    assert indicators["ema_60"] == 0.0
    assert indicators["ema_aligned"] is False
