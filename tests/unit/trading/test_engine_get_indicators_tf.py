"""Tests for StreamingIndicatorEngine.get_indicators_tf.

Verifies that BB/RSI are computed from CLOSED 15m candles only,
and that insufficient-data guard returns an empty dict.
"""

from services.trading.indicator_engine import (
    Candle,
    StreamingIndicatorEngine,
)


def test_get_indicators_tf_uses_closed_15m_candles_only():
    eng = StreamingIndicatorEngine(
        bb_period=5, bb_std=2.0, rsi_period=5, mtf_timeframes=[15]
    )
    sym = "101S6000"
    for i in range(95):  # 95 one-minute candles
        hh = 9 + (i // 60)
        mm = i % 60
        minute = hh * 100 + mm
        c = Candle(open=400.0 + i, high=401.0 + i, low=399.0 + i,
                   close=400.5 + i, volume=1.0, minute=minute)
        eng._feed_mtf_candle(sym, c)
    res = eng.get_indicators_tf(sym, 15)
    assert set(res) >= {"bb_lower", "bb_middle", "bb_upper", "rsi"}
    mtf = eng._mtf_accumulators[sym][15]
    assert len(mtf.candles) >= eng.bb_period
    closed_closes = [c.close for c in mtf.candles]
    expected_mid = sum(closed_closes[-5:]) / 5
    assert abs(res["bb_middle"] - expected_mid) < 1e-6


def test_get_indicators_tf_empty_when_insufficient_closed():
    eng = StreamingIndicatorEngine(
        bb_period=20, bb_std=2.0, rsi_period=14, mtf_timeframes=[15]
    )
    sym = "X"
    for i in range(10):  # < 1 closed 15m candle
        eng._feed_mtf_candle(
            sym, Candle(open=1, high=1, low=1, close=1, volume=1,
                        minute=900 + i)
        )
    assert eng.get_indicators_tf(sym, 15) == {}


def test_get_indicators_tf_cache_hit_returns_copy_and_tracks_stats():
    eng = StreamingIndicatorEngine(
        bb_period=5, bb_std=2.0, rsi_period=5, mtf_timeframes=[15]
    )
    sym = "101S6000"
    for i in range(95):  # enough for several closed 15m candles
        hh = 9 + (i // 60)
        mm = i % 60
        minute = hh * 100 + mm
        c = Candle(open=400.0 + i, high=401.0 + i, low=399.0 + i,
                   close=400.5 + i, volume=1.0, minute=minute)
        eng._feed_mtf_candle(sym, c)

    # First call: cache miss
    a = eng.get_indicators_tf(sym, 15)
    stats_after_first = eng.get_cache_stats()
    assert stats_after_first["mtf_base_cache_misses"] == 1
    assert stats_after_first["mtf_base_cache_hits"] == 0

    # Second call with no new candle between: cache hit
    b = eng.get_indicators_tf(sym, 15)
    stats_after_hit = eng.get_cache_stats()
    assert stats_after_hit["mtf_base_cache_misses"] == 1
    assert stats_after_hit["mtf_base_cache_hits"] == 1

    # Equal in value but distinct dict objects (a .copy() is returned,
    # not the cached reference) so callers may safely mutate.
    assert a == b
    assert a is not b
