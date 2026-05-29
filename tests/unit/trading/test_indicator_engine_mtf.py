"""Tests for Multi-Timeframe (MTF) candle aggregation in StreamingIndicatorEngine."""

from __future__ import annotations

from datetime import datetime, timedelta

from services.trading.indicator_engine import (
    MultiTimeframeCandleAccumulator,
    StreamingIndicatorEngine,
    Candle,
)


class TestMultiTimeframeCandleAccumulator:
    """Tests for MultiTimeframeCandleAccumulator - aggregating 1m candles to higher timeframes."""

    def test_5m_candle_from_single_1m_candle(self):
        """A single 1-min candle should buffer, not finalize, until bucket changes."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=100)

        # 09:30 candle (bucket 930)
        candle = Candle(open=100.0, high=101.0, low=99.0, close=100.5, volume=1000, minute=930)
        result = acc.on_1m_candle(candle)

        assert result is None, "First candle should buffer, not finalize"
        assert len(acc.candles) == 0, "No completed candles yet"
        assert len(acc._buffer) == 1, "One candle in buffer"

    def test_5m_candle_aggregation_ohlcv(self):
        """5-min candle should aggregate OHLCV correctly from buffered 1-min candles.

        Note: The accumulator only finalizes the buffer when a NEW bucket arrives.
        Feeding candles 930-933 (bucket 930) then next_candle at 935 (bucket 935)
        triggers finalization of the 4-candle buffer [930, 931, 932, 933].
        The 5th candle (934) is NOT fed before the trigger; it's part of one_min_candles
        but skipped by the [:-1] slice. So the finalized 5-min candle covers 930-933.
        """
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=100)

        # Feed 5 candles for 09:30-09:34 (bucket 930)
        one_min_candles = [
            Candle(open=100.0, high=101.0, low=99.0, close=100.5, volume=1000, minute=930),
            Candle(open=100.5, high=102.0, low=100.0, close=101.5, volume=1100, minute=931),
            Candle(open=101.5, high=103.0, low=101.0, close=102.0, volume=1200, minute=932),
            Candle(open=102.0, high=102.5, low=101.5, close=101.8, volume=1150, minute=933),
            Candle(open=101.8, high=102.2, low=101.0, close=101.5, volume=1050, minute=934),
        ]

        for c in one_min_candles[:-1]:
            result = acc.on_1m_candle(c)
            assert result is None, "Should buffer until bucket changes"

        # Next bucket (935) triggers finalization of 4 buffered candles (930-933)
        next_candle = Candle(open=101.5, high=102.0, low=101.0, close=101.8, volume=1300, minute=935)
        result = acc.on_1m_candle(next_candle)

        assert result is not None, "Bucket change should finalize previous 5-min candle"
        assert len(acc.candles) == 1, "One completed 5-min candle"

        # Verify aggregated OHLCV — buffer contains candles 930, 931, 932, 933
        assert result.open == 100.0, "Open should be from first 1-min candle (930)"
        assert result.high == 103.0, "High should be max of all highs (101, 102, 103, 102.5)"
        assert result.low == 99.0, "Low should be min of all lows (99, 100, 101, 101.5)"
        assert result.close == 101.8, "Close should be from last buffered candle (933, not 934)"
        assert result.volume == 4450, "Volume should be sum of 4 candles (1000+1100+1200+1150)"
        assert result.minute == 930, "Minute should be bucket start"

    def test_15m_candle_aggregation(self):
        """15-min candle should aggregate 15 consecutive 1-min candles correctly."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=15, maxlen=100)

        # Feed 15 candles for 09:30-09:44 (bucket 930)
        base_price = 100.0
        cumulative_volume = 0

        for i in range(15):
            minute = 930 + i
            if minute % 100 >= 60:  # Handle hour boundary
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

        # Next bucket (945) triggers finalization
        next_candle = Candle(open=108.0, high=109.0, low=107.5, close=108.5, volume=1200, minute=945)
        result = acc.on_1m_candle(next_candle)

        assert result is not None, "Bucket change should finalize 15-min candle"
        assert result.open == 100.0, "Open should be from first candle"
        assert result.high == 107.5, "High should be max of all highs (100 + 14*0.5 + 0.5)"
        # price increases each candle: price[i] = 100 + i*0.5, low[i] = price[i] - 0.5
        # For i=0: low=99.5 (minimum, since prices increase)
        assert result.low == 99.5, "Low should be min of all lows (candle i=0: low=100.0-0.5=99.5)"
        assert result.volume == cumulative_volume, f"Volume should be sum of all 15 candles"

    def test_bucket_calculation_edge_cases(self):
        """Test bucket calculation for various minute values."""
        acc_5m = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=100)
        acc_15m = MultiTimeframeCandleAccumulator(timeframe_minutes=15, maxlen=100)

        # 5-minute buckets
        assert acc_5m._get_bucket(930) == 930   # 09:30 → 930
        assert acc_5m._get_bucket(932) == 930   # 09:32 → 930
        assert acc_5m._get_bucket(934) == 930   # 09:34 → 930
        assert acc_5m._get_bucket(935) == 935   # 09:35 → 935
        assert acc_5m._get_bucket(939) == 935   # 09:39 → 935
        assert acc_5m._get_bucket(940) == 940   # 09:40 → 940
        assert acc_5m._get_bucket(1000) == 1000 # 10:00 → 1000
        assert acc_5m._get_bucket(1003) == 1000 # 10:03 → 1000

        # 15-minute buckets
        assert acc_15m._get_bucket(930) == 930   # 09:30 → 930
        assert acc_15m._get_bucket(935) == 930   # 09:35 → 930
        assert acc_15m._get_bucket(944) == 930   # 09:44 → 930
        assert acc_15m._get_bucket(945) == 945   # 09:45 → 945
        assert acc_15m._get_bucket(959) == 945   # 09:59 → 945
        assert acc_15m._get_bucket(1000) == 1000 # 10:00 → 1000
        assert acc_15m._get_bucket(1014) == 1000 # 10:14 → 1000
        assert acc_15m._get_bucket(1015) == 1015 # 10:15 → 1015

    def test_incomplete_bucket_not_finalized(self):
        """Partial bucket (e.g., 3 candles in 5-min bucket) should not auto-finalize."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=100)

        # Feed only 3 candles in 09:30 bucket
        for i in range(3):
            candle = Candle(open=100.0, high=101.0, low=99.0, close=100.5, volume=1000, minute=930 + i)
            result = acc.on_1m_candle(candle)
            assert result is None

        assert len(acc.candles) == 0, "Partial bucket should not finalize"
        assert len(acc._buffer) == 3, "3 candles buffered"

    def test_flush_finalizes_partial_bucket(self):
        """flush() should finalize any buffered candles."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=100)

        # Feed 3 candles (partial bucket)
        for i in range(3):
            candle = Candle(open=100.0 + i, high=101.0 + i, low=99.0 + i, close=100.5 + i, volume=1000, minute=930 + i)
            acc.on_1m_candle(candle)

        assert len(acc.candles) == 0, "No finalized candles yet"

        # Flush should finalize the partial bucket
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

        # Feed 15 1-min candles (3 complete 5-min buckets)
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

            # Buckets: 930 (930-934), 935 (935-939), 940 (940-944)
            # Finalization happens at minute 935 and 940
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

        # Create 20 5-min candles (100 1-min candles)
        for bucket_idx in range(20):
            bucket_start = 930 + bucket_idx * 5
            if bucket_start % 100 >= 60:
                bucket_start = ((bucket_start // 100) + 1) * 100 + (bucket_start % 100 - 60)

            for offset in range(5):
                minute = bucket_start + offset
                if minute % 100 >= 60:
                    minute = ((minute // 100) + 1) * 100 + (minute % 100 - 60)

                candle = Candle(open=100.0, high=101.0, low=99.0, close=100.5, volume=1000, minute=minute)
                acc.on_1m_candle(candle)

        # maxlen=3, so only last 3 completed candles should be retained
        assert len(acc.candles) <= 3, f"Should retain at most 3 candles, got {len(acc.candles)}"


class TestStreamingIndicatorEngineMTF:
    """Tests for MTF integration in StreamingIndicatorEngine."""

    def test_mtf_disabled_by_default(self):
        """MTF accumulators should not be created if mtf_timeframes is empty."""
        engine = StreamingIndicatorEngine(staleness_seconds=0)

        # Feed ticks to create 1-min candles
        engine.on_tick("005930", {"close": 100.0, "high": 101.0, "low": 99.0, "volume": 1000}, datetime(2026, 3, 7, 9, 30, 0))
        engine.on_tick("005930", {"close": 101.0, "high": 102.0, "low": 100.0, "volume": 2000}, datetime(2026, 3, 7, 9, 31, 0))

        # No MTF accumulators should exist
        assert "005930" not in engine._mtf_accumulators or len(engine._mtf_accumulators["005930"]) == 0

    def test_mtf_enabled_with_timeframes(self):
        """MTF accumulators should be created for configured timeframes."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[5, 15], staleness_seconds=0)

        # Feed ticks to create 1-min candles (cumulative volumes)
        cumulative = 0
        for minute in range(10):
            cumulative += 1000 + minute * 10
            engine.on_tick(
                "005930",
                {"close": 100.0 + minute, "high": 101.0 + minute, "low": 99.0 + minute, "volume": cumulative},
                datetime(2026, 3, 7, 9, 30 + minute, 30),
            )

        # Cross to next minute to finalize last candle
        cumulative += 1100
        engine.on_tick("005930", {"close": 110.0, "high": 111.0, "low": 109.0, "volume": cumulative}, datetime(2026, 3, 7, 9, 40, 30))

        # MTF accumulators should exist for both timeframes
        assert "005930" in engine._mtf_accumulators
        assert 5 in engine._mtf_accumulators["005930"]
        assert 15 in engine._mtf_accumulators["005930"]

    def test_get_mtf_candles_5m(self):
        """get_mtf_candles should return 5-min candles aggregated from 1-min candles.

        Note on timing: on_tick finalizes a 1m candle when the minute boundary changes.
        A tick at minute M finalizes the candle for minute M-1. So to finalize a 5m
        bucket ending at minute 934, we need a candle from minute 935 (from a tick at
        9:36). To then finalize bucket 935 (935-939), we need a tick at 9:45 that
        creates the 9:44 candle (bucket 940), triggering bucket 935 finalization.
        """
        engine = StreamingIndicatorEngine(mtf_timeframes=[5], staleness_seconds=0)

        # Feed 10 1-min candles (ticks at 9:30-9:39)
        # This will complete 1m candles for 9:30-9:38 (finalized at next-minute tick)
        cumulative = 0
        for minute in range(10):
            cumulative += 1000 + minute * 10
            engine.on_tick(
                "005930",
                {"close": 100.0 + minute, "high": 101.0 + minute, "low": 99.0 + minute, "volume": cumulative},
                datetime(2026, 3, 7, 9, 30 + minute, 30),
            )

        # Tick at 9:40 finalizes the 9:39 1m candle (bucket 935),
        # adding it to the bucket-935 buffer but not triggering MTF finalization
        # (still in bucket 935). Need 9:45 tick to finalize bucket 935.
        cumulative += 1100
        engine.on_tick("005930", {"close": 110.0, "high": 111.0, "low": 109.0, "volume": cumulative}, datetime(2026, 3, 7, 9, 40, 30))

        # After ticks 9:30-9:40, only bucket 930 (9:30-9:34) has been finalized.
        # Bucket 935 (9:35-9:39) is still buffered (needs tick at 9:45 to finalize).
        candles_5m = engine.get_mtf_candles("005930", timeframe=5)

        assert len(candles_5m) == 1, "Only bucket 930 is finalized; bucket 935 still buffered"

        # First 5-min candle (930-934): 1m candles at minutes 930-934
        # 1m candle[0]: close=100, high=101, low=99 (from tick at 9:30 finalized at 9:31)
        # 1m candle[4]: close=104, high=105, low=103 (from tick at 9:34 finalized at 9:35)
        assert candles_5m[0]["open"] == 100.0, "First candle open from minute 930"
        assert candles_5m[0]["high"] == 105.0, "First candle high is max(101..105)"
        assert candles_5m[0]["low"] == 99.0, "First candle low is min(99..103)"
        assert candles_5m[0]["close"] == 104.0, "First candle close from minute 934"
        assert candles_5m[0]["volume"] == 5100, "First candle volume sum (1000+1010+1020+1030+1040)"

    def test_get_mtf_candles_15m(self):
        """get_mtf_candles should return 15-min candles aggregated from 1-min candles.

        Note on timing: a tick at minute M finalizes the 1m candle for minute M-1.
        Ticks at 9:30-9:49 finalize 1m candles for 9:30-9:48. Bucket 930 covers
        9:30-9:44 (15 candles). The 9:44 1m candle (close=114, high=115) is finalized
        by the tick at 9:45. The 9:45 1m candle is in bucket 945, triggering MTF
        finalization of bucket 930. So with 20 ticks (9:30-9:49), bucket 930 is
        finalized and bucket 945 has 4 buffered candles (9:45-9:48).
        """
        engine = StreamingIndicatorEngine(mtf_timeframes=[15], staleness_seconds=0)

        # Feed 20 1-min candles (1 complete 15-min bucket + partial second bucket)
        cumulative = 0
        for minute in range(20):
            cumulative += 1000 + minute * 10
            engine.on_tick(
                "005930",
                {"close": 100.0 + minute, "high": 101.0 + minute, "low": 99.0 + minute, "volume": cumulative},
                datetime(2026, 3, 7, 9, 30 + minute, 30),
            )

        # Get 15-min candles
        candles_15m = engine.get_mtf_candles("005930", timeframe=15)

        # Only first bucket (930-944) should be complete
        assert len(candles_15m) == 1, "Should have 1 completed 15-min candle"

        assert candles_15m[0]["open"] == 100.0, "Open from minute 930"
        # 1m candle high[i] = 101+i. Bucket 930 covers 1m candles 930-944:
        # max high = 101+14 = 115 (from candle at minute 944)
        assert candles_15m[0]["high"] == 115.0, "High is max of 15 candles (101+14=115)"
        assert candles_15m[0]["low"] == 99.0, "Low is min of 15 candles"
        assert candles_15m[0]["close"] == 114.0, "Close from minute 944 (100+14=114)"

    def test_get_mtf_candles_limit(self):
        """get_mtf_candles should respect limit parameter."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[5], staleness_seconds=0)

        # Feed 25 1-min candles (5 complete 5-min buckets)
        cumulative = 0
        for minute in range(26):  # 26 to finalize 5th bucket
            cumulative += 1000 + minute * 10
            engine.on_tick(
                "005930",
                {"close": 100.0 + minute, "high": 101.0 + minute, "low": 99.0 + minute, "volume": cumulative},
                datetime(2026, 3, 7, 9, 30 + minute, 30),
            )

        # Get last 2 candles only
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

        # Feed some candles
        cumulative = 0
        for minute in range(5):
            cumulative += 1000
            engine.on_tick(
                "005930",
                {"close": 100.0, "high": 101.0, "low": 99.0, "volume": cumulative},
                datetime(2026, 3, 7, 9, 30 + minute, 30),
            )

        # Request 15-min candles (not configured)
        candles = engine.get_mtf_candles("005930", timeframe=15)
        assert candles == [], "Should return empty list for unconfigured timeframe"

    def test_seed_mtf_candles(self):
        """seed_mtf_candles should pre-warm MTF accumulator with historical candles."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[5], staleness_seconds=0)

        # Seed 10 historical 5-min candles
        historical_5m = []
        for i in range(10):
            historical_5m.append({
                "open": 100.0 + i * 2,
                "high": 102.0 + i * 2,
                "low": 98.0 + i * 2,
                "close": 101.0 + i * 2,
                "volume": 5000 + i * 100,
            })

        engine.seed_mtf_candles("005930", historical_5m, timeframe=5)

        # Verify candles were seeded
        candles = engine.get_mtf_candles("005930", timeframe=5)
        assert len(candles) == 10, "Should have 10 seeded candles"
        assert candles[0]["open"] == 100.0
        assert candles[0]["volume"] == 5000
        assert candles[9]["close"] == 119.0

    def test_seed_mtf_adds_timeframe_if_missing(self):
        """seed_mtf_candles should add timeframe to _mtf_timeframes if not present."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[], staleness_seconds=0)

        assert 5 not in engine._mtf_timeframes, "5-min timeframe not initially configured"

        engine.seed_mtf_candles("005930", [{"open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000}], timeframe=5)

        assert 5 in engine._mtf_timeframes, "5-min timeframe should be added"

    def test_multiple_symbols_independent_mtf(self):
        """MTF candles for different symbols should be tracked independently.

        Note on timing: a tick at minute M finalizes the 1m candle for minute M-1.
        With 10 ticks (9:30-9:39) + trigger at 9:40, only bucket 930 (9:30-9:34) is
        finalized. Bucket 935 (9:35-9:39) remains buffered until a tick at 9:45 arrives.
        Each symbol maintains its own independent accumulators.
        """
        engine = StreamingIndicatorEngine(mtf_timeframes=[5], staleness_seconds=0)

        # Feed ticks for two symbols
        for symbol, base_price in [("005930", 100.0), ("000660", 200.0)]:
            cumulative = 0
            for minute in range(10):
                cumulative += 1000 + minute * 10
                engine.on_tick(
                    symbol,
                    {"close": base_price + minute, "high": base_price + minute + 1, "low": base_price + minute - 1, "volume": cumulative},
                    datetime(2026, 3, 7, 9, 30 + minute, 30),
                )
            # Tick at 9:40 finalizes 9:39 candle (bucket 935), adds to buffer.
            # Bucket 935 not yet finalized (needs 9:45 tick).
            cumulative += 1100
            engine.on_tick(symbol, {"close": base_price + 10, "high": base_price + 11, "low": base_price + 9, "volume": cumulative}, datetime(2026, 3, 7, 9, 40, 30))

        # Get candles for each symbol
        candles_samsung = engine.get_mtf_candles("005930", timeframe=5)
        candles_sk = engine.get_mtf_candles("000660", timeframe=5)

        # Only bucket 930 is finalized for each symbol
        assert len(candles_samsung) == 1
        assert len(candles_sk) == 1

        # Verify prices are different (first 1m candle in bucket 930 comes from 9:30)
        assert candles_samsung[0]["open"] == 100.0
        assert candles_sk[0]["open"] == 200.0

    def test_multiple_timeframes_same_symbol(self):
        """Multiple timeframes for same symbol should all receive candles."""
        engine = StreamingIndicatorEngine(mtf_timeframes=[5, 15], staleness_seconds=0)

        # Feed 20 1-min candles
        cumulative = 0
        for minute in range(20):
            cumulative += 1000 + minute * 10
            engine.on_tick(
                "005930",
                {"close": 100.0 + minute, "high": 101.0 + minute, "low": 99.0 + minute, "volume": cumulative},
                datetime(2026, 3, 7, 9, 30 + minute, 30),
            )

        # Get candles for both timeframes
        candles_5m = engine.get_mtf_candles("005930", timeframe=5)
        candles_15m = engine.get_mtf_candles("005930", timeframe=15)

        # 5-min: 20 minutes = 4 complete buckets (partial 5th buffered)
        assert len(candles_5m) == 3, "Should have 3 completed 5-min candles (930-934, 935-939, 940-944)"

        # 15-min: 20 minutes = 1 complete bucket (930-944, partial second buffered)
        assert len(candles_15m) == 1, "Should have 1 completed 15-min candle"

    def test_mtf_candles_match_manual_aggregation(self):
        """MTF candles should exactly match manually aggregated values.

        Note on timing: on_tick finalizes a 1m candle when minute boundary changes.
        Feeding ticks at 9:30-9:34 (5 ticks) will finalize 1m candles for 9:30-9:33
        (4 candles). The 9:34 candle is only in the CandleAccumulator buffer.
        The tick at 9:35 then finalizes the 9:34 1m candle and adds it to the MTF
        buffer (still bucket 930). The 9:35 1m candle (bucket 935) triggers MTF
        finalization only from the NEXT tick at 9:36. So 5 ticks at 9:30-9:34 +
        trigger at 9:35 produces a 5m candle covering 1m candles at 930-933 (4 candles).

        To get all 5 candles in the 5m bucket, we need ticks at 9:30-9:35 (6 ticks),
        then a trigger at 9:36 (which finalizes 9:35 candle with bucket=935, triggering
        MTF finalization of bucket 930 containing candles 930-934).
        """
        engine = StreamingIndicatorEngine(mtf_timeframes=[5], staleness_seconds=0)

        # Feed ticks at 9:30-9:35 (6 ticks) to create 1m candles for 9:30-9:34 (5 candles)
        # and trigger MTF bucket 930 finalization
        one_min_data = [
            {"minute": 930, "open": 100.0, "high": 102.0, "low": 98.0, "close": 101.0, "volume": 1000},
            {"minute": 931, "open": 101.0, "high": 103.0, "low": 100.0, "close": 102.5, "volume": 1100},
            {"minute": 932, "open": 102.5, "high": 105.0, "low": 101.0, "close": 104.0, "volume": 1200},
            {"minute": 933, "open": 104.0, "high": 106.0, "low": 103.0, "close": 105.5, "volume": 1300},
            {"minute": 934, "open": 105.5, "high": 107.0, "low": 104.5, "close": 106.0, "volume": 1400},
        ]

        cumulative = 0
        for data in one_min_data:
            cumulative += data["volume"]
            engine.on_tick(
                "TEST",
                {"close": data["close"], "high": data["high"], "low": data["low"], "volume": cumulative},
                datetime(2026, 3, 7, 9, data["minute"] % 100, 30),
            )

        # Tick at 9:35 finalizes the 9:34 1m candle (bucket 930), adding to buffer.
        # Bucket 930 still not finalized (need bucket 935 candle to trigger it).
        cumulative += 1500
        engine.on_tick("TEST", {"close": 107.0, "high": 108.0, "low": 106.0, "volume": cumulative}, datetime(2026, 3, 7, 9, 35, 30))

        # Tick at 9:36 finalizes the 9:35 1m candle (bucket 935), which triggers
        # MTF finalization of bucket 930 (containing all 5 candles 930-934).
        cumulative += 1600
        engine.on_tick("TEST", {"close": 108.0, "high": 109.0, "low": 107.0, "volume": cumulative}, datetime(2026, 3, 7, 9, 36, 30))

        candles_5m = engine.get_mtf_candles("TEST", timeframe=5)
        assert len(candles_5m) == 1

        # Manual aggregation of all 5 candles (930-934)
        # Note: 1m candles from CandleAccumulator use the tick's close/high/low directly
        # since each tick is in a different minute. Open = first tick's close in that minute.
        expected_open = one_min_data[0]["close"]  # 101.0 (open of 930 1m candle = close of first tick)
        expected_high = max(d["high"] for d in one_min_data)  # 107.0
        expected_low = min(d["low"] for d in one_min_data)  # 98.0
        expected_close = one_min_data[-1]["close"]  # 106.0
        expected_volume = sum(d["volume"] for d in one_min_data)  # 6000

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

        candle = Candle(open=100.0, high=101.0, low=99.0, close=100.5, volume=1000, minute=930)
        acc.on_1m_candle(candle)

        result = acc.flush()
        assert result is not None
        assert result.open == 100.0
        assert result.close == 100.5
        assert result.volume == 1000

    def test_hour_boundary_bucket_calculation(self):
        """Bucket calculation should handle hour boundaries correctly."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=15, maxlen=100)

        # Test buckets around 10:00
        assert acc._get_bucket(945) == 945   # 09:45
        assert acc._get_bucket(959) == 945   # 09:59 → 945
        assert acc._get_bucket(1000) == 1000 # 10:00 → 1000
        assert acc._get_bucket(1014) == 1000 # 10:14 → 1000
        assert acc._get_bucket(1015) == 1015 # 10:15 → 1015

    def test_zero_volume_candles(self):
        """Zero-volume candles should aggregate correctly."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=100)

        for i in range(5):
            candle = Candle(open=100.0, high=101.0, low=99.0, close=100.5, volume=0, minute=930 + i)
            acc.on_1m_candle(candle)

        # Next bucket to finalize
        next_candle = Candle(open=100.5, high=101.5, low=99.5, close=101.0, volume=1000, minute=935)
        result = acc.on_1m_candle(next_candle)

        assert result is not None
        assert result.volume == 0, "Aggregated volume should be 0"

    def test_price_extremes(self):
        """Very large or very small prices should aggregate correctly."""
        acc = MultiTimeframeCandleAccumulator(timeframe_minutes=5, maxlen=100)

        # Extremely large prices
        for i in range(5):
            candle = Candle(open=1000000.0, high=1000100.0, low=999900.0, close=1000050.0, volume=100, minute=930 + i)
            acc.on_1m_candle(candle)

        next_candle = Candle(open=1000050.0, high=1000150.0, low=999950.0, close=1000100.0, volume=100, minute=935)
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
    """Seed ``count`` sequential 1-minute candles via ``seed_candles``.

    ``seed_candles`` derives the HHMM ``minute`` from each ``datetime`` and
    feeds the MTF accumulators, mirroring the orchestrator prewarm path. Prices
    are irrelevant to warmth (is_warm only counts candles).
    """
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
    """is_warm must account for the deepest numeric MTF timeframe.

    Regression: a 15m strategy (mtf_base_15m) cannot emit signals until the
    15m accumulator holds ``bb_period`` closed candles. If is_warm reports warm
    as soon as the 1m accumulator fills, the orchestrator prewarm short-circuits
    (``if is_warm(symbol): continue``) and skips the deep ClickHouse load that
    seeds those 15m bars — producing zero signals indefinitely.
    """

    def test_not_warm_until_deepest_mtf_filled(self):
        engine = StreamingIndicatorEngine(
            bb_period=20, mtf_timeframes=[5, 15], staleness_seconds=0
        )
        # 60 1m candles -> 1m accumulator warm (>=20), but 15m only ~3 closed.
        _seed_minutes(engine, "TEST", 60)
        assert len(engine._accumulators["TEST"].candles) >= 20
        assert engine.mtf_total_appended("TEST", 15) < 20
        assert not engine.is_warm("TEST"), (
            "1m warm but 15m starved -> must NOT report warm "
            "(else prewarm skips the deep ClickHouse load)"
        )

    def test_warm_once_deepest_mtf_filled(self):
        engine = StreamingIndicatorEngine(
            bb_period=20, mtf_timeframes=[5, 15], staleness_seconds=0
        )
        # ~22 distinct 15m buckets -> >=21 closed 15m candles.
        _seed_minutes(engine, "TEST", 330)
        assert engine.mtf_total_appended("TEST", 15) >= 20
        assert engine.is_warm("TEST")

    def test_deepest_tf_gates_not_shallowest(self):
        # 5m fills well before 15m; warmth must follow the deepest (15m).
        engine = StreamingIndicatorEngine(
            bb_period=20, mtf_timeframes=[5, 15], staleness_seconds=0
        )
        _seed_minutes(engine, "TEST", 120)
        assert engine.mtf_total_appended("TEST", 5) >= 20
        assert engine.mtf_total_appended("TEST", 15) < 20
        assert not engine.is_warm("TEST")

    def test_warm_unchanged_without_mtf(self):
        # Backward compat: no MTF configured -> 1m bb_period alone warms.
        engine = StreamingIndicatorEngine(bb_period=20, staleness_seconds=0)
        _seed_minutes(engine, "TEST", 25)
        assert engine.is_warm("TEST")

    def test_daily_does_not_gate_warmth(self):
        # 'daily' is loaded from ClickHouse separately, never fed from the 1m
        # stream, so it must not gate 1m/MTF warmth.
        engine = StreamingIndicatorEngine(
            bb_period=20, mtf_timeframes=[15, "daily"], staleness_seconds=0
        )
        _seed_minutes(engine, "TEST", 330)
        assert engine.is_warm("TEST")
