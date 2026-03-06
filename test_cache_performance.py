#!/usr/bin/env python3
"""TEMPORARY: Verify cache hit rates in realistic RL inference scenario.

This script simulates a realistic backtest scenario where both entry and exit
strategies query the same bar within milliseconds, expecting:
- Market features cache hit rate: >95%
- Time features cache hit rate: ~100% (when queries are within same minute)

Expected behavior:
- Bar 1: Entry (miss) + Exit (hit) = 50% hit rate for that bar
- Bar 2+: Entry (hit from previous) + Exit (hit) = 100% hit rate
- Overall: >95% hit rate for market features, ~100% for time features
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import numpy as np

# Import the module we're testing
from shared.strategy.rl_model_helpers import (
    build_rl_observation,
    get_cache_stats,
    reset_cache_stats,
)


def create_mock_scaler():
    """Create a mock StandardScaler that just returns the input."""

    class MockScaler:
        def transform(self, X):
            return X

    return MockScaler()


def create_mock_env_config():
    """Create a mock RLEnvConfig."""

    class MockEnvConfig:
        market_open = "09:00"
        market_close = "15:45"

    return MockEnvConfig()


def generate_market_features(bar_index: int) -> tuple[dict, dict]:
    """Generate realistic market data and indicators for a given bar.

    Returns slightly different values per bar to simulate market movement.
    """
    # Simulate price movement
    base_price = 100.0 + bar_index * 0.1

    market_data = {
        "close": base_price,
        "volume": 1000 + bar_index * 10,
    }

    # Generate RL features (25 features total)
    indicators = {
        "close_normalized": base_price / 100.0,
        "returns": 0.001 * (bar_index % 10 - 5),
        "log_returns": 0.0005 * (bar_index % 10 - 5),
        "volume_ratio": 1.0 + 0.1 * (bar_index % 5),
        "bb_upper": base_price * 1.02,
        "bb_middle": base_price,
        "bb_lower": base_price * 0.98,
        "bb_position": 0.5,
        "bb_bandwidth": 0.04,
        "rsi": 50.0 + (bar_index % 20 - 10),
        "macd": 0.1 * np.sin(bar_index * 0.1),
        "macd_signal": 0.1 * np.sin(bar_index * 0.1 - 0.2),
        "macd_hist": 0.01,
        "atr": 2.0,
        "atr_ratio": 0.02,
        "stoch_k": 50.0 + (bar_index % 30 - 15),
        "stoch_d": 50.0 + (bar_index % 30 - 15),
        "cci": 0.0,
        "adx": 25.0,
        "plus_di": 20.0,
        "minus_di": 20.0,
        "obv": 10000 + bar_index * 100,
        "obv_ema": 10000 + bar_index * 95,
        "vwap": base_price,
        "vwap_distance": 0.0,
    }

    return market_data, indicators


def simulate_realistic_backtest(num_bars: int = 150):
    """Simulate a realistic backtest with entry + exit queries per bar.

    Args:
        num_bars: Number of 1-minute bars to simulate (default 150 = 2.5 hours)
    """
    print(f"\n{'='*60}")
    print(f"Simulating realistic backtest with {num_bars} bars")
    print(f"{'='*60}\n")

    # Reset counters
    reset_cache_stats()

    scaler = create_mock_scaler()
    env_config = create_mock_env_config()
    kst = ZoneInfo("Asia/Seoul")

    # Start at market open
    start_time = datetime(2024, 1, 2, 9, 0, 0, tzinfo=kst)

    # Simulate each bar
    for bar_idx in range(num_bars):
        # Current bar timestamp
        current_time = start_time + timedelta(minutes=bar_idx)

        # Generate market data for this bar
        market_data, indicators = generate_market_features(bar_idx)

        # Position state (simulate having a position after bar 10)
        position_side = 1.0 if bar_idx > 10 else 0.0
        contracts = 0.5 if bar_idx > 10 else 0.0
        unrealized_pnl = 0.02 * (bar_idx - 10) if bar_idx > 10 else 0.0

        # Entry strategy query (first call for this bar)
        obs_entry = build_rl_observation(
            market_data=market_data,
            indicators=indicators,
            position_side=position_side,
            contracts=contracts,
            unrealized_pnl=unrealized_pnl,
            timestamp=current_time,
            scaler=scaler,
            env_config=env_config,
        )

        # Exit strategy query (second call for same bar, ~1ms later)
        # This simulates the realistic scenario where entry and exit both check the same bar
        obs_exit = build_rl_observation(
            market_data=market_data,
            indicators=indicators,
            position_side=position_side,
            contracts=contracts,
            unrealized_pnl=unrealized_pnl,
            timestamp=current_time + timedelta(milliseconds=1),  # Same minute
            scaler=scaler,
            env_config=env_config,
        )

        # Verify observations are identical (they should be with caching)
        assert obs_entry is not None and obs_exit is not None
        assert np.allclose(obs_entry, obs_exit), f"Bar {bar_idx}: Observations mismatch!"

        # Print progress every 30 bars
        if (bar_idx + 1) % 30 == 0:
            stats = get_cache_stats()
            print(f"Bar {bar_idx + 1:3d}: "
                  f"Market hit rate: {stats['market_hit_rate']:.1f}%, "
                  f"Time hit rate: {stats['time_hit_rate']:.1f}%")

    # Final statistics
    stats = get_cache_stats()

    print(f"\n{'='*60}")
    print("FINAL CACHE STATISTICS")
    print(f"{'='*60}")
    print(f"Market Features Cache:")
    print(f"  - Hits:      {stats['market_cache_hits']}")
    print(f"  - Misses:    {stats['market_cache_misses']}")
    print(f"  - Hit Rate:  {stats['market_hit_rate']:.2f}%")
    print(f"  - Cache Size: {stats['market_cache_size']}")
    print()
    print(f"Time Features Cache:")
    print(f"  - Hits:      {stats['time_cache_hits']}")
    print(f"  - Misses:    {stats['time_cache_misses']}")
    print(f"  - Hit Rate:  {stats['time_hit_rate']:.2f}%")
    print(f"  - Cache Size: {stats['time_cache_size']}")
    print(f"{'='*60}\n")

    # Verify expectations
    market_hit_rate = stats['market_hit_rate']
    time_hit_rate = stats['time_hit_rate']

    print("VERIFICATION:")

    # Market cache: expect >95% hit rate
    # First bar has 2 calls: entry (miss) + exit (hit) = 50%
    # Subsequent bars: entry (hit from prev bar cache) + exit (hit) = 100%
    # Overall: (1*50% + (N-1)*100%) / N = (50 + 100N - 100) / N = (100N - 50) / N
    # For N=150: (15000 - 50) / 150 = 99.67%
    expected_market_min = 95.0
    if market_hit_rate >= expected_market_min:
        print(f"✓ Market cache hit rate {market_hit_rate:.2f}% >= {expected_market_min}% (PASS)")
    else:
        print(f"✗ Market cache hit rate {market_hit_rate:.2f}% < {expected_market_min}% (FAIL)")
        return False

    # Time cache: expect ~100% hit rate (all queries within same minute)
    # Same logic as market cache since we query within same minute
    expected_time_min = 95.0
    if time_hit_rate >= expected_time_min:
        print(f"✓ Time cache hit rate {time_hit_rate:.2f}% >= {expected_time_min}% (PASS)")
    else:
        print(f"✗ Time cache hit rate {time_hit_rate:.2f}% < {expected_time_min}% (FAIL)")
        return False

    print("\n✓ All cache performance expectations met!")
    return True


def test_cache_eviction_behavior():
    """Test that cache properly evicts old entries when full."""
    print(f"\n{'='*60}")
    print("Testing cache eviction behavior")
    print(f"{'='*60}\n")

    reset_cache_stats()

    scaler = create_mock_scaler()
    env_config = create_mock_env_config()
    kst = ZoneInfo("Asia/Seoul")

    # Cache size is 120, so simulate 150 unique bars to trigger eviction
    start_time = datetime(2024, 1, 2, 9, 0, 0, tzinfo=kst)

    for bar_idx in range(150):
        current_time = start_time + timedelta(minutes=bar_idx)
        market_data, indicators = generate_market_features(bar_idx)

        obs = build_rl_observation(
            market_data=market_data,
            indicators=indicators,
            position_side=0.0,
            contracts=0.0,
            unrealized_pnl=0.0,
            timestamp=current_time,
            scaler=scaler,
            env_config=env_config,
        )
        assert obs is not None

    stats = get_cache_stats()

    print(f"After 150 unique bars:")
    print(f"  - Market cache size: {stats['market_cache_size']}")
    print(f"  - Time cache size: {stats['time_cache_size']}")
    print(f"  - Market cache misses: {stats['market_cache_misses']}")
    print(f"  - Time cache misses: {stats['time_cache_misses']}")

    # Cache should not exceed 120 entries
    assert stats['market_cache_size'] <= 120, "Market cache exceeded size limit!"
    assert stats['time_cache_size'] <= 120, "Time cache exceeded size limit!"

    print("\n✓ Cache eviction working correctly (size limited to 120)")
    return True


if __name__ == "__main__":
    try:
        # Run realistic backtest simulation
        success1 = simulate_realistic_backtest(num_bars=150)

        # Run eviction test
        success2 = test_cache_eviction_behavior()

        if success1 and success2:
            print(f"\n{'='*60}")
            print("ALL VERIFICATION TESTS PASSED")
            print(f"{'='*60}\n")
            exit(0)
        else:
            print(f"\n{'='*60}")
            print("SOME VERIFICATION TESTS FAILED")
            print(f"{'='*60}\n")
            exit(1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
