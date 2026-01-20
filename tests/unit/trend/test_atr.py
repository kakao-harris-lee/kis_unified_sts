"""Test ATR and volatility calculations."""
import pytest


def test_atr_calculation():
    """Test Average True Range calculation."""
    from shared.trend.technical_calculator import TechnicalCalculator
    from shared.trend.config import TechnicalConfig

    config = TechnicalConfig(atr_period=14)
    calc = TechnicalCalculator(config)

    # Feed 20 candles with known volatility
    for i in range(20):
        high = 100 + i + 2  # +2 range
        low = 100 + i - 2   # -2 range
        close = 100 + i
        calc.update(close=close, high=high, low=low)

    atr = calc.get_atr()
    assert atr is not None

    # ATR should reflect the 4-point range (high - low = 4)
    assert 3.5 < atr < 4.5


def test_atr_increases_with_volatility():
    """Test ATR increases when volatility increases."""
    from shared.trend.technical_calculator import TechnicalCalculator
    from shared.trend.config import TechnicalConfig

    config = TechnicalConfig(atr_period=5)
    calc = TechnicalCalculator(config)

    # Feed low volatility data first
    for i in range(10):
        high = 100 + 0.5
        low = 100 - 0.5
        calc.update(close=100, high=high, low=low)

    atr_low = calc.get_atr()

    # Now feed high volatility data
    for i in range(10):
        high = 100 + 5
        low = 100 - 5
        calc.update(close=100, high=high, low=low)

    atr_high = calc.get_atr()

    assert atr_high > atr_low


def test_atr_gap_handling():
    """Test ATR handles gaps correctly (True Range includes gaps)."""
    from shared.trend.technical_calculator import TechnicalCalculator
    from shared.trend.config import TechnicalConfig

    config = TechnicalConfig(atr_period=5)
    calc = TechnicalCalculator(config)

    # Start with stable prices
    for i in range(5):
        calc.update(close=100, high=101, low=99)

    atr_before = calc.get_atr()

    # Gap up - open above previous high
    calc.update(close=110, high=111, low=109)  # Gap of ~9 points

    atr_after = calc.get_atr()

    # ATR should increase due to gap
    assert atr_after > atr_before


def test_get_technical_data():
    """Test getting complete TechnicalData snapshot."""
    from shared.trend.technical_calculator import TechnicalCalculator
    from shared.trend.config import TechnicalConfig

    config = TechnicalConfig(
        ma_short_period=5,
        ma_long_period=10,
        atr_period=5,
        ichimoku_tenkan_period=5,
        ichimoku_kijun_period=10,
        ichimoku_senkou_b_period=10
    )
    calc = TechnicalCalculator(config)

    # Feed enough data
    for i in range(20):
        price = 100 + i * 0.5
        calc.update(close=price, high=price + 1, low=price - 1)

    data = calc.get_technical_data(timestamp=1705300800.0)
    assert data is not None

    # All fields should be populated
    assert data.close == pytest.approx(109.5)  # Last price
    assert data.ma_short is not None
    assert data.ma_long is not None
    assert data.atr is not None
    assert data.ichimoku_tenkan is not None
    assert data.ichimoku_kijun is not None


def test_volatility_regime():
    """Test volatility regime detection."""
    from shared.trend.technical_calculator import TechnicalCalculator
    from shared.trend.config import TechnicalConfig

    config = TechnicalConfig(atr_period=5)
    calc = TechnicalCalculator(config)

    # Low volatility period (0.5% ATR)
    for i in range(10):
        calc.update(close=100, high=100.25, low=99.75)

    assert calc.get_volatility_regime() == "LOW"

    # High volatility period (20% ATR)
    for i in range(20):
        calc.update(close=100, high=110, low=90)

    assert calc.get_volatility_regime() == "HIGH"
