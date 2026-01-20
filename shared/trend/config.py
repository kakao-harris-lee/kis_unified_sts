"""Trend engine configuration."""
from pydantic import BaseModel, ConfigDict, Field


class TechnicalConfig(BaseModel):
    """Configuration for technical indicators."""

    model_config = ConfigDict(frozen=True)

    # Moving averages
    ma_short_period: int = Field(default=20, description="Short MA period")
    ma_long_period: int = Field(default=60, description="Long MA period")

    # Ichimoku (standard 9-26-52)
    ichimoku_tenkan_period: int = Field(default=9, description="Tenkan-sen period")
    ichimoku_kijun_period: int = Field(default=26, description="Kijun-sen period")
    ichimoku_senkou_b_period: int = Field(default=52, description="Senkou Span B period")

    # ATR
    atr_period: int = Field(default=14, description="ATR period")


class TrendConfig(BaseModel):
    """Configuration for trend engine (Mode B)."""

    model_config = ConfigDict(frozen=True)

    # Technical indicator config
    technical: TechnicalConfig = Field(default_factory=TechnicalConfig)

    # Entry filters
    entry_threshold: float = Field(default=0.7, description="Minimum confidence for entry")
    min_atr: float = Field(default=0.5, description="Minimum ATR for volatility filter")

    # Position sizing
    atr_stop_multiplier: float = Field(default=2.0, description="ATR multiplier for stop loss")
    atr_target_multiplier: float = Field(default=3.0, description="ATR multiplier for take profit")

    # Risk management
    max_positions: int = Field(default=3, description="Maximum concurrent positions")
    position_size: float = Field(default=5.0, description="Default position size (contracts)")

    # Futures constants
    tick_size: float = Field(default=0.05, description="KOSPI Mini tick size")
    multiplier: int = Field(default=50000, description="KRW per point")
