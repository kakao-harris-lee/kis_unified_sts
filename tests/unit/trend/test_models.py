"""Test trend data models."""
import pytest


def test_technical_data_creation():
    """Test TechnicalData dataclass."""
    from shared.trend.models import TechnicalData

    data = TechnicalData(
        timestamp=1705300800.0,
        close=330.50,
        ma_short=330.25,
        ma_long=329.80,
        ichimoku_tenkan=330.10,
        ichimoku_kijun=329.90,
        ichimoku_senkou_a=330.00,
        ichimoku_senkou_b=329.50,
        atr=1.25,
    )

    assert data.close == 330.50
    assert data.ma_short > data.ma_long  # Bullish MA crossover


def test_trend_signal_creation():
    """Test TrendSignal dataclass."""
    from shared.trend.models import TrendSignal, TechnicalData

    tech_data = TechnicalData(
        timestamp=1705300800.0,
        close=330.50,
        ma_short=330.25,
        ma_long=329.80,
        ichimoku_tenkan=330.10,
        ichimoku_kijun=329.90,
        ichimoku_senkou_a=330.00,
        ichimoku_senkou_b=329.50,
        atr=1.25,
    )

    signal = TrendSignal(
        timestamp=1705300800.0,
        direction="LONG",
        confidence=0.85,
        entry_price=330.50,
        stop_loss=328.00,
        take_profit=335.00,
        technical_data=tech_data,
    )

    assert signal.direction == "LONG"
    assert signal.confidence > 0.8


def test_ichimoku_data_creation():
    """Test IchimokuData dataclass."""
    from shared.trend.models import IchimokuData

    data = IchimokuData(
        tenkan=330.10,
        kijun=329.90,
        senkou_a=330.00,
        senkou_b=329.50,
        chikou=330.50,
    )

    assert data.tenkan > data.kijun  # Bullish TK cross
    assert data.senkou_a > data.senkou_b  # Green cloud
