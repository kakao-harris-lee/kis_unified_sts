"""Tests for FeatureCalculator and RLFeatureCalculator.

Covers base 10-feature calculation, RL 25-feature extension,
RSI, ATR, Stochastic, and feature extraction utilities.
"""

import numpy as np
import pandas as pd
import pytest

from shared.ml.rl.features import (
    FEATURE_COLUMNS,
    RL_EXTRA_COLUMNS,
    RL_FEATURE_COLUMNS,
    FeatureCalculator,
    RLFeatureCalculator,
)


@pytest.fixture
def ohlcv_df() -> pd.DataFrame:
    """Generate synthetic OHLCV data (200 bars, uptrend with noise)."""
    np.random.seed(42)
    n = 200
    base = 350.0
    trend = np.linspace(0, 10, n)
    noise = np.random.randn(n) * 0.5

    close = base + trend + np.cumsum(noise)
    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)
    open_ = close + np.random.randn(n) * 0.1
    volume = np.random.randint(100, 1000, n).astype(float)

    return pd.DataFrame(
        {
            "datetime": pd.date_range("2026-01-01 09:00", periods=n, freq="min"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


@pytest.fixture
def calc() -> FeatureCalculator:
    return FeatureCalculator()


@pytest.fixture
def rl_calc() -> RLFeatureCalculator:
    return RLFeatureCalculator()


class TestFeatureColumns:
    def test_feature_columns_count(self):
        assert len(FEATURE_COLUMNS) == 10

    def test_rl_extra_columns_count(self):
        assert len(RL_EXTRA_COLUMNS) == 15

    def test_rl_feature_columns_count(self):
        assert len(RL_FEATURE_COLUMNS) == 25

    def test_no_duplicate_columns(self):
        assert len(set(RL_FEATURE_COLUMNS)) == 25


class TestFeatureCalculator:
    def test_calculate_returns_all_base_features(self, calc, ohlcv_df):
        result = calc.calculate(ohlcv_df)
        for col in FEATURE_COLUMNS:
            assert col in result.columns, f"Missing column: {col}"

    def test_calculate_preserves_ohlcv(self, calc, ohlcv_df):
        result = calc.calculate(ohlcv_df)
        for col in ["open", "high", "low", "close", "volume", "datetime"]:
            assert col in result.columns

    def test_calculate_does_not_mutate_input(self, calc, ohlcv_df):
        original_cols = set(ohlcv_df.columns)
        calc.calculate(ohlcv_df)
        assert set(ohlcv_df.columns) == original_cols

    def test_returns_first_is_nan(self, calc, ohlcv_df):
        result = calc.calculate(ohlcv_df)
        assert pd.isna(result["returns"].iloc[0])

    def test_ma_ratios_near_one(self, calc, ohlcv_df):
        result = calc.calculate(ohlcv_df)
        for w in [5, 10, 20]:
            valid = result[f"ma_ratio_{w}"].dropna()
            assert valid.mean() == pytest.approx(1.0, abs=0.1)

    def test_rsi_bounded_0_100(self, calc, ohlcv_df):
        result = calc.calculate(ohlcv_df)
        valid_rsi = result["rsi"].dropna()
        assert valid_rsi.min() >= 0
        assert valid_rsi.max() <= 100

    def test_bb_position_mostly_bounded(self, calc, ohlcv_df):
        result = calc.calculate(ohlcv_df)
        valid_bb = result["bb_position"].dropna()
        # Most values should be between 0 and 1 (some outliers ok)
        in_range = ((valid_bb >= -0.5) & (valid_bb <= 1.5)).mean()
        assert in_range > 0.9

    def test_volume_ratio_positive(self, calc, ohlcv_df):
        result = calc.calculate(ohlcv_df)
        valid = result["volume_ratio"].dropna()
        assert (valid > 0).all()

    def test_hl_range_non_negative(self, calc, ohlcv_df):
        result = calc.calculate(ohlcv_df)
        valid = result["hl_range"].dropna()
        assert (valid >= 0).all()

    def test_custom_rsi_period(self, ohlcv_df):
        calc = FeatureCalculator(rsi_period=7)
        result = calc.calculate(ohlcv_df)
        # Shorter RSI period means more valid values (less NaN warmup)
        rsi_default = FeatureCalculator(rsi_period=14).calculate(ohlcv_df)["rsi"]
        assert result["rsi"].notna().sum() >= rsi_default.notna().sum()


class TestFeatureCalculatorRSI:
    def test_rsi_all_gains(self, calc):
        prices = pd.Series([10.0 + i for i in range(30)])
        rsi = calc._calc_rsi(prices, period=14)
        # All positive changes -> RSI near 100
        assert rsi.dropna().iloc[-1] > 90

    def test_rsi_all_losses(self, calc):
        prices = pd.Series([30.0 - i for i in range(30)])
        rsi = calc._calc_rsi(prices, period=14)
        # All negative changes -> RSI near 0
        assert rsi.dropna().iloc[-1] < 10

    def test_rsi_flat_market(self, calc):
        prices = pd.Series([100.0] * 30)
        rsi = calc._calc_rsi(prices, period=14)
        # No change -> gain=0, loss=0, rs=0/(epsilon)~0, RSI~0
        valid = rsi.dropna()
        if len(valid) > 0:
            assert valid.iloc[-1] == pytest.approx(0.0, abs=1.0)


class TestFeatureCalculatorExtract:
    def test_extract_features_shape(self, calc, ohlcv_df):
        result = calc.calculate(ohlcv_df)
        features = calc.extract_features(result)
        assert features.ndim == 2
        assert features.shape[1] == 10

    def test_extract_features_no_nans(self, calc, ohlcv_df):
        result = calc.calculate(ohlcv_df)
        features = calc.extract_features(result)
        assert not np.isnan(features).any()


class TestPrepareSequence:
    def test_returns_none_if_insufficient(self, calc):
        features = [{"returns": 0.01}] * 5
        result = calc.prepare_sequence(features, seq_len=60)
        assert result is None

    def test_returns_correct_shape(self, calc):
        features = [{"returns": 0.01, "rsi": 50, "bb_position": 0.5} for _ in range(100)]
        result = calc.prepare_sequence(features, seq_len=60)
        assert result is not None
        assert result.shape == (60, 10)

    def test_uses_most_recent(self, calc):
        features = []
        for i in range(80):
            features.append({col: float(i) for col in FEATURE_COLUMNS})
        result = calc.prepare_sequence(features, seq_len=60)
        # Last row should contain values from feature index 79
        assert result[-1, 0] == 79.0

    def test_handles_none_values(self, calc):
        features = [{col: None for col in FEATURE_COLUMNS} for _ in range(70)]
        for f in features:
            f["returns"] = 0.01  # needs "returns" to pass filter
        result = calc.prepare_sequence(features, seq_len=60)
        assert result is not None
        # None -> 0.0
        assert (result[:, 1:] == 0.0).all()


class TestRLFeatureCalculator:
    def test_calculate_returns_all_25_features(self, rl_calc, ohlcv_df):
        result = rl_calc.calculate(ohlcv_df)
        for col in RL_FEATURE_COLUMNS:
            assert col in result.columns, f"Missing RL column: {col}"

    def test_inherits_base_features(self, rl_calc, ohlcv_df):
        result = rl_calc.calculate(ohlcv_df)
        for col in FEATURE_COLUMNS:
            assert col in result.columns

    def test_macd_signal_hist_consistency(self, rl_calc, ohlcv_df):
        result = rl_calc.calculate(ohlcv_df)
        valid = result[["macd", "macd_signal", "macd_hist"]].dropna()
        # hist = macd - signal
        np.testing.assert_allclose(
            valid["macd_hist"].values,
            (valid["macd"] - valid["macd_signal"]).values,
            atol=1e-10,
        )

    def test_bb_width_positive(self, rl_calc, ohlcv_df):
        result = rl_calc.calculate(ohlcv_df)
        valid = result["bb_width"].dropna()
        assert (valid >= 0).all()

    def test_stoch_k_bounded(self, rl_calc, ohlcv_df):
        result = rl_calc.calculate(ohlcv_df)
        valid = result["stoch_k"].dropna()
        assert valid.min() >= -1  # small epsilon tolerance
        assert valid.max() <= 101

    def test_atr_non_negative(self, rl_calc, ohlcv_df):
        result = rl_calc.calculate(ohlcv_df)
        valid = result["atr"].dropna()
        assert (valid >= 0).all()

    def test_extract_rl_features_shape(self, rl_calc, ohlcv_df):
        result = rl_calc.calculate(ohlcv_df)
        features = rl_calc.extract_rl_features(result)
        assert features.ndim == 2
        assert features.shape[1] == 25

    def test_extract_rl_features_no_nans(self, rl_calc, ohlcv_df):
        result = rl_calc.calculate(ohlcv_df)
        features = rl_calc.extract_rl_features(result)
        assert not np.isnan(features).any()

    def test_get_feature_names(self, rl_calc):
        names = rl_calc.get_feature_names()
        assert names == RL_FEATURE_COLUMNS
        # Ensure it returns a copy
        names.append("extra")
        assert len(rl_calc.get_feature_names()) == 25


class TestRLFeatureCalculatorATR:
    def test_atr_known_values(self, rl_calc):
        """ATR for constant-range candles should equal that range / close."""
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=30, freq="min"),
                "open": [100.0] * 30,
                "high": [102.0] * 30,
                "low": [98.0] * 30,
                "close": [100.0] * 30,
                "volume": [500.0] * 30,
            }
        )
        atr = rl_calc._calc_atr(df, period=14)
        # TR = high - low = 4.0 for all bars (no gaps), ATR = 4.0
        # Normalized: 4.0 / 100.0 = 0.04
        valid = atr.dropna()
        assert valid.iloc[-1] == pytest.approx(0.04, abs=0.001)


class TestRLFeatureCalculatorStochastic:
    def test_stochastic_at_high(self, rl_calc):
        """Close at period high -> stoch_k near 100."""
        n = 30
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": [100.0] * n,
                "high": [100.0 + i for i in range(n)],
                "low": [90.0] * n,
                "close": [100.0 + i for i in range(n)],  # close = high
                "volume": [500.0] * n,
            }
        )
        k, d = rl_calc._calc_stochastic(df, period=14, smooth=3)
        assert k.dropna().iloc[-1] == pytest.approx(100.0, abs=1.0)

    def test_stochastic_at_low(self, rl_calc):
        """Close at period low -> stoch_k near 0."""
        n = 30
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": [100.0] * n,
                "high": [110.0] * n,
                "low": [100.0 - i for i in range(n)],
                "close": [100.0 - i for i in range(n)],  # close = low
                "volume": [500.0] * n,
            }
        )
        k, d = rl_calc._calc_stochastic(df, period=14, smooth=3)
        assert k.dropna().iloc[-1] == pytest.approx(0.0, abs=1.0)
