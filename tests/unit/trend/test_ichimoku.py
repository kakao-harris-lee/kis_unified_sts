"""Test Ichimoku Cloud calculations."""
import pytest


def test_ichimoku_tenkan_calculation():
    """Test Tenkan-sen (conversion line) calculation."""
    from shared.trend.technical_calculator import TechnicalCalculator
    from shared.trend.config import TechnicalConfig

    # Use shorter periods for test
    config = TechnicalConfig(
        ichimoku_tenkan_period=9,
        ichimoku_kijun_period=9,  # Same as tenkan for simplicity
        ichimoku_senkou_b_period=9
    )
    calc = TechnicalCalculator(config)

    # Feed 9 candles with clear high/low
    for i in range(9):
        calc.update(close=100 + i, high=102 + i, low=98 + i)

    ichimoku = calc.get_ichimoku()
    assert ichimoku is not None

    # Tenkan = (highest high + lowest low) / 2 over 9 periods
    # Highs: 102-110, Lows: 98-106
    # Expected: (110 + 98) / 2 = 104.0
    assert ichimoku.tenkan == pytest.approx(104.0)


def test_ichimoku_kijun_calculation():
    """Test Kijun-sen (base line) calculation."""
    from shared.trend.technical_calculator import TechnicalCalculator
    from shared.trend.config import TechnicalConfig

    config = TechnicalConfig(ichimoku_kijun_period=26)
    calc = TechnicalCalculator(config)

    # Feed 26 candles
    for i in range(26):
        calc.update(close=100 + i, high=102 + i, low=98 + i)

    ichimoku = calc.get_ichimoku()
    assert ichimoku is not None

    # Kijun = (highest high + lowest low) / 2 over 26 periods
    # Highs: 102-127, Lows: 98-123
    # Expected: (127 + 98) / 2 = 112.5
    assert ichimoku.kijun == pytest.approx(112.5)


def test_ichimoku_cloud_calculation():
    """Test Senkou Span A and B calculations."""
    from shared.trend.technical_calculator import TechnicalCalculator
    from shared.trend.config import TechnicalConfig

    config = TechnicalConfig(
        ichimoku_tenkan_period=9,
        ichimoku_kijun_period=26,
        ichimoku_senkou_b_period=52
    )
    calc = TechnicalCalculator(config)

    # Feed 52 candles for full Ichimoku
    for i in range(52):
        calc.update(close=100 + i * 0.5, high=102 + i * 0.5, low=98 + i * 0.5)

    ichimoku = calc.get_ichimoku()
    assert ichimoku is not None

    # Senkou A = (Tenkan + Kijun) / 2
    expected_senkou_a = (ichimoku.tenkan + ichimoku.kijun) / 2
    assert ichimoku.senkou_a == pytest.approx(expected_senkou_a)

    # Senkou B should be calculated from 52-period high/low
    assert ichimoku.senkou_b is not None


def test_ichimoku_bullish_cloud():
    """Test detection of bullish (green) cloud."""
    from shared.trend.technical_calculator import TechnicalCalculator
    from shared.trend.config import TechnicalConfig

    config = TechnicalConfig()
    calc = TechnicalCalculator(config)

    # Feed uptrend data
    for i in range(60):
        price = 100 + i * 2  # Strong uptrend
        calc.update(close=price, high=price + 2, low=price - 2)

    ichimoku = calc.get_ichimoku()
    assert ichimoku is not None

    # In uptrend, Senkou A should be above Senkou B (green cloud)
    assert ichimoku.senkou_a > ichimoku.senkou_b


def test_ichimoku_price_above_cloud():
    """Test if price is above the cloud."""
    from shared.trend.technical_calculator import TechnicalCalculator
    from shared.trend.config import TechnicalConfig

    config = TechnicalConfig()
    calc = TechnicalCalculator(config)

    # Feed strong uptrend
    for i in range(60):
        price = 100 + i * 3
        calc.update(close=price, high=price + 2, low=price - 2)

    assert calc.is_price_above_cloud()
