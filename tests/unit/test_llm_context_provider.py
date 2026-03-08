"""Unit tests for services/trading/llm_context_provider.py

Tests cache behavior, TTL expiration, Redis integration, and graceful
degradation of LLMContextProvider.
"""

from __future__ import annotations

import time
from datetime import datetime
from threading import Thread
from unittest.mock import MagicMock, Mock, patch

import pytest

from services.trading.llm_context_provider import (
    DEFAULT_CACHE_TTL_SECONDS,
    LLMContextProvider,
)
from shared.llm.data_classes import MarketSignal, RiskMode
from shared.llm.market_context import MarketContext


# =============================================================================
# Helpers
# =============================================================================


def _make_market_context(
    regime: str = "BULL_STRONG",
    risk_score: float = 30.0,
    confidence: float = 0.8,
) -> MarketContext:
    """Create a sample MarketContext for testing."""
    return MarketContext(
        regime=regime,
        overall_signal=MarketSignal.BULLISH,
        risk_mode=RiskMode.RISK_ON,
        risk_score=risk_score,
        confidence=confidence,
        sector_rotation={"Technology": "INFLOW", "Energy": "OUTFLOW"},
        generated_at=datetime(2026, 3, 8, 10, 30, 0),
        metadata={"source": "llm_analysis"},
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestLLMContextProviderInit:
    """Test LLMContextProvider initialization."""

    def test_init_with_defaults(self):
        """Provider initializes with default cache TTL."""
        provider = LLMContextProvider("stock")
        assert provider._asset_class == "stock"
        assert provider._cache_ttl_seconds == DEFAULT_CACHE_TTL_SECONDS
        assert provider._cached_context is None
        assert provider._cache_timestamp == 0.0
        assert provider._reader is None

    def test_init_with_custom_ttl(self):
        """Provider accepts custom cache TTL."""
        provider = LLMContextProvider("futures", cache_ttl_seconds=120.0)
        assert provider._asset_class == "futures"
        assert provider._cache_ttl_seconds == 120.0

    def test_init_different_asset_classes(self):
        """Provider can be initialized for different asset classes."""
        stock_provider = LLMContextProvider("stock")
        futures_provider = LLMContextProvider("futures")
        assert stock_provider._asset_class == "stock"
        assert futures_provider._asset_class == "futures"


# =============================================================================
# Cache Behavior Tests
# =============================================================================


class TestLLMContextProviderCache:
    """Test cache hit/miss/staleness logic."""

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_cache_miss_on_first_call(self, mock_reader_cls):
        """First get_context() call reads from Redis (cache miss)."""
        mock_context = _make_market_context()
        mock_reader = Mock()
        mock_reader.get_market_context.return_value = mock_context
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock")
        result = provider.get_context()

        assert result == mock_context
        mock_reader.get_market_context.assert_called_once()

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_cache_hit_on_second_call(self, mock_reader_cls):
        """Second get_context() within TTL returns cached value (no Redis call)."""
        mock_context = _make_market_context()
        mock_reader = Mock()
        mock_reader.get_market_context.return_value = mock_context
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock", cache_ttl_seconds=60.0)

        # First call: cache miss → Redis read
        result1 = provider.get_context()
        assert result1 == mock_context
        assert mock_reader.get_market_context.call_count == 1

        # Second call: cache hit → no Redis read
        result2 = provider.get_context()
        assert result2 == mock_context
        assert mock_reader.get_market_context.call_count == 1  # Still 1, not 2

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_cache_miss_after_ttl_expiration(self, mock_reader_cls):
        """get_context() after TTL expiry refreshes from Redis."""
        mock_context1 = _make_market_context(regime="BULL_STRONG")
        mock_context2 = _make_market_context(regime="BEAR_MODERATE")
        mock_reader = Mock()
        mock_reader.get_market_context.side_effect = [mock_context1, mock_context2]
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock", cache_ttl_seconds=0.1)  # 100ms TTL

        # First call: cache miss
        result1 = provider.get_context()
        assert result1 == mock_context1
        assert result1.regime == "BULL_STRONG"

        # Wait for TTL to expire
        time.sleep(0.15)

        # Second call: cache expired → refresh from Redis
        result2 = provider.get_context()
        assert result2 == mock_context2
        assert result2.regime == "BEAR_MODERATE"
        assert mock_reader.get_market_context.call_count == 2

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_force_refresh_bypasses_cache(self, mock_reader_cls):
        """force_refresh=True bypasses cache even if fresh."""
        mock_context1 = _make_market_context(regime="BULL_STRONG")
        mock_context2 = _make_market_context(regime="SIDEWAYS")
        mock_reader = Mock()
        mock_reader.get_market_context.side_effect = [mock_context1, mock_context2]
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock", cache_ttl_seconds=60.0)

        # First call: cache miss
        result1 = provider.get_context()
        assert result1.regime == "BULL_STRONG"

        # Second call with force_refresh: bypasses cache
        result2 = provider.get_context(force_refresh=True)
        assert result2.regime == "SIDEWAYS"
        assert mock_reader.get_market_context.call_count == 2

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_cache_updates_timestamp_on_refresh(self, mock_reader_cls):
        """Cache timestamp is updated after refresh."""
        mock_context = _make_market_context()
        mock_reader = Mock()
        mock_reader.get_market_context.return_value = mock_context
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock")
        assert provider._cache_timestamp == 0.0

        provider.get_context()
        first_timestamp = provider._cache_timestamp
        assert first_timestamp > 0.0

        time.sleep(0.05)
        provider.get_context(force_refresh=True)
        second_timestamp = provider._cache_timestamp
        assert second_timestamp > first_timestamp


# =============================================================================
# Graceful Degradation Tests
# =============================================================================


class TestLLMContextProviderGracefulDegradation:
    """Test graceful handling of Redis failures and missing data."""

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_redis_failure_returns_none(self, mock_reader_cls):
        """Redis connection error returns None instead of raising."""
        mock_reader = Mock()
        mock_reader.get_market_context.side_effect = ConnectionError("Redis down")
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock")
        result = provider.get_context()

        assert result is None
        mock_reader.get_market_context.assert_called_once()

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_redis_returns_none(self, mock_reader_cls):
        """Redis returns None (no data) → provider returns None."""
        mock_reader = Mock()
        mock_reader.get_market_context.return_value = None
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock")
        result = provider.get_context()

        assert result is None

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_redis_exception_returns_none(self, mock_reader_cls):
        """Any exception during Redis read returns None gracefully."""
        mock_reader = Mock()
        mock_reader.get_market_context.side_effect = ValueError("Invalid data")
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock")
        result = provider.get_context()

        assert result is None

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_cached_none_is_not_reused(self, mock_reader_cls):
        """Cached None is treated as stale → retries Redis on next call."""
        mock_context = _make_market_context()
        mock_reader = Mock()
        # First call: Redis returns None, second call: Redis returns context
        mock_reader.get_market_context.side_effect = [None, mock_context]
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock", cache_ttl_seconds=60.0)

        # First call: Redis returns None
        result1 = provider.get_context()
        assert result1 is None

        # Second call: should retry Redis (cached None is stale)
        result2 = provider.get_context()
        assert result2 == mock_context
        assert mock_reader.get_market_context.call_count == 2


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestLLMContextProviderHelpers:
    """Test helper methods: clear_cache, get_cache_age."""

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_clear_cache(self, mock_reader_cls):
        """clear_cache() resets cached context and timestamp."""
        mock_context = _make_market_context()
        mock_reader = Mock()
        mock_reader.get_market_context.return_value = mock_context
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock")
        provider.get_context()

        assert provider._cached_context is not None
        assert provider._cache_timestamp > 0.0

        provider.clear_cache()

        assert provider._cached_context is None
        assert provider._cache_timestamp == 0.0

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_clear_cache_forces_refresh(self, mock_reader_cls):
        """After clear_cache(), next get_context() reads from Redis."""
        mock_context1 = _make_market_context(regime="BULL_STRONG")
        mock_context2 = _make_market_context(regime="SIDEWAYS")
        mock_reader = Mock()
        mock_reader.get_market_context.side_effect = [mock_context1, mock_context2]
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock", cache_ttl_seconds=60.0)

        # First call: cache miss
        result1 = provider.get_context()
        assert result1.regime == "BULL_STRONG"

        # Clear cache
        provider.clear_cache()

        # Next call: cache miss again → reads from Redis
        result2 = provider.get_context()
        assert result2.regime == "SIDEWAYS"
        assert mock_reader.get_market_context.call_count == 2

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_get_cache_age_empty_cache(self, mock_reader_cls):
        """get_cache_age() returns None when cache is empty."""
        provider = LLMContextProvider("stock")
        assert provider.get_cache_age() is None

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_get_cache_age_returns_elapsed_time(self, mock_reader_cls):
        """get_cache_age() returns elapsed seconds since cache was populated."""
        mock_context = _make_market_context()
        mock_reader = Mock()
        mock_reader.get_market_context.return_value = mock_context
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock")
        provider.get_context()

        time.sleep(0.1)
        age = provider.get_cache_age()

        assert age is not None
        assert 0.1 <= age <= 0.2  # Should be ~100ms

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_get_cache_age_after_clear(self, mock_reader_cls):
        """get_cache_age() returns None after clear_cache()."""
        mock_context = _make_market_context()
        mock_reader = Mock()
        mock_reader.get_market_context.return_value = mock_context
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock")
        provider.get_context()

        assert provider.get_cache_age() is not None

        provider.clear_cache()
        assert provider.get_cache_age() is None


# =============================================================================
# Thread Safety Tests
# =============================================================================


class TestLLMContextProviderThreadSafety:
    """Test thread-safe cache access."""

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_concurrent_access_does_not_corrupt_cache(self, mock_reader_cls):
        """Multiple threads accessing get_context() don't corrupt cache."""
        mock_context = _make_market_context()
        mock_reader = Mock()
        mock_reader.get_market_context.return_value = mock_context
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock", cache_ttl_seconds=1.0)
        results = []

        def worker():
            result = provider.get_context()
            results.append(result)

        # Launch 10 concurrent threads
        threads = [Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should get the same context
        assert len(results) == 10
        assert all(r == mock_context for r in results)
        # Due to locking, only one thread should read from Redis
        # (others should use cache or wait)
        assert mock_reader.get_market_context.call_count >= 1

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_concurrent_clear_and_get(self, mock_reader_cls):
        """Concurrent clear_cache() and get_context() don't deadlock."""
        mock_context = _make_market_context()
        mock_reader = Mock()
        mock_reader.get_market_context.return_value = mock_context
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock", cache_ttl_seconds=1.0)

        def getter():
            for _ in range(5):
                provider.get_context()
                time.sleep(0.01)

        def clearer():
            for _ in range(5):
                provider.clear_cache()
                time.sleep(0.01)

        threads = [Thread(target=getter), Thread(target=clearer)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Test passes if no deadlock or exception occurs
        assert True


# =============================================================================
# Integration-Style Tests
# =============================================================================


class TestLLMContextProviderIntegration:
    """Integration-style tests with realistic scenarios."""

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_typical_usage_pattern(self, mock_reader_cls):
        """Simulate typical usage: periodic reads with occasional force refresh."""
        contexts = [
            _make_market_context(regime="BULL_STRONG", risk_score=30.0),
            _make_market_context(regime="SIDEWAYS", risk_score=50.0),
            _make_market_context(regime="BEAR_MODERATE", risk_score=70.0),
        ]
        mock_reader = Mock()
        mock_reader.get_market_context.side_effect = contexts
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock", cache_ttl_seconds=0.2)

        # First read: cache miss
        ctx1 = provider.get_context()
        assert ctx1.regime == "BULL_STRONG"

        # Second read within TTL: cache hit
        ctx2 = provider.get_context()
        assert ctx2.regime == "BULL_STRONG"
        assert mock_reader.get_market_context.call_count == 1

        # Wait for TTL to expire
        time.sleep(0.25)

        # Third read: cache expired → refresh
        ctx3 = provider.get_context()
        assert ctx3.regime == "SIDEWAYS"
        assert mock_reader.get_market_context.call_count == 2

        # Force refresh
        ctx4 = provider.get_context(force_refresh=True)
        assert ctx4.regime == "BEAR_MODERATE"
        assert mock_reader.get_market_context.call_count == 3

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_recovery_after_redis_failure(self, mock_reader_cls):
        """Provider recovers after Redis failure."""
        mock_context = _make_market_context()
        mock_reader = Mock()
        # First call: Redis fails, second call: Redis succeeds
        mock_reader.get_market_context.side_effect = [
            ConnectionError("Redis down"),
            mock_context,
        ]
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock")

        # First call: Redis failure → returns None
        result1 = provider.get_context()
        assert result1 is None

        # Second call: Redis recovered → returns context
        result2 = provider.get_context()
        assert result2 == mock_context
        assert result2.regime == "BULL_STRONG"

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_lazy_reader_initialization(self, mock_reader_cls):
        """TradingStateReader is lazily initialized on first use."""
        provider = LLMContextProvider("stock")
        assert provider._reader is None

        mock_reader = Mock()
        mock_reader.get_market_context.return_value = None
        mock_reader_cls.return_value = mock_reader

        provider.get_context()

        # Reader should now be initialized
        assert provider._reader is not None
        mock_reader_cls.assert_called_once_with("stock")


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestLLMContextProviderEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_zero_ttl_always_refreshes(self, mock_reader_cls):
        """TTL=0 means cache is always stale → always refresh."""
        contexts = [
            _make_market_context(regime="BULL"),
            _make_market_context(regime="BEAR"),
            _make_market_context(regime="SIDEWAYS"),
        ]
        mock_reader = Mock()
        mock_reader.get_market_context.side_effect = contexts
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock", cache_ttl_seconds=0.0)

        ctx1 = provider.get_context()
        ctx2 = provider.get_context()
        ctx3 = provider.get_context()

        assert ctx1.regime == "BULL"
        assert ctx2.regime == "BEAR"
        assert ctx3.regime == "SIDEWAYS"
        assert mock_reader.get_market_context.call_count == 3

    @patch("services.trading.llm_context_provider.TradingStateReader")
    def test_very_long_ttl_caches_indefinitely(self, mock_reader_cls):
        """Very long TTL means cache is effectively permanent."""
        mock_context = _make_market_context()
        mock_reader = Mock()
        mock_reader.get_market_context.return_value = mock_context
        mock_reader_cls.return_value = mock_reader

        provider = LLMContextProvider("stock", cache_ttl_seconds=86400.0)  # 1 day

        # Multiple reads should all use cache
        for _ in range(5):
            result = provider.get_context()
            assert result == mock_context

        assert mock_reader.get_market_context.call_count == 1

    def test_negative_ttl_raises_no_error(self):
        """Negative TTL doesn't raise error (treated as always stale)."""
        # Should not raise during initialization
        provider = LLMContextProvider("stock", cache_ttl_seconds=-1.0)
        assert provider._cache_ttl_seconds == -1.0
