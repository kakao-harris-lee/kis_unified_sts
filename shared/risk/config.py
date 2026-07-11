"""Risk Management Configuration

Pydantic configuration schema for portfolio-level risk management.
Loaded from config/risk_management.yaml.

Usage:
    from shared.risk.config import RiskConfig, AssetLimits

    # Create with defaults
    config = RiskConfig(daily_loss_limit_pct=5.0, max_total_positions=20)

    # Load from dict
    config = RiskConfig.from_dict(yaml_data)

Futures-specific risk config (Phase 3):
    from shared.risk.config import FuturesRiskConfig, load_trading_windows

    config = FuturesRiskConfig.from_yaml()
    windows = load_trading_windows()
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


# Validation constants
MIN_LOSS_LIMIT_PCT = 0.1  # 0.1%
MAX_LOSS_LIMIT_PCT = 50.0  # 50%
MIN_POSITIONS = 1
MAX_POSITIONS = 100
MIN_CAPITAL = 100_000  # 10만원
MAX_CAPITAL = 10_000_000_000  # 100억원
MIN_EXPOSURE_PCT = 1.0
MAX_EXPOSURE_PCT = 100.0
MIN_POSITION_SIZE_PCT = 0.1
MAX_POSITION_SIZE_PCT = 100.0
MIN_DRAWDOWN_THRESHOLD = 0.1
MAX_DRAWDOWN_THRESHOLD = 50.0
MIN_SAVE_INTERVAL = 10  # seconds
MAX_SAVE_INTERVAL = 3600  # 1 hour


@dataclass
class DrawdownThresholds:
    """Drawdown alert thresholds"""

    warning: float = 3.0  # %
    danger: float = 5.0  # %
    critical: float = 7.0  # %

    def __post_init__(self):
        """Validate thresholds."""
        self._validate()

    def _validate(self):
        """Validate all threshold values."""
        for name, value in [
            ("warning", self.warning),
            ("danger", self.danger),
            ("critical", self.critical),
        ]:
            if not (MIN_DRAWDOWN_THRESHOLD <= value <= MAX_DRAWDOWN_THRESHOLD):
                raise ValueError(
                    f"Drawdown threshold '{name}' must be between "
                    f"{MIN_DRAWDOWN_THRESHOLD} and {MAX_DRAWDOWN_THRESHOLD}, got {value}"
                )

        if not (self.warning < self.danger < self.critical):
            raise ValueError(
                f"Drawdown thresholds must be ascending: warning ({self.warning}) < "
                f"danger ({self.danger}) < critical ({self.critical})"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DrawdownThresholds:
        """Create from dict."""
        return cls(
            warning=float(data.get("warning", 3.0)),
            danger=float(data.get("danger", 5.0)),
            critical=float(data.get("critical", 7.0)),
        )


@dataclass
class DrawdownConfig:
    """Drawdown monitoring configuration"""

    enabled: bool = True
    thresholds: DrawdownThresholds = field(default_factory=DrawdownThresholds)
    lookback_days: int = 30
    alert_once_per_level: bool = True

    def __post_init__(self):
        """Validate configuration."""
        self._validate()

    def _validate(self):
        """Validate drawdown config."""
        if not isinstance(self.enabled, bool):
            raise TypeError(f"enabled must be bool, got {type(self.enabled)}")

        if not (1 <= self.lookback_days <= 365):
            raise ValueError(
                f"lookback_days must be between 1 and 365, got {self.lookback_days}"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DrawdownConfig:
        """Create from dict."""
        thresholds_data = data.get("thresholds", {})
        return cls(
            enabled=bool(data.get("enabled", True)),
            thresholds=DrawdownThresholds.from_dict(thresholds_data),
            lookback_days=int(data.get("lookback_days", 30)),
            alert_once_per_level=bool(data.get("alert_once_per_level", True)),
        )


@dataclass
class AssetLimits:
    """Per-asset class position limits"""

    max_positions: int = 10
    max_position_size_pct: float = 10.0
    max_total_exposure_pct: float = 80.0

    def __post_init__(self):
        """Validate limits."""
        self._validate()

    def _validate(self):
        """Validate all limit values."""
        if not (MIN_POSITIONS <= self.max_positions <= MAX_POSITIONS):
            raise ValueError(
                f"max_positions must be between {MIN_POSITIONS} and {MAX_POSITIONS}, "
                f"got {self.max_positions}"
            )

        if not (
            MIN_POSITION_SIZE_PCT <= self.max_position_size_pct <= MAX_POSITION_SIZE_PCT
        ):
            raise ValueError(
                f"max_position_size_pct must be between {MIN_POSITION_SIZE_PCT} "
                f"and {MAX_POSITION_SIZE_PCT}, got {self.max_position_size_pct}"
            )

        if not (MIN_EXPOSURE_PCT <= self.max_total_exposure_pct <= MAX_EXPOSURE_PCT):
            raise ValueError(
                f"max_total_exposure_pct must be between {MIN_EXPOSURE_PCT} "
                f"and {MAX_EXPOSURE_PCT}, got {self.max_total_exposure_pct}"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssetLimits:
        """Create from dict."""
        return cls(
            max_positions=int(data.get("max_positions", 10)),
            max_position_size_pct=float(data.get("max_position_size_pct", 10.0)),
            max_total_exposure_pct=float(data.get("max_total_exposure_pct", 80.0)),
        )


@dataclass
class PositionSizingConfig:
    """Position sizing controls"""

    adaptive_sizing_enabled: bool = True
    scale_down_at_pct: float = 0.8
    scale_down_factor: float = 0.5
    min_position_value: int = 1_000_000

    def __post_init__(self):
        """Validate configuration."""
        self._validate()

    def _validate(self):
        """Validate position sizing config."""
        if not isinstance(self.adaptive_sizing_enabled, bool):
            raise TypeError(
                f"adaptive_sizing_enabled must be bool, got {type(self.adaptive_sizing_enabled)}"
            )

        if not (0.0 < self.scale_down_at_pct <= 1.0):
            raise ValueError(
                f"scale_down_at_pct must be between 0.0 and 1.0, "
                f"got {self.scale_down_at_pct}"
            )

        if not (0.0 < self.scale_down_factor <= 1.0):
            raise ValueError(
                f"scale_down_factor must be between 0.0 and 1.0, "
                f"got {self.scale_down_factor}"
            )

        if not (MIN_CAPITAL <= self.min_position_value <= MAX_CAPITAL):
            raise ValueError(
                f"min_position_value must be between {MIN_CAPITAL} and {MAX_CAPITAL}, "
                f"got {self.min_position_value}"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PositionSizingConfig:
        """Create from dict."""
        return cls(
            adaptive_sizing_enabled=bool(data.get("adaptive_sizing_enabled", True)),
            scale_down_at_pct=float(data.get("scale_down_at_pct", 0.8)),
            scale_down_factor=float(data.get("scale_down_factor", 0.5)),
            min_position_value=int(data.get("min_position_value", 1_000_000)),
        )


@dataclass
class MonitoringConfig:
    """Risk monitoring configuration"""

    update_on_position_change: bool = True
    save_interval_seconds: int = 60
    daily_reset_time: str = "09:00"
    auto_unblock_on_reset: bool = True

    def __post_init__(self):
        """Validate configuration."""
        self._validate()

    def _validate(self):
        """Validate monitoring config."""
        if not isinstance(self.update_on_position_change, bool):
            raise TypeError(
                f"update_on_position_change must be bool, got {type(self.update_on_position_change)}"
            )

        if not (MIN_SAVE_INTERVAL <= self.save_interval_seconds <= MAX_SAVE_INTERVAL):
            raise ValueError(
                f"save_interval_seconds must be between {MIN_SAVE_INTERVAL} and "
                f"{MAX_SAVE_INTERVAL}, got {self.save_interval_seconds}"
            )

        # Validate time format HH:MM
        if not isinstance(self.daily_reset_time, str):
            raise TypeError(
                f"daily_reset_time must be str, got {type(self.daily_reset_time)}"
            )

        parts = self.daily_reset_time.split(":")
        if len(parts) != 2:
            raise ValueError(
                f"daily_reset_time must be in HH:MM format, got {self.daily_reset_time}"
            )

        try:
            hour, minute = int(parts[0]), int(parts[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError(
                    f"Invalid time in daily_reset_time: {self.daily_reset_time}"
                )
        except ValueError as e:
            raise ValueError(
                f"daily_reset_time must be valid HH:MM format, got {self.daily_reset_time}: {e}"
            ) from e

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MonitoringConfig:
        """Create from dict."""
        return cls(
            update_on_position_change=bool(data.get("update_on_position_change", True)),
            save_interval_seconds=int(data.get("save_interval_seconds", 60)),
            daily_reset_time=str(data.get("daily_reset_time", "09:00")),
            auto_unblock_on_reset=bool(data.get("auto_unblock_on_reset", True)),
        )


@dataclass
class NotificationEvents:
    """Notification events configuration"""

    daily_loss_limit_breached: bool = True
    drawdown_threshold_crossed: bool = True
    position_limit_reached: bool = True
    exposure_limit_approached: bool = True
    trading_blocked: bool = True
    trading_unblocked: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NotificationEvents:
        """Create from dict."""
        return cls(
            daily_loss_limit_breached=bool(data.get("daily_loss_limit_breached", True)),
            drawdown_threshold_crossed=bool(
                data.get("drawdown_threshold_crossed", True)
            ),
            position_limit_reached=bool(data.get("position_limit_reached", True)),
            exposure_limit_approached=bool(data.get("exposure_limit_approached", True)),
            trading_blocked=bool(data.get("trading_blocked", True)),
            trading_unblocked=bool(data.get("trading_unblocked", True)),
        )


@dataclass
class NotificationConfig:
    """Risk notification configuration"""

    enabled: bool = True
    events: NotificationEvents = field(default_factory=NotificationEvents)
    use_critical_flag: bool = True

    def __post_init__(self):
        """Validate configuration."""
        if not isinstance(self.enabled, bool):
            raise TypeError(f"enabled must be bool, got {type(self.enabled)}")

        if not isinstance(self.use_critical_flag, bool):
            raise TypeError(
                f"use_critical_flag must be bool, got {type(self.use_critical_flag)}"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NotificationConfig:
        """Create from dict."""
        events_data = data.get("events", {})
        return cls(
            enabled=bool(data.get("enabled", True)),
            events=NotificationEvents.from_dict(events_data),
            use_critical_flag=bool(data.get("use_critical_flag", True)),
        )


@dataclass
class RedisConfig:
    """Redis persistence configuration"""

    key_prefix: str = "risk:portfolio"
    state_ttl: int = 86400  # 24 hours
    db: int = 1

    def __post_init__(self):
        """Validate configuration."""
        self._validate()

    def _validate(self):
        """Validate redis config."""
        if not isinstance(self.key_prefix, str):
            raise TypeError(f"key_prefix must be str, got {type(self.key_prefix)}")

        if not self.key_prefix:
            raise ValueError("key_prefix cannot be empty")

        if not (1 <= self.state_ttl <= 31536000):  # 1 second to 1 year
            raise ValueError(
                f"state_ttl must be between 1 and 31536000 seconds, got {self.state_ttl}"
            )

        if not isinstance(self.db, int):
            raise TypeError(f"db must be int, got {type(self.db)}")

        if not (0 <= self.db <= 15):
            raise ValueError(f"db must be between 0 and 15, got {self.db}")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RedisConfig:
        """Create from dict."""
        return cls(
            key_prefix=str(data.get("key_prefix", "risk:portfolio")),
            state_ttl=int(data.get("state_ttl", 86400)),
            db=int(data.get("db", 1)),
        )


@dataclass
class RiskConfig:
    """Risk management configuration

    Portfolio-level risk controls and limits for cross-asset trading.

    Attributes:
        daily_loss_limit_pct: Daily loss limit as percentage of initial capital
        max_total_positions: Maximum concurrent positions across all asset classes
        initial_capital: Initial capital for risk calculations (KRW)
        drawdown: Drawdown monitoring configuration
        asset_limits: Per-asset class limits (stock, futures)
        position_sizing: Position sizing controls
        monitoring: Risk monitoring configuration
        notifications: Notification configuration
        redis: Redis persistence configuration
    """

    # Portfolio-level limits
    daily_loss_limit_pct: float = 5.0
    max_total_positions: int = 20
    initial_capital: int = 10_000_000

    # Futures-native circuit breakers (0 = disabled). The KRW %-of-capital
    # daily_loss_limit_pct above is mis-scaled for a single futures contract
    # (notional ~30x the risk capital), so these unit-safe breakers halt new
    # entries on a losing streak instead. Both reset on the daily reset.
    max_consecutive_losses: int = 0  # halt after N consecutive losing closes
    daily_loss_limit_points: float = 0.0  # halt when session realized PnL <= -this
    #   (in the position's native PnL unit — index points for futures)

    # Sub-configurations
    drawdown: DrawdownConfig = field(default_factory=DrawdownConfig)
    asset_limits: dict[str, AssetLimits] = field(default_factory=dict)
    position_sizing: PositionSizingConfig = field(default_factory=PositionSizingConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)

    def __post_init__(self):
        """Validate configuration values."""
        self._validate()
        self._set_defaults()

    def _validate(self):
        """Validate all configuration parameters."""
        if not (MIN_LOSS_LIMIT_PCT <= self.daily_loss_limit_pct <= MAX_LOSS_LIMIT_PCT):
            raise ValueError(
                f"daily_loss_limit_pct must be between {MIN_LOSS_LIMIT_PCT} and "
                f"{MAX_LOSS_LIMIT_PCT}, got {self.daily_loss_limit_pct}"
            )

        if not (MIN_POSITIONS <= self.max_total_positions <= MAX_POSITIONS):
            raise ValueError(
                f"max_total_positions must be between {MIN_POSITIONS} and "
                f"{MAX_POSITIONS}, got {self.max_total_positions}"
            )

        if not (MIN_CAPITAL <= self.initial_capital <= MAX_CAPITAL):
            raise ValueError(
                f"initial_capital must be between {MIN_CAPITAL} and {MAX_CAPITAL}, "
                f"got {self.initial_capital}"
            )

        if self.max_consecutive_losses < 0:
            raise ValueError(
                f"max_consecutive_losses must be >= 0, got {self.max_consecutive_losses}"
            )

        if self.daily_loss_limit_points < 0:
            raise ValueError(
                f"daily_loss_limit_points must be >= 0, got {self.daily_loss_limit_points}"
            )

    def _set_defaults(self):
        """Set default asset limits if not provided."""
        if "stock" not in self.asset_limits:
            self.asset_limits["stock"] = AssetLimits(
                max_positions=15,
                max_position_size_pct=10.0,
                max_total_exposure_pct=80.0,
            )

        if "futures" not in self.asset_limits:
            self.asset_limits["futures"] = AssetLimits(
                max_positions=5,
                max_position_size_pct=15.0,
                max_total_exposure_pct=50.0,
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RiskConfig:
        """Create config from dict with validation.

        Args:
            data: Configuration dictionary from YAML

        Returns:
            Validated RiskConfig

        Raises:
            ValueError: If validation fails
            TypeError: If type validation fails
        """
        # Get risk_management section if it exists (for full YAML file)
        if "risk_management" in data:
            data = data["risk_management"]

        # Parse core fields
        daily_loss_limit_pct = float(data.get("daily_loss_limit_pct", 5.0))
        max_total_positions = int(data.get("max_total_positions", 20))
        initial_capital = int(data.get("initial_capital", 10_000_000))
        max_consecutive_losses = int(data.get("max_consecutive_losses", 0))
        daily_loss_limit_points = float(data.get("daily_loss_limit_points", 0.0))

        # Parse sub-configurations
        drawdown_data = data.get("drawdown", {})
        drawdown = DrawdownConfig.from_dict(drawdown_data)

        # Parse asset limits
        asset_limits_data = data.get("asset_limits", {})
        asset_limits: dict[str, AssetLimits] = {}
        for asset_class, limits_data in asset_limits_data.items():
            asset_limits[asset_class] = AssetLimits.from_dict(limits_data)

        # Parse other configs
        position_sizing_data = data.get("position_sizing", {})
        position_sizing = PositionSizingConfig.from_dict(position_sizing_data)

        monitoring_data = data.get("monitoring", {})
        monitoring = MonitoringConfig.from_dict(monitoring_data)

        notifications_data = data.get("notifications", {})
        notifications = NotificationConfig.from_dict(notifications_data)

        redis_data = data.get("redis", {})
        redis_config = RedisConfig.from_dict(redis_data)

        return cls(
            daily_loss_limit_pct=daily_loss_limit_pct,
            max_total_positions=max_total_positions,
            initial_capital=initial_capital,
            max_consecutive_losses=max_consecutive_losses,
            daily_loss_limit_points=daily_loss_limit_points,
            drawdown=drawdown,
            asset_limits=asset_limits,
            position_sizing=position_sizing,
            monitoring=monitoring,
            notifications=notifications,
            redis=redis_config,
        )

    def get_asset_limits(self, asset_class: str) -> AssetLimits:
        """Get limits for specific asset class.

        Args:
            asset_class: Asset class name ('stock', 'futures')

        Returns:
            AssetLimits for the asset class

        Raises:
            ValueError: If asset class not configured
        """
        if asset_class not in self.asset_limits:
            raise ValueError(f"No limits configured for asset class: {asset_class}")

        return self.asset_limits[asset_class]


# ---------------------------------------------------------------------------
# Phase 3: Futures intraday risk config (ServiceConfigBase-based)
# ---------------------------------------------------------------------------

from typing import Literal  # noqa: E402 — grouped with the deferred imports

from pydantic import BaseModel, Field  # noqa: E402 — deferred import (circulars)

from shared.config.base import ServiceConfigBase  # noqa: E402


class PortfolioMddFilterSettings(BaseModel):
    """Unified portfolio-MDD filter knobs (Phase 3B, roadmap §5.5).

    The filter reads the ``portfolio:equity:latest`` hash published by
    ``services/portfolio_monitor`` and fails OPEN whenever the key is absent,
    stale, unparseable, or the published breaker ``mode`` is not ``enforce``.
    Stage thresholds/size factors live in ``config/portfolio.yaml`` — this
    block only wires the read side.
    """

    enabled: bool = Field(
        default=True,
        description="Run the portfolio_mdd filter in the RiskFilterLayer chain",
    )
    latest_key: str = Field(
        default="portfolio:equity:latest",
        description="Redis hash published by services/portfolio_monitor",
    )
    stale_max_age_seconds: int = Field(
        default=93600,
        description=(
            "Fail-open when the snapshot asof_ts (KST naive ISO) is older "
            "than this. 26h covers the daily 19:00 KST cadence with slack; "
            "the key's own 24h TTL is the harder bound."
        ),
    )


class ConcurrentPositionsFilterSettings(BaseModel):
    """Total + per-asset concurrent-entry caps (Phase 4-e).

    Ports the World-A ``RiskManager`` concurrency caps (``max_total_positions``
    and per-asset ``asset_limits.*.max_positions``) into the decoupled
    ``RiskFilterLayer``. The cap field names are kept aligned with the World-A
    keys so the P4-h2 two-world config unification can converge on one source.

    ``enabled`` defaults to ``False`` so the filter is **structurally inert**
    (never even constructed) until an operator opts in — the shadow daemons'
    existing pass-through behaviour is unchanged. Even when enabled the filter
    fails OPEN whenever the count provider or both caps are absent.
    """

    enabled: bool = Field(
        default=False,
        description="Build the concurrent_positions filter in the layer chain",
    )
    max_total_positions: int | None = Field(
        default=None,
        gt=0,
        description=(
            "Portfolio-wide open-position cap (aligned with World-A "
            "risk_management.max_total_positions). None disables the total check. "
            "Must be > 0 (a 0 cap would reject every entry — matches World-A "
            "MIN_POSITIONS=1)."
        ),
    )
    max_positions_per_asset: int | None = Field(
        default=None,
        gt=0,
        description=(
            "Per-asset-class open-position cap (aligned with World-A "
            "asset_limits.<asset>.max_positions). None disables the per-asset "
            "check. Must be > 0."
        ),
    )


class CoreSectorCapSettings(BaseModel):
    """Rule 2 — sector cap on Track B open-position notional (Phase 5B §7.2).

    Rejects NEW entries into ``sector_key`` while that sector's share of the
    current Track B open-position notional is at or above ``cap``.

    ``classification_source`` is deliberately restricted: the only trustworthy
    symbol→sector mapping wired today is the Track A core-holdings ledger
    itself (operator-assigned ``sector`` on holdings/candidates). No repo
    source classifies arbitrary KOSPI/KOSDAQ codes — the screener universe,
    theme targets, and market-structure stores carry no per-symbol sector, and
    ``config/trade_trend_priority.yaml::symbol_sectors`` is a ~17-symbol
    screener-priority whitelist, not a risk-grade classification. Until a real
    sector pipeline exists this rule therefore only fires for candidates the
    operator has explicitly listed in the ledger (conservative reduced scope).
    """

    enabled: bool = Field(
        default=True,
        description="Run the core_sector_cap filter in the stock chain",
    )
    sector_key: str = Field(
        default="semiconductor_equipment",
        description="Capped sector key (config/portfolio/core_holdings.yaml sectors)",
    )
    cap: float = Field(
        default=0.40,
        gt=0.0,
        le=1.0,
        description="Reject new sector entries when sector share >= cap",
    )
    skip_reason: str = Field(
        default="sector_cap_semiconductor",
        description="Rejection tag emitted when the cap blocks an entry",
    )
    classification_source: Literal["core_holdings"] = Field(
        default="core_holdings",
        description="Symbol→sector source (only the Track A ledger is wired)",
    )


class CoreCorrelationSettings(BaseModel):
    """Track A/B correlation rules (Phase 5B, roadmap §5.1 / 설계서 §7.2).

    Both rules read the Track A manual core-holdings ledger
    (``config/portfolio/core_holdings.yaml``) and are automatic no-ops while
    the ledger is empty. Ledger load failures fail OPEN (pass + warning).
    """

    overlap_enabled: bool = Field(
        default=True,
        description=(
            "Rule 1 — reject Track B candidates already held in Track A "
            "(skip_reason: track_a_overlap)"
        ),
    )
    reload_interval_seconds: int = Field(
        default=60,
        gt=0,
        description=(
            "Ledger mtime re-check cadence; YAML is re-parsed only when the "
            "mtime actually changed (never on the hot path)"
        ),
    )
    sector_cap: CoreSectorCapSettings = Field(
        default_factory=CoreSectorCapSettings,
        description="Rule 2 — sector cap on Track B open-position notional",
    )


class FuturesRiskConfig(ServiceConfigBase):
    """Futures intraday risk parameters for the Phase 3 RiskFilterLayer.

    Loaded from ``config/risk.yaml`` under the ``risk:`` section.

    Attributes:
        account_equity_krw: Account equity in KRW (used for MDD calculations).
        daily_mdd_limit_pct: Max daily drawdown as a fraction of equity (e.g. 0.03 = 3%).
        weekly_mdd_limit_pct: Max weekly drawdown as a fraction of equity (e.g. 0.07 = 7%).
        max_position_risk_pct: Max risk per trade as a fraction of equity (e.g. 0.015 = 1.5%).
        max_daily_trades: Maximum number of trades allowed per session day.
        max_position_size_contracts: Hard cap on contracts per order.
        consecutive_loss_soft_threshold: After this many consecutive losses,
            position size is halved (soft reduction, not a hard block).
        consecutive_loss_hard_threshold: After this many consecutive losses,
            all new entries are rejected until reset.
        max_spread_ticks: Maximum bid-ask spread in ticks; signals are rejected
            above this threshold.
    """

    _default_config_file: ClassVar[str] = "risk.yaml"
    _default_section: ClassVar[str] = "risk"
    _env_prefix: ClassVar[str] = "RISK_"
    #: Asset class this config drives — used to bind the per-asset concurrency
    #: cap (ConcurrentPositionsFilter). StockRiskConfig overrides it.
    _asset_class: ClassVar[str] = "futures"

    account_equity_krw: int = Field(
        default=5_000_000,
        description="Account equity in KRW",
    )
    daily_mdd_limit_pct: float = Field(
        default=0.03,
        description="Max daily MDD as fraction of equity (e.g. 0.03 = 3%)",
    )
    weekly_mdd_limit_pct: float = Field(
        default=0.07,
        description="Max weekly MDD as fraction of equity (e.g. 0.07 = 7%)",
    )
    max_position_risk_pct: float = Field(
        default=0.015,
        description="Max risk per trade as fraction of equity (e.g. 0.015 = 1.5%)",
    )
    max_daily_trades: int = Field(
        default=3,
        description="Maximum number of trades allowed per session day",
    )
    max_position_size_contracts: int = Field(
        default=2,
        description="Hard cap on contracts per order",
    )
    consecutive_loss_soft_threshold: int = Field(
        default=4,
        description="Consecutive losses before position size is halved",
    )
    consecutive_loss_hard_threshold: int = Field(
        default=6,
        description="Consecutive losses before all new entries are rejected",
    )
    soft_reduce_persist_days: int = Field(
        default=14,
        description=(
            "Days (KST) the x0.5 soft size reduction persists once the "
            "consecutive-loss streak reaches the soft threshold (design "
            "spec §4.2). 0 disables persistence (legacy behaviour: the "
            "reduction ends on the first win)."
        ),
    )
    reduce_blocks_at_floor: bool = Field(
        default=False,
        description=(
            "Operator policy for the floor-at-1 limit: when the soft "
            "reduction is active but cannot take effect (base quantity 1 "
            "floors x0.5 back to 1 contract), True rejects entries outright "
            "instead of passing at effectively full size. Default False "
            "preserves current behaviour (observable via filter logs)."
        ),
    )
    max_spread_ticks: int = Field(
        default=2,
        description="Max bid-ask spread in ticks; signals above this are rejected",
    )
    portfolio_mdd: PortfolioMddFilterSettings = Field(
        default_factory=PortfolioMddFilterSettings,
        description="Unified portfolio-MDD circuit-breaker filter (Phase 3B)",
    )
    concurrent_positions: ConcurrentPositionsFilterSettings = Field(
        default_factory=ConcurrentPositionsFilterSettings,
        description="Total + per-asset concurrent-entry caps (Phase 4-e)",
    )


class StockRiskConfig(FuturesRiskConfig):
    """Stock intraday risk parameters for the M4-R StockRiskFilterDaemon.

    FuturesRiskConfig's fields are asset-neutral (equity, MDD, consecutive-loss,
    trade-count, spread); only the YAML section and env prefix differ. Loaded
    from ``config/risk.yaml`` under the ``risk_stock:`` section.
    """

    _default_section: ClassVar[str] = "risk_stock"
    _env_prefix: ClassVar[str] = "STOCK_RISK_"
    _asset_class: ClassVar[str] = "stock"

    core_correlation: CoreCorrelationSettings = Field(
        default_factory=CoreCorrelationSettings,
        description=(
            "Track A/B correlation rules (Phase 5B) — stock-only; the field "
            "exists on StockRiskConfig only so the futures chain never grows "
            "these filters"
        ),
    )


def _load_risk_yaml(path: str | None = None) -> dict[str, Any]:
    """Load ``risk.yaml`` as a raw dict, resolving *path* the same way for all callers.

    - *None*: resolve via :class:`~shared.config.loader.ConfigLoader` (respects
      ``KIS_CONFIG_DIR``) using the default ``risk.yaml`` filename.
    - absolute path: ``open()`` directly (returns ``{}`` if the file is missing).
    - relative path: route through ``ConfigLoader.load`` so the loader's traversal
      protection applies.

    Returns ``{}`` for any non-dict / malformed YAML so callers can treat the
    result as a mapping unconditionally.
    """
    import yaml

    from shared.config.loader import ConfigLoader

    if path is None:
        env_config_dir = os.environ.get("KIS_CONFIG_DIR")
        if env_config_dir and Path(env_config_dir) != ConfigLoader.get_config_dir():
            ConfigLoader.set_config_dir(env_config_dir)
        raw_data = ConfigLoader.load("risk.yaml")
    elif os.path.isabs(str(path)):
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8") as f:
            raw_data = yaml.safe_load(f) or {}
    else:
        raw_data = ConfigLoader.load(path)

    return raw_data if isinstance(raw_data, dict) else {}


def load_stock_trading_windows(path: str | None = None) -> list[str]:
    """Load the ``trading_windows_stock`` list from ``config/risk.yaml``.

    Mirrors :func:`load_trading_windows` but reads the stock session key.
    Returns ``[]`` if the key is absent.
    """
    windows = _load_risk_yaml(path).get("trading_windows_stock", [])
    return list(windows) if isinstance(windows, list) else []


def load_trading_windows(path: str | None = None) -> list[str]:
    """Load the ``trading_windows`` list from ``config/risk.yaml``.

    The ``trading_windows`` key lives at the top level of ``risk.yaml``
    (sibling of the ``risk:`` section), so it is read separately from
    :class:`FuturesRiskConfig` which only extracts the ``risk:`` section.

    Args:
        path: Absolute or config-relative path to the YAML file.
              If *None*, resolves via :class:`~shared.config.loader.ConfigLoader`
              using the default ``risk.yaml`` filename.

    Returns:
        List of trading window strings in ``"HH:MM-HH:MM"`` KST format,
        e.g. ``["09:00-10:30", "14:30-15:20"]``.
        Returns an empty list if the key is absent.
    """
    windows = _load_risk_yaml(path).get("trading_windows", [])
    return list(windows) if isinstance(windows, list) else []
