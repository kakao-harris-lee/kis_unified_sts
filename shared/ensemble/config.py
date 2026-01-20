"""Ensemble filter configuration."""
from pydantic import BaseModel, ConfigDict, Field


class EnsembleConfig(BaseModel):
    """Configuration for ensemble filter."""

    model_config = ConfigDict(frozen=True)

    # Probability calibration
    calibration_lookback: int = Field(default=100, description="Lookback for z-score calibration")
    min_confidence: float = Field(default=0.6, description="Minimum confidence for signal")

    # Filter thresholds
    dl_threshold: float = Field(default=0.65, description="DL probability threshold")
    ma_weight: float = Field(default=0.3, description="MA filter weight in ensemble")
    ichimoku_weight: float = Field(default=0.3, description="Ichimoku filter weight")
    dl_weight: float = Field(default=0.4, description="DL model weight")

    # Multi-horizon settings
    horizons: list = Field(default=["1m", "5m", "15m"], description="Prediction horizons")
    min_horizons_confirmed: int = Field(default=2, description="Min horizons for confirmation")

    # Position sizing
    atr_stop_multiplier: float = Field(default=2.0, description="ATR multiplier for stop loss")
    atr_target_multiplier: float = Field(default=3.0, description="ATR multiplier for take profit")
    default_position_size: float = Field(default=5.0, description="Default position size")
