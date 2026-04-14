"""Paper trading configuration."""
from pydantic import BaseModel, Field
from typing import Optional
import yaml


class PaperTradingConfig(BaseModel):
    """Configuration for paper trading engine."""

    initial_balance: float = Field(default=10_000_000, description="Initial capital")
    commission_rate: float = Field(default=0.00015, description="Commission rate (0.015%)")
    slippage_rate: float = Field(default=0.0001, description="Slippage rate (0.01%)")
    max_position_pct: float = Field(default=0.1, description="Max position as % of equity")
    max_positions: int = Field(default=5, description="Maximum concurrent positions")

    # Strategy settings
    strategy_name: Optional[str] = Field(default=None)
    asset_class: str = Field(default="stock")

    # Execution settings
    allow_shorting: bool = Field(default=False)
    market_hours_only: bool = Field(default=True)

    # Memory management
    max_equity_points: int = Field(
        default=10000,
        description="Maximum equity curve points (circular buffer size)"
    )

    # Price freshness guards (applied directly in VirtualBroker.submit_order)
    max_price_staleness_seconds: float = Field(
        default=30.0, ge=0.0,
        description="Max acceptable age of price_source_time for paper fills. 0 disables."
    )
    max_price_deviation_pct: float = Field(
        default=0.10, ge=0.0,
        description="Reject fills whose price deviates more than this fraction from reference median. 0 disables."
    )
    reference_price_lookback_minutes: int = Field(
        default=5, ge=0,
        description="Window in minutes for deviation reference median. 0 disables."
    )

    @classmethod
    def from_yaml(cls, path: str) -> "PaperTradingConfig":
        """Load config from YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)


# Backwards-compat alias — callers that imported PaperBrokerConfig still work.
PaperBrokerConfig = PaperTradingConfig
