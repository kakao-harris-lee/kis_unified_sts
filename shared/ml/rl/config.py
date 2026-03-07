"""RL Hyperparameter Configuration with Pydantic Validation

Comprehensive schema validation for all RL hyperparameters in config/ml/rl_mppo.yaml.
Validates learning rates, batch sizes, network architecture, reward shaping coefficients,
and environment settings at config load time.

Usage:
    from shared.ml.rl.config import RLMPPOConfig

    # Load and validate entire config
    config = RLMPPOConfig.from_yaml()

    # Access validated sections
    print(config.mppo.learning_rate)  # 0.0001
    print(config.env.initial_balance)  # 100_000_000

    # Validation errors are caught at load time
    try:
        config = RLMPPOConfig.from_yaml("invalid_config.yaml")
    except ValidationError as e:
        print(f"Config validation failed: {e}")

Example ValidationError:
    ValidationError: 1 validation error for RLMPPOConfig
    mppo.learning_rate
      Input should be less than or equal to 0.01 [type=less_than_equal, input_value=10.0]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from pydantic import Field, field_validator

from shared.config.base import ServiceConfigBase

logger = logging.getLogger(__name__)


# =============================================================================
# ParamSpec for Optuna Integration
# =============================================================================


@dataclass
class ParamSpec:
    """Parameter specification for Optuna optimization.

    Lightweight version to avoid importing entire optimizer module.

    Attributes:
        name: Parameter name
        param_type: Type ("int", "float", "categorical")
        low: Minimum value (int/float)
        high: Maximum value (int/float)
        step: Step size (optional)
        choices: Choices (categorical)
        log: Use log scale for sampling
    """

    name: str
    param_type: str  # "int", "float", "categorical"
    low: float | None = None
    high: float | None = None
    step: float | None = None
    choices: list[Any] | None = None
    log: bool = False

    @classmethod
    def int(
        cls,
        name: str,
        low: int,
        high: int,
        step: int = 1,
    ) -> ParamSpec:
        """Create integer parameter spec."""
        return cls(name=name, param_type="int", low=low, high=high, step=step)

    @classmethod
    def float(
        cls,
        name: str,
        low: float,
        high: float,
        step: float | None = None,
        log: bool = False,
    ) -> ParamSpec:
        """Create float parameter spec."""
        return cls(name=name, param_type="float", low=low, high=high, step=step, log=log)

    @classmethod
    def categorical(cls, name: str, choices: list[Any]) -> ParamSpec:
        """Create categorical parameter spec."""
        return cls(name=name, param_type="categorical", choices=choices)


# =============================================================================
# Environment Configuration
# =============================================================================


class EnvConfig(ServiceConfigBase):
    """Gymnasium environment configuration.

    Valid Ranges:
        - initial_balance: 1_000_000 - 1_000_000_000 (1M - 1B KRW)
        - commission_rate: 0.00001 - 0.001 (0.001% - 0.1%)
        - tick_size: > 0
        - tick_value: > 0
        - contract_multiplier: > 0
        - max_contracts: 1 - 10
        - slippage: 0.0 - 1.0 (0 - 1 tick)
        - margin_rate: 0.05 - 0.5 (5% - 50%)
        - n_market_features: 1 - 100
        - n_aux_features: 0 - 20
        - n_position_features: 1 - 20
    """

    initial_balance: float = Field(
        default=100_000_000,
        ge=1_000_000,
        le=1_000_000_000,
        description="Initial account balance (KRW)",
    )
    commission_rate: float = Field(
        default=0.00003,
        ge=0.00001,
        le=0.001,
        description="Trading commission rate",
    )
    tick_size: float = Field(default=0.05, gt=0, description="Minimum price increment")
    tick_value: int = Field(
        default=250_000, gt=0, description="KRW value per tick"
    )
    contract_multiplier: int = Field(
        default=250_000, gt=0, description="Contract size multiplier"
    )
    max_contracts: int = Field(
        default=1, ge=1, le=10, description="Maximum contracts per position"
    )
    slippage: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Slippage in ticks"
    )
    margin_rate: float = Field(
        default=0.15, ge=0.05, le=0.5, description="Margin requirement rate"
    )

    # State space dimensions
    n_market_features: int = Field(
        default=25, ge=1, le=100, description="Number of market features"
    )
    n_aux_features: int = Field(
        default=0, ge=0, le=20, description="Number of auxiliary features (TFT probs)"
    )
    n_position_features: int = Field(
        default=6, ge=1, le=20, description="Number of position features"
    )

    # Market hours (validated as HH:MM format)
    market_open: str = Field(default="09:00", description="Market open time (HH:MM)")
    market_close: str = Field(default="15:45", description="Market close time (HH:MM)")

    @field_validator("market_open", "market_close")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Validate HH:MM time format."""
        import re

        if not re.match(r"^\d{2}:\d{2}$", v):
            raise ValueError(f"Time must be in HH:MM format, got: {v}")
        hours, minutes = map(int, v.split(":"))
        if not (0 <= hours < 24 and 0 <= minutes < 60):
            raise ValueError(f"Invalid time: {v}")
        return v


# =============================================================================
# TFT Auxiliary Features Configuration
# =============================================================================


class TFTAuxConfig(ServiceConfigBase):
    """TFT auxiliary features configuration.

    Valid Ranges:
        - lookback: 10 - 200 (historical bars)
    """

    enabled: bool = Field(default=False, description="Enable TFT auxiliary features")
    model_path: str = Field(
        default="models/futures/tft/tft_cls_best", description="TFT model path"
    )
    lookback: int = Field(
        default=60, ge=10, le=200, description="Historical bars for TFT prediction"
    )
    features: list[str] = Field(
        default_factory=lambda: ["prob_up_1m", "prob_up_5m", "prob_up_15m"],
        description="TFT feature names",
    )


# =============================================================================
# Reward Function Configuration
# =============================================================================


class RewardConfig(ServiceConfigBase):
    """Reward function configuration.

    Valid Ranges:
        - w_profit: 0.0 - 20.0 (profit signal weight)
        - w_cost: 0.0 - 10.0 (cost penalty weight)
        - w_risk: 0.0 - 5.0 (risk penalty weight)
        - w_mtm: 0.0 - 5.0 (mark-to-market weight)
        - inaction_penalty: 0.0 - 1.0 (penalty for HOLD action)
        - reward_scale: 1.0 - 1000.0 (reward scaling factor)
        - max_loss: -50_000_000 - 0 (maximum acceptable loss)
        - loss_penalty_coeff: 0.0 - 10.0 (loss amplification coefficient)
    """

    w_profit: float = Field(
        default=10.0, ge=0.0, le=20.0, description="Profit signal weight"
    )
    w_cost: float = Field(
        default=0.3, ge=0.0, le=10.0, description="Cost penalty weight"
    )
    w_risk: float = Field(
        default=0.0, ge=0.0, le=5.0, description="Risk penalty weight"
    )
    w_mtm: float = Field(
        default=0.0, ge=0.0, le=5.0, description="Mark-to-market weight"
    )
    inaction_penalty: float = Field(
        default=0.0, ge=0.0, le=1.0, description="HOLD action penalty"
    )
    reward_scale: float = Field(
        default=100.0, ge=1.0, le=1000.0, description="Reward scaling factor"
    )
    max_loss: float = Field(
        default=-5_000_000,
        ge=-50_000_000,
        le=0,
        description="Maximum acceptable loss (KRW)",
    )
    loss_penalty_coeff: float = Field(
        default=2.0, ge=0.0, le=10.0, description="Loss amplification coefficient"
    )


# =============================================================================
# Network Architecture Configuration
# =============================================================================


class NetworkArchConfig(ServiceConfigBase):
    """Neural network architecture configuration.

    Valid Ranges:
        - Each layer: 64 - 512 neurons
        - pi (policy network): list of positive integers
        - vf (value network): list of positive integers
    """

    pi: list[int] = Field(
        default_factory=lambda: [256, 256],
        description="Policy network architecture",
    )
    vf: list[int] = Field(
        default_factory=lambda: [256, 256],
        description="Value network architecture",
    )

    @field_validator("pi", "vf")
    @classmethod
    def validate_architecture(cls, v: list[int]) -> list[int]:
        """Validate network architecture layers."""
        if not v:
            raise ValueError("Network architecture must have at least one layer")
        for layer_size in v:
            if not (64 <= layer_size <= 512):
                raise ValueError(
                    f"Layer size must be between 64 and 512, got: {layer_size}"
                )
        return v


class PolicyKwargsConfig(ServiceConfigBase):
    """Policy network keyword arguments."""

    net_arch: NetworkArchConfig = Field(
        default_factory=NetworkArchConfig, description="Network architecture"
    )


# =============================================================================
# MPPO Hyperparameters
# =============================================================================


class MPPOHyperparameters(ServiceConfigBase):
    """Maskable PPO hyperparameters.

    Valid Ranges:
        - learning_rate: 0.00001 - 0.01 (log scale recommended)
        - gamma: 0.9 - 0.999 (discount factor)
        - gae_lambda: 0.8 - 0.99 (GAE parameter)
        - clip_range: 0.1 - 0.4 (PPO clip range)
        - ent_coef: 0.0 - 0.2 (entropy coefficient)
        - vf_coef: 0.1 - 1.0 (value function coefficient)
        - max_grad_norm: 0.1 - 10.0 (gradient clipping)
        - n_steps: 128 - 4096 (steps per rollout)
        - batch_size: 16 - 512 (mini-batch size)
        - n_epochs: 1 - 50 (update epochs per rollout)
        - total_timesteps: 100_000 - 50_000_000
    """

    learning_rate: float = Field(
        default=0.0001,
        ge=0.00001,
        le=0.01,
        description="Learning rate (use log scale for tuning)",
    )
    gamma: float = Field(
        default=0.999,
        ge=0.9,
        le=0.999,
        description="Discount factor for future rewards",
    )
    gae_lambda: float = Field(
        default=0.95,
        ge=0.8,
        le=0.99,
        description="GAE (Generalized Advantage Estimation) parameter",
    )
    clip_range: float = Field(
        default=0.2, ge=0.1, le=0.4, description="PPO clipping range"
    )
    ent_coef: float = Field(
        default=0.05,
        ge=0.0,
        le=0.2,
        description="Entropy coefficient for exploration",
    )
    vf_coef: float = Field(
        default=0.5, ge=0.1, le=1.0, description="Value function loss coefficient"
    )
    max_grad_norm: float = Field(
        default=0.5, ge=0.1, le=10.0, description="Maximum gradient norm for clipping"
    )
    n_steps: int = Field(
        default=2048,
        ge=128,
        le=4096,
        description="Number of steps per rollout",
    )
    batch_size: int = Field(
        default=64, ge=16, le=512, description="Mini-batch size for updates"
    )
    n_epochs: int = Field(
        default=10, ge=1, le=50, description="Number of epochs per rollout"
    )
    total_timesteps: int = Field(
        default=5_000_000,
        ge=100_000,
        le=50_000_000,
        description="Total training timesteps",
    )
    policy_kwargs: PolicyKwargsConfig = Field(
        default_factory=PolicyKwargsConfig, description="Policy network configuration"
    )


# =============================================================================
# Comparison Algorithm Hyperparameters
# =============================================================================


class DQNHyperparameters(ServiceConfigBase):
    """DQN hyperparameters.

    Valid Ranges:
        - learning_rate: 0.00001 - 0.01
        - gamma: 0.9 - 0.999
        - buffer_size: 1_000 - 1_000_000
        - learning_starts: 100 - 100_000
        - batch_size: 16 - 512
        - target_update_interval: 100 - 10_000
        - exploration_fraction: 0.0 - 1.0
        - exploration_final_eps: 0.0 - 0.2
        - total_timesteps: 100_000 - 50_000_000
    """

    learning_rate: float = Field(default=0.0001, ge=0.00001, le=0.01)
    gamma: float = Field(default=0.99, ge=0.9, le=0.999)
    buffer_size: int = Field(default=100_000, ge=1_000, le=1_000_000)
    learning_starts: int = Field(default=10_000, ge=100, le=100_000)
    batch_size: int = Field(default=64, ge=16, le=512)
    target_update_interval: int = Field(default=1000, ge=100, le=10_000)
    exploration_fraction: float = Field(default=0.1, ge=0.0, le=1.0)
    exploration_final_eps: float = Field(default=0.05, ge=0.0, le=0.2)
    total_timesteps: int = Field(default=5_000_000, ge=100_000, le=50_000_000)


class A2CHyperparameters(ServiceConfigBase):
    """A2C hyperparameters.

    Valid Ranges:
        - learning_rate: 0.00001 - 0.01
        - gamma: 0.9 - 0.999
        - gae_lambda: 0.8 - 0.99
        - ent_coef: 0.0 - 0.2
        - vf_coef: 0.1 - 1.0
        - n_steps: 1 - 100
        - total_timesteps: 100_000 - 50_000_000
    """

    learning_rate: float = Field(default=0.0007, ge=0.00001, le=0.01)
    gamma: float = Field(default=0.99, ge=0.9, le=0.999)
    gae_lambda: float = Field(default=0.95, ge=0.8, le=0.99)
    ent_coef: float = Field(default=0.01, ge=0.0, le=0.2)
    vf_coef: float = Field(default=0.5, ge=0.1, le=1.0)
    n_steps: int = Field(default=5, ge=1, le=100)
    total_timesteps: int = Field(default=5_000_000, ge=100_000, le=50_000_000)


class PPOHyperparameters(ServiceConfigBase):
    """PPO (non-maskable) hyperparameters.

    Valid Ranges:
        - learning_rate: 0.00001 - 0.01
        - gamma: 0.9 - 0.999
        - gae_lambda: 0.8 - 0.99
        - clip_range: 0.1 - 0.4
        - ent_coef: 0.0 - 0.2
        - vf_coef: 0.1 - 1.0
        - n_steps: 128 - 4096
        - batch_size: 16 - 512
        - n_epochs: 1 - 50
        - total_timesteps: 100_000 - 50_000_000
    """

    learning_rate: float = Field(default=0.0001, ge=0.00001, le=0.01)
    gamma: float = Field(default=0.99, ge=0.9, le=0.999)
    gae_lambda: float = Field(default=0.95, ge=0.8, le=0.99)
    clip_range: float = Field(default=0.2, ge=0.1, le=0.4)
    ent_coef: float = Field(default=0.01, ge=0.0, le=0.2)
    vf_coef: float = Field(default=0.5, ge=0.1, le=1.0)
    n_steps: int = Field(default=2048, ge=128, le=4096)
    batch_size: int = Field(default=64, ge=16, le=512)
    n_epochs: int = Field(default=10, ge=1, le=50)
    total_timesteps: int = Field(default=5_000_000, ge=100_000, le=50_000_000)


class SACHyperparameters(ServiceConfigBase):
    """SAC hyperparameters.

    Valid Ranges:
        - learning_rate: 0.00001 - 0.01
        - gamma: 0.9 - 0.999
        - buffer_size: 1_000 - 1_000_000
        - tau: 0.001 - 0.1 (soft update coefficient)
        - ent_coef: 'auto' or 0.0 - 1.0
        - batch_size: 16 - 512
        - total_timesteps: 100_000 - 50_000_000
    """

    learning_rate: float = Field(default=0.0003, ge=0.00001, le=0.01)
    gamma: float = Field(default=0.99, ge=0.9, le=0.999)
    buffer_size: int = Field(default=100_000, ge=1_000, le=1_000_000)
    tau: float = Field(default=0.005, ge=0.001, le=0.1)
    ent_coef: str | float = Field(default="auto")
    batch_size: int = Field(default=64, ge=16, le=512)
    total_timesteps: int = Field(default=5_000_000, ge=100_000, le=50_000_000)

    @field_validator("ent_coef")
    @classmethod
    def validate_ent_coef(cls, v: str | float) -> str | float:
        """Validate entropy coefficient (auto or float)."""
        if isinstance(v, str):
            if v != "auto":
                raise ValueError(f"String ent_coef must be 'auto', got: {v}")
        elif isinstance(v, (int, float)):
            if not (0.0 <= v <= 1.0):
                raise ValueError(f"Numeric ent_coef must be in [0.0, 1.0], got: {v}")
        else:
            raise ValueError(f"ent_coef must be 'auto' or float, got: {type(v)}")
        return v


class MACrossConfig(ServiceConfigBase):
    """Moving Average Crossover strategy configuration.

    Valid Ranges:
        - short_window: 2 - 50
        - long_window: 10 - 200
    """

    short_window: int = Field(default=5, ge=2, le=50)
    long_window: int = Field(default=20, ge=10, le=200)

    @field_validator("long_window")
    @classmethod
    def validate_window_order(cls, v: int, info: Any) -> int:
        """Ensure long_window > short_window."""
        if "short_window" in info.data and v <= info.data["short_window"]:
            raise ValueError(
                f"long_window ({v}) must be greater than short_window ({info.data['short_window']})"
            )
        return v


# =============================================================================
# Data Configuration
# =============================================================================


class DataQualityConfig(ServiceConfigBase):
    """Data quality validation configuration."""

    enabled: bool = Field(default=True, description="Enable data quality checks")
    reject_duplicate_datetime: bool = Field(
        default=True, description="Reject duplicate timestamps"
    )
    require_monotonic_datetime: bool = Field(
        default=True, description="Require monotonically increasing timestamps"
    )
    max_zero_volume_ratio: float = Field(
        default=0.95, ge=0.0, le=1.0, description="Maximum zero-volume bar ratio"
    )
    max_zero_volume_price_move_ratio: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Maximum price move on zero volume",
    )


class DataConfig(ServiceConfigBase):
    """Data loading configuration.

    Valid Ranges:
        - train_ratio: 0.5 - 0.95 (train/test split)
        - min_bars_per_day: 100 - 500
    """

    source: Literal["clickhouse"] = Field(
        default="clickhouse", description="Data source"
    )
    database: str = Field(default="kospi", description="Database name")
    table: str = Field(default="kospi200f_1m", description="Table name")
    symbol: str = Field(
        default="101S6000", description="Symbol (101S6000 = KOSPI200 futures)"
    )
    train_ratio: float = Field(
        default=0.8, ge=0.5, le=0.95, description="Training data ratio"
    )
    min_bars_per_day: int = Field(
        default=300, ge=100, le=500, description="Minimum bars per trading day"
    )
    mirror_augmentation: bool = Field(
        default=True, description="Enable LONG/SHORT mirror augmentation"
    )
    quality: DataQualityConfig = Field(
        default_factory=DataQualityConfig, description="Data quality settings"
    )


# =============================================================================
# Training Configuration
# =============================================================================


class TrainingConfig(ServiceConfigBase):
    """Training management configuration.

    Valid Ranges:
        - eval_freq: 1_000 - 100_000
        - checkpoint_freq: 10_000 - 500_000
    """

    eval_freq: int = Field(
        default=10_000, ge=1_000, le=100_000, description="Evaluation frequency (steps)"
    )
    checkpoint_freq: int = Field(
        default=50_000,
        ge=10_000,
        le=500_000,
        description="Checkpoint save frequency (steps)",
    )
    tensorboard_log: str = Field(
        default="./results/rl/tensorboard/", description="TensorBoard log directory"
    )
    save_dir: str = Field(
        default="./models/futures/rl/", description="Model save directory"
    )


# =============================================================================
# Hierarchical RL Configuration
# =============================================================================


class HighLevelConfig(ServiceConfigBase):
    """High-level policy hyperparameters."""

    learning_rate: float = Field(default=0.0003, ge=0.00001, le=0.01)
    gamma: float = Field(default=0.99, ge=0.9, le=0.999)
    n_steps: int = Field(default=128, ge=32, le=2048)
    batch_size: int = Field(default=32, ge=8, le=256)
    n_epochs: int = Field(default=10, ge=1, le=50)
    ent_coef: float = Field(default=0.05, ge=0.0, le=0.2)


class HierarchicalConfig(ServiceConfigBase):
    """Hierarchical RL configuration.

    Valid Ranges:
        - bars_per_step: 5 - 60 (multi-timeframe aggregation)
        - high_level_timesteps: 100_000 - 5_000_000
        - risk_budgets: 0.0 - 1.0 (position size fraction)
    """

    bars_per_step: int = Field(
        default=15, ge=5, le=60, description="Bars per high-level step"
    )
    high_level_timesteps: int = Field(
        default=500_000,
        ge=100_000,
        le=5_000_000,
        description="High-level training timesteps",
    )
    risk_budgets: dict[str, float] = Field(
        default_factory=lambda: {"aggressive": 1.0, "neutral": 0.5, "defensive": 0.0},
        description="Risk budget per action type",
    )
    high_level: HighLevelConfig = Field(
        default_factory=HighLevelConfig, description="High-level policy config"
    )

    @field_validator("risk_budgets")
    @classmethod
    def validate_risk_budgets(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate risk budget values."""
        for key, value in v.items():
            if not (0.0 <= value <= 1.0):
                raise ValueError(
                    f"Risk budget '{key}' must be in [0.0, 1.0], got: {value}"
                )
        return v


# =============================================================================
# Position Sizing Configuration
# =============================================================================


class PositionSizingConfig(ServiceConfigBase):
    """Kelly criterion position sizing configuration.

    Valid Ranges:
        - fraction: 0.1 - 1.0 (Kelly fraction, 0.5 = Half-Kelly)
        - min_trades: 5 - 100
        - min_scale: 0.1 - 0.5
        - max_scale: 0.5 - 2.0
        - default_win_rate: 0.3 - 0.7
        - default_wl_ratio: 1.0 - 3.0
    """

    enabled: bool = Field(default=True, description="Enable Kelly position sizing")
    fraction: float = Field(
        default=0.5, ge=0.1, le=1.0, description="Kelly fraction (0.5 = Half-Kelly)"
    )
    min_trades: int = Field(
        default=10,
        ge=5,
        le=100,
        description="Minimum trades before using actual stats",
    )
    min_scale: float = Field(
        default=0.2, ge=0.1, le=0.5, description="Minimum position scale"
    )
    max_scale: float = Field(
        default=1.0, ge=0.5, le=2.0, description="Maximum position scale"
    )
    default_win_rate: float = Field(
        default=0.45, ge=0.3, le=0.7, description="Initial win rate estimate"
    )
    default_wl_ratio: float = Field(
        default=1.83, ge=1.0, le=3.0, description="Initial win/loss ratio estimate"
    )


# =============================================================================
# Paper Trading Configuration
# =============================================================================


class PaperTradingConfig(ServiceConfigBase):
    """Paper trading configuration (legacy paper_trader.py).

    Valid Ranges:
        - warmup_bars: 50 - 500
        - force_close_time: HH:MM format
    """

    symbol: str = Field(
        default="", description="Symbol (empty = auto-detect mini front month)"
    )
    warmup_bars: int = Field(
        default=200, ge=50, le=500, description="Historical bars for warmup"
    )
    force_close_time: str = Field(
        default="15:35", description="Forced liquidation time (HH:MM)"
    )
    telegram_notify: bool = Field(
        default=True, description="Enable Telegram notifications"
    )
    log_dir: str = Field(
        default="./results/rl/paper/", description="Paper trading log directory"
    )

    @field_validator("force_close_time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Validate HH:MM time format."""
        import re

        if not re.match(r"^\d{2}:\d{2}$", v):
            raise ValueError(f"Time must be in HH:MM format, got: {v}")
        hours, minutes = map(int, v.split(":"))
        if not (0 <= hours < 24 and 0 <= minutes < 60):
            raise ValueError(f"Invalid time: {v}")
        return v


# =============================================================================
# Main RL Configuration
# =============================================================================


class RLMPPOConfig(ServiceConfigBase):
    """Complete RL MPPO configuration with full validation.

    Loads and validates all sections from config/ml/rl_mppo.yaml.

    Usage:
        # Load entire config
        config = RLMPPOConfig.from_yaml()

        # Access validated sections
        print(config.mppo.learning_rate)  # 0.0001
        print(config.env.initial_balance)  # 100_000_000

        # Validation errors
        try:
            config = RLMPPOConfig.from_yaml("invalid_config.yaml")
        except ValidationError as e:
            print(f"Config validation failed: {e}")

    Critical Hyperparameter Ranges:
        - MPPO learning_rate: 0.00001 - 0.01 (log scale)
        - MPPO gamma: 0.9 - 0.999
        - MPPO batch_size: 16 - 512
        - MPPO n_steps: 128 - 4096
        - Network layers: 64 - 512 neurons
        - Reward weights: bounded to prevent instability
    """

    _default_config_file: ClassVar[str] = "ml/rl_mppo.yaml"

    # Environment and reward
    env: EnvConfig = Field(default_factory=EnvConfig)
    tft_aux: TFTAuxConfig = Field(default_factory=TFTAuxConfig)
    reward: RewardConfig = Field(default_factory=RewardConfig)

    # Algorithm hyperparameters
    mppo: MPPOHyperparameters = Field(default_factory=MPPOHyperparameters)
    dqn: DQNHyperparameters = Field(default_factory=DQNHyperparameters)
    a2c: A2CHyperparameters = Field(default_factory=A2CHyperparameters)
    ppo: PPOHyperparameters = Field(default_factory=PPOHyperparameters)
    sac: SACHyperparameters = Field(default_factory=SACHyperparameters)
    ma_cross: MACrossConfig = Field(default_factory=MACrossConfig)

    # Data and training
    data: DataConfig = Field(default_factory=DataConfig)
    training: TrainingConfig = Field(default_factory=TrainingConfig)

    # Advanced features
    hierarchical: HierarchicalConfig = Field(default_factory=HierarchicalConfig)
    position_sizing: PositionSizingConfig = Field(
        default_factory=PositionSizingConfig
    )
    paper: PaperTradingConfig = Field(default_factory=PaperTradingConfig)

    # Slippage test values
    slippage_test_values: list[float] = Field(
        default_factory=lambda: [0.00, 0.05, 0.10, 0.15, 0.20],
        description="Slippage values for testing",
    )

    @field_validator("slippage_test_values")
    @classmethod
    def validate_slippage_values(cls, v: list[float]) -> list[float]:
        """Validate slippage test values."""
        for value in v:
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"Slippage value must be in [0.0, 1.0], got: {value}")
        return v

    @classmethod
    def from_yaml(cls, path: str = "ml/rl_mppo.yaml") -> RLMPPOConfig:
        """Load and validate RL config from YAML.

        Args:
            path: YAML config file path (relative to config directory)

        Returns:
            Validated RLMPPOConfig instance

        Raises:
            ValidationError: If any hyperparameter is out of valid range

        Example:
            >>> config = RLMPPOConfig.from_yaml()
            >>> print(config.mppo.learning_rate)
            0.0001
        """
        return super().from_yaml(path)

    @classmethod
    def get_param_ranges(cls) -> dict[str, ParamSpec]:
        """Extract Optuna-compatible parameter ranges from schema.

        Introspects Pydantic Field metadata to extract numeric constraints
        (ge, le, gt, lt) and converts them to ParamSpec objects for use with
        Optuna hyperparameter optimization.

        Returns:
            Dict mapping field paths (e.g., 'mppo.learning_rate') to ParamSpec objects

        Example:
            >>> ranges = RLMPPOConfig.get_param_ranges()
            >>> ranges["mppo.learning_rate"]
            ParamSpec(name='mppo.learning_rate', param_type='float', low=1e-05, high=0.01, log=True)
            >>> ranges["mppo.batch_size"]
            ParamSpec(name='mppo.batch_size', param_type='int', low=16, high=512)

        Usage with Optuna:
            >>> import optuna
            >>> ranges = RLMPPOConfig.get_param_ranges()
            >>> def objective(trial):
            ...     # Extract ParamSpec attributes
            ...     lr_spec = ranges["mppo.learning_rate"]
            ...     lr = trial.suggest_float(lr_spec.name, lr_spec.low, lr_spec.high, log=lr_spec.log)
            ...     # ... run training with lr
        """

        import typing

        ranges = {}

        # Define which nested configs to extract from
        config_sections = {
            "mppo": MPPOHyperparameters,
            "dqn": DQNHyperparameters,
            "a2c": A2CHyperparameters,
            "ppo": PPOHyperparameters,
            "sac": SACHyperparameters,
            "env": EnvConfig,
            "reward": RewardConfig,
            "data": DataConfig,
            "training": TrainingConfig,
            "hierarchical": HierarchicalConfig,
            "position_sizing": PositionSizingConfig,
        }

        for section_name, section_class in config_sections.items():
            for field_name, field_info in section_class.model_fields.items():
                # Extract type annotation
                field_type = field_info.annotation

                # Handle Optional/Union types
                origin = typing.get_origin(field_type)
                if origin is typing.Union:
                    args = typing.get_args(field_type)
                    # Get non-None type
                    field_type = next(
                        (arg for arg in args if arg is not type(None)), None
                    )

                # Skip non-numeric fields
                if field_type not in [int, float]:
                    continue

                # Extract constraints from field metadata (Pydantic v2)
                ge = None
                le = None
                gt = None
                lt = None

                for constraint in field_info.metadata:
                    constraint_type = type(constraint).__name__
                    if constraint_type == "Ge":
                        ge = constraint.ge
                    elif constraint_type == "Le":
                        le = constraint.le
                    elif constraint_type == "Gt":
                        gt = constraint.gt
                    elif constraint_type == "Lt":
                        lt = constraint.lt

                # Determine bounds
                low = None
                high = None

                if ge is not None:
                    low = ge
                elif gt is not None:
                    # For gt constraint, use the value as-is (Optuna handles exclusive bounds)
                    low = gt

                if le is not None:
                    high = le
                elif lt is not None:
                    # For lt constraint, use the value as-is (Optuna handles exclusive bounds)
                    high = lt

                # Need both bounds to create a range
                if low is None or high is None:
                    continue

                # Create ParamSpec
                param_name = f"{section_name}.{field_name}"

                # Detect log scale for learning rates or wide ranges (>2 orders of magnitude)
                use_log = (
                    "learning_rate" in field_name
                    or "lr" in field_name
                    or (high / low > 100 if low > 0 else False)
                )

                if field_type == int:
                    ranges[param_name] = ParamSpec.int(
                        param_name, int(low), int(high)
                    )
                else:  # float
                    ranges[param_name] = ParamSpec.float(
                        param_name, float(low), float(high), log=use_log
                    )

        return ranges
