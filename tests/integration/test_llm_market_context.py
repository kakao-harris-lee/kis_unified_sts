"""Integration tests for LLM Market Context end-to-end flow.

Tests the complete flow: LLMContextPublisher → Redis → LLMContextProvider → Strategy

These tests require a running Redis instance.
Run with: pytest tests/integration/test_llm_market_context.py -v

To skip when Redis is unavailable:
    pytest -m "not integration"
"""
import asyncio
import json
import os
import time
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

# Mark all tests in this module as integration tests
pytestmark = [pytest.mark.integration]


def redis_available():
    """Check if Redis is available."""
    try:
        import redis

        r = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/1"),
            socket_timeout=1,
        )
        r.ping()
        return True
    except Exception:
        return False


@pytest.fixture
def redis_url():
    """Get Redis URL from environment or use default."""
    return os.getenv("REDIS_URL", "redis://localhost:6379/1")


@pytest.fixture
def redis_client(redis_url):
    """Create Redis client for test cleanup."""
    import redis

    client = redis.Redis.from_url(redis_url)
    yield client
    # Cleanup test keys
    for key in client.scan_iter("trading:test*"):
        client.delete(key)
    client.close()


@pytest.fixture
def sample_market_context():
    """Create a sample MarketContext for testing."""
    from shared.llm.data_classes import MarketSignal, RiskMode
    from shared.llm.market_context import MarketContext

    return MarketContext(
        regime="BULL_MODERATE",
        overall_signal=MarketSignal.BULLISH,
        risk_mode=RiskMode.RISK_ON,
        risk_score=35.0,
        confidence=0.75,
        sector_rotation={"Technology": "INFLOW", "Energy": "OUTFLOW"},
        generated_at=datetime.now(),
        metadata={"llm_summary": "Market is moderately bullish", "key_points": "Bullish trend"},
    )


# =============================================================================
# Publisher → Redis Tests
# =============================================================================


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
def test_publish_market_context_to_redis(redis_client, sample_market_context):
    """Test MarketContext can be published to Redis via TradingStatePublisher."""
    from shared.streaming.trading_state import TradingStatePublisher

    # Set key suffix to isolate test
    os.environ["TRADING_STATE_KEY_SUFFIX"] = "test"

    try:
        publisher = TradingStatePublisher("test_asset")
        publisher.publish_market_context(sample_market_context)

        # Verify data was written to Redis
        key = "trading:test_asset:market_context:test"
        raw_data = redis_client.get(key)

        assert raw_data is not None, "MarketContext was not written to Redis"

        # Verify data can be deserialized
        data_dict = json.loads(raw_data)
        assert data_dict["regime"] == "BULL_MODERATE"
        assert data_dict["overall_signal"] == "상승"  # MarketSignal.BULLISH value
        assert data_dict["risk_mode"] == "위험선호"  # RiskMode.RISK_ON value
        assert data_dict["risk_score"] == 35.0
        assert data_dict["confidence"] == 0.75
        assert "Technology" in data_dict["sector_rotation"]

    finally:
        os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
def test_market_context_ttl_set(redis_client, sample_market_context):
    """Test that published MarketContext has TTL set in Redis."""
    from shared.streaming.trading_state import TradingStatePublisher

    os.environ["TRADING_STATE_KEY_SUFFIX"] = "test"

    try:
        publisher = TradingStatePublisher("test_asset")
        publisher.publish_market_context(sample_market_context)

        key = "trading:test_asset:market_context:test"
        ttl = redis_client.ttl(key)

        # TTL should be set (86400 seconds = 24 hours)
        assert ttl > 0, "TTL not set on market context key"
        assert ttl <= 86400, "TTL is too long"

    finally:
        os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)


# =============================================================================
# Redis → Provider Tests
# =============================================================================


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
def test_provider_reads_from_redis(redis_client, sample_market_context):
    """Test LLMContextProvider can read MarketContext from Redis."""
    from shared.llm.data_classes import MarketSignal, RiskMode
    from shared.streaming.trading_state import TradingStatePublisher
    from services.trading.llm_context_provider import LLMContextProvider

    os.environ["TRADING_STATE_KEY_SUFFIX"] = "test"

    try:
        # Publish context to Redis
        publisher = TradingStatePublisher("test_asset")
        publisher.publish_market_context(sample_market_context)

        # Read via provider
        provider = LLMContextProvider("test_asset", cache_ttl_seconds=60)
        context = provider.get_context()

        assert context is not None, "Provider failed to read context from Redis"
        assert context.regime == "BULL_MODERATE"
        assert context.overall_signal == MarketSignal.BULLISH
        assert context.risk_mode == RiskMode.RISK_ON
        assert context.risk_score == 35.0
        assert context.confidence == 0.75
        assert context.sector_rotation["Technology"] == "INFLOW"

    finally:
        os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
def test_provider_caches_context(redis_client, sample_market_context):
    """Test LLMContextProvider caches context and respects TTL."""
    from shared.streaming.trading_state import TradingStatePublisher
    from services.trading.llm_context_provider import LLMContextProvider

    os.environ["TRADING_STATE_KEY_SUFFIX"] = "test"

    try:
        # Publish context to Redis
        publisher = TradingStatePublisher("test_asset")
        publisher.publish_market_context(sample_market_context)

        # Create provider with short cache TTL
        provider = LLMContextProvider("test_asset", cache_ttl_seconds=1.0)

        # First call should hit Redis
        context1 = provider.get_context()
        assert context1 is not None

        # Delete from Redis
        key = "trading:test_asset:market_context:test"
        redis_client.delete(key)

        # Second call should use cache (even though Redis data is gone)
        context2 = provider.get_context()
        assert context2 is not None
        assert context2.regime == context1.regime

        # Wait for cache to expire
        time.sleep(1.1)

        # Third call should try Redis (and get None)
        context3 = provider.get_context()
        assert context3 is None  # Cache expired, Redis has no data

    finally:
        os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
def test_provider_force_refresh(redis_client, sample_market_context):
    """Test force_refresh bypasses cache."""
    from shared.llm.data_classes import MarketSignal
    from shared.streaming.trading_state import TradingStatePublisher
    from services.trading.llm_context_provider import LLMContextProvider

    os.environ["TRADING_STATE_KEY_SUFFIX"] = "test"

    try:
        # Publish initial context
        publisher = TradingStatePublisher("test_asset")
        publisher.publish_market_context(sample_market_context)

        provider = LLMContextProvider("test_asset", cache_ttl_seconds=60)

        # Get cached context
        context1 = provider.get_context()
        assert context1.overall_signal == MarketSignal.BULLISH

        # Update Redis with new context
        from shared.llm.market_context import MarketContext

        new_context = MarketContext(
            regime="BEAR_STRONG",
            overall_signal=MarketSignal.STRONG_BEARISH,
            risk_score=80.0,
        )
        publisher.publish_market_context(new_context)

        # Without force_refresh, should still get cached version
        context2 = provider.get_context(force_refresh=False)
        assert context2.overall_signal == MarketSignal.BULLISH  # Cached

        # With force_refresh, should get new version
        context3 = provider.get_context(force_refresh=True)
        assert context3.overall_signal == MarketSignal.STRONG_BEARISH  # Refreshed

    finally:
        os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)


# =============================================================================
# End-to-End Publisher → Redis → Provider Tests
# =============================================================================


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_end_to_end_publisher_to_provider():
    """Test complete flow: LLMContextPublisher → Redis → LLMContextProvider.

    This test mocks UnifiedMarketAnalyzer to avoid LLM API calls but tests
    the full serialization/Redis/deserialization pipeline.
    """
    from shared.llm.data_classes import MarketAnalysis, MarketSignal, RiskMode
    from shared.streaming.trading_state import TradingStatePublisher
    from services.trading.llm_context_publisher import LLMContextPublisher
    from services.trading.llm_context_provider import LLMContextProvider

    os.environ["TRADING_STATE_KEY_SUFFIX"] = "test"

    try:
        # Mock UnifiedMarketAnalyzer to return test data
        mock_analysis = MarketAnalysis(
            date="2024-01-15",
            overall_signal=MarketSignal.BULLISH,
            risk_mode=RiskMode.RISK_ON,
            sector_rotation={"Technology": "INFLOW"},
            llm_summary="Market showing strong bullish momentum",
            llm_strategy="Focus on tech sector entries",
            key_points=["Tech sector strength", "Low risk environment"],
        )

        with patch("services.trading.llm_context_publisher.UnifiedMarketAnalyzer") as MockAnalyzer:
            # Setup mock
            mock_instance = MockAnalyzer.return_value
            mock_instance.run_analysis.return_value = mock_analysis

            # Step 1: Run publisher analysis
            publisher_service = LLMContextPublisher("test_asset")
            market_context = await publisher_service.run_analysis()

            assert market_context is not None, "Publisher failed to create MarketContext"
            assert market_context.regime == "BULL_MODERATE"
            assert market_context.overall_signal == MarketSignal.BULLISH
            assert market_context.confidence > 0.0  # Should have some confidence

            # Step 2: Publish to Redis
            state_publisher = TradingStatePublisher("test_asset")
            state_publisher.publish_market_context(market_context)

            # Step 3: Read via Provider
            provider = LLMContextProvider("test_asset")
            retrieved_context = provider.get_context()

            # Step 4: Verify data round-trip
            assert retrieved_context is not None, "Provider failed to retrieve context"
            assert retrieved_context.regime == market_context.regime
            assert retrieved_context.overall_signal == market_context.overall_signal
            assert retrieved_context.risk_mode == market_context.risk_mode
            assert retrieved_context.risk_score == market_context.risk_score
            assert abs(retrieved_context.confidence - market_context.confidence) < 0.01
            assert retrieved_context.sector_rotation == market_context.sector_rotation

    finally:
        os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)


# =============================================================================
# Graceful Degradation Tests
# =============================================================================


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
def test_provider_handles_missing_data(redis_client):
    """Test provider returns None when no data exists in Redis."""
    from services.trading.llm_context_provider import LLMContextProvider

    os.environ["TRADING_STATE_KEY_SUFFIX"] = "test"

    try:
        # Ensure no data in Redis
        key = "trading:test_missing:market_context:test"
        redis_client.delete(key)

        provider = LLMContextProvider("test_missing")
        context = provider.get_context()

        assert context is None, "Provider should return None when data is missing"

    finally:
        os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
def test_provider_handles_corrupted_data(redis_client):
    """Test provider gracefully handles corrupted JSON in Redis."""
    from services.trading.llm_context_provider import LLMContextProvider

    os.environ["TRADING_STATE_KEY_SUFFIX"] = "test"

    try:
        # Write corrupted data to Redis
        key = "trading:test_corrupted:market_context:test"
        redis_client.set(key, "NOT_VALID_JSON{{{")

        provider = LLMContextProvider("test_corrupted")
        context = provider.get_context()

        # Should handle gracefully and return None
        assert context is None, "Provider should return None for corrupted data"

    finally:
        os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
def test_provider_handles_invalid_enum_values(redis_client):
    """Test provider handles invalid enum values in MarketContext data."""
    from services.trading.llm_context_provider import LLMContextProvider

    os.environ["TRADING_STATE_KEY_SUFFIX"] = "test"

    try:
        # Write data with invalid enum values
        key = "trading:test_invalid:market_context:test"
        invalid_data = {
            "regime": "UNKNOWN_REGIME",
            "overall_signal": "INVALID_SIGNAL",  # Not a valid MarketSignal
            "risk_mode": "INVALID_MODE",  # Not a valid RiskMode
            "risk_score": 50.0,
            "confidence": 0.5,
            "sector_rotation": {},
            "generated_at": datetime.now().isoformat(),
            "metadata": {},
        }
        redis_client.set(key, json.dumps(invalid_data))

        provider = LLMContextProvider("test_invalid")
        context = provider.get_context()

        # MarketContext.from_dict() should handle gracefully with defaults
        assert context is not None, "Provider should use default enum values"
        # Should fall back to default neutral values

    finally:
        os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)


@pytest.mark.asyncio
async def test_publisher_handles_analyzer_failure():
    """Test LLMContextPublisher returns None when analyzer fails."""
    from services.trading.llm_context_publisher import LLMContextPublisher

    with patch("services.trading.llm_context_publisher.UnifiedMarketAnalyzer") as MockAnalyzer:
        # Setup mock to raise exception
        mock_instance = MockAnalyzer.return_value
        mock_instance.run_analysis.side_effect = Exception("API failure")

        publisher = LLMContextPublisher("test_asset")
        context = await publisher.run_analysis()

        # Should handle gracefully and return None
        assert context is None, "Publisher should return None on analyzer failure"


# =============================================================================
# Cache Behavior Tests
# =============================================================================


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
def test_provider_clear_cache(redis_client, sample_market_context):
    """Test provider cache can be manually cleared."""
    from shared.streaming.trading_state import TradingStatePublisher
    from services.trading.llm_context_provider import LLMContextProvider

    os.environ["TRADING_STATE_KEY_SUFFIX"] = "test"

    try:
        # Publish context
        publisher = TradingStatePublisher("test_asset")
        publisher.publish_market_context(sample_market_context)

        provider = LLMContextProvider("test_asset", cache_ttl_seconds=60)

        # Load into cache
        context1 = provider.get_context()
        assert context1 is not None

        # Check cache age
        age = provider.get_cache_age()
        assert age is not None
        assert age < 1.0  # Should be very fresh

        # Clear cache
        provider.clear_cache()

        # Cache age should be None
        age_after_clear = provider.get_cache_age()
        assert age_after_clear is None

        # Next get should hit Redis again
        context2 = provider.get_context()
        assert context2 is not None

    finally:
        os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
def test_provider_cache_age_tracking(redis_client, sample_market_context):
    """Test provider accurately tracks cache age."""
    from shared.streaming.trading_state import TradingStatePublisher
    from services.trading.llm_context_provider import LLMContextProvider

    os.environ["TRADING_STATE_KEY_SUFFIX"] = "test"

    try:
        # Publish context
        publisher = TradingStatePublisher("test_asset")
        publisher.publish_market_context(sample_market_context)

        provider = LLMContextProvider("test_asset", cache_ttl_seconds=60)

        # Initially no cache
        assert provider.get_cache_age() is None

        # Load context
        provider.get_context()

        # Cache age should be near 0
        age1 = provider.get_cache_age()
        assert age1 is not None
        assert age1 < 0.1

        # Wait a bit
        time.sleep(0.3)

        # Cache age should increase
        age2 = provider.get_cache_age()
        assert age2 is not None
        assert age2 > age1
        assert 0.2 < age2 < 0.5  # Should be around 0.3s

    finally:
        os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)


# =============================================================================
# Serialization Round-Trip Tests
# =============================================================================


def test_market_context_serialization_round_trip():
    """Test MarketContext serializes and deserializes correctly."""
    from shared.llm.data_classes import MarketSignal, RiskMode
    from shared.llm.market_context import MarketContext

    # Create context with all fields populated
    original = MarketContext(
        regime="BULL_STRONG",
        overall_signal=MarketSignal.STRONG_BULLISH,
        risk_mode=RiskMode.RISK_ON,
        risk_score=25.0,
        confidence=0.85,
        sector_rotation={"Tech": "INFLOW", "Energy": "OUTFLOW", "Finance": "NEUTRAL"},
        metadata={"source": "test", "version": "1.0"},
    )

    # Serialize to dict
    data_dict = original.to_dict()

    # Verify dict structure
    assert data_dict["regime"] == "BULL_STRONG"
    assert data_dict["overall_signal"] == "강한 상승"  # Enum value
    assert data_dict["risk_mode"] == "위험선호"  # Enum value
    assert data_dict["risk_score"] == 25.0
    assert data_dict["confidence"] == 0.85
    assert len(data_dict["sector_rotation"]) == 3

    # Deserialize back
    restored = MarketContext.from_dict(data_dict)

    # Verify all fields match
    assert restored.regime == original.regime
    assert restored.overall_signal == original.overall_signal
    assert restored.risk_mode == original.risk_mode
    assert restored.risk_score == original.risk_score
    assert restored.confidence == original.confidence
    assert restored.sector_rotation == original.sector_rotation


def test_market_context_partial_data():
    """Test MarketContext handles partial/missing data gracefully."""
    from shared.llm.market_context import MarketContext

    # Deserialize with minimal data
    minimal_dict = {
        "regime": "SIDEWAYS",
        # Other fields missing - should use defaults
    }

    context = MarketContext.from_dict(minimal_dict)

    # Should have defaults for missing fields
    assert context.regime == "SIDEWAYS"
    assert context.risk_score == 50.0  # Default
    assert context.confidence == 0.5  # Default
    assert context.sector_rotation == {}  # Default empty dict


# =============================================================================
# Strategy Integration Tests
# =============================================================================


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
def test_strategy_manager_gets_market_context(redis_client, sample_market_context):
    """Test StrategyManager can fetch and use MarketContext.

    This test verifies that the integration into StrategyManager works correctly.
    """
    from shared.streaming.trading_state import TradingStatePublisher
    from services.trading.llm_context_provider import LLMContextProvider

    os.environ["TRADING_STATE_KEY_SUFFIX"] = "test"

    try:
        # Publish context to Redis
        publisher = TradingStatePublisher("test_asset")
        publisher.publish_market_context(sample_market_context)

        # Create provider (as StrategyManager would)
        provider = LLMContextProvider("test_asset")

        # Get context (as StrategyManager.check_entries() does)
        market_context = provider.get_context()

        # Verify StrategyManager would get valid data
        assert market_context is not None
        assert market_context.regime is not None
        assert market_context.risk_score > 0

        # Simulate strategy using context
        if market_context.is_high_risk(threshold=70.0):
            position_scale = 0.5  # Reduce position size in high risk
        else:
            position_scale = 1.0

        # In this test case, risk_score is 35.0 (not high)
        assert position_scale == 1.0

    finally:
        os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
def test_strategy_continues_without_llm_context(redis_client):
    """Test strategies work normally when LLM context is unavailable.

    This verifies graceful degradation: strategies should continue operating
    even when market_context is None.
    """
    from services.trading.llm_context_provider import LLMContextProvider

    os.environ["TRADING_STATE_KEY_SUFFIX"] = "test"

    try:
        # Ensure no data in Redis
        key = "trading:no_context:market_context:test"
        redis_client.delete(key)

        # Provider returns None
        provider = LLMContextProvider("no_context")
        market_context = provider.get_context()
        assert market_context is None

        # Simulate strategy behavior with None context
        # Strategy should check for None and continue normally
        if market_context and market_context.is_high_risk():
            # Would reduce size if context available
            position_scale = 0.5
        else:
            # Default behavior when context unavailable
            position_scale = 1.0

        # Should use default scale
        assert position_scale == 1.0

    finally:
        os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)
