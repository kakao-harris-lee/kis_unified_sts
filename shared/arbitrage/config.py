"""Arbitrage engine configuration."""
from pydantic import BaseModel, ConfigDict, Field


class ArbitrageConfig(BaseModel):
    """Configuration for arbitrage engine (Mode A)."""

    model_config = ConfigDict(frozen=True)

    # Basis calculation
    risk_free_rate: float = Field(default=0.035, description="Annual risk-free rate")
    rolling_window: int = Field(default=60, description="Rolling window for z-score (minutes)")
    min_samples: int = Field(default=20, description="Minimum samples before signals")

    # Entry filters
    basis_threshold: float = Field(default=2.5, description="Z-score threshold for entry")
    max_spread_ticks: int = Field(default=2, description="Maximum spread in ticks")
    depth_multiplier: float = Field(default=5.0, description="Required depth as multiple of order size")

    # Order sizing
    order_size: float = Field(default=5.0, description="Default order size (contracts)")

    # Blackout periods
    quarterly_blackout_days: int = Field(default=14, description="Days before expiry to avoid")

    # Futures constants
    tick_size: float = Field(default=0.05, gt=0, description="KOSPI Mini tick size")
    multiplier: int = Field(default=50000, description="KRW per point")
