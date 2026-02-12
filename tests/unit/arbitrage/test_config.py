"""Test arbitrage configuration."""


def test_arbitrage_config_defaults():
    """Test ArbitrageConfig default values."""
    from shared.arbitrage.config import ArbitrageConfig

    config = ArbitrageConfig()

    assert config.risk_free_rate == 0.035
    assert config.rolling_window == 60
    assert config.min_samples == 20
    assert config.basis_threshold == 2.5


def test_arbitrage_config_custom():
    """Test custom configuration."""
    from shared.arbitrage.config import ArbitrageConfig

    config = ArbitrageConfig(
        risk_free_rate=0.04,
        basis_threshold=3.0,
        max_spread_ticks=3,
    )

    assert config.risk_free_rate == 0.04
    assert config.basis_threshold == 3.0
