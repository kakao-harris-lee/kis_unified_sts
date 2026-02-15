"""Tests for TFT dataset.

Tests TFTDataset length, __getitem__ shape, target return signs,
time feature ranges, and edge cases.
"""

import math

import numpy as np
import pytest
import torch

from shared.ml.tft.dataset import TFTDataset, compute_time_features


@pytest.fixture
def sample_day_data():
    """Generate one day of sample data (200 bars)."""
    n_bars = 200
    np.random.seed(42)
    features = np.random.randn(n_bars, 25).astype(np.float32)

    # Simulate realistic close prices (random walk around 350)
    close = 350.0 + np.cumsum(np.random.randn(n_bars) * 0.1)
    prices = np.column_stack([
        close - 0.05,  # open
        close + np.abs(np.random.randn(n_bars) * 0.05),  # high
        close - np.abs(np.random.randn(n_bars) * 0.05),  # low
        close,  # close
    ]).astype(np.float32)

    return features, prices


@pytest.fixture
def multi_day_data(sample_day_data):
    """3 days of sample data."""
    feat, prices = sample_day_data
    return [feat.copy() for _ in range(3)], [prices.copy() for _ in range(3)]


class TestComputeTimeFeatures:
    def test_output_shape(self):
        features = compute_time_features(405)
        assert features.shape == (405, 3)
        assert features.dtype == np.float32

    def test_hour_norm_range(self):
        features = compute_time_features(405)
        hour_norm = features[:, 0]
        assert hour_norm[0] == pytest.approx(0.0, abs=0.01)
        assert hour_norm[-1] <= 1.0
        assert np.all(hour_norm >= 0.0)

    def test_sin_cos_range(self):
        features = compute_time_features(405)
        sin_prog = features[:, 1]
        cos_prog = features[:, 2]
        assert np.all(sin_prog >= -1.0)
        assert np.all(sin_prog <= 1.0)
        assert np.all(cos_prog >= -1.0)
        assert np.all(cos_prog <= 1.0)

    def test_sin_cos_unit_circle(self):
        """sin^2 + cos^2 should be ~1."""
        features = compute_time_features(100)
        unit = features[:, 1] ** 2 + features[:, 2] ** 2
        np.testing.assert_allclose(unit, 1.0, atol=1e-5)


class TestTFTDataset:
    def test_dataset_length(self, multi_day_data):
        features, prices = multi_day_data
        dataset = TFTDataset(features, prices, lookback=10, horizons=[1, 5, 15])
        # Each day: 200 bars, valid range: [10, 200-15) = 175 samples per day
        expected_per_day = 200 - 10 - 15
        assert len(dataset) == expected_per_day * 3

    def test_getitem_shapes(self, multi_day_data):
        features, prices = multi_day_data
        dataset = TFTDataset(features, prices, lookback=10, horizons=[1, 5, 15])

        x, y = dataset[0]
        assert x.shape == (10, 28)  # lookback x (25 features + 3 time)
        assert y.shape == (3,)  # 3 horizons

    def test_getitem_dtypes(self, multi_day_data):
        features, prices = multi_day_data
        dataset = TFTDataset(features, prices, lookback=10, horizons=[1, 5, 15])

        x, y = dataset[0]
        assert x.dtype == torch.float32
        assert y.dtype == torch.float32

    def test_target_return_values(self, sample_day_data):
        """Target returns should match manual calculation."""
        features, prices = sample_day_data
        dataset = TFTDataset([features], [prices], lookback=10, horizons=[1, 5])

        # Get the first sample
        x, y = dataset[0]
        close = prices[:, 3].astype(np.float64)
        t = 10  # first valid index

        expected_ret_1m = (close[t + 1] - close[t]) / close[t]
        expected_ret_5m = (close[t + 5] - close[t]) / close[t]

        assert y[0].item() == pytest.approx(expected_ret_1m, abs=1e-5)
        assert y[1].item() == pytest.approx(expected_ret_5m, abs=1e-5)

    def test_time_features_appended(self, multi_day_data):
        """Last 3 columns should be time features."""
        features, prices = multi_day_data
        dataset = TFTDataset(features, prices, lookback=10, horizons=[1, 5, 15])

        x, _ = dataset[0]
        # Time features are columns 25, 26, 27
        time_feats = x[:, 25:28]

        # hour_norm should be >= 0
        assert torch.all(time_feats[:, 0] >= 0)
        # sin/cos should be in [-1, 1]
        assert torch.all(time_feats[:, 1] >= -1.01)
        assert torch.all(time_feats[:, 1] <= 1.01)

    def test_empty_dataset_with_short_days(self):
        """Days shorter than lookback + max_horizon produce 0 samples."""
        short_feat = np.random.randn(20, 25).astype(np.float32)
        short_prices = np.random.randn(20, 4).astype(np.float32)
        short_prices[:, 3] = np.abs(short_prices[:, 3]) + 1.0  # positive close

        dataset = TFTDataset(
            [short_feat], [short_prices], lookback=60, horizons=[1, 5, 15]
        )
        assert len(dataset) == 0

    def test_single_horizon(self, multi_day_data):
        """Works with a single horizon."""
        features, prices = multi_day_data
        dataset = TFTDataset(features, prices, lookback=10, horizons=[5])

        x, y = dataset[0]
        assert x.shape == (10, 28)
        assert y.shape == (1,)


class TestTFTDatasetClassification:
    """Classification mode dataset tests."""

    def test_classification_targets_are_binary(self, multi_day_data):
        """Classification targets should be 0.0 or 1.0."""
        features, prices = multi_day_data
        dataset = TFTDataset(
            features, prices, lookback=10, horizons=[1, 5, 15],
            mode="classification",
        )

        for i in range(min(50, len(dataset))):
            _, y = dataset[i]
            for val in y:
                assert val.item() in (0.0, 1.0), f"Target {val} not binary at idx {i}"

    def test_classification_target_shape(self, multi_day_data):
        """Classification targets have same shape as regression."""
        features, prices = multi_day_data
        dataset = TFTDataset(
            features, prices, lookback=10, horizons=[1, 5, 15],
            mode="classification",
        )

        x, y = dataset[0]
        assert x.shape == (10, 28)
        assert y.shape == (3,)
        assert y.dtype == torch.float32

    def test_classification_threshold(self, sample_day_data):
        """Positive threshold should require larger returns for UP label."""
        features, prices = sample_day_data

        ds_zero = TFTDataset(
            [features], [prices], lookback=10, horizons=[1],
            mode="classification", classification_threshold=0.0,
        )
        ds_high = TFTDataset(
            [features], [prices], lookback=10, horizons=[1],
            mode="classification", classification_threshold=0.01,
        )

        # With high threshold, fewer UP labels expected
        ups_zero = sum(ds_zero[i][1][0].item() for i in range(len(ds_zero)))
        ups_high = sum(ds_high[i][1][0].item() for i in range(len(ds_high)))
        assert ups_high <= ups_zero

    def test_classification_same_length_as_regression(self, multi_day_data):
        """Classification and regression modes should produce same sample count."""
        features, prices = multi_day_data
        ds_reg = TFTDataset(
            features, prices, lookback=10, horizons=[1, 5, 15],
            mode="regression",
        )
        ds_cls = TFTDataset(
            features, prices, lookback=10, horizons=[1, 5, 15],
            mode="classification",
        )
        assert len(ds_reg) == len(ds_cls)
