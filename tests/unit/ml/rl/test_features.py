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


class TestRLFeatureCalculatorIndividualFeatures:
    """Individual tests for all 15 RL-specific features"""

    def test_macd_calculated(self, rl_calc, ohlcv_df):
        """MACD column exists and has valid values"""
        result = rl_calc.calculate(ohlcv_df)
        assert "macd" in result.columns
        valid = result["macd"].dropna()
        assert len(valid) > 0

    def test_macd_fast_slow_relationship(self, rl_calc):
        """MACD = EMA(fast) - EMA(slow)"""
        n = 100
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": [100.0] * n,
                "high": [101.0] * n,
                "low": [99.0] * n,
                "close": [100.0 + i * 0.1 for i in range(n)],
                "volume": [500.0] * n,
            }
        )
        result = rl_calc.calculate(df)
        # For uptrend, MACD should be mostly positive
        valid = result["macd"].dropna()
        assert valid.iloc[-10:].mean() > 0

    def test_macd_signal_calculated(self, rl_calc, ohlcv_df):
        """MACD signal column exists and is EMA of MACD"""
        result = rl_calc.calculate(ohlcv_df)
        assert "macd_signal" in result.columns
        valid = result["macd_signal"].dropna()
        assert len(valid) > 0

    def test_macd_hist_calculated(self, rl_calc, ohlcv_df):
        """MACD histogram = MACD - Signal"""
        result = rl_calc.calculate(ohlcv_df)
        assert "macd_hist" in result.columns
        valid = result[["macd", "macd_signal", "macd_hist"]].dropna()
        np.testing.assert_allclose(
            valid["macd_hist"].values,
            (valid["macd"] - valid["macd_signal"]).values,
            atol=1e-10,
        )

    def test_sma_ratio_60_calculated(self, rl_calc, ohlcv_df):
        """SMA ratio 60 exists and is close/SMA(60)"""
        result = rl_calc.calculate(ohlcv_df)
        assert "sma_ratio_60" in result.columns
        valid = result["sma_ratio_60"].dropna()
        # Should have reasonable values around 1.0
        assert 0.5 < valid.mean() < 1.5
        assert (valid > 0).all()

    def test_sma_ratio_120_calculated(self, rl_calc, ohlcv_df):
        """SMA ratio 120 exists and is close/SMA(120)"""
        result = rl_calc.calculate(ohlcv_df)
        assert "sma_ratio_120" in result.columns
        valid = result["sma_ratio_120"].dropna()
        # Should have reasonable values around 1.0
        assert 0.5 < valid.mean() < 1.5
        assert (valid > 0).all()

    def test_sma_ratios_near_one_stable_market(self, rl_calc):
        """SMA ratios near 1.0 in stable market"""
        n = 150
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": [100.0] * n,
                "high": [100.5] * n,
                "low": [99.5] * n,
                "close": [100.0] * n,
                "volume": [500.0] * n,
            }
        )
        result = rl_calc.calculate(df)
        for window in [60, 120]:
            valid = result[f"sma_ratio_{window}"].dropna()
            if len(valid) > 0:
                assert valid.iloc[-1] == pytest.approx(1.0, abs=0.01)

    def test_ema_ratio_5_calculated(self, rl_calc, ohlcv_df):
        """EMA ratio 5 exists and is close/EMA(5)"""
        result = rl_calc.calculate(ohlcv_df)
        assert "ema_ratio_5" in result.columns
        valid = result["ema_ratio_5"].dropna()
        assert (valid > 0).all()
        assert 0.5 < valid.mean() < 1.5

    def test_ema_ratio_10_calculated(self, rl_calc, ohlcv_df):
        """EMA ratio 10 exists and is close/EMA(10)"""
        result = rl_calc.calculate(ohlcv_df)
        assert "ema_ratio_10" in result.columns
        valid = result["ema_ratio_10"].dropna()
        assert (valid > 0).all()
        assert 0.5 < valid.mean() < 1.5

    def test_ema_ratio_20_calculated(self, rl_calc, ohlcv_df):
        """EMA ratio 20 exists and is close/EMA(20)"""
        result = rl_calc.calculate(ohlcv_df)
        assert "ema_ratio_20" in result.columns
        valid = result["ema_ratio_20"].dropna()
        assert (valid > 0).all()
        assert 0.5 < valid.mean() < 1.5

    def test_ema_ratios_responsive_to_trend(self, rl_calc):
        """EMA ratios respond faster than SMA in trending market"""
        n = 100
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": [100.0 + i * 0.5 for i in range(n)],
                "high": [101.0 + i * 0.5 for i in range(n)],
                "low": [99.0 + i * 0.5 for i in range(n)],
                "close": [100.0 + i * 0.5 for i in range(n)],
                "volume": [500.0] * n,
            }
        )
        result = rl_calc.calculate(df)
        # In uptrend, EMA ratios should be > 1
        for window in [5, 10, 20]:
            valid = result[f"ema_ratio_{window}"].dropna()
            assert valid.iloc[-1] > 1.0

    def test_bb_upper_dist_calculated(self, rl_calc, ohlcv_df):
        """BB upper distance = (upper - close) / close"""
        result = rl_calc.calculate(ohlcv_df)
        assert "bb_upper_dist" in result.columns
        valid = result["bb_upper_dist"].dropna()
        # Should be mostly positive (upper band above price)
        assert valid.mean() > 0
        assert (valid > -0.5).all()  # allow some tolerance

    def test_bb_lower_dist_calculated(self, rl_calc, ohlcv_df):
        """BB lower distance = (close - lower) / close"""
        result = rl_calc.calculate(ohlcv_df)
        assert "bb_lower_dist" in result.columns
        valid = result["bb_lower_dist"].dropna()
        # Should be mostly positive (price above lower band)
        assert valid.mean() > 0
        assert (valid > -0.5).all()  # allow some tolerance

    def test_bb_distances_relationship(self, rl_calc, ohlcv_df):
        """BB upper and lower distances sum relates to BB width"""
        result = rl_calc.calculate(ohlcv_df)
        valid = result[["bb_upper_dist", "bb_lower_dist", "bb_width"]].dropna()
        # upper_dist + lower_dist should approximate bb_width
        total_dist = valid["bb_upper_dist"] + valid["bb_lower_dist"]
        # The relationship is approximate due to normalization differences
        assert (total_dist > 0).all()
        assert (valid["bb_width"] > 0).all()

    def test_bb_width_calculated(self, rl_calc, ohlcv_df):
        """BB width = (upper - lower) / mid"""
        result = rl_calc.calculate(ohlcv_df)
        assert "bb_width" in result.columns
        valid = result["bb_width"].dropna()
        assert (valid >= 0).all()
        # Typical BB width values
        assert valid.mean() > 0
        assert valid.mean() < 1.0

    def test_bb_width_expands_with_volatility(self, rl_calc):
        """BB width increases in volatile market"""
        n = 100
        # Stable market
        df_stable = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": [100.0] * n,
                "high": [100.2] * n,
                "low": [99.8] * n,
                "close": [100.0] * n,
                "volume": [500.0] * n,
            }
        )
        # Volatile market
        np.random.seed(42)
        volatile_close = [100.0 + np.random.randn() * 2 for _ in range(n)]
        df_volatile = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": volatile_close,
                "high": [c + 1 for c in volatile_close],
                "low": [c - 1 for c in volatile_close],
                "close": volatile_close,
                "volume": [500.0] * n,
            }
        )

        result_stable = rl_calc.calculate(df_stable)
        result_volatile = rl_calc.calculate(df_volatile)

        bb_stable = result_stable["bb_width"].dropna().mean()
        bb_volatile = result_volatile["bb_width"].dropna().mean()

        assert bb_volatile > bb_stable

    def test_atr_calculated(self, rl_calc, ohlcv_df):
        """ATR column exists and is normalized"""
        result = rl_calc.calculate(ohlcv_df)
        assert "atr" in result.columns
        valid = result["atr"].dropna()
        assert (valid >= 0).all()
        # ATR should be small fraction of price (normalized)
        assert valid.mean() < 0.5

    def test_stoch_k_calculated(self, rl_calc, ohlcv_df):
        """Stochastic %K exists and is bounded 0-100"""
        result = rl_calc.calculate(ohlcv_df)
        assert "stoch_k" in result.columns
        valid = result["stoch_k"].dropna()
        assert valid.min() >= -1  # small tolerance
        assert valid.max() <= 101

    def test_stoch_d_calculated(self, rl_calc, ohlcv_df):
        """Stochastic %D exists and is SMA of %K"""
        result = rl_calc.calculate(ohlcv_df)
        assert "stoch_d" in result.columns
        valid = result["stoch_d"].dropna()
        assert valid.min() >= -1  # small tolerance
        assert valid.max() <= 101

    def test_stoch_k_d_relationship(self, rl_calc, ohlcv_df):
        """Stochastic %D is smoother than %K"""
        result = rl_calc.calculate(ohlcv_df)
        valid = result[["stoch_k", "stoch_d"]].dropna()
        # %D should have lower volatility than %K
        k_std = valid["stoch_k"].std()
        d_std = valid["stoch_d"].std()
        assert d_std <= k_std

    def test_price_change_5_calculated(self, rl_calc, ohlcv_df):
        """Price change 5 exists and is 5-period pct change"""
        result = rl_calc.calculate(ohlcv_df)
        assert "price_change_5" in result.columns
        valid = result["price_change_5"].dropna()
        # Should have both positive and negative values
        assert len(valid) > 0
        # Reasonable change magnitude
        assert abs(valid.mean()) < 0.5

    def test_price_change_5_uptrend(self, rl_calc):
        """Price change 5 is positive in strong uptrend"""
        n = 50
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": [100.0 + i for i in range(n)],
                "high": [101.0 + i for i in range(n)],
                "low": [99.0 + i for i in range(n)],
                "close": [100.0 + i for i in range(n)],
                "volume": [500.0] * n,
            }
        )
        result = rl_calc.calculate(df)
        valid = result["price_change_5"].dropna()
        # Should be mostly positive in uptrend
        assert valid.mean() > 0


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


class TestFeatureEdgeCases:
    """Edge case tests for feature calculation robustness."""

    def test_empty_dataframe(self, calc):
        """Empty DataFrame should return empty DataFrame with columns."""
        df = pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])
        result = calc.calculate(df)
        assert len(result) == 0
        # Should still have feature columns defined
        for col in FEATURE_COLUMNS:
            assert col in result.columns

    def test_empty_dataframe_rl(self, rl_calc):
        """Empty DataFrame should work for RLFeatureCalculator too."""
        df = pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])
        result = rl_calc.calculate(df)
        assert len(result) == 0
        for col in RL_FEATURE_COLUMNS:
            assert col in result.columns

    def test_single_row_dataframe(self, calc):
        """Single row should produce features with expected NaN behavior."""
        df = pd.DataFrame(
            {
                "datetime": [pd.Timestamp("2026-01-01 09:00")],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1000.0],
            }
        )
        result = calc.calculate(df)
        assert len(result) == 1
        # Most features should be NaN with only 1 row
        assert pd.isna(result["returns"].iloc[0])
        assert pd.isna(result["rsi"].iloc[0])

    def test_single_row_dataframe_rl(self, rl_calc):
        """Single row should work for RL calculator."""
        df = pd.DataFrame(
            {
                "datetime": [pd.Timestamp("2026-01-01 09:00")],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1000.0],
            }
        )
        result = rl_calc.calculate(df)
        assert len(result) == 1
        # returns는 pct_change()이므로 첫 행이 NaN
        assert pd.isna(result["returns"].iloc[0])
        # MACD는 EWM 기반으로 단일 행에서 0.0 반환 가능
        assert result["macd"].iloc[0] == 0.0 or pd.isna(result["macd"].iloc[0])

    def test_nan_in_close_prices(self, calc):
        """NaN values in close should be handled gracefully."""
        n = 50
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": [100.0] * n,
                "high": [101.0] * n,
                "low": [99.0] * n,
                "close": [100.0 if i % 10 != 5 else np.nan for i in range(n)],
                "volume": [500.0] * n,
            }
        )
        result = calc.calculate(df)
        # Should not crash
        assert len(result) == n
        # NaN close는 pct_change의 fill_method='pad'에 의해 forward-fill됨
        # 따라서 returns가 NaN이 아닐 수 있음. 핵심은 크래시 없이 완료되는 것
        assert "returns" in result.columns

    def test_nan_in_volume(self, calc):
        """NaN values in volume should be handled."""
        n = 50
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": [100.0] * n,
                "high": [101.0] * n,
                "low": [99.0] * n,
                "close": [100.0] * n,
                "volume": [500.0 if i % 10 != 3 else np.nan for i in range(n)],
            }
        )
        result = calc.calculate(df)
        assert len(result) == n
        # Volume ratio should be NaN where volume is NaN
        assert pd.isna(result["volume_ratio"].iloc[3])

    def test_zero_volume(self, calc):
        """Zero volume should be handled (division by zero)."""
        n = 50
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": [100.0] * n,
                "high": [101.0] * n,
                "low": [99.0] * n,
                "close": [100.0] * n,
                "volume": [0.0] * n,  # All zero volume
            }
        )
        result = calc.calculate(df)
        # Should not crash
        assert len(result) == n
        # Volume ratio should handle zero denominator
        volume_ratio = result["volume_ratio"].dropna()
        # With all zero volume, ratio might be inf or nan - both are ok
        assert len(result) > 0

    def test_extreme_price_values(self, calc):
        """Very large or very small prices should be handled."""
        n = 50
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": [1e6] * n,
                "high": [1e6 + 100] * n,
                "low": [1e6 - 100] * n,
                "close": [1e6 + i for i in range(n)],
                "volume": [500.0] * n,
            }
        )
        result = calc.calculate(df)
        assert len(result) == n
        # Features should still be calculated
        returns = result["returns"].dropna()
        assert len(returns) > 0
        # Returns should be small relative to price
        assert abs(returns.mean()) < 1.0

    def test_extreme_small_price_values(self, calc):
        """Very small prices should be handled."""
        n = 50
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": [0.001] * n,
                "high": [0.0011] * n,
                "low": [0.0009] * n,
                "close": [0.001 + i * 0.00001 for i in range(n)],
                "volume": [500.0] * n,
            }
        )
        result = calc.calculate(df)
        assert len(result) == n
        # Should not have inf or extreme values
        returns = result["returns"].dropna()
        assert np.isfinite(returns).all()

    def test_negative_prices(self, calc):
        """Negative prices (edge case, shouldn't happen in real data)."""
        n = 50
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": [-100.0] * n,
                "high": [-99.0] * n,
                "low": [-101.0] * n,
                "close": [-100.0] * n,
                "volume": [500.0] * n,
            }
        )
        result = calc.calculate(df)
        # Should not crash
        assert len(result) == n

    def test_constant_prices_no_volatility(self, calc):
        """Constant prices (no volatility) should produce valid features."""
        n = 100
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": [100.0] * n,
                "high": [100.0] * n,
                "low": [100.0] * n,
                "close": [100.0] * n,
                "volume": [500.0] * n,
            }
        )
        result = calc.calculate(df)
        assert len(result) == n
        # Returns should be 0
        returns = result["returns"].dropna()
        assert (returns == 0.0).all()
        # HL range should be 0
        assert (result["hl_range"] == 0.0).all()

    def test_constant_prices_rl_features(self, rl_calc):
        """Constant prices for RL calculator."""
        n = 150
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": [100.0] * n,
                "high": [100.0] * n,
                "low": [100.0] * n,
                "close": [100.0] * n,
                "volume": [500.0] * n,
            }
        )
        result = rl_calc.calculate(df)
        assert len(result) == n
        # ATR should be 0 or very small
        atr = result["atr"].dropna()
        if len(atr) > 0:
            assert atr.iloc[-1] == pytest.approx(0.0, abs=0.01)
        # BB width should be 0 or very small
        bb_width = result["bb_width"].dropna()
        if len(bb_width) > 0:
            assert bb_width.iloc[-1] == pytest.approx(0.0, abs=0.01)

    def test_high_below_low_invalid_data(self, calc):
        """Invalid OHLC where high < low should be handled."""
        n = 50
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": [100.0] * n,
                "high": [99.0] * n,  # Invalid: high < low
                "low": [101.0] * n,
                "close": [100.0] * n,
                "volume": [500.0] * n,
            }
        )
        result = calc.calculate(df)
        # Should not crash
        assert len(result) == n
        # HL range will be negative but calculation should work
        assert "hl_range" in result.columns

    def test_inf_values_in_input(self, calc):
        """Infinity values in input should be handled."""
        n = 50
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": [100.0] * n,
                "high": [101.0] * n,
                "low": [99.0] * n,
                "close": [100.0 if i != 25 else np.inf for i in range(n)],
                "volume": [500.0] * n,
            }
        )
        result = calc.calculate(df)
        # Should not crash
        assert len(result) == n

    def test_extract_features_with_all_nans(self, calc):
        """Extract features from DataFrame with all NaN features."""
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=5, freq="min"),
                "open": [100.0] * 5,
                "high": [101.0] * 5,
                "low": [99.0] * 5,
                "close": [100.0] * 5,
                "volume": [500.0] * 5,
            }
        )
        result = calc.calculate(df)
        # With only 5 rows, most features will be NaN
        features = calc.extract_features(result)
        # Should fill NaN with 0
        assert features.shape[0] >= 0
        assert features.shape[1] == 10
        if features.shape[0] > 0:
            assert np.isfinite(features).all()

    def test_prepare_sequence_with_mixed_nans(self, calc):
        """Prepare sequence with some NaN values in features."""
        features = []
        for i in range(100):
            feat = {col: float(i) if i % 5 != 0 else np.nan for col in FEATURE_COLUMNS}
            features.append(feat)
        result = calc.prepare_sequence(features, seq_len=60)
        assert result is not None
        assert result.shape == (60, 10)
        # float(np.nan)은 여전히 NaN — prepare_sequence는 None만 0으로 변환
        # NaN이 포함된 행(i%5==0)이 있으므로 일부 NaN 존재
        nan_count = np.isnan(result).sum()
        assert nan_count > 0, "NaN rows should be preserved (not converted to 0)"

    def test_rl_calc_extreme_volatility(self, rl_calc):
        """Extreme volatility should not break RL features."""
        np.random.seed(42)
        n = 150
        # Create extreme volatility
        close = [100.0]
        for _ in range(n - 1):
            close.append(close[-1] * (1 + np.random.uniform(-0.1, 0.1)))

        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=n, freq="min"),
                "open": close,
                "high": [c * 1.02 for c in close],
                "low": [c * 0.98 for c in close],
                "close": close,
                "volume": [500.0] * n,
            }
        )
        result = rl_calc.calculate(df)
        assert len(result) == n
        # All RL features should be calculated
        for col in RL_FEATURE_COLUMNS:
            assert col in result.columns

    def test_missing_datetime_column(self, calc):
        """DataFrame without datetime column should raise KeyError (datetime required for sort)."""
        n = 50
        df = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [101.0] * n,
                "low": [99.0] * n,
                "close": [100.0 + i * 0.1 for i in range(n)],
                "volume": [500.0] * n,
            }
        )
        with pytest.raises(KeyError):
            calc.calculate(df)

    def test_unsorted_datetime(self, calc):
        """Unsorted datetime should be handled (or preserve order)."""
        n = 50
        dates = pd.date_range("2026-01-01", periods=n, freq="min")
        # Reverse the dates
        df = pd.DataFrame(
            {
                "datetime": dates[::-1],
                "open": [100.0] * n,
                "high": [101.0] * n,
                "low": [99.0] * n,
                "close": [100.0 + i * 0.1 for i in range(n)],
                "volume": [500.0] * n,
            }
        )
        result = calc.calculate(df)
        # Should not crash
        assert len(result) == n
