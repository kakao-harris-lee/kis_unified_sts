"""Unified portfolio capital-tier configuration and track identity mapping.

Loads ``config/portfolio.yaml`` (design doc Layer 1/7, roadmap §5.5): 3-tier
capital allocation, Tier 2 B/C split, fund-movement parameters, and the
unified monthly-MDD circuit-breaker stages.

This module is also the single source of truth for **track identifiers** used
to tag RuntimeLedger rows:

- Track ``"A"`` — core portfolio (manual ledger, reserved for Phase 5).
- Track ``"B"`` — stock auto-trading pipeline.
- Track ``"C"`` — KOSPI200 futures auto-trading pipeline.

Recording paths must use :func:`track_for_asset_class` (or the ``TRACK_*``
constants) instead of hardcoding track letters.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, Field, model_validator

from shared.config.base import ServiceConfigBase
from shared.config.loader import ConfigNotFoundError

# --- Track identifiers (stable public contract; consumed by ledger tagging) --
TRACK_CORE = "A"  # Reserved: Phase 5 manual core-portfolio ledger.
TRACK_STOCK = "B"
TRACK_FUTURES = "C"

VALID_TRACK_IDS: frozenset[str] = frozenset({TRACK_CORE, TRACK_STOCK, TRACK_FUTURES})

# Asset-class → track mapping for the automated pipelines. Track A is manual
# (never derived from a runtime asset class), so it is intentionally absent.
ASSET_CLASS_TRACKS: dict[str, str] = {
    "stock": TRACK_STOCK,
    "futures": TRACK_FUTURES,
}

_RATIO_SUM_TOLERANCE = 1e-6


def track_for_asset_class(asset_class: str | None) -> str | None:
    """Return the track id for a pipeline asset class, or None when unmapped.

    Unknown/None asset classes map to None (row stays untagged) so callers
    never need to special-case: ``track_for_asset_class("stock") == "B"``,
    ``track_for_asset_class(None) is None``.
    """
    if not asset_class:
        return None
    return ASSET_CLASS_TRACKS.get(str(asset_class).strip().lower())


class TierAllocation(BaseModel):
    """Top-level capital tiers as fractions of total assets (sum to 1.0)."""

    tier1_core: float = Field(default=0.65, gt=0.0, lt=1.0)
    tier2_trading: float = Field(default=0.25, gt=0.0, lt=1.0)
    tier3_opportunity: float = Field(default=0.10, gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def _validate_sum(self) -> TierAllocation:
        total = self.tier1_core + self.tier2_trading + self.tier3_opportunity
        if abs(total - 1.0) > _RATIO_SUM_TOLERANCE:
            raise ValueError(f"tiers must sum to 1.0, got {total:.6f}")
        return self


class Tier2Split(BaseModel):
    """Tier 2 internal split between tracks B and C (sum to 1.0)."""

    track_b_stock: float = Field(default=0.70, gt=0.0, lt=1.0)
    track_c_futures: float = Field(default=0.30, gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def _validate_sum(self) -> Tier2Split:
        total = self.track_b_stock + self.track_c_futures
        if abs(total - 1.0) > _RATIO_SUM_TOLERANCE:
            raise ValueError(f"tier2_split must sum to 1.0, got {total:.6f}")
        return self


class Tier2ToTier1Rule(BaseModel):
    """Tier 2 → Tier 1 profit sweep (the only allowed direction)."""

    profit_threshold_pct: float = Field(default=0.30, gt=0.0)
    transfer_ratio: float = Field(default=0.50, gt=0.0, le=1.0)


class Tier3ActivationRule(BaseModel):
    """Tier 3 deployment trigger (manual execution; declaration only)."""

    kospi_drawdown_from_peak: float = Field(default=-0.15, lt=0.0)
    tranches: int = Field(default=3, ge=1)


class FundMovementRules(BaseModel):
    """Fund-movement parameters (설계서 §1.2 one-way principle).

    Tier 1 → Tier 2 is forbidden in principle and intentionally has no
    parameters here; the annual-rebalance exception is a manual decision.
    """

    tier2_to_tier1: Tier2ToTier1Rule = Field(default_factory=Tier2ToTier1Rule)
    tier3_activation: Tier3ActivationRule = Field(default_factory=Tier3ActivationRule)


class CapitalBaseConfig(BaseModel):
    """Absolute per-track capital anchors (KRW) for equity computation.

    ``equity(track) = capital_base + cumulative realized PnL + unrealized``.
    Track A stays ``None`` until the Phase 5 manual core ledger lands; the
    monitor then reports the track as missing (coverage recorded) instead of
    inventing a number.
    """

    track_a_core_krw: float | None = Field(default=None, gt=0.0)
    track_b_stock_krw: float = Field(default=10_000_000, gt=0.0)
    track_c_futures_krw: float = Field(default=5_000_000, gt=0.0)

    def for_track(self, track_id: str) -> float | None:
        """Capital base for a track id, or None when not yet provisioned."""
        return {
            TRACK_CORE: self.track_a_core_krw,
            TRACK_STOCK: self.track_b_stock_krw,
            TRACK_FUTURES: self.track_c_futures_krw,
        }.get(track_id)


class MonitorRedisConfig(BaseModel):
    """Redis publication contract for the Phase 3B portfolio monitor.

    Field names inside the hash are a FIXED contract with the 3D UI lane —
    see :mod:`services.portfolio_monitor.main`.
    """

    latest_key: str = Field(default="portfolio:equity:latest")
    latest_ttl_seconds: int = Field(default=86400, gt=0)
    stream_key: str = Field(default="stream:portfolio.equity")
    stream_maxlen: int = Field(default=5000, gt=0)
    stream_ttl_seconds: int = Field(default=86400, gt=0)


class MonitorAlertsConfig(BaseModel):
    """Telegram stage-transition alerts (market_risk_engine pattern)."""

    enabled: bool = Field(default=True)
    domain: str = Field(default="briefing")
    notify_stages: list[str] = Field(
        default_factory=lambda: ["REDUCE", "HALT_NEW", "FULL_STOP"]
    )


class PortfolioMonitorConfig(BaseModel):
    """Runtime knobs for the daily portfolio equity snapshot batch."""

    redis: MonitorRedisConfig = Field(default_factory=MonitorRedisConfig)
    alerts: MonitorAlertsConfig = Field(default_factory=MonitorAlertsConfig)


class MddReduceStage(BaseModel):
    """Stage 1: shrink Track B/C new-entry sizing."""

    threshold: float = Field(default=-0.05, lt=0.0)
    new_entry_size_factor: float = Field(default=0.5, gt=0.0, le=1.0)


class MddHaltNewStage(BaseModel):
    """Stage 2: halt all Track B/C new entries."""

    threshold: float = Field(default=-0.08, lt=0.0)


class MddFullStopStage(BaseModel):
    """Stage 3: full system stop + monthly review document gate."""

    threshold: float = Field(default=-0.12, lt=0.0)


class MonthlyMddStages(BaseModel):
    """Unified monthly MDD stages over total assets (설계서 §7.1).

    Track A (core) is never an MDD trigger target — stages only gate Track
    B/C new entries; core holdings are not sold by any stage.
    """

    reduce: MddReduceStage = Field(default_factory=MddReduceStage)
    halt_new: MddHaltNewStage = Field(default_factory=MddHaltNewStage)
    full_stop: MddFullStopStage = Field(default_factory=MddFullStopStage)

    @model_validator(mode="after")
    def _validate_ordering(self) -> MonthlyMddStages:
        if not (
            self.reduce.threshold > self.halt_new.threshold > self.full_stop.threshold
        ):
            raise ValueError(
                "monthly_mdd_stages thresholds must deepen monotonically: "
                f"reduce({self.reduce.threshold}) > "
                f"halt_new({self.halt_new.threshold}) > "
                f"full_stop({self.full_stop.threshold})"
            )
        return self


class CircuitBreakerConfig(BaseModel):
    """Unified circuit breaker: off | shadow (observe-only) | enforce."""

    mode: Literal["off", "shadow", "enforce"] = "shadow"
    # Intra-month latch: once a stage is reached it holds for the remainder
    # of the KST month even if equity recovers (설계서 §7.1 취지).
    stage_latch: bool = True
    monthly_mdd_stages: MonthlyMddStages = Field(default_factory=MonthlyMddStages)


class PortfolioConfig(ServiceConfigBase):
    """Top-level portfolio config loaded from ``config/portfolio.yaml``."""

    _default_config_file: ClassVar[str] = "portfolio.yaml"

    tiers: TierAllocation = Field(default_factory=TierAllocation)
    tier2_split: Tier2Split = Field(default_factory=Tier2Split)
    fund_movement: FundMovementRules = Field(default_factory=FundMovementRules)
    capital_base: CapitalBaseConfig = Field(default_factory=CapitalBaseConfig)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    monitor: PortfolioMonitorConfig = Field(default_factory=PortfolioMonitorConfig)
    # Track C monthly loss halt (fraction of Track C capital). Reference
    # declaration — enforcement is wired into kill_switch by the risk lane.
    track_c_monthly_loss_halt: float = Field(default=0.15, gt=0.0, lt=1.0)

    @classmethod
    def load_or_default(cls, path: str | None = None) -> PortfolioConfig:
        """Load from YAML when available, otherwise return validated defaults."""
        try:
            return cls.from_yaml(path)
        except ConfigNotFoundError:
            return cls()
