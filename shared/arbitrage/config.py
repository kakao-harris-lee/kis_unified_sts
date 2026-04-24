"""Arbitrage engine configuration."""

from pydantic import BaseModel, ConfigDict, Field


def _load_default_mini_multiplier() -> int:
    """Load KOSPI200 mini multiplier from ContractSpecRegistry.

    Delegates to config/execution.yaml so there is a single source of truth.
    Raises (does not silently fall back) when the registry is unreadable or
    missing the ``kospi200_mini`` key — a misconfigured deployment must fail
    loudly rather than run with phantom contract math.
    """
    from shared.execution.contract_spec import ContractSpecRegistry

    registry = ContractSpecRegistry.from_yaml("config/execution.yaml")
    spec = registry.specs.get("kospi200_mini")
    if spec is None:
        raise KeyError(
            "config/execution.yaml::futures_contract_spec.kospi200_mini missing"
        )
    return spec.multiplier_krw_per_point


class ArbitrageConfig(BaseModel):
    """Configuration for arbitrage engine (Mode A)."""

    model_config = ConfigDict(frozen=True)

    # Basis calculation
    risk_free_rate: float = Field(default=0.035, description="Annual risk-free rate")
    rolling_window: int = Field(
        default=60, description="Rolling window for z-score (minutes)"
    )
    min_samples: int = Field(default=20, description="Minimum samples before signals")

    # Entry filters
    basis_threshold: float = Field(
        default=2.5, description="Z-score threshold for entry"
    )
    max_spread_ticks: int = Field(default=2, description="Maximum spread in ticks")
    depth_multiplier: float = Field(
        default=5.0, description="Required depth as multiple of order size"
    )

    # Order sizing
    order_size: float = Field(default=5.0, description="Default order size (contracts)")

    # Blackout periods
    quarterly_blackout_days: int = Field(
        default=14, description="Days before expiry to avoid"
    )

    # Futures constants
    tick_size: float = Field(default=0.05, gt=0, description="KOSPI Mini tick size")
    multiplier: int = Field(
        default_factory=_load_default_mini_multiplier, description="KRW per point"
    )
