"""ATR consumers delegate to the canonical reference.ATRCalculator (value-preserving)."""

from __future__ import annotations

import math

import pytest

from shared.indicators.streaming.calculations import IndicatorCalculationMixin
from shared.indicators.streaming.candles import Candle

_PERIOD = 14


def _ohlc(n: int = 40) -> tuple[list[float], list[float], list[float]]:
    """Deterministic OHLC (RNG-free), gappy enough to exercise all TR terms."""
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    for i in range(n):
        close = 100.0 + 0.2 * i + 3.0 * math.sin(i / 3.0)
        span = 0.9 + 0.4 * abs(math.cos(i / 2.0))
        highs.append(max(close + span, close))
        lows.append(min(close - span, close))
        closes.append(close)
    return highs, lows, closes


def _candles(highs, lows, closes) -> list[Candle]:
    return [
        Candle(
            open=closes[i],
            high=highs[i],
            low=lows[i],
            close=closes[i],
            volume=1000.0,
            minute=900 + i,
        )
        for i in range(len(closes))
    ]


def _expected_atr_sma(highs, lows, closes, period: int) -> float | None:
    """Independent SMA of True Range over the last ``period`` bars (bars 1..n-1)."""
    trs = [
        max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        for i in range(1, len(closes))
    ]
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


def test_runtime_calc_atr_raw_is_canonical_sma() -> None:
    highs, lows, closes = _ohlc()
    expected = _expected_atr_sma(highs, lows, closes, _PERIOD)
    got = IndicatorCalculationMixin._calc_atr_raw(
        _candles(highs, lows, closes), _PERIOD
    )
    assert got == pytest.approx(expected, abs=1e-9)


def test_runtime_calc_atr_normalized_is_raw_over_close() -> None:
    highs, lows, closes = _ohlc()
    candles = _candles(highs, lows, closes)
    raw = IndicatorCalculationMixin._calc_atr_raw(candles, _PERIOD)
    norm = IndicatorCalculationMixin._calc_atr_normalized(candles, _PERIOD)
    assert norm == pytest.approx(raw / (closes[-1] + 1e-10), abs=1e-12)


def test_atr_consumers_insufficient_data_return_zero() -> None:
    highs, lows, closes = _ohlc(n=5)
    candles = _candles(highs, lows, closes)
    assert IndicatorCalculationMixin._calc_atr_raw(candles, _PERIOD) == 0.0
    assert IndicatorCalculationMixin._calc_atr_normalized(candles, _PERIOD) == 0.0
