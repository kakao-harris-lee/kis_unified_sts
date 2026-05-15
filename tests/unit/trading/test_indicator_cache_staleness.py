"""Regression: indicator/momentum caches must keep invalidating after the
candle deque saturates at its maxlen.

Bug (found 2026-05-15 via williams_r_15m backtest producing 0 trades):
  `get_indicators` / `get_momentum_indicators` / `get_daily_indicators`
  invalidated their caches with `len(acc.candles)`. The candle deques have a
  fixed `maxlen`, so once full `len()` is constant and the cache key never
  changes — indicators freeze at the first post-saturation snapshot for the
  rest of the session (live) or backtest. `williams_r` froze at -0.0.

Fix: monotonic `total_appended` counters drive cache invalidation instead.
"""
from __future__ import annotations

import pytest

from services.trading.indicator_engine import StreamingIndicatorEngine


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
        from services.trading.indicator_engine import CandleAccumulator

        acc = CandleAccumulator(maxlen=10)
        from services.trading.indicator_engine import Candle

        for i in range(25):
            acc.add_completed(
                Candle(open=i, high=i, low=i, close=i, volume=1, minute=i)
            )
        assert len(acc.candles) == 10  # deque saturated
        assert acc.total_appended == 25  # counter did NOT saturate

    def test_mtf_accumulator_counter_outlives_deque_cap(self):
        from services.trading.indicator_engine import (
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
        """Feed > candle_maxlen candles; bb_middle must keep moving with
        price after the 1-min deque saturates (was frozen pre-fix)."""
        engine = StreamingIndicatorEngine(
            bb_period=20,
            staleness_seconds=0,
            candle_maxlen=30,  # small cap so we saturate fast
        )
        sym = "TESTF"

        # Phase 1: 40 candles around price 100 (saturates the 30-cap deque)
        engine.seed_candles(sym, [_candle(100.0) for _ in range(40)], minute=900)
        first = engine.get_indicators(sym)
        bb_first = first.get("bb_middle")
        assert bb_first is not None

        # Phase 2: 40 more candles at a clearly different price level.
        # Pre-fix: len()==30 stayed constant → cache never invalidated →
        # bb_middle frozen at bb_first. Post-fix: counter advances → recompute.
        engine.seed_candles(sym, [_candle(200.0) for _ in range(40)], minute=905)
        second = engine.get_indicators(sym)
        bb_second = second.get("bb_middle")

        assert bb_second is not None
        assert bb_second != pytest.approx(bb_first), (
            f"bb_middle frozen at {bb_first} after deque saturation — "
            "cache staleness bug regression"
        )
        # Sanity: moved toward the new price regime
        assert bb_second > bb_first

    def test_momentum_williams_r_not_frozen_after_saturation(self):
        """The exact failure mode: williams_r stuck at one value (was -0.0)
        across the whole backtest once the 5-min deque saturated.

        `seed_candles` appends each input candle 1:1 to the MTF deque, so
        mtf_maxlen must exceed the momentum min_candles guard (50) for the
        indicator to compute at all.
        """
        engine = StreamingIndicatorEngine(
            bb_period=20,
            staleness_seconds=0,
            candle_maxlen=600,
            mtf_maxlen=60,  # > min_candles(50); saturates within each phase
        )
        sym = "TESTF"

        # seed_mtf_candles appends pre-aggregated 5-min candles 1:1 to the MTF
        # deque (the backtest-equivalent direct path). Phase 1: descending
        # sawtooth, 200 candles → 60-cap deque saturates.
        engine.seed_mtf_candles(
            sym, [_candle(500.0 - (i % 30)) for i in range(200)], timeframe=5
        )
        wr1 = engine.get_momentum_indicators(sym, timeframe=5).get("williams_r")

        # Phase 2: clearly higher band. Pre-fix len(deque)==60 stayed constant
        # → momentum cache key frozen → williams_r stuck at wr1.
        engine.seed_mtf_candles(
            sym, [_candle(900.0 + (i % 30)) for i in range(200)], timeframe=5
        )
        wr2 = engine.get_momentum_indicators(sym, timeframe=5).get("williams_r")

        assert wr1 is not None and wr2 is not None, (wr1, wr2)
        assert wr1 != wr2, (
            f"williams_r frozen at {wr1} after 5-min deque saturation — "
            "momentum cache staleness regression"
        )
