"""Test trend configuration."""


def test_technical_config_defaults():
    """Test TechnicalConfig default values."""
    from shared.trend.config import TechnicalConfig

    config = TechnicalConfig()

    # MA defaults
    assert config.ma_short_period == 20
    assert config.ma_long_period == 60

    # Ichimoku defaults (standard 9-26-52)
    assert config.ichimoku_tenkan_period == 9
    assert config.ichimoku_kijun_period == 26
    assert config.ichimoku_senkou_b_period == 52

    # ATR defaults
    assert config.atr_period == 14


def test_technical_config_custom():
    """Test custom configuration."""
    from shared.trend.config import TechnicalConfig

    config = TechnicalConfig(
        ma_short_period=10,
        ma_long_period=30,
        atr_period=20,
    )

    assert config.ma_short_period == 10
    assert config.ma_long_period == 30
    assert config.atr_period == 20


def test_trend_config_defaults():
    """Test TrendConfig for trend engine."""
    from shared.trend.config import TrendConfig

    config = TrendConfig()

    assert config.entry_threshold == 0.7
    assert config.atr_stop_multiplier == 2.0
    assert config.atr_target_multiplier == 3.0
