"""ATR consumers delegate to the canonical reference.ATRCalculator (value-preserving).

Phase 1 of the ATR SoT unification (docs/plans/2026-07-05-atr-sot-unification.md)
migrated four standalone ATR consumers to ``reference.ATRCalculator(mode="sma")``.
These tests lock each consumer to the canonical SMA-of-True-Range value computed
*independently here*, so the migration is verified non-circularly and cannot
silently drift from the standalone-ATR convention every consumer used before.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from services.trading.indicator_calculations import IndicatorCalculationMixin
from services.trading.indicator_candles import Candle
from shared.llm.stock_screening import calc_atr_pct
from shared.regime.adaptive_detector import AdaptiveRegimeDetector
from shared.strategy.entry.trix_golden import TrixGoldenEntry

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


def test_llm_calc_atr_pct_is_canonical_fraction() -> None:
    highs, lows, closes = _ohlc()
    df = pd.DataFrame({"고가": highs, "저가": lows, "종가": closes})
    expected = _expected_atr_sma(highs, lows, closes, _PERIOD) / closes[-1]
    assert calc_atr_pct(df, _PERIOD) == pytest.approx(expected, abs=1e-9)


def test_trix_calc_atr_pct_is_canonical_fraction() -> None:
    highs, lows, closes = _ohlc()
    df = pd.DataFrame({"high": highs, "low": lows, "close": closes})
    expected = _expected_atr_sma(highs, lows, closes, _PERIOD) / closes[-1]
    assert TrixGoldenEntry._calc_atr_pct(df, _PERIOD) == pytest.approx(
        expected, abs=1e-9
    )


def test_regime_calc_atr_is_canonical_sma() -> None:
    """Phase 1b: the regime detector's ATR delegates to the canonical SMA ATR.

    The detector gates on ``len(df) >= min_bars (50) > period + 1``, so this
    (steady-state) equality is what the live-but-dormant detector actually sees.
    """
    highs, lows, closes = _ohlc()
    expected = _expected_atr_sma(highs, lows, closes, _PERIOD)
    got = AdaptiveRegimeDetector()._calc_atr(
        np.asarray(highs), np.asarray(lows), np.asarray(closes), period=_PERIOD
    )
    assert got == pytest.approx(expected, abs=1e-9)


def test_atr_consumers_insufficient_data_return_zero() -> None:
    highs, lows, closes = _ohlc(n=5)  # < period + 1
    candles = _candles(highs, lows, closes)
    assert IndicatorCalculationMixin._calc_atr_raw(candles, _PERIOD) == 0.0
    assert IndicatorCalculationMixin._calc_atr_normalized(candles, _PERIOD) == 0.0
    assert (
        calc_atr_pct(
            pd.DataFrame({"고가": highs, "저가": lows, "종가": closes}), _PERIOD
        )
        == 0.0
    )
