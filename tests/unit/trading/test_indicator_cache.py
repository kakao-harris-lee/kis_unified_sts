"""Tests for indicator caching behavior in StreamingIndicatorEngine."""

from __future__ import annotations

from datetime import datetime

import pytest

from services.trading.indicator_engine import StreamingIndicatorEngine


@pytest.fixture
def engine():
    """Create a fresh engine instance for each test."""
    return StreamingIndicatorEngine(
        bb_period=20,
        rsi_period=14,
        high_period=5,
        rvol_short=5,
        rvol_long=20,
        staleness_seconds=0,  # Disable staleness guard for tests
    )


@pytest.fixture
def warm_engine():
    """Create an engine with 25 warm candles for a symbol."""
    engine = StreamingIndicatorEngine(
        bb_period=20,
        high_period=5,
        rvol_short=5,
        rvol_long=20,
        staleness_seconds=0,
    )
    symbol = "005930"

    # Feed 25 candles by ticking across minute boundaries
    cumulative_volume = 0
    for minute in range(25):
        ts = datetime(2026, 2, 17, 9, minute, 30)
        price = 70000.0 + minute * 100
        cumulative_volume += 1000 + minute * 10

        engine.on_tick(
            symbol,
            {
                "close": price,
                "high": price + 50,
                "low": price - 50,
                "volume": cumulative_volume,
            },
            ts,
        )

    # Finalize last candle with tick in minute 25
    cumulative_volume += 1250
    engine.on_tick(
        symbol,
        {
            "close": 72500.0,
            "high": 72550.0,
            "low": 72450.0,
            "volume": cumulative_volume,
        },
        datetime(2026, 2, 17, 9, 25, 30),
    )

    assert engine.is_warm(symbol), "Engine should be warm with 25 candles"
    return engine


class TestIndicatorCacheBasics:
    """Test basic caching behavior for get_indicators()."""

    def test_cache_starts_empty(self, engine):
        """Cache statistics should start at zero."""
        stats = engine.get_cache_stats()

        assert stats["indicator_cache_hits"] == 0
        assert stats["indicator_cache_misses"] == 0
        assert stats["indicator_cache_size"] == 0
        assert stats["indicator_hit_rate"] == 0.0

    def test_first_call_is_cache_miss(self, warm_engine):
        """First call to get_indicators() should be a cache miss."""
        stats_before = warm_engine.get_cache_stats()
        warm_engine.get_indicators("005930")
        stats_after = warm_engine.get_cache_stats()

        assert stats_after["indicator_cache_misses"] == stats_before["indicator_cache_misses"] + 1
        assert stats_after["indicator_cache_hits"] == 0
        assert stats_after["indicator_cache_size"] == 1

    def test_repeated_calls_are_cache_hits(self, warm_engine):
        """Repeated calls without new candles should hit the cache."""
        symbol = "005930"

        # First call: cache miss
        warm_engine.get_indicators(symbol)
        stats_after_first = warm_engine.get_cache_stats()
        assert stats_after_first["indicator_cache_misses"] == 1
        assert stats_after_first["indicator_cache_hits"] == 0

        # Second and third calls: cache hits
        warm_engine.get_indicators(symbol)
        warm_engine.get_indicators(symbol)
        stats_after_repeat = warm_engine.get_cache_stats()

        assert stats_after_repeat["indicator_cache_misses"] == 1
        assert stats_after_repeat["indicator_cache_hits"] == 2
        assert stats_after_repeat["indicator_hit_rate"] == pytest.approx(66.67, rel=0.1)

    def test_cache_invalidation_on_new_candle(self, warm_engine):
        """Cache should invalidate when a new candle completes."""
        symbol = "005930"

        # First call and cache hit
        result1 = warm_engine.get_indicators(symbol)
        warm_engine.get_indicators(symbol)  # cache hit
        stats_before_new_candle = warm_engine.get_cache_stats()

        assert stats_before_new_candle["indicator_cache_hits"] == 1
        assert stats_before_new_candle["indicator_cache_misses"] == 1

        # Add a new candle by crossing minute boundary
        warm_engine.on_tick(
            symbol,
            {"close": 73000.0, "high": 73050.0, "low": 72950.0, "volume": 50000},
            datetime(2026, 2, 17, 9, 26, 30),
        )

        # Next call should be a cache miss due to new candle
        result2 = warm_engine.get_indicators(symbol)
        stats_after_new_candle = warm_engine.get_cache_stats()

        assert stats_after_new_candle["indicator_cache_misses"] == 2
        assert stats_after_new_candle["indicator_cache_hits"] == 1

        # Results should be different due to new candle
        assert result1 != result2

    def test_cache_returns_copy_not_reference(self, warm_engine):
        """Cached results should be copies to prevent external mutation."""
        symbol = "005930"

        result1 = warm_engine.get_indicators(symbol)
        result2 = warm_engine.get_indicators(symbol)  # cache hit

        # Mutate result2
        result2["bb_lower"] = 99999.0

        # result1 should be unchanged
        assert result1["bb_lower"] != 99999.0

        # Next call should return unmodified cached value
        result3 = warm_engine.get_indicators(symbol)
        assert result3["bb_lower"] == result1["bb_lower"]

    def test_cache_miss_result_mutation_does_not_corrupt_cache(self, warm_engine):
        """Mutating the result from a cache miss must not corrupt the cache."""
        symbol = "005930"

        result_miss = warm_engine.get_indicators(symbol)  # cache miss
        original_bb = result_miss["bb_lower"]

        # Mutate the miss result (orchestrator does indicators.update())
        result_miss["bb_lower"] = 99999.0

        # Cache hit should return the original value, not the mutated one
        result_hit = warm_engine.get_indicators(symbol)
        assert result_hit["bb_lower"] == original_bb


class TestCacheClearingBehavior:
    """Test cache clearing on symbol removal."""

    def test_remove_symbol_clears_indicator_cache(self, warm_engine):
        """remove_symbol() should clear the indicator cache entry."""
        symbol = "005930"

        # Populate cache
        warm_engine.get_indicators(symbol)
        stats_before = warm_engine.get_cache_stats()
        assert stats_before["indicator_cache_size"] == 1

        # Remove symbol
        warm_engine.remove_symbol(symbol)
        stats_after = warm_engine.get_cache_stats()

        # Cache should be cleared
        assert stats_after["indicator_cache_size"] == 0

        # Next call should be a cache miss (and fail because symbol was removed)
        result = warm_engine.get_indicators(symbol)
        assert result == {}

    def test_cleanup_orphans_clears_cache(self, warm_engine):
        """cleanup_orphans() should clear cache for removed symbols."""
        symbol1 = "005930"
        symbol2 = "035720"

        # Warm up both symbols
        for minute in range(25):
            ts = datetime(2026, 2, 17, 9, minute, 30)
            warm_engine.on_tick(
                symbol2,
                {
                    "close": 50000.0 + minute * 100,
                    "high": 50050.0 + minute * 100,
                    "low": 49950.0 + minute * 100,
                    "volume": 1000 * (minute + 1),
                },
                ts,
            )

        warm_engine.on_tick(
            symbol2,
            {"close": 52500.0, "high": 52550.0, "low": 52450.0, "volume": 26000},
            datetime(2026, 2, 17, 9, 25, 30),
        )

        # Populate cache for both
        warm_engine.get_indicators(symbol1)
        warm_engine.get_indicators(symbol2)
        stats_before = warm_engine.get_cache_stats()
        assert stats_before["indicator_cache_size"] == 2

        # Cleanup orphans - keep only symbol1
        orphan_count = warm_engine.cleanup_orphans({symbol1})
        stats_after = warm_engine.get_cache_stats()

        assert orphan_count == 1
        assert stats_after["indicator_cache_size"] == 1


class TestMomentumCacheStats:
    """Test caching behavior for get_momentum_indicators()."""

    def test_momentum_cache_hits_tracked(self, warm_engine):
        """Momentum cache hits should be tracked separately."""
        symbol = "005930"

        # Enable multi-timeframe tracking (must set both lists)
        warm_engine._mtf_timeframes = [5]
        warm_engine._numeric_mtf_timeframes = [5]

        # Feed enough 1-min candles to build 5-min candles
        for i in range(50):
            minute = 25 + i
            ts = datetime(2026, 2, 17, 9 + minute // 60, minute % 60, 30)
            warm_engine.on_tick(
                symbol,
                {
                    "close": 72500.0 + i * 10,
                    "high": 72550.0 + i * 10,
                    "low": 72450.0 + i * 10,
                    "volume": 50000 + i * 100,
                },
                ts,
            )

        # First call: cache miss (use min_candles=1 to bypass the candle count guard)
        warm_engine.get_momentum_indicators(symbol, timeframe=5, min_candles=1)
        stats_after_first = warm_engine.get_cache_stats()

        assert stats_after_first["momentum_cache_misses"] == 1
        assert stats_after_first["momentum_cache_hits"] == 0

        # Repeated calls: cache hits
        warm_engine.get_momentum_indicators(symbol, timeframe=5, min_candles=1)
        warm_engine.get_momentum_indicators(symbol, timeframe=5, min_candles=1)
        stats_after_hits = warm_engine.get_cache_stats()

        assert stats_after_hits["momentum_cache_misses"] == 1
        assert stats_after_hits["momentum_cache_hits"] == 2
        assert stats_after_hits["momentum_cache_size"] == 1
        assert stats_after_hits["momentum_hit_rate"] == pytest.approx(66.67, rel=0.1)

    def test_momentum_cache_invalidates_on_new_candle(self, warm_engine):
        """Momentum cache should invalidate when candle count changes."""
        symbol = "005930"
        warm_engine._mtf_timeframes = [5]
        warm_engine._numeric_mtf_timeframes = [5]

        # Build initial 5-min candles
        for i in range(50):
            minute = 25 + i
            ts = datetime(2026, 2, 17, 9 + minute // 60, minute % 60, 30)
            warm_engine.on_tick(
                symbol,
                {
                    "close": 72500.0 + i * 10,
                    "high": 72550.0 + i * 10,
                    "low": 72450.0 + i * 10,
                    "volume": 50000 + i * 100,
                },
                ts,
            )

        # Get momentum indicators and cache hit (use min_candles=1 to bypass guard)
        warm_engine.get_momentum_indicators(symbol, timeframe=5, min_candles=1)
        warm_engine.get_momentum_indicators(symbol, timeframe=5, min_candles=1)  # cache hit
        stats_before = warm_engine.get_cache_stats()

        assert stats_before["momentum_cache_hits"] == 1

        # Add ticks to complete a new 5-min candle (cross into new 5-min bucket)
        for i in range(5):
            ts = datetime(2026, 2, 17, 10, 20 + i, 30)
            warm_engine.on_tick(
                symbol,
                {
                    "close": 73000.0 + i * 10,
                    "high": 73050.0 + i * 10,
                    "low": 72950.0 + i * 10,
                    "volume": 55000 + i * 100,
                },
                ts,
            )

        # Next call should be a cache miss
        warm_engine.get_momentum_indicators(symbol, timeframe=5, min_candles=1)
        stats_after = warm_engine.get_cache_stats()

        assert stats_after["momentum_cache_misses"] == 2
        assert stats_after["momentum_cache_hits"] == 1


class TestCachePerformanceBenefit:
    """Verify caching provides measurable performance benefits."""

    def test_high_hit_rate_for_repeated_queries(self, warm_engine):
        """Simulate realistic hot-path usage with high cache hit rate."""
        symbol = "005930"

        # Simulate 100 repeated queries (typical for entry/exit checks)
        for _ in range(100):
            warm_engine.get_indicators(symbol)

        stats = warm_engine.get_cache_stats()

        # First call is a miss, remaining 99 are hits
        assert stats["indicator_cache_misses"] == 1
        assert stats["indicator_cache_hits"] == 99
        assert stats["indicator_hit_rate"] == pytest.approx(99.0, rel=0.01)

    def test_cache_stats_include_all_counters(self, engine):
        """get_cache_stats() should include all expected fields."""
        stats = engine.get_cache_stats()

        required_fields = {
            "indicator_cache_hits",
            "indicator_cache_misses",
            "momentum_cache_hits",
            "momentum_cache_misses",
            "indicator_cache_size",
            "momentum_cache_size",
            "indicator_hit_rate",
            "momentum_hit_rate",
        }

        assert set(stats.keys()) == required_fields

    def test_multi_symbol_caching(self, engine):
        """Cache should work independently for multiple symbols."""
        symbols = ["005930", "035720", "000660"]

        # Warm up all symbols
        for symbol in symbols:
            for minute in range(25):
                ts = datetime(2026, 2, 17, 9, minute, 30)
                engine.on_tick(
                    symbol,
                    {
                        "close": 70000.0 + minute * 100,
                        "high": 70050.0 + minute * 100,
                        "low": 69950.0 + minute * 100,
                        "volume": 1000 * (minute + 1),
                    },
                    ts,
                )

        # First call for each symbol: 3 misses
        for symbol in symbols:
            engine.get_indicators(symbol)

        stats_after_first = engine.get_cache_stats()
        assert stats_after_first["indicator_cache_misses"] == 3
        assert stats_after_first["indicator_cache_size"] == 3

        # Repeated calls: all hits
        for symbol in symbols:
            engine.get_indicators(symbol)
            engine.get_indicators(symbol)

        stats_after_repeat = engine.get_cache_stats()
        assert stats_after_repeat["indicator_cache_hits"] == 6
        assert stats_after_repeat["indicator_cache_misses"] == 3
        assert stats_after_repeat["indicator_hit_rate"] == pytest.approx(66.67, rel=0.1)


class TestCacheEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_cache_with_insufficient_candles(self, engine):
        """Cache should handle symbols with insufficient candles."""
        symbol = "TEST"

        # Add only 5 candles (less than bb_period=20)
        for minute in range(5):
            ts = datetime(2026, 2, 17, 9, minute, 30)
            engine.on_tick(
                symbol,
                {
                    "close": 100.0 + minute,
                    "high": 101.0 + minute,
                    "low": 99.0 + minute,
                    "volume": 1000 * (minute + 1),
                },
                ts,
            )

        # get_indicators() should return empty dict
        result = engine.get_indicators(symbol)
        assert result == {}

        # Should not increment cache counters for insufficient data
        stats = engine.get_cache_stats()
        assert stats["indicator_cache_size"] == 0

    def test_zero_hit_rate_with_only_misses(self, warm_engine):
        """Hit rate should be 0% when there are only misses."""
        # Force cache invalidation by adding new candles between each call
        symbol = "005930"

        for i in range(5):
            warm_engine.on_tick(
                symbol,
                {
                    "close": 73000.0 + i * 100,
                    "high": 73100.0 + i * 100,
                    "low": 72900.0 + i * 100,
                    "volume": 50000 + i * 1000,
                },
                datetime(2026, 2, 17, 9, 26 + i, 30),
            )
            warm_engine.get_indicators(symbol)  # Each call is a miss due to new candle

        stats = warm_engine.get_cache_stats()
        assert stats["indicator_cache_hits"] == 0
        assert stats["indicator_cache_misses"] == 5
        assert stats["indicator_hit_rate"] == 0.0

    def test_hundred_percent_hit_rate(self, warm_engine):
        """Hit rate should be 100% after warming cache with repeated queries."""
        symbol = "005930"

        # First call to warm cache
        warm_engine.get_indicators(symbol)

        # Clear stats to start fresh
        warm_engine._indicator_cache_hits = 0
        warm_engine._indicator_cache_misses = 0

        # All subsequent calls should be hits
        for _ in range(10):
            warm_engine.get_indicators(symbol)

        stats = warm_engine.get_cache_stats()
        assert stats["indicator_cache_hits"] == 10
        assert stats["indicator_cache_misses"] == 0
        assert stats["indicator_hit_rate"] == 100.0
