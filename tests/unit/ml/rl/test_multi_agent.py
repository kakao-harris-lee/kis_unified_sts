"""Unit tests for shared/ml/rl/multi_agent.py (RegimeAwareAgent)"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest

from shared.ml.rl.env import Action
from shared.ml.rl.multi_agent import RegimeAwareAgent
from shared.regime.hmm_detector import HMMRegimeState

# ============================================================================
# Test config dict to mock ConfigLoader
# ============================================================================

TEST_CONFIG = {
    "env": {
        "initial_balance": 100_000_000,
        "commission_rate": 0.00003,
        "tick_size": 0.05,
        "tick_value": 250_000,
        "contract_multiplier": 250_000,
        "max_contracts": 1,
        "slippage": 0.0,
        "margin_rate": 0.15,
        "n_market_features": 25,
        "n_position_features": 6,
    },
    "reward": {
        "w_profit": 10.0,
        "w_cost": 0.3,
        "w_risk": 0.0,
        "w_mtm": 0.0,
        "inaction_penalty": 0.0,
        "reward_scale": 100.0,
        "max_loss": -5_000_000,
        "loss_penalty_coeff": 2.0,
    },
    "hmm": {
        "n_states": 3,
        "covariance_type": "full",
        "n_iter": 100,
        "random_state": 42,
    },
    "multi_agent": {
        "algo": "mppo",
        "confidence_threshold": 0.5,
        "min_days_per_regime": 5,
    },
    "mppo": {
        "learning_rate": 0.0001,
        "gamma": 0.999,
        "total_timesteps": 100,
    },
    "data": {
        "source": "clickhouse",
        "database": "kospi",
        "table": "kospi200f_1m",
        "symbol": "101S6000",
        "train_ratio": 0.8,
        "min_bars_per_day": 300,
    },
    "training": {
        "eval_freq": 1000,
        "save_dir": "/tmp/test_multi_agent/",
    },
}


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_config():
    """Mock ConfigLoader to return TEST_CONFIG"""
    with patch("shared.ml.rl.multi_agent.ConfigLoader") as mock_loader:
        mock_loader.load.return_value = TEST_CONFIG
        yield mock_loader


@pytest.fixture
def mock_hmm():
    """Mock HMMRegimeDetector"""
    hmm = MagicMock()
    hmm.is_fitted = True
    hmm.predict.return_value = HMMRegimeState.SIDEWAYS
    hmm.predict_proba.return_value = np.array([[0.1, 0.2, 0.7]])  # SIDEWAYS dominant
    return hmm


@pytest.fixture
def mock_env_config():
    """Mock RLEnvConfig.from_yaml"""
    with patch("shared.ml.rl.multi_agent.RLEnvConfig") as mock_cls:
        mock_cls.from_yaml.return_value = MagicMock()
        yield mock_cls


@pytest.fixture
def agent(mock_config, mock_env_config, mock_hmm, tmp_path):
    """Create RegimeAwareAgent with mocked dependencies"""
    # Override save_dir to use tmp_path
    cfg = TEST_CONFIG.copy()
    cfg["training"]["save_dir"] = str(tmp_path)
    mock_config.load.return_value = cfg

    # Create agent with injected HMM
    with patch("shared.ml.rl.multi_agent.HMMRegimeDetector") as mock_hmm_cls:
        mock_hmm_cls.from_yaml.return_value = mock_hmm
        agent = RegimeAwareAgent(config_path="ml/rl_multi_agent.yaml", hmm_detector=mock_hmm)
        yield agent


# ============================================================================
# TestPredict: predict() method
# ============================================================================


class TestPredict:
    """Test predict() method"""

    def test_predict_no_models_loaded(self, agent):
        """No models loaded → returns Action.HOLD"""
        agent.fallback_model = None
        agent.regime_models = {}

        obs = np.zeros(31)
        action, regime = agent.predict(obs)

        assert action == Action.HOLD
        assert regime == HMMRegimeState.SIDEWAYS  # default

    def test_predict_regime_routing_high_confidence(self, agent):
        """High confidence → uses regime-specific model"""
        # Mock regime-specific model
        regime_model = MagicMock()
        regime_model.predict.return_value = (Action.LONG_ENTRY, None)
        agent.regime_models[HMMRegimeState.SIDEWAYS] = regime_model

        # Mock HMM prediction with high confidence
        agent.hmm.predict.return_value = HMMRegimeState.SIDEWAYS
        agent.hmm.predict_proba.return_value = np.array([[0.1, 0.1, 0.8]])  # 80% confidence
        agent.confidence_threshold = 0.5

        obs = np.zeros(31)
        regime_features = np.random.randn(10, 3)
        action, regime = agent.predict(obs, regime_features=regime_features)

        # Should use regime model
        assert action == Action.LONG_ENTRY
        assert regime == HMMRegimeState.SIDEWAYS
        regime_model.predict.assert_called_once()

    def test_predict_regime_routing_low_confidence(self, agent):
        """Low confidence → uses fallback model"""
        # Mock fallback model
        fallback_model = MagicMock()
        fallback_model.predict.return_value = (Action.SHORT_ENTRY, None)
        agent.fallback_model = fallback_model

        # Mock regime model (should NOT be used)
        regime_model = MagicMock()
        agent.regime_models[HMMRegimeState.BULL] = regime_model

        # Mock HMM prediction with LOW confidence
        agent.hmm.predict.return_value = HMMRegimeState.BULL
        agent.hmm.predict_proba.return_value = np.array([[0.4, 0.3, 0.3]])  # 40% confidence
        agent.confidence_threshold = 0.5

        obs = np.zeros(31)
        regime_features = np.random.randn(10, 3)
        action, regime = agent.predict(obs, regime_features=regime_features)

        # Should use fallback model
        assert action == Action.SHORT_ENTRY
        assert regime == HMMRegimeState.BULL
        fallback_model.predict.assert_called_once()
        regime_model.predict.assert_not_called()

    def test_predict_regime_features_none(self, agent):
        """regime_features=None → falls back to SIDEWAYS with 0.0 confidence"""
        # Mock fallback model
        fallback_model = MagicMock()
        fallback_model.predict.return_value = (Action.HOLD, None)
        agent.fallback_model = fallback_model

        obs = np.zeros(31)
        action, regime = agent.predict(obs, regime_features=None)

        # Should use fallback (confidence 0.0 < threshold)
        assert action == Action.HOLD
        assert regime == HMMRegimeState.SIDEWAYS
        fallback_model.predict.assert_called_once()

    def test_predict_hmm_not_fitted(self, agent):
        """HMM not fitted → uses fallback"""
        agent.hmm.is_fitted = False

        fallback_model = MagicMock()
        fallback_model.predict.return_value = (Action.LONG_ENTRY, None)
        agent.fallback_model = fallback_model

        obs = np.zeros(31)
        regime_features = np.random.randn(10, 3)
        action, regime = agent.predict(obs, regime_features=regime_features)

        assert action == Action.LONG_ENTRY
        assert regime == HMMRegimeState.SIDEWAYS
        fallback_model.predict.assert_called_once()

    def test_predict_with_action_masks(self, agent):
        """Test predict() passes action_masks to model"""
        fallback_model = MagicMock()
        fallback_model.predict.return_value = (Action.LONG_ENTRY, None)
        agent.fallback_model = fallback_model

        obs = np.zeros(31)
        masks = np.array([True, False, True, False, False])  # Only LONG_ENTRY and SHORT_ENTRY valid
        action, regime = agent.predict(obs, action_masks=masks, regime_features=None)

        # Check action_masks was passed
        fallback_model.predict.assert_called_once()
        call_kwargs = fallback_model.predict.call_args[1]
        assert "action_masks" in call_kwargs
        np.testing.assert_array_equal(call_kwargs["action_masks"], masks)

    def test_predict_typeerror_fallback(self, agent):
        """Model.predict() raises TypeError → falls back to simple predict"""
        fallback_model = MagicMock()
        # First call (with action_masks) raises TypeError
        # Second call (without action_masks) succeeds
        fallback_model.predict.side_effect = [
            TypeError("unexpected keyword"),
            (Action.HOLD, None),
        ]
        agent.fallback_model = fallback_model

        obs = np.zeros(31)
        masks = np.array([True, True, True])
        action, regime = agent.predict(obs, action_masks=masks)

        # Should retry without action_masks
        assert action == Action.HOLD
        assert fallback_model.predict.call_count == 2


# ============================================================================
# TestExtractRegimeFeatures: _extract_regime_features() method
# ============================================================================


class TestExtractRegimeFeatures:
    """Test _extract_regime_features() method"""

    def test_extract_regime_features_correct_columns(self, agent):
        """Correctly extracts returns (col 0), volatility (col 7), volume_ratio (col 6)"""
        # Create mock day data with known values
        day1 = np.random.randn(100, 25)  # 100 bars, 25 features
        day1[:, 0] = 0.01  # returns
        day1[:, 7] = 0.02  # volatility
        day1[:, 6] = 1.5   # volume_ratio

        day2 = np.random.randn(100, 25)
        day2[:, 0] = -0.005
        day2[:, 7] = 0.03
        day2[:, 6] = 0.8

        days = [day1, day2]
        features = agent._extract_regime_features(days)

        assert features.shape == (2, 3)
        np.testing.assert_almost_equal(features[0, 0], 0.01)      # day1 returns
        np.testing.assert_almost_equal(features[0, 1], 0.02)      # day1 volatility
        np.testing.assert_almost_equal(features[0, 2], 1.5)       # day1 volume_ratio
        np.testing.assert_almost_equal(features[1, 0], -0.005)    # day2 returns
        np.testing.assert_almost_equal(features[1, 1], 0.03)      # day2 volatility
        np.testing.assert_almost_equal(features[1, 2], 0.8)       # day2 volume_ratio

    def test_extract_regime_features_averaging(self, agent):
        """Correctly averages across bars within each day"""
        # Day with varying values
        day_data = np.zeros((3, 25))
        day_data[:, 0] = [0.01, 0.02, 0.03]  # returns
        day_data[:, 7] = [0.1, 0.2, 0.3]     # volatility
        day_data[:, 6] = [1.0, 2.0, 3.0]     # volume_ratio

        days = [day_data]
        features = agent._extract_regime_features(days)

        assert features.shape == (1, 3)
        np.testing.assert_almost_equal(features[0, 0], 0.02)  # mean([0.01, 0.02, 0.03])
        np.testing.assert_almost_equal(features[0, 1], 0.2)   # mean([0.1, 0.2, 0.3])
        np.testing.assert_almost_equal(features[0, 2], 2.0)   # mean([1.0, 2.0, 3.0])

    def test_extract_regime_features_empty_list(self, agent):
        """Empty days list → returns empty array"""
        days = []
        features = agent._extract_regime_features(days)

        assert features.shape[0] == 0  # Empty array


# ============================================================================
# TestGetModelClass: _get_model_class() method
# ============================================================================


class TestGetModelClass:
    """Test _get_model_class() method"""

    def test_get_model_class_mppo(self, agent):
        """algo='mppo' → returns MaskablePPO"""
        agent.config["multi_agent"]["algo"] = "mppo"

        with patch("sb3_contrib.MaskablePPO") as mock_mppo:
            cls = agent._get_model_class()
            assert cls is mock_mppo

    def test_get_model_class_sac(self, agent):
        """algo='sac' → returns SAC"""
        agent.config["multi_agent"]["algo"] = "sac"

        with patch("stable_baselines3.SAC") as mock_sac:
            cls = agent._get_model_class()
            assert cls is mock_sac

    def test_get_model_class_dqn(self, agent):
        """algo='dqn' → returns DQN"""
        agent.config["multi_agent"]["algo"] = "dqn"

        with patch("stable_baselines3.DQN") as mock_dqn:
            cls = agent._get_model_class()
            assert cls is mock_dqn

    def test_get_model_class_a2c(self, agent):
        """algo='a2c' → returns A2C"""
        agent.config["multi_agent"]["algo"] = "a2c"

        with patch("stable_baselines3.A2C") as mock_a2c:
            cls = agent._get_model_class()
            assert cls is mock_a2c

    def test_get_model_class_ppo(self, agent):
        """algo='ppo' → returns PPO"""
        agent.config["multi_agent"]["algo"] = "ppo"

        with patch("stable_baselines3.PPO") as mock_ppo:
            cls = agent._get_model_class()
            assert cls is mock_ppo

    def test_get_model_class_unknown_fallback(self, agent):
        """Unknown algo → falls back to MaskablePPO with warning"""
        agent.config["multi_agent"]["algo"] = "unknown_algo"

        with patch("sb3_contrib.MaskablePPO") as mock_mppo:
            with patch("shared.ml.rl.multi_agent.logger") as mock_logger:
                cls = agent._get_model_class()
                assert cls is mock_mppo
                mock_logger.warning.assert_called_once()
                assert "unknown_algo" in mock_logger.warning.call_args[0][0]


# ============================================================================
# TestLoadModels: load_models() method
# ============================================================================


class TestLoadModels:
    """Test load_models() method"""

    def test_load_models_all_exist(self, agent, tmp_path):
        """All model files exist → loads all models"""
        agent._save_dir = tmp_path / "multi_agent"
        agent._save_dir.mkdir(parents=True, exist_ok=True)

        # Create dummy files
        (agent._save_dir / "hmm_detector.joblib").touch()
        (agent._save_dir / "fallback.zip").touch()
        (agent._save_dir / "bull.zip").touch()
        (agent._save_dir / "bear.zip").touch()
        (agent._save_dir / "sideways.zip").touch()

        # Mock model loading
        with patch("sb3_contrib.MaskablePPO") as mock_mppo:
            mock_model = MagicMock()
            mock_mppo.load.return_value = mock_model

            agent.load_models()

            # Check HMM loaded
            agent.hmm.load.assert_called_once()

            # Check models loaded
            assert mock_mppo.load.call_count == 4  # fallback + 3 regimes
            assert agent.fallback_model == mock_model
            assert agent.regime_models[HMMRegimeState.BULL] == mock_model
            assert agent.regime_models[HMMRegimeState.BEAR] == mock_model
            assert agent.regime_models[HMMRegimeState.SIDEWAYS] == mock_model

    def test_load_models_missing_hmm(self, agent, tmp_path):
        """HMM file missing → gracefully continues without crash"""
        agent._save_dir = tmp_path / "multi_agent"
        agent._save_dir.mkdir(parents=True, exist_ok=True)

        # Only create fallback
        (agent._save_dir / "fallback.zip").touch()

        with patch("sb3_contrib.MaskablePPO") as mock_mppo:
            mock_model = MagicMock()
            mock_mppo.load.return_value = mock_model

            agent.load_models()

            # HMM load should not be called
            agent.hmm.load.assert_not_called()
            # But fallback should load
            assert agent.fallback_model == mock_model

    def test_load_models_missing_regime_uses_fallback(self, agent, tmp_path):
        """Missing regime model → uses fallback model"""
        agent._save_dir = tmp_path / "multi_agent"
        agent._save_dir.mkdir(parents=True, exist_ok=True)

        # Only create fallback and bull
        (agent._save_dir / "fallback.zip").touch()
        (agent._save_dir / "bull.zip").touch()

        with patch("sb3_contrib.MaskablePPO") as mock_mppo:
            fallback = MagicMock(name="fallback")
            bull = MagicMock(name="bull")

            def load_side_effect(path):
                if "fallback" in path:
                    return fallback
                elif "bull" in path:
                    return bull

            mock_mppo.load.side_effect = load_side_effect

            agent.load_models()

            # Fallback loaded
            assert agent.fallback_model == fallback
            # Bull loaded separately
            assert agent.regime_models[HMMRegimeState.BULL] == bull
            # Bear and Sideways should use fallback
            assert agent.regime_models[HMMRegimeState.BEAR] == fallback
            assert agent.regime_models[HMMRegimeState.SIDEWAYS] == fallback

    def test_load_models_no_files_exist(self, agent, tmp_path):
        """No model files exist → gracefully handles (no crash)"""
        agent._save_dir = tmp_path / "multi_agent"
        agent._save_dir.mkdir(parents=True, exist_ok=True)

        # No files created

        with patch("sb3_contrib.MaskablePPO") as mock_mppo:
            agent.load_models()

            # Nothing loaded
            assert agent.fallback_model is None
            assert len(agent.regime_models) == 0
            agent.hmm.load.assert_not_called()
            mock_mppo.load.assert_not_called()


# ============================================================================
# TestFallbackAssignment: Fallback model assignment in train()
# ============================================================================


class TestFallbackAssignment:
    """Test fallback model assignment when regime has too few days"""

    def test_train_regime_too_few_days_uses_fallback(self, agent, tmp_path):
        """Regime with fewer than min_days_per_regime → assigns fallback model"""
        agent._save_dir = tmp_path / "multi_agent"
        agent.min_days_per_regime = 5

        # Create minimal training data
        train_days = [np.random.randn(100, 25) for _ in range(10)]
        train_prices = [np.random.randn(100) for _ in range(10)]

        # Mock HMM to label only 2 days as BULL (< min_days_per_regime)
        def hmm_predict_side_effect(features):
            # First 2 days: BULL, rest: SIDEWAYS
            if len(features) == 1:
                idx = len(agent.hmm.predict.call_args_list) - 1
                if idx < 2:
                    return HMMRegimeState.BULL
                else:
                    return HMMRegimeState.SIDEWAYS
            return HMMRegimeState.SIDEWAYS

        agent.hmm.predict.side_effect = hmm_predict_side_effect

        # Mock trainer
        with patch.object(agent, "_save_models"):  # Prevent saving
            with patch("shared.ml.rl.trainer.RLTrainer") as mock_trainer_cls:
                mock_trainer = MagicMock()
                mock_trainer_cls.return_value = mock_trainer

                fallback_model = MagicMock(name="fallback")
                sideways_model = MagicMock(name="sideways")

                # First train call: fallback, second: sideways
                mock_trainer.train.side_effect = [fallback_model, sideways_model]

                results = agent.train(train_days, train_prices)

                # Should have trained fallback + sideways only
                assert mock_trainer.train.call_count == 2

                # BULL should use fallback (too few days)
                assert results["BULL"] == "fallback"
                assert agent.regime_models[HMMRegimeState.BULL] == fallback_model

                # SIDEWAYS should be trained (enough days)
                assert "trained" in results["SIDEWAYS"]
                assert agent.regime_models[HMMRegimeState.SIDEWAYS] == sideways_model

    def test_train_all_regimes_sufficient_days(self, agent, tmp_path):
        """All regimes have sufficient days → all trained separately"""
        agent._save_dir = tmp_path / "multi_agent"
        agent.min_days_per_regime = 3

        # Create data with 10 days total
        train_days = [np.random.randn(100, 25) for _ in range(10)]
        train_prices = [np.random.randn(100) for _ in range(10)]

        # Mock HMM to distribute days evenly across regimes
        regime_sequence = [
            HMMRegimeState.BULL,
            HMMRegimeState.BULL,
            HMMRegimeState.BULL,
            HMMRegimeState.BULL,
            HMMRegimeState.BEAR,
            HMMRegimeState.BEAR,
            HMMRegimeState.BEAR,
            HMMRegimeState.SIDEWAYS,
            HMMRegimeState.SIDEWAYS,
            HMMRegimeState.SIDEWAYS,
        ]

        predict_calls = []

        def hmm_predict_side_effect(features):
            call_idx = len(predict_calls)
            predict_calls.append(call_idx)
            if call_idx < len(regime_sequence):
                return regime_sequence[call_idx]
            return HMMRegimeState.SIDEWAYS

        agent.hmm.predict.side_effect = hmm_predict_side_effect

        with patch.object(agent, "_save_models"):  # Prevent saving
            with patch("shared.ml.rl.trainer.RLTrainer") as mock_trainer_cls:
                mock_trainer = MagicMock()
                mock_trainer_cls.return_value = mock_trainer

                fallback = MagicMock(name="fallback")
                bull = MagicMock(name="bull")
                bear = MagicMock(name="bear")
                sideways = MagicMock(name="sideways")

                mock_trainer.train.side_effect = [fallback, bull, bear, sideways]

                results = agent.train(train_days, train_prices)

                # Should train fallback + 3 regimes
                assert mock_trainer.train.call_count == 4

                # All regimes trained
                assert "trained" in results["BULL"]
                assert "trained" in results["BEAR"]
                assert "trained" in results["SIDEWAYS"]

                assert agent.regime_models[HMMRegimeState.BULL] == bull
                assert agent.regime_models[HMMRegimeState.BEAR] == bear
                assert agent.regime_models[HMMRegimeState.SIDEWAYS] == sideways


# ============================================================================
# TestInitialization: __init__ and from_yaml
# ============================================================================


class TestInitialization:
    """Test initialization and class methods"""

    def test_init_default_parameters(self, mock_config, mock_env_config):
        """Test default parameter extraction from config"""
        with patch("shared.ml.rl.multi_agent.HMMRegimeDetector") as mock_hmm_cls:
            mock_hmm = MagicMock()
            mock_hmm_cls.from_yaml.return_value = mock_hmm

            agent = RegimeAwareAgent(config_path="ml/rl_multi_agent.yaml")

            assert agent.confidence_threshold == 0.5
            assert agent.min_days_per_regime == 5
            assert agent.fallback_model is None
            assert agent.regime_models == {}

    def test_from_yaml_classmethod(self, mock_config, mock_env_config):
        """Test from_yaml() class method"""
        with patch("shared.ml.rl.multi_agent.HMMRegimeDetector") as mock_hmm_cls:
            mock_hmm_cls.from_yaml.return_value = MagicMock()

            agent = RegimeAwareAgent.from_yaml("ml/rl_multi_agent.yaml")

            assert isinstance(agent, RegimeAwareAgent)
            mock_config.load.assert_called_once_with("ml/rl_multi_agent.yaml")

    def test_init_custom_hmm_detector(self, mock_config, mock_env_config):
        """Test initialization with custom HMM detector"""
        custom_hmm = MagicMock()

        agent = RegimeAwareAgent(
            config_path="ml/rl_multi_agent.yaml",
            hmm_detector=custom_hmm,
        )

        assert agent.hmm is custom_hmm

    def test_save_dir_creation(self, mock_config, mock_env_config, tmp_path):
        """Test save directory is created on init"""
        cfg = TEST_CONFIG.copy()
        cfg["training"]["save_dir"] = str(tmp_path / "models")
        mock_config.load.return_value = cfg

        with patch("shared.ml.rl.multi_agent.HMMRegimeDetector") as mock_hmm_cls:
            mock_hmm_cls.from_yaml.return_value = MagicMock()

            agent = RegimeAwareAgent(config_path="ml/rl_multi_agent.yaml")

            expected_dir = tmp_path / "models" / "multi_agent"
            assert agent._save_dir == expected_dir
            assert expected_dir.exists()
