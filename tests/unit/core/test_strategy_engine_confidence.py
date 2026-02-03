"""Unit tests for StrategyEngine confidence calculation (no polars dependency)."""

from core.strategy_engine import StrategyEngine


def test_confidence_increases_when_more_oversold_and_positive_macd():
    engine = StrategyEngine()

    c1 = engine._calculate_confidence(rsi=29.0, macd_hist=0.1)
    c2 = engine._calculate_confidence(rsi=20.0, macd_hist=0.1)
    c3 = engine._calculate_confidence(rsi=20.0, macd_hist=0.3)

    assert 0.0 <= c1 <= 1.0
    assert 0.0 <= c2 <= 1.0
    assert 0.0 <= c3 <= 1.0

    assert c2 >= c1  # lower RSI (more oversold) => higher confidence
    assert c3 >= c2  # higher positive MACD hist => higher confidence


def test_confidence_zero_macd_hist_component_when_non_positive():
    engine = StrategyEngine()

    c_pos = engine._calculate_confidence(rsi=20.0, macd_hist=0.2)
    c_zero = engine._calculate_confidence(rsi=20.0, macd_hist=0.0)
    c_neg = engine._calculate_confidence(rsi=20.0, macd_hist=-0.2)

    assert c_pos > c_zero
    assert c_zero == c_neg

