"""Golden pins: shared/scanner/accumulation.py hand-rolled indicator math (P1-b4).

Pins the exact numeric behavior of the accumulation scanner's scoring inputs
BEFORE/AFTER delegation to ``shared.indicators.series``
(``docs/plans/2026-07-08-new-architecture-refactoring-plan.md`` §3, P1-b item 4):

* ``_calculate_atr``               — TR with first-bar prev_close = close[0],
                                     ``rolling(period, min_periods=1)`` mean
* ``_calculate_obv_score``         — mean-normalized OBV linear-regression slope
* ``_calculate_rvol_score``        — 5d/20d trailing-mean volume ratio
* ``_calculate_compression_score`` — ATR[-1]/ATR[-2] shrink ratio
* ``_calculate_strength_score``    — 20d relative strength vs market (diff form)

``_orig_*`` below are verbatim copies of the pre-refactor math. Assertions are
EXACT (``==`` / ``np.array_equal``): the delegation must be bit-identical.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from shared.indicators.volume import OBVCalculator
from shared.scanner.accumulation import (
    _calculate_atr,
    _calculate_compression_score,
    _calculate_obv_score,
    _calculate_rvol_score,
    _calculate_strength_score,
)

# ---------------------------------------------------------------------------
# Verbatim pre-refactor implementations (the golden reference)
# ---------------------------------------------------------------------------


def _orig_calculate_atr(df: pd.DataFrame, period: int = 14) -> np.ndarray:
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr1 = high - low
    tr2 = np.abs(high - prev_close)
    tr3 = np.abs(low - prev_close)
    true_range = np.maximum(tr1, np.maximum(tr2, tr3))
    atr = pd.Series(true_range).rolling(window=period, min_periods=1).mean().values
    return atr


def _orig_calculate_obv_score(df: pd.DataFrame) -> tuple[float, float]:
    if len(df) < 10:
        return 0.0, 0.0
    calculator = OBVCalculator()
    prices = df["close"].tolist()
    volumes = [int(v) for v in df["volume"].tolist()]
    obv_data = calculator.calculate(prices, volumes)
    obv_values = obv_data.obv_values
    x = np.arange(len(obv_values))
    y = np.array(obv_values)
    if len(x) < 2:
        return 0.0, 0.0
    y_mean = np.mean(y)
    if y_mean == 0:
        return 0.0, 0.0
    y_norm = y / y_mean
    coeffs = np.polyfit(x, y_norm, 1)
    slope = coeffs[0]
    if slope > 0.02:
        score = 40.0
    elif slope > 0.01:
        score = 20.0 + (slope - 0.01) / 0.01 * 20.0
    elif slope > 0:
        score = slope / 0.01 * 20.0
    else:
        score = 0.0
    return min(score, 40.0), slope


def _orig_calculate_rvol_score(df: pd.DataFrame) -> tuple[float, float, float, float]:
    if len(df) < 20:
        return 0.0, 0.0, 0.0, 0.0
    volumes = df["volume"].values
    avg_5d = np.mean(volumes[-5:])
    avg_20d = np.mean(volumes[-20:])
    if avg_20d == 0:
        return 0.0, 0.0, avg_5d, avg_20d
    rvol_ratio = avg_5d / avg_20d
    if rvol_ratio >= 1.5:
        score = 30.0
    elif rvol_ratio >= 1.2:
        score = 15.0 + (rvol_ratio - 1.2) / 0.3 * 15.0
    elif rvol_ratio >= 1.0:
        score = (rvol_ratio - 1.0) / 0.2 * 15.0
    else:
        score = 0.0
    return min(score, 30.0), rvol_ratio, avg_5d, avg_20d


def _orig_calculate_compression_score(df: pd.DataFrame) -> tuple[float, float]:
    if len(df) < 14:
        return 0.0, 0.0
    atr = _orig_calculate_atr(df, period=14)
    if len(atr) < 2:
        return 0.0, 0.0
    current_atr = atr[-1]
    prev_atr = atr[-2]
    if prev_atr == 0:
        return 0.0, 0.0
    compression_ratio = current_atr / prev_atr
    recent_data = df.tail(5)
    high = recent_data["high"].max()
    low = recent_data["low"].min()
    close = df["close"].iloc[-1]
    price_range_pct = 0.0 if close == 0 else (high - low) / close * 100
    if compression_ratio < 0.8:
        score = 20.0
    elif compression_ratio < 0.9:
        score = 10.0 + (0.9 - compression_ratio) / 0.1 * 10.0
    elif compression_ratio < 1.0:
        score = (1.0 - compression_ratio) / 0.1 * 10.0
    else:
        score = 0.0
    return min(score, 20.0), price_range_pct


def _orig_calculate_strength_score(df: pd.DataFrame, market_df: pd.DataFrame) -> float:
    if len(df) < 20 or len(market_df) < 20:
        return 0.0
    stock_start = df["close"].iloc[-20]
    stock_end = df["close"].iloc[-1]
    market_start = market_df["close"].iloc[-20]
    market_end = market_df["close"].iloc[-1]
    if stock_start == 0 or market_start == 0:
        return 0.0
    stock_pct = (stock_end - stock_start) / stock_start * 100
    market_pct = (market_end - market_start) / market_start * 100
    relative_strength = stock_pct - market_pct
    if relative_strength >= 5.0:
        score = 10.0
    elif relative_strength >= 2.0:
        score = 5.0 + (relative_strength - 2.0) / 3.0 * 5.0
    elif relative_strength >= 0:
        score = relative_strength / 2.0 * 5.0
    else:
        score = 0.0
    return min(score, 10.0)


# ---------------------------------------------------------------------------
# Seeded input generators
# ---------------------------------------------------------------------------


def _ohlcv(seed: int, n: int, flat_volume: float | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 10_000.0 + np.cumsum(rng.normal(0.0, 120.0, n))
    spread = np.abs(rng.normal(0.0, 80.0, n))
    volume = (
        np.full(n, flat_volume)
        if flat_volume is not None
        else rng.integers(50_000, 2_000_000, n).astype(float)
    )
    return pd.DataFrame(
        {
            "open": close - rng.normal(0.0, 40.0, n),
            "high": close + spread,
            "low": close - spread,
            "close": close,
            "volume": volume,
        }
    )


class TestAccumulationAtrGolden:
    def test_seeded_frames_bit_identical(self):
        for seed in range(20):
            for n in (1, 2, 3, 13, 14, 15, 30, 60):
                df = _ohlcv(seed=700 + seed, n=n)
                got = _calculate_atr(df, period=14)
                want = _orig_calculate_atr(df, period=14)
                assert np.array_equal(got, want), f"seed={seed} n={n}"

    def test_alternate_period(self):
        df = _ohlcv(seed=808, n=40)
        assert np.array_equal(_calculate_atr(df, period=5), _orig_calculate_atr(df, 5))


class TestObvScoreGolden:
    def test_seeded_frames_bit_identical(self):
        for seed in range(30):
            n = int(np.random.default_rng(seed).integers(5, 60))
            df = _ohlcv(seed=900 + seed, n=n)
            assert _calculate_obv_score(df) == _orig_calculate_obv_score(df)

    def test_short_frame_zero(self):
        df = _ohlcv(seed=911, n=9)
        assert _calculate_obv_score(df) == (0.0, 0.0)

    def test_zero_volume_zero_mean_obv(self):
        df = _ohlcv(seed=912, n=20, flat_volume=0.0)
        assert _calculate_obv_score(df) == _orig_calculate_obv_score(df)


class TestRvolScoreGolden:
    def test_seeded_frames_bit_identical(self):
        for seed in range(30):
            n = int(np.random.default_rng(seed).integers(15, 60))
            df = _ohlcv(seed=1000 + seed, n=n)
            assert _calculate_rvol_score(df) == _orig_calculate_rvol_score(df)

    def test_zero_volume(self):
        df = _ohlcv(seed=1010, n=25, flat_volume=0.0)
        assert _calculate_rvol_score(df) == _orig_calculate_rvol_score(df)

    def test_surging_volume(self):
        df = _ohlcv(seed=1011, n=25)
        df.loc[df.index[-5:], "volume"] = df["volume"].iloc[-5:] * 10
        assert _calculate_rvol_score(df) == _orig_calculate_rvol_score(df)


class TestCompressionScoreGolden:
    def test_seeded_frames_bit_identical(self):
        for seed in range(30):
            n = int(np.random.default_rng(seed).integers(10, 60))
            df = _ohlcv(seed=1100 + seed, n=n)
            assert _calculate_compression_score(df) == _orig_calculate_compression_score(
                df
            )


class TestStrengthScoreGolden:
    def test_seeded_frames_bit_identical(self):
        for seed in range(30):
            rng = np.random.default_rng(seed)
            n = int(rng.integers(15, 60))
            m = int(rng.integers(15, 60))
            df = _ohlcv(seed=1200 + seed, n=n)
            market_df = _ohlcv(seed=1300 + seed, n=m)
            assert _calculate_strength_score(df, market_df) == (
                _orig_calculate_strength_score(df, market_df)
            )

    def test_zero_start_price(self):
        df = _ohlcv(seed=1400, n=25)
        market_df = _ohlcv(seed=1401, n=25)
        df.loc[df.index[-20], "close"] = 0.0
        assert _calculate_strength_score(df, market_df) == (
            _orig_calculate_strength_score(df, market_df)
        )
