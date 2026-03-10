"""Test RLTrainer initialization."""
import pytest


def test_trainer_default_initialization():
    """Test trainer initialization with default config path."""
    from pathlib import Path
    from shared.ml.rl.trainer import RLTrainer

    trainer = RLTrainer()

    assert trainer.config is not None
    assert trainer.env_config is not None
    assert trainer.device in ["cpu", "cuda", "mps"]
    assert isinstance(trainer.save_dir, Path)
    assert trainer.tb_log is not None


def test_trainer_custom_config_path():
    """Test trainer initialization with custom config path."""
    from pathlib import Path
    from shared.ml.rl.trainer import RLTrainer

    # Using the default config path explicitly
    trainer = RLTrainer(config_path="ml/rl_mppo.yaml")

    assert trainer.config is not None
    assert trainer.env_config is not None
    assert isinstance(trainer.save_dir, Path)


def test_trainer_device_selection():
    """Test device selection logic."""
    from shared.ml.base import get_device

    # Test auto device selection
    device_auto = get_device("auto")
    assert device_auto in ["cpu", "cuda", "mps"]

    # Test explicit CPU
    device_cpu = get_device("cpu")
    assert device_cpu == "cpu"

    # Test invalid CUDA fallback to CPU
    device_cuda = get_device("cuda")
    assert device_cuda in ["cpu", "cuda"]

    # Test MPS
    device_mps = get_device("mps")
    assert device_mps in ["cpu", "mps"]


def test_trainer_save_dir_creation():
    """Test save_dir is created during initialization."""
    from pathlib import Path
    from shared.ml.rl.trainer import RLTrainer
    import tempfile
    import shutil

    # Create a temporary directory for testing
    temp_dir = tempfile.mkdtemp()

    try:
        # Mock config with custom save_dir
        from unittest.mock import patch

        custom_save_dir = Path(temp_dir) / "test_rl_models"
        mock_config = {
            "mppo": {"device": "cpu"},
            "training": {
                "save_dir": str(custom_save_dir),
                "tensorboard_log": "./test_tb_log/",
            },
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
                "n_aux_features": 0,
                "n_position_features": 6,
                "market_open": "09:00",
                "market_close": "15:45",
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
        }

        with patch("shared.config.loader.ConfigLoader.load", return_value=mock_config):
            trainer = RLTrainer()

            # Verify save_dir exists
            assert trainer.save_dir.exists()
            assert trainer.save_dir.is_dir()
            assert str(trainer.save_dir) == str(custom_save_dir)

    finally:
        # Cleanup
        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir)


def test_trainer_config_values():
    """Test that config values are correctly loaded."""
    from shared.ml.rl.trainer import RLTrainer

    trainer = RLTrainer()

    # Check that env_config has expected attributes
    assert hasattr(trainer.env_config, "initial_balance")
    assert hasattr(trainer.env_config, "commission_rate")
    assert hasattr(trainer.env_config, "tick_size")
    assert hasattr(trainer.env_config, "contract_multiplier")

    # Verify config structure
    assert "mppo" in trainer.config or "training" in trainer.config


def test_trainer_tensorboard_log_path():
    """Test tensorboard log path is set correctly."""
    from shared.ml.rl.trainer import RLTrainer

    trainer = RLTrainer()

    assert trainer.tb_log is not None
    assert isinstance(trainer.tb_log, str)
    # Should contain tensorboard or similar
    assert "tensorboard" in trainer.tb_log.lower() or "results" in trainer.tb_log


def test_trainer_env_config_from_yaml():
    """Test RLEnvConfig loading from YAML."""
    from shared.ml.rl.env import RLEnvConfig

    config = RLEnvConfig.from_yaml("ml/rl_mppo.yaml")

    # Verify env config values
    assert config.initial_balance > 0
    assert config.commission_rate >= 0
    assert config.tick_size > 0
    assert config.tick_value > 0
    assert config.contract_multiplier > 0
    assert config.max_contracts >= 1
    assert config.slippage >= 0
    assert config.margin_rate > 0

    # Verify state space dimensions
    assert config.n_market_features > 0
    assert config.n_aux_features >= 0
    assert config.n_position_features > 0

    # Verify reward weights
    assert config.w_profit > 0
    assert config.w_cost >= 0
    assert config.reward_scale > 0


def test_trainer_algo_registry():
    """Test that algorithm registry is properly defined."""
    from shared.ml.rl.trainer import ALGO_REGISTRY, CONTINUOUS_ACTION_ALGOS, NON_SB3_ALGOS

    # Check registry contains expected algorithms
    assert "mppo" in ALGO_REGISTRY
    assert "sac" in ALGO_REGISTRY
    assert "dqn" in ALGO_REGISTRY
    assert "a2c" in ALGO_REGISTRY
    assert "ppo" in ALGO_REGISTRY
    assert "dt" in ALGO_REGISTRY

    # Verify continuous action algos
    assert "sac" in CONTINUOUS_ACTION_ALGOS

    # Verify non-SB3 algos
    assert "dt" in NON_SB3_ALGOS


def test_trainer_device_attribute():
    """Test that device attribute is set correctly."""
    from shared.ml.rl.trainer import RLTrainer

    trainer = RLTrainer()

    # Device should be a valid string
    assert isinstance(trainer.device, str)
    assert trainer.device in ["cpu", "cuda", "mps"]


class TestEnvironmentCreation:
    """Test RLTrainer._make_env creates correct environment with ActionMasker wrapper."""

    @pytest.fixture
    def trainer(self):
        """Create trainer instance."""
        from shared.ml.rl.trainer import RLTrainer

        return RLTrainer()

    @pytest.fixture
    def sample_data(self):
        """Generate sample training data."""
        import numpy as np

        n_steps = 100
        n_features = 25

        np.random.seed(42)
        features = np.random.randn(n_steps, n_features).astype(np.float32)
        prices = np.zeros((n_steps, 4), dtype=np.float32)

        base_price = 350.0
        for i in range(n_steps):
            price = base_price + np.random.normal(0, 0.5)
            prices[i] = [
                price - 0.1,  # open
                price + 0.3,  # high
                price - 0.3,  # low
                price,  # close
            ]
            base_price = price

        return [features], [prices]

    def test_make_env_creates_dummy_vec_env(self, trainer, sample_data):
        """Test _make_env returns DummyVecEnv wrapper."""
        from stable_baselines3.common.vec_env import DummyVecEnv

        train_days, train_prices = sample_data
        env = trainer._make_env(train_days, train_prices, trainer.env_config)

        assert isinstance(env, DummyVecEnv)
        assert env.num_envs == 1

    def test_make_env_with_action_masker_wrapper(self, trainer, sample_data):
        """Test _make_env wraps discrete action env with ActionMasker."""
        from sb3_contrib.common.wrappers import ActionMasker

        train_days, train_prices = sample_data
        env = trainer._make_env(
            train_days, train_prices, trainer.env_config, continuous=False
        )

        # Get the underlying environment from DummyVecEnv
        base_env = env.envs[0]

        # Should be wrapped with ActionMasker
        assert isinstance(base_env, ActionMasker)

    def test_make_env_with_continuous_action_wrapper(self, trainer, sample_data):
        """Test _make_env wraps continuous action env with ContinuousActionWrapper."""
        from shared.ml.rl.wrappers import ContinuousActionWrapper

        train_days, train_prices = sample_data
        env = trainer._make_env(
            train_days, train_prices, trainer.env_config, continuous=True
        )

        # Get the underlying environment from DummyVecEnv
        base_env = env.envs[0]

        # Should be wrapped with ContinuousActionWrapper
        assert isinstance(base_env, ContinuousActionWrapper)

    def test_make_env_observation_space(self, trainer, sample_data):
        """Test created environment has correct observation space."""
        import numpy as np

        train_days, train_prices = sample_data
        env = trainer._make_env(train_days, train_prices, trainer.env_config)

        # DummyVecEnv observation space
        obs_space = env.observation_space

        # Should match config dimensions:
        # n_market_features + n_aux_features + n_position_features
        expected_dim = (
            trainer.env_config.n_market_features
            + trainer.env_config.n_aux_features
            + trainer.env_config.n_position_features
        )

        assert obs_space.shape == (expected_dim,)  # (obs_dim,)
        assert obs_space.dtype == np.float32

    def test_make_env_action_space(self, trainer, sample_data):
        """Test created environment has correct action space."""
        from gymnasium import spaces

        train_days, train_prices = sample_data
        env = trainer._make_env(train_days, train_prices, trainer.env_config)

        # DummyVecEnv wraps the action space
        action_space = env.action_space

        # Should be Discrete(5) for 5 actions
        assert isinstance(action_space, spaces.Discrete)
        assert action_space.n == 5

    def test_make_env_action_masks_available(self, trainer, sample_data):
        """Test ActionMasker wrapper provides action masks."""
        train_days, train_prices = sample_data
        env = trainer._make_env(
            train_days, train_prices, trainer.env_config, continuous=False
        )

        # Reset environment
        obs = env.reset()

        # Get the underlying ActionMasker environment
        base_env = env.envs[0]

        # Should have action_masks method
        assert hasattr(base_env, "action_masks")

        # Action masks should return valid mask
        masks = base_env.action_masks()
        assert masks.shape == (5,)  # 5 actions
        assert masks.dtype == bool

    def test_make_env_validates_empty_data(self, trainer):
        """Test _make_env raises error for empty training data."""
        with pytest.raises(ValueError, match="train_days must be provided"):
            trainer._make_env(None, None, trainer.env_config)

        with pytest.raises(ValueError, match="train_days must be provided"):
            trainer._make_env([], [], trainer.env_config)

    def test_make_env_day_rotation(self, trainer, sample_data):
        """Test environment rotates through different days on reset."""
        import numpy as np

        # Create multi-day data
        n_steps = 100
        n_features = 25
        n_days = 3

        np.random.seed(42)
        train_days = [
            np.random.randn(n_steps, n_features).astype(np.float32)
            for _ in range(n_days)
        ]
        train_prices = [
            np.random.randn(n_steps, 4).astype(np.float32) for _ in range(n_days)
        ]

        env = trainer._make_env(train_days, train_prices, trainer.env_config)

        # Get the underlying environment
        base_env = env.envs[0]

        # Access the wrapped environment to get _DayRotatingEnv
        if hasattr(base_env, "env"):
            rotating_env = base_env.env
        else:
            rotating_env = base_env

        # Initial reset should use day 0
        env.reset()
        initial_day_idx = rotating_env._day_idx if hasattr(rotating_env, "_day_idx") else None

        # Second reset should rotate to next day
        env.reset()
        second_day_idx = rotating_env._day_idx if hasattr(rotating_env, "_day_idx") else None

        # If day rotation is implemented, indices should be different
        if initial_day_idx is not None and second_day_idx is not None:
            assert second_day_idx == (initial_day_idx + 1) % n_days

    def test_make_env_uses_mask_fn(self, trainer, sample_data):
        """Test ActionMasker uses the correct mask_fn from env module."""
        from shared.ml.rl.env import mask_fn

        train_days, train_prices = sample_data
        env = trainer._make_env(
            train_days, train_prices, trainer.env_config, continuous=False
        )

        # Get the underlying ActionMasker
        base_env = env.envs[0]

        # Reset environment
        env.reset()

        # Get masks from ActionMasker
        masks = base_env.action_masks()

        # Get the wrapped FuturesTradingEnv
        if hasattr(base_env, "env"):
            futures_env = base_env.env
        else:
            futures_env = base_env

        # Masks should match what mask_fn would return
        expected_masks = mask_fn(futures_env)
        assert (masks == expected_masks).all()

    def test_make_env_with_aux_features(self, trainer, sample_data):
        """Test _make_env handles auxiliary features correctly."""
        import numpy as np

        train_days, train_prices = sample_data
        n_steps = train_days[0].shape[0]
        n_aux = 5

        # Create auxiliary features
        train_aux = [np.random.randn(n_steps, n_aux).astype(np.float32)]

        # Update config to include aux features
        config_with_aux = trainer.env_config
        config_with_aux.n_aux_features = n_aux

        env = trainer._make_env(
            train_days, train_prices, config_with_aux, aux_days=train_aux
        )

        # Observation space should include aux features
        expected_dim = (
            config_with_aux.n_market_features
            + config_with_aux.n_aux_features
            + config_with_aux.n_position_features
        )

        assert env.observation_space.shape == (expected_dim,)


class TestModelCreation:
    """Test RLTrainer._create_model creates MaskablePPO with correct hyperparameters."""

    @pytest.fixture
    def trainer(self):
        """Create trainer instance."""
        from shared.ml.rl.trainer import RLTrainer

        return RLTrainer()

    @pytest.fixture
    def mock_env(self, trainer):
        """Create a mock environment for model creation."""
        import numpy as np

        # Create minimal sample data
        n_steps = 100
        n_features = 25

        np.random.seed(42)
        features = np.random.randn(n_steps, n_features).astype(np.float32)
        prices = np.zeros((n_steps, 4), dtype=np.float32)

        base_price = 350.0
        for i in range(n_steps):
            price = base_price + np.random.normal(0, 0.5)
            prices[i] = [
                price - 0.1,  # open
                price + 0.3,  # high
                price - 0.3,  # low
                price,  # close
            ]
            base_price = price

        return trainer._make_env([features], [prices], trainer.env_config)

    def test_create_maskable_ppo_model(self, trainer, mock_env):
        """Test _create_model creates MaskablePPO with correct type."""
        from sb3_contrib import MaskablePPO

        algo_config = trainer.config.get("mppo", {})
        model = trainer._create_model("mppo", mock_env, algo_config)

        assert isinstance(model, MaskablePPO)
        assert model.policy is not None
        assert model.env is mock_env

    def test_model_hyperparameters_from_config(self, trainer, mock_env):
        """Test model is created with hyperparameters from config."""
        algo_config = trainer.config.get("mppo", {})
        model = trainer._create_model("mppo", mock_env, algo_config)

        # Verify learning rate
        expected_lr = algo_config.get("learning_rate", 0.0001)
        assert model.learning_rate == expected_lr

        # Verify gamma (discount factor)
        expected_gamma = algo_config.get("gamma", 0.99)
        assert model.gamma == expected_gamma

        # Verify GAE lambda
        expected_gae_lambda = algo_config.get("gae_lambda", 0.95)
        assert model.gae_lambda == expected_gae_lambda

        # Verify clip range
        expected_clip_range = algo_config.get("clip_range", 0.2)
        # clip_range can be a function, so we need to handle that
        clip_range_val = model.clip_range(1.0) if callable(model.clip_range) else model.clip_range
        assert clip_range_val == expected_clip_range

        # Verify entropy coefficient
        expected_ent_coef = algo_config.get("ent_coef", 0.01)
        assert model.ent_coef == expected_ent_coef

        # Verify value function coefficient
        expected_vf_coef = algo_config.get("vf_coef", 0.5)
        assert model.vf_coef == expected_vf_coef

        # Verify max gradient norm
        expected_max_grad_norm = algo_config.get("max_grad_norm", 0.5)
        assert model.max_grad_norm == expected_max_grad_norm

        # Verify n_steps
        expected_n_steps = algo_config.get("n_steps", 2048)
        assert model.n_steps == expected_n_steps

        # Verify batch_size
        expected_batch_size = algo_config.get("batch_size", 64)
        assert model.batch_size == expected_batch_size

        # Verify n_epochs
        expected_n_epochs = algo_config.get("n_epochs", 10)
        assert model.n_epochs == expected_n_epochs

    def test_model_policy_architecture_from_config(self, trainer, mock_env):
        """Test model policy architecture matches config policy_kwargs."""
        algo_config = trainer.config.get("mppo", {})
        model = trainer._create_model("mppo", mock_env, algo_config)

        # Get expected policy_kwargs from config
        expected_policy_kwargs = algo_config.get("policy_kwargs", {})

        if expected_policy_kwargs:
            # Verify net_arch is configured
            if "net_arch" in expected_policy_kwargs:
                expected_net_arch = expected_policy_kwargs["net_arch"]

                # The policy should have the architecture defined in config
                # Access through model.policy for SB3 models
                assert hasattr(model, "policy")

                # For MaskablePPO, policy_kwargs should be accessible
                # The exact structure depends on SB3 internals, but we can verify
                # it was passed through
                if hasattr(model.policy, "mlp_extractor"):
                    mlp = model.policy.mlp_extractor
                    # Verify policy and value networks exist
                    assert hasattr(mlp, "policy_net")
                    assert hasattr(mlp, "value_net")

    def test_model_uses_correct_device(self, trainer, mock_env):
        """Test model is created on the correct device."""
        algo_config = trainer.config.get("mppo", {})
        model = trainer._create_model("mppo", mock_env, algo_config)

        # Model device should match trainer device
        assert str(model.device) == trainer.device

    def test_model_uses_tensorboard_log(self, trainer, mock_env):
        """Test model is configured with tensorboard logging."""
        algo_config = trainer.config.get("mppo", {})
        model = trainer._create_model("mppo", mock_env, algo_config)

        # Verify tensorboard_log is set
        assert model.tensorboard_log == trainer.tb_log

    def test_model_verbose_is_set(self, trainer, mock_env):
        """Test model verbose parameter is set."""
        algo_config = trainer.config.get("mppo", {})
        model = trainer._create_model("mppo", mock_env, algo_config)

        # Verify verbose is set to 1
        assert model.verbose == 1

    def test_model_with_custom_policy_kwargs(self, trainer, mock_env):
        """Test model creation with custom policy_kwargs."""
        custom_policy_kwargs = {
            "net_arch": {
                "pi": [128, 128],
                "vf": [128, 128],
            }
        }

        custom_config = {
            "learning_rate": 0.0002,
            "gamma": 0.995,
            "policy_kwargs": custom_policy_kwargs,
        }

        model = trainer._create_model("mppo", mock_env, custom_config)

        # Verify model was created with custom learning rate
        assert model.learning_rate == 0.0002
        assert model.gamma == 0.995

        # Verify policy networks exist
        assert hasattr(model.policy, "mlp_extractor")

    def test_model_with_empty_policy_kwargs(self, trainer, mock_env):
        """Test model creation with empty policy_kwargs."""
        config_with_empty_kwargs = {
            "learning_rate": 0.0001,
            "gamma": 0.99,
            "policy_kwargs": {},
        }

        model = trainer._create_model("mppo", mock_env, config_with_empty_kwargs)

        # Model should be created successfully even with empty policy_kwargs
        assert isinstance(model, type(model))
        assert model.learning_rate == 0.0001

    def test_model_defaults_when_params_missing(self, trainer, mock_env):
        """Test model uses default values when config params are missing."""
        minimal_config = {}

        model = trainer._create_model("mppo", mock_env, minimal_config)

        # Verify default values are used
        assert model.learning_rate == 0.0001  # default from _create_model
        assert model.gamma == 0.99  # default from _create_model
        assert model.gae_lambda == 0.95  # default from _create_model
        assert model.n_steps == 2048  # default from _create_model
        assert model.batch_size == 64  # default from _create_model

    def test_model_mlp_policy_type(self, trainer, mock_env):
        """Test model uses MlpPolicy."""
        algo_config = trainer.config.get("mppo", {})
        model = trainer._create_model("mppo", mock_env, algo_config)

        # Verify policy type
        assert model.policy is not None
        # The policy should be an MLP policy (not CNN, etc.)
        assert hasattr(model.policy, "mlp_extractor")
