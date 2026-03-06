"""Unit tests for RL model helpers cache behavior."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import numpy as np

from shared.strategy import rl_model_helpers


def test_scaled_market_cache_size_is_120():
    """Verify the scaled market cache size is set to 120 entries."""
    assert rl_model_helpers._scaled_market_cache_size == 120


def test_time_feature_cache_size_is_120():
    """Verify the time feature cache size is set to 120 entries."""
    assert rl_model_helpers._time_feature_cache_size == 120


def test_scaled_market_cache_hit_on_duplicate_features():
    """Verify cache hit when same market features are requested twice."""
    # Clear cache before test
    rl_model_helpers._scaled_market_cache.clear()

    # Mock scaler that tracks transform calls
    mock_scaler = MagicMock()
    transform_count = {"count": 0}

    def mock_transform(arr):
        transform_count["count"] += 1
        return arr

    mock_scaler.transform = mock_transform

    # Mock env_config
    mock_env = MagicMock()
    mock_env.market_open = "09:00"
    mock_env.market_close = "15:45"

    market_data = {"close": 100.0}
    indicators = {
        "bb_middle": 100.0,
        "bb_upper": 105.0,
        "bb_lower": 95.0,
        "bb_width": 0.1,
        "rsi": 50.0,
    }
    timestamp = datetime(2026, 3, 6, 10, 0, 0)

    # First call - should miss cache and call scaler.transform
    obs1 = rl_model_helpers.build_rl_observation(
        market_data=market_data,
        indicators=indicators,
        position_side=0.0,
        contracts=0.0,
        unrealized_pnl=0.0,
        timestamp=timestamp,
        scaler=mock_scaler,
        env_config=mock_env,
    )

    assert transform_count["count"] == 1
    assert obs1 is not None

    # Second call with same market features - should hit cache, no scaler call
    obs2 = rl_model_helpers.build_rl_observation(
        market_data=market_data,
        indicators=indicators,
        position_side=0.0,
        contracts=0.0,
        unrealized_pnl=0.0,
        timestamp=timestamp,
        scaler=mock_scaler,
        env_config=mock_env,
    )

    assert transform_count["count"] == 1  # No additional transform call
    assert obs2 is not None
    np.testing.assert_array_equal(obs1, obs2)


def test_scaled_market_cache_eviction_when_full():
    """Verify cache eviction when exceeding 120 entries."""
    # Clear cache before test
    rl_model_helpers._scaled_market_cache.clear()

    mock_scaler = None  # Use raw features for simplicity
    mock_env = MagicMock()
    mock_env.market_open = "09:00"
    mock_env.market_close = "15:45"

    timestamp = datetime(2026, 3, 6, 10, 0, 0)

    # Fill cache with 120 unique entries
    for i in range(120):
        market_data = {"close": 100.0 + i}
        indicators = {"bb_middle": 100.0 + i, "rsi": 50.0 + i}

        rl_model_helpers.build_rl_observation(
            market_data=market_data,
            indicators=indicators,
            position_side=0.0,
            contracts=0.0,
            unrealized_pnl=0.0,
            timestamp=timestamp,
            scaler=mock_scaler,
            env_config=mock_env,
        )

    # Cache should be at max size
    assert len(rl_model_helpers._scaled_market_cache) == 120

    # Add one more entry - should trigger eviction
    market_data = {"close": 9999.0}
    indicators = {"bb_middle": 9999.0, "rsi": 99.0}

    rl_model_helpers.build_rl_observation(
        market_data=market_data,
        indicators=indicators,
        position_side=0.0,
        contracts=0.0,
        unrealized_pnl=0.0,
        timestamp=timestamp,
        scaler=mock_scaler,
        env_config=mock_env,
    )

    # Cache should still be at max size (oldest entry evicted)
    assert len(rl_model_helpers._scaled_market_cache) == 120


def test_time_feature_cache_hit_on_same_minute():
    """Verify time feature cache hit when timestamps are within the same minute."""
    # Clear cache before test
    rl_model_helpers._time_feature_cache.clear()

    mock_scaler = None
    mock_env = MagicMock()
    mock_env.market_open = "09:00"
    mock_env.market_close = "15:45"

    market_data = {"close": 100.0}
    indicators = {"bb_middle": 100.0, "rsi": 50.0}

    # First call at 10:05:15
    timestamp1 = datetime(2026, 3, 6, 10, 5, 15)
    obs1 = rl_model_helpers.build_rl_observation(
        market_data=market_data,
        indicators=indicators,
        position_side=0.0,
        contracts=0.0,
        unrealized_pnl=0.0,
        timestamp=timestamp1,
        scaler=mock_scaler,
        env_config=mock_env,
    )

    # Cache should have 1 entry
    assert len(rl_model_helpers._time_feature_cache) == 1

    # Second call at 10:05:45 (same minute) - should hit cache
    timestamp2 = datetime(2026, 3, 6, 10, 5, 45)
    obs2 = rl_model_helpers.build_rl_observation(
        market_data=market_data,
        indicators=indicators,
        position_side=0.0,
        contracts=0.0,
        unrealized_pnl=0.0,
        timestamp=timestamp2,
        scaler=mock_scaler,
        env_config=mock_env,
    )

    # Cache should still have 1 entry (same minute)
    assert len(rl_model_helpers._time_feature_cache) == 1

    # Observations should be identical (time features are the same)
    np.testing.assert_array_equal(obs1, obs2)


def test_time_feature_cache_miss_on_different_minute():
    """Verify time feature cache miss when timestamps are in different minutes."""
    # Clear cache before test
    rl_model_helpers._time_feature_cache.clear()

    mock_scaler = None
    mock_env = MagicMock()
    mock_env.market_open = "09:00"
    mock_env.market_close = "15:45"

    market_data = {"close": 100.0}
    indicators = {"bb_middle": 100.0, "rsi": 50.0}

    # First call at 10:05:00
    timestamp1 = datetime(2026, 3, 6, 10, 5, 0)
    obs1 = rl_model_helpers.build_rl_observation(
        market_data=market_data,
        indicators=indicators,
        position_side=0.0,
        contracts=0.0,
        unrealized_pnl=0.0,
        timestamp=timestamp1,
        scaler=mock_scaler,
        env_config=mock_env,
    )

    # Cache should have 1 entry
    assert len(rl_model_helpers._time_feature_cache) == 1

    # Second call at 10:06:00 (different minute) - should miss cache
    timestamp2 = datetime(2026, 3, 6, 10, 6, 0)
    obs2 = rl_model_helpers.build_rl_observation(
        market_data=market_data,
        indicators=indicators,
        position_side=0.0,
        contracts=0.0,
        unrealized_pnl=0.0,
        timestamp=timestamp2,
        scaler=mock_scaler,
        env_config=mock_env,
    )

    # Cache should now have 2 entries (different minutes)
    assert len(rl_model_helpers._time_feature_cache) == 2

    # Time features should be different (different progress values)
    assert not np.array_equal(obs1[-3:], obs2[-3:])


def test_time_feature_cache_eviction_when_full():
    """Verify time feature cache eviction when exceeding 120 entries."""
    # Clear cache before test
    rl_model_helpers._time_feature_cache.clear()

    mock_scaler = None
    mock_env = MagicMock()
    mock_env.market_open = "09:00"
    mock_env.market_close = "15:45"

    market_data = {"close": 100.0}
    indicators = {"bb_middle": 100.0, "rsi": 50.0}

    # Fill cache with 120 unique entries (one per minute)
    base_timestamp = datetime(2026, 3, 6, 9, 0, 0)
    for i in range(120):
        # Add i minutes to create unique minute-level timestamps
        timestamp = base_timestamp.replace(
            hour=9 + i // 60, minute=i % 60, second=0, microsecond=0
        )
        rl_model_helpers.build_rl_observation(
            market_data=market_data,
            indicators=indicators,
            position_side=0.0,
            contracts=0.0,
            unrealized_pnl=0.0,
            timestamp=timestamp,
            scaler=mock_scaler,
            env_config=mock_env,
        )

    # Cache should be at max size
    assert len(rl_model_helpers._time_feature_cache) == 120

    # Add one more entry - should trigger eviction
    timestamp_extra = datetime(2026, 3, 6, 11, 1, 0)
    rl_model_helpers.build_rl_observation(
        market_data=market_data,
        indicators=indicators,
        position_side=0.0,
        contracts=0.0,
        unrealized_pnl=0.0,
        timestamp=timestamp_extra,
        scaler=mock_scaler,
        env_config=mock_env,
    )

    # Cache should still be at max size (oldest entry evicted)
    assert len(rl_model_helpers._time_feature_cache) == 120


def test_cache_isolation_between_tests():
    """Verify that cache state doesn't leak between function calls with different data."""
    # This test ensures cache keys are properly computed
    rl_model_helpers._scaled_market_cache.clear()
    rl_model_helpers._time_feature_cache.clear()

    mock_scaler = None
    mock_env = MagicMock()
    mock_env.market_open = "09:00"
    mock_env.market_close = "15:45"

    # Data set 1
    market_data_1 = {"close": 100.0}
    indicators_1 = {"bb_middle": 100.0, "rsi": 50.0}
    timestamp_1 = datetime(2026, 3, 6, 10, 0, 0)

    obs1 = rl_model_helpers.build_rl_observation(
        market_data=market_data_1,
        indicators=indicators_1,
        position_side=0.0,
        contracts=0.0,
        unrealized_pnl=0.0,
        timestamp=timestamp_1,
        scaler=mock_scaler,
        env_config=mock_env,
    )

    # Data set 2 (different market data, same time)
    market_data_2 = {"close": 200.0}
    indicators_2 = {"bb_middle": 200.0, "rsi": 60.0}
    timestamp_2 = datetime(2026, 3, 6, 10, 0, 30)  # Same minute

    obs2 = rl_model_helpers.build_rl_observation(
        market_data=market_data_2,
        indicators=indicators_2,
        position_side=0.0,
        contracts=0.0,
        unrealized_pnl=0.0,
        timestamp=timestamp_2,
        scaler=mock_scaler,
        env_config=mock_env,
    )

    # Market features should be different (different cache keys)
    assert not np.array_equal(obs1[:25], obs2[:25])

    # Time features should be the same (same minute)
    np.testing.assert_array_equal(obs1[-3:], obs2[-3:])

    # Should have 2 market cache entries and 1 time cache entry
    assert len(rl_model_helpers._scaled_market_cache) == 2
    assert len(rl_model_helpers._time_feature_cache) == 1


def test_build_observation_with_scaler_error_fallback():
    """Verify graceful fallback when scaler.transform() raises an exception."""
    # Clear cache before test
    rl_model_helpers._scaled_market_cache.clear()

    # Mock scaler that raises an exception
    mock_scaler = MagicMock()
    mock_scaler.transform.side_effect = ValueError("Scaler error")

    mock_env = MagicMock()
    mock_env.market_open = "09:00"
    mock_env.market_close = "15:45"

    market_data = {"close": 100.0}
    indicators = {"bb_middle": 100.0, "rsi": 50.0}
    timestamp = datetime(2026, 3, 6, 10, 0, 0)

    # Should not raise - should fall back to raw features
    obs = rl_model_helpers.build_rl_observation(
        market_data=market_data,
        indicators=indicators,
        position_side=0.0,
        contracts=0.0,
        unrealized_pnl=0.0,
        timestamp=timestamp,
        scaler=mock_scaler,
        env_config=mock_env,
    )

    assert obs is not None
    assert obs.shape == (31,)


def test_cache_key_collision_resistance():
    """Verify that similar but different feature sets don't collide in cache."""
    rl_model_helpers._scaled_market_cache.clear()

    mock_scaler = None
    mock_env = MagicMock()
    mock_env.market_open = "09:00"
    mock_env.market_close = "15:45"
    timestamp = datetime(2026, 3, 6, 10, 0, 0)

    # Create two feature sets that should hash differently
    # Use actual RL_FEATURE_COLUMNS names so the features differ in the obs vector
    market_data_1 = {"close": 100.0}
    indicators_1 = {"returns": 0.01, "rsi": 50.0}

    market_data_2 = {"close": 100.0}
    indicators_2 = {"returns": 0.05, "rsi": 60.0}  # Different RL feature values

    obs1 = rl_model_helpers.build_rl_observation(
        market_data=market_data_1,
        indicators=indicators_1,
        position_side=0.0,
        contracts=0.0,
        unrealized_pnl=0.0,
        timestamp=timestamp,
        scaler=mock_scaler,
        env_config=mock_env,
    )

    obs2 = rl_model_helpers.build_rl_observation(
        market_data=market_data_2,
        indicators=indicators_2,
        position_side=0.0,
        contracts=0.0,
        unrealized_pnl=0.0,
        timestamp=timestamp,
        scaler=mock_scaler,
        env_config=mock_env,
    )

    # Should have 2 cache entries (different features)
    assert len(rl_model_helpers._scaled_market_cache) == 2

    # Market features should be different
    assert not np.array_equal(obs1[:25], obs2[:25])
