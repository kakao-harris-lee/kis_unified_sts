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
