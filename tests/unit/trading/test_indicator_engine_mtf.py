"""Tests for Multi-Timeframe (MTF) candle aggregation in StreamingIndicatorEngine."""

from __future__ import annotations

from datetime import datetime, timedelta

from shared.indicators.streaming.engine import (
    Candle,
    MultiTimeframeCandleAccumulator,
    StreamingIndicatorEngine,
)


class TestMultiTimeframeCandleAccumulator:
    """Tests for MultiTimeframeCandleAccumulator - aggregating 1m candles to higher timeframes."""

    def test_5m_candle_from_single_1m_candle(self):
        """A single 1-min candle should buffer, not finalize, until bucket changes."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=100)

        candle = Candle(
            open=100.0, high=101.0, low=99.0, close=100.5, volume=1000, minute=930
        )
        result = acc.on_1m_candle(candle)

        assert result is None, "First candle should buffer, not finalize"
        assert len(acc.candles) == 0, "No completed candles yet"
        assert len(acc._buffer) == 1, "One candle in buffer"

    def test_5m_candle_aggregation_ohlcv(self):
        """5-min candle should aggregate OHLCV correctly from buffered 1-min candles."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=100)

        one_min_candles = [
            Candle(
                open=100.0, high=101.0, low=99.0, close=100.5, volume=1000, minute=930
            ),
            Candle(
                open=100.5, high=102.0, low=100.0, close=101.5, volume=1100, minute=931
            ),
            Candle(
                open=101.5, high=103.0, low=101.0, close=102.0, volume=1200, minute=932
            ),
            Candle(
                open=102.0, high=102.5, low=101.5, close=101.8, volume=1150, minute=933
            ),
            Candle(
                open=101.8, high=102.2, low=101.0, close=101.5, volume=1050, minute=934
            ),
        ]

        for c in one_min_candles[:-1]:
            result = acc.on_1m_candle(c)
            assert result is None, "Should buffer until bucket changes"

        next_candle = Candle(
            open=101.5, high=102.0, low=101.0, close=101.8, volume=1300, minute=935
        )
        result = acc.on_1m_candle(next_candle)

        assert result is not None, "Bucket change should finalize previous 5-min candle"
        assert len(acc.candles) == 1, "One completed 5-min candle"

        assert result.open == 100.0, "Open should be from first 1-min candle (930)"
        assert (
            result.high == 103.0
        ), "High should be max of all highs (101, 102, 103, 102.5)"
        assert result.low == 99.0, "Low should be min of all lows (99, 100, 101, 101.5)"
        assert (
            result.close == 101.8
        ), "Close should be from last buffered candle (933, not 934)"
        assert (
            result.volume == 4450
        ), "Volume should be sum of 4 candles (1000+1100+1200+1150)"
        assert result.minute == 930, "Minute should be bucket start"

    def test_15m_candle_aggregation(self):
        """15-min candle should aggregate 15 consecutive 1-min candles correctly."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=15, maxlen=100)

        base_price = 100.0
        cumulative_volume = 0

        for i in range(15):
            minute = 930 + i
            if minute % 100 >= 60:
                minute = ((minute // 100) + 1) * 100 + (minute % 100 - 60)

            price = base_price + i * 0.5
            volume = 1000 + i * 10
            cumulative_volume += volume

            candle = Candle(
                open=price,
                high=price + 0.5,
                low=price - 0.5,
                close=price + 0.2,
                volume=volume,
                minute=minute,
            )
            result = acc.on_1m_candle(candle)
            assert result is None, f"Candle {i+1} should buffer (same 15-min bucket)"

        next_candle = Candle(
            open=108.0, high=109.0, low=107.5, close=108.5, volume=1200, minute=945
        )
        result = acc.on_1m_candle(next_candle)

        assert result is not None, "Bucket change should finalize 15-min candle"
        assert result.open == 100.0, "Open should be from first candle"
        assert (
            result.high == 107.5
        ), "High should be max of all highs (100 + 14*0.5 + 0.5)"
        assert (
            result.low == 99.5
        ), "Low should be min of all lows (candle i=0: low=100.0-0.5=99.5)"
        assert (
            result.volume == cumulative_volume
        ), "Volume should be sum of all 15 candles"

    def test_bucket_calculation_edge_cases(self):
        """Test bucket calculation for various minute values."""
        acc_5m = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=100)
        acc_15m = MultiTimeframeCandleAccumulator(timeframe_minutes=15, maxlen=100)

        assert acc_5m._get_bucket(930) == 930
        assert acc_5m._get_bucket(932) == 930
        assert acc_5m._get_bucket(934) == 930
        assert acc_5m._get_bucket(935) == 935
        assert acc_5m._get_bucket(939) == 935
        assert acc_5m._get_bucket(940) == 940
        assert acc_5m._get_bucket(1000) == 1000
        assert acc_5m._get_bucket(1003) == 1000

        assert acc_15m._get_bucket(930) == 930
        assert acc_15m._get_bucket(935) == 930
        assert acc_15m._get_bucket(944) == 930
        assert acc_15m._get_bucket(945) == 945
        assert acc_15m._get_bucket(959) == 945
        assert acc_15m._get_bucket(1000) == 1000
        assert acc_15m._get_bucket(1014) == 1000
        assert acc_15m._get_bucket(1015) == 1015

    def test_incomplete_bucket_not_finalized(self):
        """Partial bucket (e.g., 3 candles in 5-min bucket) should not auto-finalize."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=100)

        for i in range(3):
            candle = Candle(
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000,
                minute=930 + i,
            )
            result = acc.on_1m_candle(candle)
            assert result is None

        assert len(acc.candles) == 0, "Partial bucket should not finalize"
        assert len(acc._buffer) == 3, "3 candles buffered"

    def test_flush_finalizes_partial_bucket(self):
        """flush() should finalize any buffered candles."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=100)

        for i in range(3):
            candle = Candle(
                open=100.0 + i,
                high=101.0 + i,
                low=99.0 + i,
                close=100.5 + i,
                volume=1000,
                minute=930 + i,
            )
            acc.on_1m_candle(candle)

        assert len(acc.candles) == 0, "No finalized candles yet"

        result = acc.flush()

        assert result is not None, "flush() should finalize buffered candles"
        assert len(acc.candles) == 1, "One completed candle after flush"
        assert result.open == 100.0, "Open from first buffered candle"
        assert result.close == 102.5, "Close from last buffered candle"
        assert result.volume == 3000, "Sum of 3 candles"
        assert len(acc._buffer) == 0, "Buffer should be cleared"
        assert acc._current_bucket is None, "Bucket should be reset"

    def test_multiple_5m_candles_sequential(self):
        """Test multiple sequential 5-min candles are created correctly."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=100)

        completed_count = 0
        for i in range(15):
            minute = 930 + i
            candle = Candle(
                open=100.0 + i,
                high=101.0 + i,
                low=99.0 + i,
                close=100.5 + i,
                volume=1000 + i * 10,
                minute=minute,
            )
            result = acc.on_1m_candle(candle)

            if minute in [935, 940]:
                completed_count += 1
                assert result is not None, f"Should finalize at minute {minute}"
            else:
                assert result is None, f"Should buffer at minute {minute}"

        assert completed_count == 2, "Should have 2 completed 5-min candles"
        assert len(acc.candles) == 2, "2 candles in accumulator"
        assert len(acc._buffer) == 5, "5 candles in current buffer (940-944)"

    def test_maxlen_enforces_capacity(self):
        """Accumulator should respect maxlen limit."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=3)

        for bucket_idx in range(20):
            bucket_start = 930 + bucket_idx * 5
            if bucket_start % 100 >= 60:
                bucket_start = ((bucket_start // 100) + 1) * 100 + (
                    bucket_start % 100 - 60
                )

            for offset in range(5):
                minute = bucket_start + offset
                if minute % 100 >= 60:
                    minute = ((minute // 100) + 1) * 100 + (minute % 100 - 60)

                candle = Candle(
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.5,
                    volume=1000,
                    minute=minute,
                )
                acc.on_1m_candle(candle)

        assert (
            len(acc.candles) <= 3
        ), f"Should retain at most 3 candles, got {len(acc.candles)}"


class TestStreamingIndicatorEngineMTF:
    """Tests for MTF integration in StreamingIndicatorEngine."""

    def test_mtf_disabled_by_default(self):
        """MTF accumulators should not be created if mtf_timeframes is empty."""
        engine = StreamingIndicatorEngine(staleness_seconds=0)

        engine.on_tick(
            "005930",
            {"close": 100.0, "high": 101.0, "low": 99.0, "volume": 1000},
            datetime(2026, 3, 7, 9, 30, 0),
        )
        engine.on_tick(
            "005930",
            {"close": 101.0, "high": 102.0, "low": 100.0, "volume": 2000},
            datetime(2026, 3, 7, 9, 31, 0),
        )

        assert (
            "005930" not in engine._mtf_accumulators
            or len(engine._mtf_accumulators["005930"]) == 0
        )

    def test_mtf_enabled_with_timeframes(self):
        """MTF accumulators should be created for configured timeframes."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[5, 15], staleness_seconds=0)

        cumulative = 0
        for minute in range(10):
            cumulative += 1000 + minute * 10
            engine.on_tick(
                "005930",
                {
                    "close": 100.0 + minute,
                    "high": 101.0 + minute,
                    "low": 99.0 + minute,
                    "volume": cumulative,
                },
                datetime(2026, 3, 7, 9, 30 + minute, 30),
            )

        cumulative += 1100
        engine.on_tick(
            "005930",
            {"close": 110.0, "high": 111.0, "low": 109.0, "volume": cumulative},
            datetime(2026, 3, 7, 9, 40, 30),
        )

        assert "005930" in engine._mtf_accumulators
        assert 5 in engine._mtf_accumulators["005930"]
        assert 15 in engine._mtf_accumulators["005930"]

    def test_get_mtf_candles_5m(self):
        """get_mtf_candles should return 5-min candles aggregated from 1-min candles."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[5], staleness_seconds=0)

        cumulative = 0
        for minute in range(10):
            cumulative += 1000 + minute * 10
            engine.on_tick(
                "005930",
                {
                    "close": 100.0 + minute,
                    "high": 101.0 + minute,
                    "low": 99.0 + minute,
                    "volume": cumulative,
                },
                datetime(2026, 3, 7, 9, 30 + minute, 30),
            )

        cumulative += 1100
        engine.on_tick(
            "005930",
            {"close": 110.0, "high": 111.0, "low": 109.0, "volume": cumulative},
            datetime(2026, 3, 7, 9, 40, 30),
        )

        candles_5m = engine.get_mtf_candles("005930", timeframe=5)

        assert (
            len(candles_5m) == 1
        ), "Only bucket 930 is finalized; bucket 935 still buffered"

        assert candles_5m[0]["open"] == 100.0, "First candle open from minute 930"
        assert candles_5m[0]["high"] == 105.0, "First candle high is max(101..105)"
        assert candles_5m[0]["low"] == 99.0, "First candle low is min(99..103)"
        assert candles_5m[0]["close"] == 104.0, "First candle close from minute 934"
        assert (
            candles_5m[0]["volume"] == 5100
        ), "First candle volume sum (1000+1010+1020+1030+1040)"

    def test_get_mtf_candles_15m(self):
        """get_mtf_candles should return 15-min candles aggregated from 1-min candles."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[15], staleness_seconds=0)

        cumulative = 0
        for minute in range(20):
            cumulative += 1000 + minute * 10
            engine.on_tick(
                "005930",
                {
                    "close": 100.0 + minute,
                    "high": 101.0 + minute,
                    "low": 99.0 + minute,
                    "volume": cumulative,
                },
                datetime(2026, 3, 7, 9, 30 + minute, 30),
            )

        candles_15m = engine.get_mtf_candles("005930", timeframe=15)

        assert len(candles_15m) == 1, "Should have 1 completed 15-min candle"

        assert candles_15m[0]["open"] == 100.0, "Open from minute 930"
        assert candles_15m[0]["high"] == 115.0, "High is max of 15 candles (101+14=115)"
        assert candles_15m[0]["low"] == 99.0, "Low is min of 15 candles"
        assert candles_15m[0]["close"] == 114.0, "Close from minute 944 (100+14=114)"

    def test_get_mtf_candles_limit(self):
        """get_mtf_candles should respect limit parameter."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[5], staleness_seconds=0)

        cumulative = 0
        for minute in range(26):
            cumulative += 1000 + minute * 10
            engine.on_tick(
                "005930",
                {
                    "close": 100.0 + minute,
                    "high": 101.0 + minute,
                    "low": 99.0 + minute,
                    "volume": cumulative,
                },
                datetime(2026, 3, 7, 9, 30 + minute, 30),
            )

        candles = engine.get_mtf_candles("005930", timeframe=5, limit=2)
        assert len(candles) == 2, "Should return only last 2 candles"

    def test_get_mtf_candles_nonexistent_symbol(self):
        """get_mtf_candles should return empty list for non-existent symbol."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[5], staleness_seconds=0)

        candles = engine.get_mtf_candles("NONEXISTENT", timeframe=5)
        assert candles == [], "Should return empty list"

    def test_get_mtf_candles_nonexistent_timeframe(self):
        """get_mtf_candles should return empty list for non-configured timeframe."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[5], staleness_seconds=0)

        cumulative = 0
        for minute in range(5):
            cumulative += 1000
            engine.on_tick(
                "005930",
                {"close": 100.0, "high": 101.0, "low": 99.0, "volume": cumulative},
                datetime(2026, 3, 7, 9, 30 + minute, 30),
            )

        candles = engine.get_mtf_candles("005930", timeframe=15)
        assert candles == [], "Should return empty list for unconfigured timeframe"

    def test_seed_mtf_candles(self):
        """seed_mtf_candles should pre-warm MTF accumulator with historical candles."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[5], staleness_seconds=0)

        historical_5m = []
        for i in range(10):
            historical_5m.append(
                {
                    "open": 100.0 + i * 2,
                    "high": 102.0 + i * 2,
                    "low": 98.0 + i * 2,
                    "close": 101.0 + i * 2,
                    "volume": 5000 + i * 100,
                }
            )

        engine.seed_mtf_candles("005930", historical_5m, timeframe=5)

        candles = engine.get_mtf_candles("005930", timeframe=5)
        assert len(candles) == 10, "Should have 10 seeded candles"
        assert candles[0]["open"] == 100.0
        assert candles[0]["volume"] == 5000
        assert candles[9]["close"] == 119.0

    def test_seed_mtf_adds_timeframe_if_missing(self):
        """seed_mtf_candles should add timeframe to _mtf_timeframes if not present."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[], staleness_seconds=0)

        assert (
            5 not in engine._mtf_timeframes
        ), "5-min timeframe not initially configured"

        engine.seed_mtf_candles(
            "005930",
            [{"open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000}],
            timeframe=5,
        )

        assert 5 in engine._mtf_timeframes, "5-min timeframe should be added"

    def test_multiple_symbols_independent_mtf(self):
        """MTF candles for different symbols should be tracked independently."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[5], staleness_seconds=0)

        for symbol, base_price in [("005930", 100.0), ("000660", 200.0)]:
            cumulative = 0
            for minute in range(10):
                cumulative += 1000 + minute * 10
                engine.on_tick(
                    symbol,
                    {
                        "close": base_price + minute,
                        "high": base_price + minute + 1,
                        "low": base_price + minute - 1,
                        "volume": cumulative,
                    },
                    datetime(2026, 3, 7, 9, 30 + minute, 30),
                )
            cumulative += 1100
            engine.on_tick(
                symbol,
                {
                    "close": base_price + 10,
                    "high": base_price + 11,
                    "low": base_price + 9,
                    "volume": cumulative,
                },
                datetime(2026, 3, 7, 9, 40, 30),
            )

        candles_samsung = engine.get_mtf_candles("005930", timeframe=5)
        candles_sk = engine.get_mtf_candles("000660", timeframe=5)

        assert len(candles_samsung) == 1
        assert len(candles_sk) == 1

        assert candles_samsung[0]["open"] == 100.0
        assert candles_sk[0]["open"] == 200.0

    def test_multiple_timeframes_same_symbol(self):
        """Multiple timeframes for same symbol should all receive candles."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[5, 15], staleness_seconds=0)

        cumulative = 0
        for minute in range(20):
            cumulative += 1000 + minute * 10
            engine.on_tick(
                "005930",
                {
                    "close": 100.0 + minute,
                    "high": 101.0 + minute,
                    "low": 99.0 + minute,
                    "volume": cumulative,
                },
                datetime(2026, 3, 7, 9, 30 + minute, 30),
            )

        candles_5m = engine.get_mtf_candles("005930", timeframe=5)
        candles_15m = engine.get_mtf_candles("005930", timeframe=15)

        assert (
            len(candles_5m) == 3
        ), "Should have 3 completed 5-min candles (930-934, 935-939, 940-944)"

        assert len(candles_15m) == 1, "Should have 1 completed 15-min candle"

    def test_mtf_candles_match_manual_aggregation(self):
        """MTF candles should exactly match manually aggregated values."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[5], staleness_seconds=0)

        one_min_data = [
            {
                "minute": 930,
                "open": 100.0,
                "high": 102.0,
                "low": 98.0,
                "close": 101.0,
                "volume": 1000,
            },
            {
                "minute": 931,
                "open": 101.0,
                "high": 103.0,
                "low": 100.0,
                "close": 102.5,
                "volume": 1100,
            },
            {
                "minute": 932,
                "open": 102.5,
                "high": 105.0,
                "low": 101.0,
                "close": 104.0,
                "volume": 1200,
            },
            {
                "minute": 933,
                "open": 104.0,
                "high": 106.0,
                "low": 103.0,
                "close": 105.5,
                "volume": 1300,
            },
            {
                "minute": 934,
                "open": 105.5,
                "high": 107.0,
                "low": 104.5,
                "close": 106.0,
                "volume": 1400,
            },
        ]

        cumulative = 0
        for data in one_min_data:
            cumulative += data["volume"]
            engine.on_tick(
                "TEST",
                {
                    "close": data["close"],
                    "high": data["high"],
                    "low": data["low"],
                    "volume": cumulative,
                },
                datetime(2026, 3, 7, 9, data["minute"] % 100, 30),
            )

        cumulative += 1500
        engine.on_tick(
            "TEST",
            {"close": 107.0, "high": 108.0, "low": 106.0, "volume": cumulative},
            datetime(2026, 3, 7, 9, 35, 30),
        )

        cumulative += 1600
        engine.on_tick(
            "TEST",
            {"close": 108.0, "high": 109.0, "low": 107.0, "volume": cumulative},
            datetime(2026, 3, 7, 9, 36, 30),
        )

        candles_5m = engine.get_mtf_candles("TEST", timeframe=5)
        assert len(candles_5m) == 1

        expected_open = one_min_data[0]["close"]
        expected_high = max(d["high"] for d in one_min_data)
        expected_low = min(d["low"] for d in one_min_data)
        expected_close = one_min_data[-1]["close"]
        expected_volume = sum(d["volume"] for d in one_min_data)

        assert candles_5m[0]["open"] == expected_open
        assert candles_5m[0]["high"] == expected_high
        assert candles_5m[0]["low"] == expected_low
        assert candles_5m[0]["close"] == expected_close
        assert candles_5m[0]["volume"] == expected_volume


class TestMTFEdgeCases:
    """Edge cases and error conditions for MTF functionality."""

    def test_empty_buffer_flush(self):
        """Flushing empty buffer should return None."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=100)

        result = acc.flush()
        assert result is None, "Flushing empty buffer should return None"

    def test_single_candle_flush(self):
        """Flushing single buffered candle should finalize it."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=100)

        candle = Candle(
            open=100.0, high=101.0, low=99.0, close=100.5, volume=1000, minute=930
        )
        acc.on_1m_candle(candle)

        result = acc.flush()
        assert result is not None
        assert result.open == 100.0
        assert result.close == 100.5
        assert result.volume == 1000

    def test_hour_boundary_bucket_calculation(self):
        """Bucket calculation should handle hour boundaries correctly."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=15, maxlen=100)

        assert acc._get_bucket(945) == 945
        assert acc._get_bucket(959) == 945
        assert acc._get_bucket(1000) == 1000
        assert acc._get_bucket(1014) == 1000
        assert acc._get_bucket(1015) == 1015

    def test_zero_volume_candles(self):
        """Zero-volume candles should aggregate correctly."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=100)

        for i in range(5):
            candle = Candle(
                open=100.0, high=101.0, low=99.0, close=100.5, volume=0, minute=930 + i
            )
            acc.on_1m_candle(candle)

        next_candle = Candle(
            open=100.5, high=101.5, low=99.5, close=101.0, volume=1000, minute=935
        )
        result = acc.on_1m_candle(next_candle)

        assert result is not None
        assert result.volume == 0, "Aggregated volume should be 0"

    def test_price_extremes(self):
        """Very large or very small prices should aggregate correctly."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=100)

        for i in range(5):
            candle = Candle(
                open=1000000.0,
                high=1000100.0,
                low=999900.0,
                close=1000050.0,
                volume=100,
                minute=930 + i,
            )
            acc.on_1m_candle(candle)

        next_candle = Candle(
            open=1000050.0,
            high=1000150.0,
            low=999950.0,
            close=1000100.0,
            volume=100,
            minute=935,
        )
        result = acc.on_1m_candle(next_candle)

        assert result is not None
        assert result.high == 1000100.0
        assert result.low == 999900.0


def _seed_minutes(
    engine: StreamingIndicatorEngine,
    symbol: str,
    count: int,
    base_price: float = 300.0,
    start: datetime | None = None,
) -> None:
    """Seed ``count`` sequential 1-minute candles via ``seed_candles``."""
    start = start or datetime(2026, 2, 17, 9, 0)
    candles = [
        {
            "datetime": start + timedelta(minutes=i),
            "open": base_price + (i % 10),
            "high": base_price + (i % 10) + 1,
            "low": base_price + (i % 10) - 1,
            "close": base_price + (i % 10),
            "volume": 100,
        }
        for i in range(count)
    ]
    engine.seed_candles(symbol, candles)


class TestIsWarmMtfAware:
    """is_warm must account for the *strategy-required* MTF timeframe."""

    def test_not_warm_until_deepest_mtf_filled(self):
        engine = StreamingIndicatorEngine(
            bb_period=20,
            mtf_timeframes=[5, 15],
            mtf_warmth_timeframe=15,
            staleness_seconds=0,
        )
        _seed_minutes(engine, "TEST", 60)
        assert len(engine._accumulators["TEST"].candles) >= 20
        assert engine.mtf_total_appended("TEST", 15) < 20
        assert not engine.is_warm("TEST"), (
            "1m warm but 15m starved -> must NOT report warm "
            "(else prewarm skips the deep Parquet load)"
        )

    def test_warm_once_deepest_mtf_filled(self):
        engine = StreamingIndicatorEngine(
            bb_period=20,
            mtf_timeframes=[5, 15],
            mtf_warmth_timeframe=15,
            staleness_seconds=0,
        )
        _seed_minutes(engine, "TEST", 330)
        assert engine.mtf_total_appended("TEST", 15) >= 20
        assert engine.is_warm("TEST")

    def test_deepest_tf_gates_not_shallowest(self):
        engine = StreamingIndicatorEngine(
            bb_period=20,
            mtf_timeframes=[5, 15],
            mtf_warmth_timeframe=15,
            staleness_seconds=0,
        )
        _seed_minutes(engine, "TEST", 120)
        assert engine.mtf_total_appended("TEST", 5) >= 20
        assert engine.mtf_total_appended("TEST", 15) < 20
        assert not engine.is_warm("TEST")

    def test_warm_unchanged_without_mtf(self):
        engine = StreamingIndicatorEngine(bb_period=20, staleness_seconds=0)
        _seed_minutes(engine, "TEST", 25)
        assert engine.is_warm("TEST")

    def test_daily_does_not_gate_warmth(self):
        engine = StreamingIndicatorEngine(
            bb_period=20,
            mtf_timeframes=[15, "daily"],
            mtf_warmth_timeframe=15,
            staleness_seconds=0,
        )
        _seed_minutes(engine, "TEST", 330)
        assert engine.is_warm("TEST")

    def test_stock_engine_not_blocked_by_unused_mtf(self):
        engine = StreamingIndicatorEngine(
            bb_period=20,
            mtf_timeframes=[5, 15],
            mtf_warmth_timeframe=None,
            staleness_seconds=0,
        )
        _seed_minutes(engine, "TEST", 25)
        assert engine.mtf_total_appended("TEST", 15) < 20
        assert engine.is_warm(
            "TEST"
        ), "1m-only strategy must not be gated by accumulated-but-unused 15m"

    def test_warmth_tf_not_accumulated_falls_back_to_1m(self):
        engine = StreamingIndicatorEngine(
            bb_period=20,
            mtf_timeframes=[5],
            mtf_warmth_timeframe=15,
            staleness_seconds=0,
        )
        _seed_minutes(engine, "TEST", 25)
        assert engine.mtf_total_appended("TEST", 15) == 0
        assert engine.is_warm("TEST")

    def test_seed_candles_minute_fallback_feeds_mtf(self):
        engine = StreamingIndicatorEngine(
            bb_period=20,
            mtf_timeframes=[15],
            mtf_warmth_timeframe=15,
            staleness_seconds=0,
        )
        candles = [
            {
                "minute": (9 * 60 + i) // 60 * 100 + (9 * 60 + i) % 60,
                "open": 300.0,
                "high": 301.0,
                "low": 299.0,
                "close": 300.0,
                "volume": 100,
            }
            for i in range(330)
        ]
        engine.seed_candles("TEST", candles)
        assert (
            engine.mtf_total_appended("TEST", 15) >= 20
        ), "minute-keyed (Redis) candles must advance MTF buckets"
