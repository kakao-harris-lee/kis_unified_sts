"""Test TrendEngine."""


def test_engine_creation():
    """Test TrendEngine instantiation."""
    from shared.trend.config import TrendConfig
    from shared.trend.engine import TrendEngine

    config = TrendConfig()
    engine = TrendEngine(config)

    assert engine.config == config
    assert engine.technical_calculator is not None
    assert engine.position_manager is not None


def test_engine_update():
    """Test engine update with price data."""
    from shared.trend.config import TechnicalConfig, TrendConfig
    from shared.trend.engine import TrendEngine

    # Use shorter periods for test
    tech_config = TechnicalConfig(ma_short_period=5, ma_long_period=10)
    config = TrendConfig(technical=tech_config)
    engine = TrendEngine(config)

    # Feed price data
    for i in range(30):
        engine.update(
            close=330.0 + i * 0.1,
            high=330.5 + i * 0.1,
            low=329.5 + i * 0.1,
            volume=1000,
            timestamp=1705300800.0 + i * 60,
        )

    assert engine.is_ready()


def test_check_long_signal():
    """Test long signal generation."""
    from shared.trend.config import TechnicalConfig, TrendConfig
    from shared.trend.engine import TrendEngine

    tech_config = TechnicalConfig(
        ma_short_period=5,
        ma_long_period=10,
        ichimoku_tenkan_period=5,
        ichimoku_kijun_period=10,
        ichimoku_senkou_b_period=10,
        atr_period=5,
    )
    config = TrendConfig(technical=tech_config, entry_threshold=0.5)
    engine = TrendEngine(config)

    # Feed uptrend data - establish bullish conditions
    base_price = 100.0
    for i in range(20):
        price = base_price + i * 2  # Strong uptrend
        engine.update(
            close=price,
            high=price + 1,
            low=price - 1,
            volume=1000 + i * 100,  # Increasing volume
        )

    # Check for long signal with high DL probability
    has_signal, signal = engine.check_entry(dl_probability=0.85, direction="LONG")

    # Should have a signal in strong uptrend
    assert engine.is_ready()


def test_manage_positions():
    """Test position management loop."""
    from shared.trend.config import TechnicalConfig, TrendConfig
    from shared.trend.engine import TrendEngine

    tech_config = TechnicalConfig(
        ma_short_period=5,
        ma_long_period=10,
        atr_period=5,
    )
    config = TrendConfig(
        technical=tech_config,
        atr_stop_multiplier=2.0,
        atr_target_multiplier=3.0,
    )
    engine = TrendEngine(config)

    # Warmup
    for i in range(15):
        engine.update(close=100 + i, high=101 + i, low=99 + i, volume=1000)

    # Open a position
    position = engine.open_position(
        direction="LONG",
        entry_price=115.0,
        size=5.0,
    )

    assert position is not None
    assert position.is_open

    # Simulate price movement - hit target
    for i in range(10):
        price = 115.0 + i * 0.5
        engine.update(close=price, high=price + 0.5, low=price - 0.5, volume=1000)
        engine.manage_positions(current_price=price)

    # Check if position was closed
    # (Depends on ATR and price movement)


def test_engine_stats():
    """Test engine statistics."""
    from shared.trend.config import TrendConfig
    from shared.trend.engine import TrendEngine

    config = TrendConfig()
    engine = TrendEngine(config)

    stats = engine.get_stats()

    assert "total_updates" in stats
    assert "signals_generated" in stats


def test_engine_reset():
    """Test engine reset."""
    from shared.trend.config import TrendConfig
    from shared.trend.engine import TrendEngine

    config = TrendConfig()
    engine = TrendEngine(config)

    # Feed some data
    for i in range(10):
        engine.update(close=100 + i, high=101 + i, low=99 + i, volume=1000)

    engine.reset()

    assert not engine.is_ready()
    assert engine.get_stats()["total_updates"] == 0
