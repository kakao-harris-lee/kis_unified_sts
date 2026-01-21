"""Test config from_dict methods."""
import pytest


def test_v35_config_from_dict():
    """Test V35Config.from_dict()."""
    from shared.strategy.entry.v35_optimized import V35Config

    data = {
        "bb_period": 30,
        "rsi_oversold": 25,
        "unknown_key": "ignored",
    }

    config = V35Config.from_dict(data)

    assert config.bb_period == 30
    assert config.rsi_oversold == 25
    assert config.bb_std == 2.0  # Default value


def test_stochrsi_config_from_dict():
    """Test StochRSIConfig.from_dict()."""
    from shared.strategy.entry.stochrsi_trend import StochRSIConfig

    data = {
        "oversold": 15,
        "overbought": 85,
        "extra_param": 123,
    }

    config = StochRSIConfig.from_dict(data)

    assert config.oversold == 15
    assert config.overbought == 85
    assert config.rsi_period == 14  # Default


def test_mean_reversion_config_from_dict():
    """Test MeanReversionConfig.from_dict()."""
    from shared.strategy.entry.mean_reversion import MeanReversionConfig

    data = {
        "bb_period": 25,
        "rsi_overbought": 75,
    }

    config = MeanReversionConfig.from_dict(data)

    assert config.bb_period == 25
    assert config.rsi_overbought == 75


def test_breakout_config_from_dict():
    """Test BreakoutConfig.from_dict()."""
    from shared.strategy.entry.breakout import BreakoutConfig

    data = {
        "lookback_period": 30,
        "volume_confirm": False,
        "volume_threshold": 2.0,
    }

    config = BreakoutConfig.from_dict(data)

    assert config.lookback_period == 30
    assert config.volume_confirm is False
    assert config.volume_threshold == 2.0


def test_config_from_dict_empty():
    """Test from_dict with empty dict returns defaults."""
    from shared.strategy.entry.v35_optimized import V35Config

    config = V35Config.from_dict({})

    assert config.bb_period == 20
    assert config.rsi_oversold == 30


def test_config_from_dict_ignores_unknown_keys():
    """Test that unknown keys are silently ignored."""
    from shared.strategy.entry.breakout import BreakoutConfig

    data = {
        "lookback_period": 25,
        "unknown1": "value1",
        "unknown2": 42,
        "nested": {"key": "value"},
    }

    # Should not raise
    config = BreakoutConfig.from_dict(data)
    assert config.lookback_period == 25
