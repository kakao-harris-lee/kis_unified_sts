"""Regression: indicator/momentum caches must keep invalidating after the"""

from __future__ import annotations

import pytest

from shared.indicators.streaming.engine import StreamingIndicatorEngine


def _candle(close: float) -> dict:
    return {
        "open": close,
        "high": close + 5.0,
        "low": close - 5.0,
        "close": close,
        "volume": 100.0,
    }


class TestAccumulatorMonotonicCounter:
    def test_candle_accumulator_counter_outlives_deque_cap(self):
        from shared.indicators.streaming.engine import CandleAccumulator

        acc = CandleAccumulator(maxlen=10)
        from shared.indicators.streaming.engine import Candle

        for i in range(25):
            acc.add_completed(
                Candle(open=i, high=i, low=i, close=i, volume=1, minute=i)
            )
        assert len(acc.candles) == 10
        assert acc.total_appended == 25

    def test_mtf_accumulator_counter_outlives_deque_cap(self):
        from shared.indicators.streaming.engine import (
            Candle,
            MultiTimeframeCandleAccumulator,
        )

        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=8)
        for i in range(30):
            acc.add_completed(
                Candle(open=i, high=i, low=i, close=i, volume=1, minute=i)
            )
        assert len(acc.candles) == 8
        assert acc.total_appended == 30


class TestGetIndicatorsCacheInvalidationPastSaturation:
    def test_indicators_keep_updating_after_deque_full(self):
        """Feed > candle_maxlen candles; bb_middle must keep moving with"""
        engine = StreamingIndicatorEngine(
            bb_period=20,
            staleness_seconds=0,
            candle_maxlen=30,
        )
        sym = "TESTF"

        engine.seed_candles(sym, [_candle(100.0) for _ in range(40)], minute=900)
        first = engine.get_indicators(sym)
        bb_first = first.get("bb_middle")
        assert bb_first is not None

        engine.seed_candles(sym, [_candle(200.0) for _ in range(40)], minute=905)
        second = engine.get_indicators(sym)
        bb_second = second.get("bb_middle")

        assert bb_second is not None
        assert bb_second != pytest.approx(bb_first), (
            f"bb_middle frozen at {bb_first} after deque saturation — "
            "cache staleness bug regression"
        )
        assert bb_second > bb_first

    def test_momentum_williams_r_not_frozen_after_saturation(self):
        """The exact failure mode: williams_r stuck at one value (was -0.0)"""
        engine = StreamingIndicatorEngine(
            bb_period=20,
            staleness_seconds=0,
            candle_maxlen=600,
            mtf_maxlen=60,
        )
        sym = "TESTF"

        engine.seed_mtf_candles(
            sym, [_candle(500.0 - (i % 30)) for i in range(200)], timeframe=5
        )
        wr1 = engine.get_momentum_indicators(sym, timeframe=5).get("williams_r")

        engine.seed_mtf_candles(
            sym, [_candle(900.0 + (i % 30)) for i in range(200)], timeframe=5
        )
        wr2 = engine.get_momentum_indicators(sym, timeframe=5).get("williams_r")

        assert wr1 is not None and wr2 is not None, (wr1, wr2)
        assert wr1 != wr2, (
            f"williams_r frozen at {wr1} after 5-min deque saturation — "
            "momentum cache staleness regression"
        )
