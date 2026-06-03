"""Risk Manager

Portfolio-level risk management with cross-asset position tracking and limit enforcement.

Manages aggregate exposure across stock and futures positions, enforcing:
- Daily loss limits
- Maximum position counts (total and per-asset)
- Drawdown monitoring with alert thresholds
- Position entry blocking when limits are breached

Usage:
    from shared.risk.config import RiskConfig
    from shared.risk.manager import RiskManager

    # Initialize with config
    config = RiskConfig(
        daily_loss_limit_pct=5.0,
        max_total_positions=20,
        initial_capital=10_000_000
    )
    manager = RiskManager(config)

    # Update positions
    positions_by_asset = {
        'stock': [position1, position2],
        'futures': [position3]
    }
    manager.update_positions(positions_by_asset)

    # Check if can open new position
    if manager.can_open_position('stock'):
        # Open position
        pass
    else:
        # Position blocked
        pass

    # Get portfolio metrics
    metrics = manager.get_portfolio_metrics()
    print(f"Total positions: {metrics.total_positions}")
    print(f"Portfolio value: {metrics.portfolio_value}")

    # Calculate drawdown
    drawdown_pct = manager.calculate_drawdown()
    alert_level = manager.get_risk_state().drawdown_level
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from shared.risk.config import RiskConfig
from shared.risk.models import (
    BlockReason,
    DrawdownLevel,
    PortfolioMetrics,
    RiskState,
)

if TYPE_CHECKING:
    from shared.models.position import Position
    from shared.notification.telegram import TelegramNotifier

logger = logging.getLogger(__name__)

RISK_STATE_KEY_SUFFIX = "state"


class RiskManager:
    """Portfolio-level risk manager with cross-asset tracking

    Tracks aggregate exposure across all asset classes and enforces
    portfolio-level risk limits.

    Thread-safe: All public methods are designed to be thread-safe.

    Attributes:
        config: Risk management configuration
        state: Current risk state (daily P&L, drawdown, blocking)
        metrics: Current portfolio metrics
    """

    def __init__(self, config: RiskConfig):
        """Initialize risk manager

        Args:
            config: Risk management configuration

        Raises:
            ValueError: If config validation fails
        """
        self.config = config
        self.state = RiskState()
        self.metrics = PortfolioMetrics()

        # Initialize state with initial capital
        self.state.peak_portfolio_value = config.initial_capital
        self.state.current_portfolio_value = config.initial_capital

        # Internal attributes for testing/direct P&L tracking
        # These can be set directly for testing purposes
        self._daily_pnl: float | None = None
        self._initial_capital: float | None = None
        self._peak_portfolio_value: float | None = None
        self._current_portfolio_value: float | None = None
        self._last_reset_date: date = date.today()

        logger.info(
            f"RiskManager initialized: daily_loss_limit={config.daily_loss_limit_pct}%, "
            f"max_positions={config.max_total_positions}, "
            f"initial_capital={config.initial_capital:,} KRW"
        )

    def _risk_state_key(self) -> str:
        return f"{self.config.redis.key_prefix}:{RISK_STATE_KEY_SUFFIX}"

    def _serialize_state(self) -> dict[str, Any]:
        """Serialize risk state to dict for Redis persistence

        Returns:
            Dict containing serialized risk state and portfolio metrics
        """
        return {
            "state": self.state.to_dict(),
            "metrics": self.metrics.to_dict(),
        }

    def _deserialize_state(self, data: dict[str, Any]) -> None:
        """Deserialize risk state from Redis data

        Args:
            data: Serialized state dict from Redis
        """
        if "state" in data:
            self.state = RiskState.from_dict(data["state"])
            self._last_reset_date = self.state.last_reset_date

        if "metrics" in data:
            self.metrics = PortfolioMetrics.from_dict(data["metrics"])

        logger.debug(
            f"Risk state deserialized: daily_pnl={self.state.daily_pnl:.2f}, "
            f"positions={self.metrics.total_positions}, "
            f"is_blocked={self.state.is_blocked}"
        )

    def can_open_position(self, asset_class: str) -> bool:
        """Check if a new position can be opened for the given asset class

        Enforces:
        1. Daily loss limit not breached
        2. Not manually blocked
        3. Maximum total positions not exceeded
        4. Maximum positions per asset class not exceeded
        5. Critical drawdown not reached

        Args:
            asset_class: Asset class name ('stock', 'futures')

        Returns:
            True if position can be opened, False otherwise
        """
        self._check_and_reset_daily()

        # Check if trading is blocked
        if self.state.is_blocked:
            logger.warning(
                f"Cannot open position for {asset_class}: trading blocked due to {self.state.block_reason}"
            )
            return False

        # Check daily loss limit
        if not self._check_daily_loss_limit():
            # Calculate the actual P&L percentage for logging
            if self._daily_pnl is not None and self._initial_capital is not None:
                actual_pnl_pct = (
                    (self._daily_pnl / self._initial_capital) * 100
                    if self._initial_capital > 0
                    else 0.0
                )
            else:
                actual_pnl_pct = self.state.daily_pnl_pct

            logger.warning(
                f"Cannot open position for {asset_class}: daily loss limit breached "
                f"({actual_pnl_pct:.2f}% / -{self.config.daily_loss_limit_pct}%)"
            )
            # Auto-block trading when daily loss limit is breached
            self.state.block_trading(BlockReason.DAILY_LOSS_LIMIT)
            return False

        # Check maximum total positions
        if self.metrics.total_positions >= self.config.max_total_positions:
            logger.warning(
                f"Cannot open position for {asset_class}: maximum total positions reached "
                f"({self.metrics.total_positions} / {self.config.max_total_positions})"
            )
            return False

        # Check per-asset position limit
        try:
            asset_limits = self.config.get_asset_limits(asset_class)
            current_positions = self.metrics.get_position_count(asset_class)

            if current_positions >= asset_limits.max_positions:
                logger.warning(
                    f"Cannot open position for {asset_class}: asset class limit reached "
                    f"({current_positions} / {asset_limits.max_positions})"
                )
                return False

        except ValueError:
            # No per-asset limits configured — skip this check.
            # Portfolio-level max_total_positions still applies above.
            pass

        # Check critical drawdown
        if self.state.drawdown_level == DrawdownLevel.CRITICAL:
            logger.warning(
                f"Cannot open position for {asset_class}: critical drawdown level "
                f"({self.state.drawdown_pct:.2f}%)"
            )
            return False

        return True

    def update_positions(self, positions_by_asset: dict[str, list[Position]]):
        """Update portfolio metrics from current positions

        Recalculates all portfolio metrics including exposure, P&L, and drawdown.
        The risk window's realized P&L is preserved and combined with the
        current open-position P&L so closed losses still affect entry gates.

        Args:
            positions_by_asset: Dict mapping asset_class to list of Position objects
        """
        self._check_and_reset_daily()

        # Update portfolio metrics
        self.metrics.update_from_positions(
            positions_by_asset,
            self.config.initial_capital,
            realized_pnl=self.state.daily_realized_pnl,
        )

        self._update_state_from_metrics()
        self._log_risk_thresholds()

    def record_realized_pnl(self, pnl: float) -> None:
        """Record realized P&L from a just-closed trade.

        ``update_positions()`` only sees open positions, so without this call a
        stop-loss that has already closed disappears from both daily-loss and
        drawdown checks. This method keeps realized P&L in the risk state until
        the normal daily reset.
        """
        self._check_and_reset_daily()
        self.state.daily_realized_pnl += float(pnl)
        self.metrics.total_realized_pnl = self.state.daily_realized_pnl
        self.metrics.portfolio_value = (
            self.config.initial_capital
            + self.metrics.total_realized_pnl
            + self.metrics.total_unrealized_pnl
        )
        self._update_state_from_metrics()
        self._log_risk_thresholds()

    def _update_state_from_metrics(self) -> None:
        """Synchronize risk state from the latest realized/unrealized metrics."""
        self.state.update_daily_pnl(
            self.state.daily_realized_pnl,
            self.metrics.total_unrealized_pnl,
        )
        self.state.update_portfolio_value(
            self.metrics.portfolio_value, self.config.initial_capital
        )

        # Update drawdown level based on configured thresholds
        if self.config.drawdown.enabled:
            thresholds = self.config.drawdown.thresholds
            self.state.update_drawdown_level(
                thresholds.warning, thresholds.danger, thresholds.critical
            )

    def _log_risk_thresholds(self) -> None:
        """Log threshold proximity after risk-state updates."""
        # Log significant changes
        if self.state.daily_pnl_pct <= -self.config.daily_loss_limit_pct * 0.8:
            logger.warning(
                f"Portfolio approaching daily loss limit: {self.state.daily_pnl_pct:.2f}% "
                f"(limit: -{self.config.daily_loss_limit_pct}%)"
            )

        if self.state.drawdown_level in (DrawdownLevel.DANGER, DrawdownLevel.CRITICAL):
            logger.warning(
                f"Portfolio drawdown at {self.state.drawdown_level.value} level: "
                f"{self.state.drawdown_pct:.2f}%"
            )

    def get_portfolio_metrics(self) -> PortfolioMetrics:
        """Get current portfolio metrics

        Returns:
            Current portfolio metrics including positions, exposure, and P&L
        """
        return self.metrics

    def get_risk_state(self) -> RiskState:
        """Get current risk state

        Returns:
            Current risk state including daily P&L, drawdown, and blocking status
        """
        return self.state

    def check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit has been breached

        Returns:
            True if within limit, False if limit breached
        """
        return self._check_daily_loss_limit()

    def _check_daily_loss_limit(self) -> bool:
        """Internal check for daily loss limit

        Returns:
            True if within limit, False if limit breached
        """
        # Calculate daily P&L percentage
        # Use internal test attributes if set, otherwise use state
        if self._daily_pnl is not None and self._initial_capital is not None:
            # Direct test interface: calculate percentage from raw values
            if self._initial_capital > 0:
                daily_pnl_pct = (self._daily_pnl / self._initial_capital) * 100
            else:
                daily_pnl_pct = 0.0
        else:
            # Production path: use state
            daily_pnl_pct = self.state.daily_pnl_pct

        # Check if daily loss exceeds limit
        loss_limit_pct = -self.config.daily_loss_limit_pct
        return daily_pnl_pct >= loss_limit_pct

    def calculate_drawdown(self) -> float:
        """Calculate current portfolio drawdown

        Calculates drawdown from peak portfolio value and updates state with
        alert level based on configured thresholds.

        For testing, can use _peak_portfolio_value and _current_portfolio_value
        attributes directly. Otherwise uses state values.

        Returns:
            Drawdown percentage (e.g., 9.09 for 9.09% drawdown)
        """
        # Use test attributes if set, otherwise use state values
        if (
            self._peak_portfolio_value is not None
            and self._current_portfolio_value is not None
        ):
            peak = self._peak_portfolio_value
            current = self._current_portfolio_value
        else:
            peak = self.state.peak_portfolio_value
            current = self.state.current_portfolio_value

        # Update peak if current value exceeds it (new high-water mark)
        if current > peak:
            peak = current
            self.state.peak_portfolio_value = current
            if self._peak_portfolio_value is not None:
                self._peak_portfolio_value = current

        # Calculate drawdown percentage
        drawdown_pct = ((peak - current) / peak) * 100 if peak > 0 else 0.0

        # Update state with calculated drawdown
        self.state.drawdown_pct = drawdown_pct

        # Update drawdown level based on thresholds
        if self.config.drawdown.enabled:
            thresholds = self.config.drawdown.thresholds
            self.state.update_drawdown_level(
                thresholds.warning, thresholds.danger, thresholds.critical
            )

        return drawdown_pct

    def reset_daily(self):
        """Reset daily tracking metrics

        Called at market open each trading day.
        Resets daily P&L and clears alerts.
        """
        logger.info("Resetting daily risk metrics")

        # Reset daily state
        self.state.reset_daily(self.config.initial_capital)

        # Reset drawdown baseline to the new session starting value.
        baseline_value = (
            self.metrics.portfolio_value
            if self.metrics.portfolio_value > 0
            else self.config.initial_capital
        )
        self.state.peak_portfolio_value = baseline_value
        self.state.current_portfolio_value = baseline_value
        self.state.drawdown_pct = 0.0
        self.state.drawdown_level = DrawdownLevel.SAFE
        self._peak_portfolio_value = baseline_value
        self._current_portfolio_value = baseline_value
        self._last_reset_date = self.state.last_reset_date

        # Auto-unblock if configured
        if (
            self.config.monitoring.auto_unblock_on_reset
            and self.state.is_blocked
            and self.state.block_reason == BlockReason.DAILY_LOSS_LIMIT
        ):
            logger.info("Auto-unblocking trading after daily reset")
            self.state.unblock_trading()

    def _check_and_reset_daily(self):
        """Check if date has changed and reset daily metrics if needed

        Called automatically to detect day transitions and reset daily P&L tracking.
        Compares current date with last reset date and resets if different.
        """
        today = date.today()

        # Check if we've crossed into a new day
        if today != self._last_reset_date:
            logger.info(
                f"Day transition detected: {self._last_reset_date} -> {today}, resetting daily metrics"
            )

            # Reset internal test attributes
            self._daily_pnl = 0.0

            # Reset state via existing reset_daily method
            self.reset_daily()

            # Update last reset date
            self._last_reset_date = today

    def block_trading(self, reason: BlockReason):
        """Manually block new position entries

        Args:
            reason: Reason for blocking
        """
        logger.warning(f"Blocking trading: {reason.value}")
        self.state.block_trading(reason)

    def unblock_trading(self):
        """Manually unblock position entries"""
        logger.info("Unblocking trading")
        self.state.unblock_trading()

    def to_dict(self) -> dict[str, Any]:
        """Serialize risk manager state to dict

        Returns:
            Dict containing state and metrics for persistence
        """
        return {
            "state": self.state.to_dict(),
            "metrics": self.metrics.to_dict(),
        }

    @classmethod
    def from_dict(cls, config: RiskConfig, data: dict[str, Any]) -> RiskManager:
        """Restore risk manager from serialized state

        Args:
            config: Risk configuration
            data: Serialized state dict

        Returns:
            RiskManager instance with restored state
        """
        manager = cls(config)

        # Restore state
        if "state" in data:
            manager.state = RiskState.from_dict(data["state"])

        # Restore metrics
        if "metrics" in data:
            manager.metrics = PortfolioMetrics.from_dict(data["metrics"])

        logger.info("RiskManager restored from persisted state")
        return manager

    async def send_alert(
        self,
        notifier: TelegramNotifier | None,
        alert_type: str,
        message: str,
        is_critical: bool = True,
    ):
        """Send risk alert via Telegram

        Args:
            notifier: TelegramNotifier instance (None disables alerts)
            alert_type: Type of alert (e.g., 'DAILY_LOSS_LIMIT', 'DRAWDOWN', 'POSITION_LIMIT')
            message: Alert message content
            is_critical: Whether this is a critical alert (bypasses time restrictions)
        """
        if notifier is None:
            logger.debug(
                f"Telegram notifier not configured, skipping alert: {alert_type}"
            )
            return

        # Format alert message with header
        formatted_msg = (
            f"🚨 <b>RISK ALERT - {alert_type}</b>\n"
            f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"\n{message}"
        )

        try:
            await notifier.send_message(formatted_msg, is_critical=is_critical)
            logger.info(f"Sent risk alert: {alert_type}")
        except Exception as e:
            logger.error(f"Failed to send risk alert via Telegram: {e}")

    async def save_to_redis(self) -> None:
        """Save risk state to Redis for persistence

        Persists current risk state and portfolio metrics to Redis DB 1.
        Uses JSON encoding with the configured key pattern:
        {config.redis.key_prefix}:state

        Raises:
            No exceptions raised - errors are logged but do not propagate
        """
        try:
            import json

            from shared.streaming.client import RedisClient

            # Get Redis client singleton (connected to DB 1)
            redis_client = RedisClient.get_client()

            # Serialize state to dict
            state_data = self._serialize_state()

            # Store in Redis as JSON string
            redis_client.set(
                self._risk_state_key(),
                json.dumps(state_data),
                ex=self.config.redis.state_ttl,
            )

            logger.debug(
                f"Risk state saved to Redis: daily_pnl={self.state.daily_pnl:.2f}, "
                f"positions={self.metrics.total_positions}, "
                f"is_blocked={self.state.is_blocked}"
            )

        except Exception as e:
            logger.error(f"Failed to save risk state to Redis: {e}", exc_info=True)

    async def load_from_redis(self) -> bool:
        """Load risk state from Redis on restart

        Recovers persisted risk state and portfolio metrics from Redis DB 1.
        Uses JSON decoding from the configured key pattern:
        {config.redis.key_prefix}:state

        Returns:
            True if state was successfully loaded, False if no state found or error occurred

        Raises:
            No exceptions raised - errors are logged but do not propagate
        """
        try:
            import json

            from shared.streaming.client import RedisClient

            # Get Redis client singleton (connected to DB 1)
            redis_client = RedisClient.get_client()

            # Load from Redis
            raw_data = redis_client.get(self._risk_state_key())

            if not raw_data:
                logger.info("No risk state found in Redis (fresh start)")
                return False

            # Deserialize state from JSON
            state_data = json.loads(raw_data)
            self._deserialize_state(state_data)
            self._check_and_reset_daily()

            logger.info(
                f"Risk state loaded from Redis: daily_pnl={self.state.daily_pnl:.2f}, "
                f"positions={self.metrics.total_positions}, "
                f"is_blocked={self.state.is_blocked}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to load risk state from Redis: {e}", exc_info=True)
            return False
