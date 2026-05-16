"""Risk State Data Models

Data models for tracking portfolio-level risk metrics and exposure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class DrawdownLevel(Enum):
    """Drawdown alert level"""

    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"
    CRITICAL = "critical"


class BlockReason(Enum):
    """Reason for blocking new positions"""

    DAILY_LOSS_LIMIT = "daily_loss_limit"
    MAX_POSITIONS = "max_positions"
    DRAWDOWN_CRITICAL = "drawdown_critical"
    MANUAL = "manual"


@dataclass
class AssetExposure:
    """Per-asset class exposure tracking

    Attributes:
        asset_class: Asset class name ('stock', 'futures')
        position_count: Number of open positions
        total_value: Total market value of positions (KRW)
        unrealized_pnl: Total unrealized P&L (KRW)
        exposure_pct: Exposure as percentage of portfolio
    """

    asset_class: str
    position_count: int = 0
    total_value: float = 0.0
    unrealized_pnl: float = 0.0
    exposure_pct: float = 0.0

    def update(
        self,
        position_count: int,
        total_value: float,
        unrealized_pnl: float,
        portfolio_value: float,
    ):
        """Update exposure metrics

        Args:
            position_count: Number of positions
            total_value: Total market value
            unrealized_pnl: Unrealized P&L
            portfolio_value: Total portfolio value for percentage calc
        """
        self.position_count = position_count
        self.total_value = total_value
        self.unrealized_pnl = unrealized_pnl
        self.exposure_pct = (
            (total_value / portfolio_value * 100) if portfolio_value > 0 else 0.0
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization"""
        return {
            "asset_class": self.asset_class,
            "position_count": self.position_count,
            "total_value": self.total_value,
            "unrealized_pnl": self.unrealized_pnl,
            "exposure_pct": self.exposure_pct,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssetExposure:
        """Create from dict"""
        return cls(
            asset_class=data["asset_class"],
            position_count=data.get("position_count", 0),
            total_value=data.get("total_value", 0.0),
            unrealized_pnl=data.get("unrealized_pnl", 0.0),
            exposure_pct=data.get("exposure_pct", 0.0),
        )


@dataclass
class PortfolioMetrics:
    """Aggregate portfolio metrics across all asset classes

    Attributes:
        total_positions: Total number of open positions
        total_exposure: Total portfolio exposure (KRW)
        total_unrealized_pnl: Total unrealized P&L (KRW)
        portfolio_value: Current portfolio value (KRW)
        exposure_by_asset: Per-asset class exposure breakdown
    """

    total_positions: int = 0
    total_exposure: float = 0.0
    total_realized_pnl: float = 0.0
    total_unrealized_pnl: float = 0.0
    portfolio_value: float = 0.0
    exposure_by_asset: dict[str, AssetExposure] = field(default_factory=dict)

    def update_from_positions(
        self,
        positions_by_asset: dict[str, list],
        initial_capital: float,
        realized_pnl: float = 0.0,
    ):
        """Update metrics from position data

        Args:
            positions_by_asset: Dict of asset_class -> list of Position objects
            initial_capital: Initial capital for portfolio value calculation
            realized_pnl: Realized P&L already locked in for the current risk window
        """
        self.total_positions = 0
        self.total_exposure = 0.0
        self.total_realized_pnl = realized_pnl
        self.total_unrealized_pnl = 0.0
        self.exposure_by_asset.clear()

        # Aggregate metrics by asset class
        for asset_class, positions in positions_by_asset.items():
            if not positions:
                continue

            # Calculate asset-level metrics
            asset_position_count = len(positions)
            asset_total_value = sum(
                pos.current_price * pos.quantity for pos in positions
            )
            asset_unrealized_pnl = sum(pos.unrealized_pnl for pos in positions)

            # Update portfolio totals
            self.total_positions += asset_position_count
            self.total_exposure += asset_total_value
            self.total_unrealized_pnl += asset_unrealized_pnl

            # Store asset exposure
            self.exposure_by_asset[asset_class] = AssetExposure(asset_class)

        # Calculate portfolio value
        self.portfolio_value = (
            initial_capital + self.total_realized_pnl + self.total_unrealized_pnl
        )

        # Update exposure percentages
        for asset_class, positions in positions_by_asset.items():
            if not positions:
                continue

            asset_total_value = sum(
                pos.current_price * pos.quantity for pos in positions
            )
            asset_unrealized_pnl = sum(pos.unrealized_pnl for pos in positions)

            if asset_class in self.exposure_by_asset:
                self.exposure_by_asset[asset_class].update(
                    position_count=len(positions),
                    total_value=asset_total_value,
                    unrealized_pnl=asset_unrealized_pnl,
                    portfolio_value=self.portfolio_value,
                )

    def get_position_count(self, asset_class: str) -> int:
        """Get position count for specific asset class

        Args:
            asset_class: Asset class name

        Returns:
            Number of positions for asset class
        """
        if asset_class in self.exposure_by_asset:
            return self.exposure_by_asset[asset_class].position_count
        return 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization"""
        return {
            "total_positions": self.total_positions,
            "total_exposure": self.total_exposure,
            "total_realized_pnl": self.total_realized_pnl,
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "portfolio_value": self.portfolio_value,
            "exposure_by_asset": {
                k: v.to_dict() for k, v in self.exposure_by_asset.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PortfolioMetrics:
        """Create from dict"""
        exposure_by_asset = {
            k: AssetExposure.from_dict(v)
            for k, v in data.get("exposure_by_asset", {}).items()
        }

        return cls(
            total_positions=data.get("total_positions", 0),
            total_exposure=data.get("total_exposure", 0.0),
            total_realized_pnl=data.get("total_realized_pnl", 0.0),
            total_unrealized_pnl=data.get("total_unrealized_pnl", 0.0),
            portfolio_value=data.get("portfolio_value", 0.0),
            exposure_by_asset=exposure_by_asset,
        )


@dataclass
class RiskState:
    """Portfolio risk state tracking

    Tracks daily P&L, peak portfolio value, drawdown, and blocking state.

    Attributes:
        daily_pnl: Daily profit/loss (KRW)
        daily_realized_pnl: Realized daily profit/loss (KRW)
        daily_pnl_pct: Daily P&L as percentage of initial capital
        peak_portfolio_value: Peak portfolio value (for drawdown)
        current_portfolio_value: Current portfolio value
        drawdown_pct: Current drawdown percentage
        drawdown_level: Current drawdown alert level
        is_blocked: Whether new positions are blocked
        block_reason: Reason for blocking (if blocked)
        last_reset_date: Date of last daily reset
        last_updated: Timestamp of last update
        alerts_sent: Set of alert levels already sent (for deduplication)
    """

    # Daily P&L tracking
    daily_pnl: float = 0.0
    daily_realized_pnl: float = 0.0
    daily_pnl_pct: float = 0.0

    # Drawdown tracking
    peak_portfolio_value: float = 0.0
    current_portfolio_value: float = 0.0
    drawdown_pct: float = 0.0
    drawdown_level: DrawdownLevel = DrawdownLevel.SAFE

    # Blocking state
    is_blocked: bool = False
    block_reason: BlockReason | None = None

    # Timestamps
    last_reset_date: date = field(default_factory=date.today)
    last_updated: datetime = field(default_factory=datetime.now)

    # Alert tracking (for deduplication)
    alerts_sent: set[str] = field(default_factory=set)

    def update_daily_pnl(self, realized_pnl: float, unrealized_pnl: float):
        """Update daily P&L

        Args:
            realized_pnl: Realized P&L for the day
            unrealized_pnl: Current unrealized P&L
        """
        self.daily_realized_pnl = realized_pnl
        self.daily_pnl = realized_pnl + unrealized_pnl
        self.last_updated = datetime.now()

    def update_portfolio_value(self, current_value: float, initial_capital: float):
        """Update portfolio value and calculate drawdown

        Args:
            current_value: Current portfolio value
            initial_capital: Initial capital for percentage calculations
        """
        self.current_portfolio_value = current_value

        # Update peak
        if current_value > self.peak_portfolio_value:
            self.peak_portfolio_value = current_value

        # Calculate drawdown
        if self.peak_portfolio_value > 0:
            self.drawdown_pct = (
                (self.peak_portfolio_value - current_value)
                / self.peak_portfolio_value
                * 100
            )
        else:
            self.drawdown_pct = 0.0

        # Calculate daily P&L percentage
        if initial_capital > 0:
            self.daily_pnl_pct = (self.daily_pnl / initial_capital) * 100
        else:
            self.daily_pnl_pct = 0.0

        self.last_updated = datetime.now()

    def update_drawdown_level(
        self,
        warning_threshold: float,
        danger_threshold: float,
        critical_threshold: float,
    ):
        """Update drawdown alert level based on thresholds

        Args:
            warning_threshold: Warning level threshold (%)
            danger_threshold: Danger level threshold (%)
            critical_threshold: Critical level threshold (%)
        """
        if self.drawdown_pct >= critical_threshold:
            self.drawdown_level = DrawdownLevel.CRITICAL
        elif self.drawdown_pct >= danger_threshold:
            self.drawdown_level = DrawdownLevel.DANGER
        elif self.drawdown_pct >= warning_threshold:
            self.drawdown_level = DrawdownLevel.WARNING
        else:
            self.drawdown_level = DrawdownLevel.SAFE

    def block_trading(self, reason: BlockReason):
        """Block new position entries

        Args:
            reason: Reason for blocking
        """
        self.is_blocked = True
        self.block_reason = reason
        self.last_updated = datetime.now()

    def unblock_trading(self):
        """Unblock position entries"""
        self.is_blocked = False
        self.block_reason = None
        self.last_updated = datetime.now()

    def reset_daily(self, initial_capital: float):
        """Reset daily tracking metrics

        Args:
            initial_capital: Initial capital to reset peak if needed
        """
        self.daily_pnl = 0.0
        self.daily_realized_pnl = 0.0
        self.daily_pnl_pct = 0.0
        self.last_reset_date = date.today()
        self.alerts_sent.clear()

        # Reset peak if starting fresh
        if self.peak_portfolio_value == 0.0:
            self.peak_portfolio_value = initial_capital

        self.last_updated = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization"""
        return {
            "daily_pnl": self.daily_pnl,
            "daily_realized_pnl": self.daily_realized_pnl,
            "daily_pnl_pct": self.daily_pnl_pct,
            "peak_portfolio_value": self.peak_portfolio_value,
            "current_portfolio_value": self.current_portfolio_value,
            "drawdown_pct": self.drawdown_pct,
            "drawdown_level": self.drawdown_level.value,
            "is_blocked": self.is_blocked,
            "block_reason": self.block_reason.value if self.block_reason else None,
            "last_reset_date": self.last_reset_date.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "alerts_sent": list(self.alerts_sent),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RiskState:
        """Create from dict

        Args:
            data: Serialized state dict

        Returns:
            RiskState instance
        """
        # Parse enums
        drawdown_level = DrawdownLevel(data.get("drawdown_level", "safe"))
        block_reason = None
        if data.get("block_reason"):
            block_reason = BlockReason(data["block_reason"])

        # Parse dates
        last_reset_date = date.fromisoformat(
            data.get("last_reset_date", date.today().isoformat())
        )
        last_updated = datetime.fromisoformat(
            data.get("last_updated", datetime.now().isoformat())
        )

        return cls(
            daily_pnl=data.get("daily_pnl", 0.0),
            daily_realized_pnl=data.get("daily_realized_pnl", 0.0),
            daily_pnl_pct=data.get("daily_pnl_pct", 0.0),
            peak_portfolio_value=data.get("peak_portfolio_value", 0.0),
            current_portfolio_value=data.get("current_portfolio_value", 0.0),
            drawdown_pct=data.get("drawdown_pct", 0.0),
            drawdown_level=drawdown_level,
            is_blocked=data.get("is_blocked", False),
            block_reason=block_reason,
            last_reset_date=last_reset_date,
            last_updated=last_updated,
            alerts_sent=set(data.get("alerts_sent", [])),
        )
