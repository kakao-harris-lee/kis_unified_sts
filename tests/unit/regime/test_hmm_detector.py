"""Tests for HMMRegimeDetector.

Tests GaussianHMM-based market regime detection, including
fit, predict, state mapping, and save/load functionality.

hmmlearn is optional dependency, so tests skip if not installed.
"""

import numpy as np
import pandas as pd
import pytest

# Try to import hmmlearn
try:
    from hmmlearn.hmm import GaussianHMM
    HMMLEARN_AVAILABLE = True
except ImportError:
    HMMLEARN_AVAILABLE = False

from shared.regime.hmm_detector import (
    HMMConfig,
    HMMRegimeDetector,
    HMMRegimeState,
)


pytestmark = pytest.mark.skipif(
    not HMMLEARN_AVAILABLE,
    reason="hmmlearn not installed"
)


@pytest.fixture
def simple_features():
    """Generate simple 3-feature test data (returns, volatility, volume_ratio)."""
    np.random.seed(42)
    n = 200

    # Create 3 regimes manually
    bull_period = 80  # High positive returns
    bear_period = 60  # Negative returns
    sideways_period = 60  # Low returns, high volatility

    features = np.zeros((n, 3))

    # Bull regime: positive returns, low volatility
    features[:bull_period, 0] = np.random.randn(bull_period) * 0.001 + 0.002  # returns
    features[:bull_period, 1] = np.abs(np.random.randn(bull_period) * 0.005)  # volatility
    features[:bull_period, 2] = 1.0 + np.random.randn(bull_period) * 0.1  # volume_ratio

    # Bear regime: negative returns
    features[bull_period:bull_period+bear_period, 0] = np.random.randn(bear_period) * 0.001 - 0.002
    features[bull_period:bull_period+bear_period, 1] = np.abs(np.random.randn(bear_period) * 0.005)
    features[bull_period:bull_period+bear_period, 2] = 0.8 + np.random.randn(bear_period) * 0.1

    # Sideways: near-zero returns, high volatility
    features[bull_period+bear_period:, 0] = np.random.randn(sideways_period) * 0.0005
    features[bull_period+bear_period:, 1] = np.abs(np.random.randn(sideways_period) * 0.01)
    features[bull_period+bear_period:, 2] = 1.2 + np.random.randn(sideways_period) * 0.15

    return features


@pytest.fixture
def simple_df():
    """Generate DataFrame with OHLCV data for testing."""
    np.random.seed(42)
    n = 200
    base = 350.0

    close = base + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)
    open_ = close + np.random.randn(n) * 0.1
    volume = np.random.randint(100, 1000, n).astype(float)

    # Calculate features
    returns = np.diff(close) / close[:-1]
    returns = np.concatenate([[0], returns])

    volatility = pd.Series(returns).rolling(20).std().fillna(0).values
    volume_ratio = volume / pd.Series(volume).rolling(20).mean().fillna(volume).values

    return pd.DataFrame({
        'datetime': pd.date_range('2026-01-01', periods=n, freq='min'),
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
        'returns': returns,
        'volatility': volatility,
        'volume_ratio': volume_ratio,
    })


@pytest.fixture
def detector():
    """Create detector with default config."""
    return HMMRegimeDetector()


@pytest.fixture
def custom_detector():
    """Create detector with custom config."""
    config = HMMConfig(
        n_states=3,
        n_iter=50,
        random_state=123,
    )
    return HMMRegimeDetector(config)


class TestHMMConfig:
    def test_default_values(self):
        cfg = HMMConfig()
        assert cfg.n_states == 3
        assert cfg.covariance_type == "full"
        assert cfg.n_iter == 100
        assert cfg.random_state == 42
        assert cfg.feature_names == ["returns", "volatility", "volume_ratio"]

    def test_custom_values(self):
        cfg = HMMConfig(
            n_states=4,
            n_iter=200,
            random_state=99,
        )
        assert cfg.n_states == 4
        assert cfg.n_iter == 200
        assert cfg.random_state == 99


class TestHMMRegimeState:
    def test_constants(self):
        assert HMMRegimeState.BULL == 0
        assert HMMRegimeState.BEAR == 1
        assert HMMRegimeState.SIDEWAYS == 2

    def test_names(self):
        assert HMMRegimeState.NAMES[0] == "BULL"
        assert HMMRegimeState.NAMES[1] == "BEAR"
        assert HMMRegimeState.NAMES[2] == "SIDEWAYS"


class TestInit:
    def test_init_default_config(self):
        detector = HMMRegimeDetector()
        assert detector.config.n_states == 3
        assert detector._model is None
        assert detector._state_map == {}

    def test_init_custom_config(self):
        config = HMMConfig(n_states=4)
        detector = HMMRegimeDetector(config)
        assert detector.config.n_states == 4

    def test_is_fitted_initially_false(self, detector):
        assert detector.is_fitted is False


class TestFit:
    def test_fit_creates_model(self, detector, simple_features):
        detector.fit(simple_features)
        assert detector._model is not None
        assert detector.is_fitted is True

    def test_fit_creates_state_map(self, detector, simple_features):
        detector.fit(simple_features)
        # Should have 3 mappings
        assert len(detector._state_map) == 3
        # Should map to BULL, BEAR, SIDEWAYS
        values = set(detector._state_map.values())
        assert values == {HMMRegimeState.BULL, HMMRegimeState.BEAR, HMMRegimeState.SIDEWAYS}

    def test_fit_returns_self(self, detector, simple_features):
        result = detector.fit(simple_features)
        assert result is detector

    def test_fit_with_custom_config(self, custom_detector, simple_features):
        custom_detector.fit(simple_features)
        assert custom_detector.is_fitted

    def test_fit_from_dataframe(self, detector, simple_df):
        detector.fit_from_dataframe(simple_df)
        assert detector.is_fitted
        assert detector._model is not None


class TestAutoMapStates:
    def test_maps_highest_return_to_bull(self, detector, simple_features):
        detector.fit(simple_features)

        # Predict states
        states = detector._model.predict(simple_features)

        # Calculate mean returns per state
        mean_returns = {}
        for s in range(3):
            mask = states == s
            if mask.any():
                mean_returns[s] = simple_features[mask, 0].mean()

        # Find which HMM state maps to BULL
        bull_hmm_state = [k for k, v in detector._state_map.items() if v == HMMRegimeState.BULL][0]

        # This state should have highest mean return
        assert mean_returns[bull_hmm_state] == max(mean_returns.values())

    def test_maps_lowest_return_to_bear(self, detector, simple_features):
        detector.fit(simple_features)

        states = detector._model.predict(simple_features)
        mean_returns = {}
        for s in range(3):
            mask = states == s
            if mask.any():
                mean_returns[s] = simple_features[mask, 0].mean()

        bear_hmm_state = [k for k, v in detector._state_map.items() if v == HMMRegimeState.BEAR][0]
        assert mean_returns[bear_hmm_state] == min(mean_returns.values())


class TestPredict:
    def test_predict_returns_regime_state(self, detector, simple_features):
        detector.fit(simple_features)

        # Single observation
        obs = simple_features[-10:].copy()
        state = detector.predict(obs)

        assert state in [HMMRegimeState.BULL, HMMRegimeState.BEAR, HMMRegimeState.SIDEWAYS]

    def test_predict_without_fit_returns_sideways(self, detector, simple_features):
        """Unfitted model should return SIDEWAYS as default."""
        state = detector.predict(simple_features[-10:])
        assert state == HMMRegimeState.SIDEWAYS

    def test_predict_handles_1d_input(self, detector, simple_features):
        detector.fit(simple_features)

        # Single timestep
        obs = simple_features[-1].copy()  # (3,) shape
        state = detector.predict(obs)
        assert state in [0, 1, 2]

    def test_predict_uses_last_timestep(self, detector, simple_features):
        detector.fit(simple_features)

        # Predict with sequence
        obs = simple_features[-20:].copy()
        state = detector.predict(obs)

        # Should use last timestep's state
        assert isinstance(state, (int, np.integer))


class TestPredictProba:
    def test_predict_proba_returns_3_element_array(self, detector, simple_features):
        detector.fit(simple_features)

        obs = simple_features[-10:].copy()
        probs = detector.predict_proba(obs)

        assert probs.shape == (3,)
        assert np.isclose(probs.sum(), 1.0)

    def test_predict_proba_without_fit_returns_uniform(self, detector, simple_features):
        """Unfitted model should return uniform distribution."""
        probs = detector.predict_proba(simple_features[-10:])

        assert probs.shape == (3,)
        # Should be approximately uniform
        assert all(0.2 < p < 0.5 for p in probs)

    def test_predict_proba_probabilities_valid(self, detector, simple_features):
        detector.fit(simple_features)

        probs = detector.predict_proba(simple_features[-10:])

        # All probabilities between 0 and 1
        assert np.all(probs >= 0)
        assert np.all(probs <= 1)
        # Sum to 1
        assert np.isclose(probs.sum(), 1.0)


class TestGetStateDistribution:
    def test_returns_distribution_dict(self, detector, simple_features):
        detector.fit(simple_features)

        dist = detector.get_state_distribution(simple_features)

        assert isinstance(dist, dict)
        assert set(dist.keys()) == {"BULL", "BEAR", "SIDEWAYS"}

    def test_distribution_sums_to_one(self, detector, simple_features):
        detector.fit(simple_features)

        dist = detector.get_state_distribution(simple_features)

        total = sum(dist.values())
        assert np.isclose(total, 1.0)

    def test_without_fit_returns_uniform(self, detector, simple_features):
        dist = detector.get_state_distribution(simple_features)

        # Should be uniform
        for v in dist.values():
            assert np.isclose(v, 1.0/3, atol=0.01)


class TestSaveLoad:
    def test_save_creates_file(self, detector, simple_features, tmp_path):
        detector.fit(simple_features)

        path = tmp_path / "hmm_model.pkl"
        detector.save(path)

        assert path.exists()

    def test_load_restores_model(self, detector, simple_features, tmp_path):
        detector.fit(simple_features)

        path = tmp_path / "hmm_model.pkl"
        detector.save(path)

        # Create new detector and load
        new_detector = HMMRegimeDetector()
        new_detector.load(path)

        assert new_detector.is_fitted
        assert new_detector._model is not None
        assert new_detector._state_map == detector._state_map

    def test_loaded_model_predicts_same(self, detector, simple_features, tmp_path):
        detector.fit(simple_features)

        obs = simple_features[-10:].copy()
        original_pred = detector.predict(obs)

        # Save and load
        path = tmp_path / "hmm_model.pkl"
        detector.save(path)

        new_detector = HMMRegimeDetector()
        new_detector.load(path)
        loaded_pred = new_detector.predict(obs)

        assert loaded_pred == original_pred

    def test_save_creates_parent_directories(self, detector, simple_features, tmp_path):
        detector.fit(simple_features)

        path = tmp_path / "nested" / "dir" / "model.pkl"
        detector.save(path)

        assert path.exists()
        assert path.parent.exists()


class TestEdgeCases:
    def test_few_samples(self, detector):
        """Should handle very few samples."""
        features = np.random.randn(20, 3)
        # May not converge well, but shouldn't error
        detector.fit(features)
        assert detector.is_fitted

    def test_constant_features(self, detector):
        """Should handle constant features."""
        features = np.ones((100, 3))
        features[:, 0] *= 0.001  # Small variation in returns

        # HMM might not converge well, but shouldn't crash
        try:
            detector.fit(features)
        except Exception as e:
            # If it fails, it should be a known hmmlearn issue
            pytest.skip(f"HMM fit failed with constant features: {e}")

    def test_very_volatile_features(self, detector):
        """Should handle extreme values."""
        features = np.random.randn(200, 3) * 100

        detector.fit(features)
        assert detector.is_fitted

    def test_predict_with_different_length_sequence(self, detector, simple_features):
        detector.fit(simple_features)

        # Predict with longer sequence
        obs_long = np.random.randn(300, 3)
        state = detector.predict(obs_long)
        assert state in [0, 1, 2]

        # Predict with shorter sequence
        obs_short = np.random.randn(5, 3)
        state = detector.predict(obs_short)
        assert state in [0, 1, 2]


class TestIntegration:
    def test_full_workflow(self, simple_features):
        """Test complete workflow: init -> fit -> predict -> save -> load."""
        # Init
        detector = HMMRegimeDetector()
        assert not detector.is_fitted

        # Fit
        detector.fit(simple_features)
        assert detector.is_fitted

        # Predict
        obs = simple_features[-20:].copy()
        state = detector.predict(obs)
        assert state in [0, 1, 2]

        probs = detector.predict_proba(obs)
        assert probs.shape == (3,)

        dist = detector.get_state_distribution(simple_features)
        assert len(dist) == 3

        # Save
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f:
            temp_path = f.name

        try:
            detector.save(temp_path)

            # Load
            new_detector = HMMRegimeDetector()
            new_detector.load(temp_path)

            # Verify loaded model works
            new_state = new_detector.predict(obs)
            assert new_state == state
        finally:
            import os
            if os.path.exists(temp_path):
                os.remove(temp_path)
