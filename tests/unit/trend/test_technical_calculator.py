"""Test TechnicalCalculator."""
import pytest
import numpy as np


def test_calculator_creation():
    """Test TechnicalCalculator instantiation."""
    from shared.trend.technical_calculator import TechnicalCalculator
    from shared.trend.config import TechnicalConfig

    config = TechnicalConfig()
    calc = TechnicalCalculator(config)

    assert calc.config == config


def test_sma_calculation():
    """Test simple moving average calculation."""
    from shared.trend.technical_calculator import TechnicalCalculator
    from shared.trend.config import TechnicalConfig

    config = TechnicalConfig(ma_short_period=5)
    calc = TechnicalCalculator(config)

    # Feed 10 prices: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    prices = list(range(1, 11))
    for price in prices:
        calc.update(price)

    # SMA(5) of last 5 values [6,7,8,9,10] = 8.0
    assert calc.get_ma_short() == pytest.approx(8.0)


def test_ema_calculation():
    """Test exponential moving average calculation."""
    from shared.trend.technical_calculator import TechnicalCalculator
    from shared.trend.config import TechnicalConfig

    config = TechnicalConfig(ma_short_period=5)
    calc = TechnicalCalculator(config)

    # Feed prices
    prices = [100, 102, 101, 103, 105, 104, 106]
    for price in prices:
        calc.update(price)

    ema = calc.get_ema_short()
    assert ema is not None
    assert 103 < ema < 106  # Should be weighted towards recent prices


def test_ma_crossover_detection():
    """Test MA crossover signal detection."""
    from shared.trend.technical_calculator import TechnicalCalculator
    from shared.trend.config import TechnicalConfig

    config = TechnicalConfig(ma_short_period=3, ma_long_period=5)
    calc = TechnicalCalculator(config)

    # Feed downtrend then uptrend
    downtrend = [110, 108, 106, 104, 102]
    for price in downtrend:
        calc.update(price)

    # Short MA should be below long MA
    assert calc.get_ma_short() < calc.get_ma_long()

    # Now feed uptrend
    uptrend = [104, 108, 112, 116]
    for price in uptrend:
        calc.update(price)

    # Short MA should cross above long MA
    assert calc.get_ma_short() > calc.get_ma_long()


def test_is_ready():
    """Test readiness check based on warmup period."""
    from shared.trend.technical_calculator import TechnicalCalculator
    from shared.trend.config import TechnicalConfig

    config = TechnicalConfig(ma_long_period=10)
    calc = TechnicalCalculator(config)

    # Not ready yet
    for i in range(5):
        calc.update(100 + i)
    assert not calc.is_ready()

    # Feed more prices
    for i in range(10):
        calc.update(105 + i)
    assert calc.is_ready()
