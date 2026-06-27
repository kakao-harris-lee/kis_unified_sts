"""
Momentum Decay Exit Strategy

Momentum decay exit strategy for swing trading in the KIS Unified STS project.
Detects momentum exhaustion through price retracement and volume velocity analysis.

Exit Triggers (Priority Order):
    1. Hard Stop: profit_pct <= stop_loss_pct
    2. EOD Close: Trading day end forced exit
    3. Max Hold: max_hold_days exceeded
    4. Friday Close: Weekend risk management (if enabled)
    5. Momentum Decay: Retracement from high + negative volume velocity
    6. VWAP Breakdown: Price < VWAP with negative volume
    7. No-Profit Time Cut: Stale position without profit
    8. Trailing Stop: Dynamic trailing based on profit level

Usage:
    config = MomentumDecayConfig(
        stop_loss_pct=-0.03,
        decay_retracement_pct=0.015,
        trailing_activation_pct=0.05,
    )
    exit_strategy = MomentumDecayExit(config)

    # Single position exit check
    should_exit, signal = await exit_strategy.should_exit(context)

    # Multiple position scan
    signals = await exit_strategy.scan_positions(positions, market_data)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import TYPE_CHECKING, Any

from shared.calendar import get_market_calendar
from shared.config.mixins import ConfigMixin
from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason, ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator, MarketStateProtocol
from shared.strategy.market_data import (
    get_numeric_field,
    get_price_from_snapshot,
    get_symbol_snapshot,
)
from shared.strategy.market_time import (
    effective_close_time,
    is_trading_day_kst,
    now_kst,
    to_kst,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class MomentumDecayConfig(ConfigMixin):
    """Momentum Decay Exit Configuration

    Attributes:
        stop_loss_pct: Hard stop loss threshold (negative, e.g., -0.03 = -3%)
        decay_retracement_pct: Retracement from session high to trigger exit
        decay_volume_threshold: Volume velocity threshold (0.0 = must be negative)
        vwap_breakdown_enabled: Enable VWAP breakdown exit
        trailing_activation_pct: Profit level to activate trailing (e.g., 0.05 = +5%)
        trailing_stop_pct: Trailing gap from high (negative, e.g., -0.05 = -5%)
        tight_trail_activation: Profit level to tighten trail (e.g., 0.10 = +10%)
        tight_trail_pct: Tightened trailing gap (negative, e.g., -0.03 = -3%)
        no_profit_days: Exit if no profit after N days
        max_hold_days: Maximum holding period (force exit)
        close_before_weekend: Close positions before weekend
        eod_close_enabled: Enable EOD forced close (False for swing strategies)
        eod_close_hour: End-of-day close hour
        eod_close_minute: End-of-day close minute
        fee_rate: Transaction fee rate (e.g., 0.003 = 0.3%)
    """

    # Hard stop
    stop_loss_pct: float = -0.03  # -3%

    # Momentum decay detection
    decay_retracement_pct: float = 0.015  # 1.5% drop from session high
    decay_volume_threshold: float = 0.0  # Volume velocity must be negative

    # VWAP breakdown
    vwap_breakdown_enabled: bool = True

    # Trailing (swing width)
    trailing_activation_pct: float = 0.05  # Activate at +5%
    trailing_stop_pct: float = -0.05  # Trail at -5%
    tight_trail_activation: float = 0.10  # At +10%, tighten
    tight_trail_pct: float = -0.03  # Tighten to -3%

    # Time-based
    no_profit_days: int = 2  # Exit if no profit after 2 days
    max_hold_days: int = 5  # Force exit
    close_before_weekend: bool = False

    # EOD
    eod_close_enabled: bool = True  # Set false for swing strategies
    eod_close_hour: int = 15
    eod_close_minute: int = 15

    # Fee
    fee_rate: float = 0.003

    @property
    def eod_close_time(self) -> time:
        """End-of-day close time"""
        return time(self.eod_close_hour, self.eod_close_minute)

    def validate(self) -> None:
        """Validate configuration"""
        if self.stop_loss_pct >= 0:
            raise ValueError("stop_loss_pct must be negative")
        if self.trailing_stop_pct >= 0:
            raise ValueError("trailing_stop_pct must be negative")
        if self.tight_trail_pct >= 0:
            raise ValueError("tight_trail_pct must be negative")
        if abs(self.tight_trail_pct) >= abs(self.trailing_stop_pct):
            raise ValueError(
                "tight_trail_pct should be tighter (smaller absolute value) "
                "than trailing_stop_pct"
            )
        if self.decay_retracement_pct <= 0:
            raise ValueError("decay_retracement_pct must be positive")
        if self.no_profit_days <= 0:
            raise ValueError("no_profit_days must be positive")
        if self.max_hold_days <= 0:
            raise ValueError("max_hold_days must be positive")


# =============================================================================
# Momentum Decay Exit Strategy
# =============================================================================


class MomentumDecayExit(ExitSignalGenerator[MomentumDecayConfig]):
    """Momentum Decay Exit Strategy

    Configuration-based swing trading exit strategy.
    Detects momentum exhaustion through price retracement and volume analysis.

    All thresholds loaded from MomentumDecayConfig.
    No hardcoded values - fully configuration-driven.

    Usage:
        config = MomentumDecayConfig(
            stop_loss_pct=-0.03,
            decay_retracement_pct=0.015,
        )
        strategy = MomentumDecayExit(config)

        # Single position exit check
        should_exit, signal = await strategy.should_exit(context)

        # Multiple position scan
        signals = await strategy.scan_positions(positions, market_data)
    """

    NAME = "MOMENTUM_DECAY_EXIT"
    VERSION = "E5"
    DESCRIPTION = "Momentum decay exit strategy for swing trading"
    CONFIG_CLASS = MomentumDecayConfig  # For registry auto-conversion

    def __init__(self, config: MomentumDecayConfig):
        super().__init__(config)

        logger.info(
            f"{self.name} ({self.version}) initialized: "
            f"stop_loss={config.stop_loss_pct:.1%}, "
            f"decay_retracement={config.decay_retracement_pct:.1%}, "
            f"trailing={config.trailing_stop_pct:.1%}, "
            f"max_hold={config.max_hold_days}d"
        )

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def version(self) -> str:
        return self.VERSION

    def _validate_config(self):
        """Validate configuration"""
        self.config.validate()

    # -------------------------------------------------------------------------
    # Side-Aware Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _calc_profit_pct(position: Position, current_price: float) -> float:
        """Side-aware profit percentage."""
        if position.side == PositionSide.SHORT:
            return (position.entry_price - current_price) / position.entry_price
        return (current_price - position.entry_price) / position.entry_price

    @staticmethod
    def _calc_profit_amount(position: Position, current_price: float) -> float:
        """Side-aware profit amount."""
        if position.side == PositionSide.SHORT:
            return (position.entry_price - current_price) * position.quantity
        return (current_price - position.entry_price) * position.quantity

    @staticmethod
    def _get_extreme_since_entry(position: Position, current_price: float) -> float:
        """Most favorable price since entry (high for LONG, low for SHORT)."""
        if position.side == PositionSide.SHORT:
            return min(
                position.lowest_price if position.lowest_price < float("inf")
                else position.entry_price,
                current_price,
            )
        return max(position.highest_price or position.entry_price, current_price)

    @staticmethod
    def _stop_hit(position: Position, current_price: float, stop_price: float) -> bool:
        """Check if stop price is hit (direction-aware)."""
        if position.side == PositionSide.SHORT:
            return current_price >= stop_price
        return current_price <= stop_price

    # -------------------------------------------------------------------------
    # Main Interface
    # -------------------------------------------------------------------------

    async def should_exit(
        self, context: ExitContext
    ) -> tuple[bool, ExitSignal | None]:
        """Check if single position should exit

        Args:
            context: Exit decision context

        Returns:
            (should_exit, signal): Whether to exit and exit signal
        """
        signal = self._check_position(
            position=context.position,
            market_data=context.market_data,
            market_state=context.market_state,
            now=context.timestamp,
        )

        return (signal is not None, signal)

    async def scan_positions(
        self,
        positions: list[Position],
        market_data: dict[str, Any],
        market_state: MarketStateProtocol | None = None,
    ) -> list[ExitSignal]:
        """Scan multiple positions for exit signals

        Args:
            positions: List of current positions
            market_data: Market data (code -> price mapping)
            market_state: Current market state (optional)

        Returns:
            List of ExitSignals for positions to exit
        """
        if not positions:
            return []

        signals = []
        now = now_kst()

        for position in positions:
            signal = self._check_position(
                position=position,
                market_data=market_data,
                market_state=market_state,
                now=now,
            )
            if signal:
                signals.append(signal)

        if signals:
            logger.info(
                f"[{self.name}] {len(signals)}/{len(positions)} positions "
                f"triggered exit signals"
            )

        return signals

    # -------------------------------------------------------------------------
    # Position Check Logic
    # -------------------------------------------------------------------------

    def _check_position(
        self,
        position: Position,
        market_data: dict[str, Any],
        market_state: MarketStateProtocol | None,
        now: datetime,
    ) -> ExitSignal | None:
        """Check individual position for exit conditions

        Priority:
            1. Hard Stop
            2. EOD Close
            3. Max Hold Days
            4. Friday Close (if enabled)
            5. Momentum Decay
            6. VWAP Breakdown
            7. No-Profit Time Cut
            8. Trailing Stop
        """
        _ = market_state
        # Get current price
        snapshot = get_symbol_snapshot(market_data, position.code)
        current_price = self._get_current_price(position, market_data)
        if current_price is None:
            return None

        # Calculate profit (side-aware)
        profit_pct = self._calc_profit_pct(position, current_price)
        profit_amount = self._calc_profit_amount(position, current_price)

        # Extreme price since entry (LONG: high, SHORT: low)
        high_since_entry = self._get_extreme_since_entry(position, current_price)

        # Holding period
        holding_days = self._get_holding_days(position, now)

        # 1. Hard Stop (highest priority)
        if profit_pct <= self.config.stop_loss_pct:
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.STOP_LOSS,
                priority=1,
                high_since_entry=high_since_entry,
                holding_minutes=holding_days * 390,
            )

        # 2. EOD Close (skipped for swing strategies with eod_close_enabled=False)
        if self.config.eod_close_enabled:
            close_time = effective_close_time(self.config.eod_close_time)
            if is_trading_day_kst(now) and to_kst(now).time() >= close_time:
                return self._create_exit_signal(
                    position=position,
                    current_price=current_price,
                    profit_pct=profit_pct,
                    profit_amount=profit_amount,
                    reason=ExitReason.EOD_CLOSE,
                    priority=1,
                    high_since_entry=high_since_entry,
                    holding_minutes=holding_days * 390,
                )

        # 3. Max Hold Days
        if holding_days >= self.config.max_hold_days:
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.TIME_CUT,
                priority=2,
                high_since_entry=high_since_entry,
                holding_minutes=holding_days * 390,
            )

        # 4. Friday Close (if enabled)
        if self.config.close_before_weekend and self._is_friday_afternoon(now):
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.EOD_CLOSE,
                priority=2,
                high_since_entry=high_since_entry,
                holding_minutes=holding_days * 390,
            )

        # Get volume velocity from market data
        volume_velocity = get_numeric_field(snapshot, "volume_velocity", 0.0)

        # 5. Momentum Decay
        if self._check_momentum_decay(
            position=position,
            current_price=current_price,
            high_since_entry=high_since_entry,
            volume_velocity=volume_velocity,
        ):
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.MOMENTUM_DECAY,
                priority=2,
                high_since_entry=high_since_entry,
                holding_minutes=holding_days * 390,
            )

        # 6. VWAP Breakdown
        if self.config.vwap_breakdown_enabled:
            vwap = get_numeric_field(snapshot, "vwap", 0.0)
            if self._check_vwap_breakdown(
                current_price=current_price,
                vwap=vwap,
                volume_velocity=volume_velocity,
            ):
                return self._create_exit_signal(
                    position=position,
                    current_price=current_price,
                    profit_pct=profit_pct,
                    profit_amount=profit_amount,
                    reason=ExitReason.VWAP_BREAKDOWN,
                    priority=2,
                    high_since_entry=high_since_entry,
                    holding_minutes=holding_days * 390,
                )

        # 7. No-Profit Time Cut
        if holding_days >= self.config.no_profit_days and profit_pct <= 0:
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.TIME_CUT,
                priority=3,
                high_since_entry=high_since_entry,
                holding_minutes=holding_days * 390,
            )

        # 8. Trailing Stop
        trailing_exit = self._check_trailing_stop(
            position=position,
            current_price=current_price,
            profit_pct=profit_pct,
            profit_amount=profit_amount,
            high_since_entry=high_since_entry,
            holding_minutes=holding_days * 390,
        )
        if trailing_exit:
            return trailing_exit

        return None

    def _get_current_price(
        self, position: Position, market_data: dict[str, Any]
    ) -> float | None:
        """Get current price from market data"""
        snapshot = get_symbol_snapshot(market_data, position.code)
        price = get_price_from_snapshot(snapshot)
        if price is not None:
            return price

        # Fallback to position's current_price
        if position.current_price > 0:
            return position.current_price

        return None

    def _get_holding_days(self, position: Position, now: datetime) -> int:
        """Calculate holding days using exchange trading calendar."""
        calendar = get_market_calendar()
        start = to_kst(position.entry_time).date()
        end = to_kst(now).date()
        if end <= start:
            return 0
        trading_days = calendar.get_trading_days_in_range(start, end)
        # entry day counts as day 0 holding
        return max(0, len(trading_days) - 1)

    def _is_friday_afternoon(self, now: datetime) -> bool:
        """Check if current time is Friday afternoon (KST)"""
        kst_now = to_kst(now)
        # Friday = 4 (0=Monday, 6=Sunday)
        is_friday = kst_now.weekday() == 4
        # After 14:00
        is_afternoon = kst_now.hour >= 14
        return is_friday and is_afternoon

    def _check_momentum_decay(
        self,
        position: Position,
        current_price: float,
        high_since_entry: float,
        volume_velocity: float,
    ) -> bool:
        """Check for momentum decay (side-aware)

        Momentum decay detected when:
        - Price has retraced decay_retracement_pct from session extreme
        - Volume velocity is negative
        """
        if high_since_entry <= 0:
            return False

        # Retracement from extreme (side-aware)
        if position.side == PositionSide.SHORT:
            retracement = (current_price - high_since_entry) / high_since_entry
        else:
            retracement = (high_since_entry - current_price) / high_since_entry

        # Check both conditions
        price_decay = retracement >= self.config.decay_retracement_pct
        volume_decay = volume_velocity < self.config.decay_volume_threshold

        if price_decay and volume_decay:
            logger.debug(
                f"Momentum decay detected: retracement={retracement:.2%}, "
                f"volume_velocity={volume_velocity:.4f}"
            )
            return True

        return False

    def _check_vwap_breakdown(
        self,
        current_price: float,
        vwap: float,
        volume_velocity: float,
    ) -> bool:
        """Check for VWAP breakdown

        VWAP breakdown detected when:
        - Price < VWAP
        - Volume velocity is negative
        """
        if vwap <= 0:
            return False

        price_below_vwap = current_price < vwap
        volume_decay = volume_velocity < self.config.decay_volume_threshold

        if price_below_vwap and volume_decay:
            logger.debug(
                f"VWAP breakdown detected: price={current_price:.2f}, "
                f"vwap={vwap:.2f}, volume_velocity={volume_velocity:.4f}"
            )
            return True

        return False

    def _check_trailing_stop(
        self,
        position: Position,
        current_price: float,
        profit_pct: float,
        profit_amount: float,
        high_since_entry: float,
        holding_minutes: int,
    ) -> ExitSignal | None:
        """Check trailing stop

        Two-tier trailing:
        - If profit >= tight_trail_activation: trail at tight_trail_pct from high
        - If profit >= trailing_activation_pct: trail at trailing_stop_pct from high
        """
        # Determine trailing gap based on profit level
        trailing_gap = None

        if profit_pct >= self.config.tight_trail_activation:
            # Tight trailing for higher profits
            trailing_gap = abs(self.config.tight_trail_pct)
        elif profit_pct >= self.config.trailing_activation_pct:
            # Normal trailing
            trailing_gap = abs(self.config.trailing_stop_pct)

        if trailing_gap is None:
            # Not in trailing mode yet
            return None

        # Calculate trailing stop price (side-aware)
        is_short = position.side == PositionSide.SHORT
        if is_short:
            trailing_stop_price = high_since_entry * (1 + trailing_gap)
            if position.stop_price > 0:
                trailing_stop_price = min(trailing_stop_price, position.stop_price)
        else:
            trailing_stop_price = high_since_entry * (1 - trailing_gap)
            if position.stop_price > 0:
                trailing_stop_price = max(trailing_stop_price, position.stop_price)

        # Check if trailing stop hit
        if self._stop_hit(position, current_price, trailing_stop_price):
            logger.debug(
                f"Trailing stop hit: price={current_price:.2f}, "
                f"stop={trailing_stop_price:.2f}, gap={trailing_gap:.1%}"
            )
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.TRAILING_STOP,
                priority=2,
                high_since_entry=high_since_entry,
                holding_minutes=holding_minutes,
            )

        return None

    # -------------------------------------------------------------------------
    # Signal Creation
    # -------------------------------------------------------------------------

    def _create_exit_signal(
        self,
        position: Position,
        current_price: float,
        profit_pct: float,
        profit_amount: float,
        reason: ExitReason,
        priority: int,
        high_since_entry: float,
        holding_minutes: int,
    ) -> ExitSignal:
        """Create ExitSignal"""
        confidence = self._calculate_confidence(reason, profit_pct)

        logger.info(
            f"[{self.name}] Exit signal: {position.code} | "
            f"Reason: {reason.value} | "
            f"P/L: {profit_pct:+.2%} | "
            f"Hold: {holding_minutes // 390}d"
        )

        return ExitSignal(
            code=position.code,
            name=position.name,
            position_id=position.id,
            reason=reason,
            strategy=self.name,
            current_price=current_price,
            exit_price=current_price,
            entry_price=position.entry_price,
            profit_amount=profit_amount,
            profit_pct=profit_pct,
            confidence=confidence,
            priority=priority,
            timestamp=now_kst(),
            high_since_entry=high_since_entry,
            holding_minutes=holding_minutes,
            quantity=position.quantity,
        )

    def _calculate_confidence(
        self, reason: ExitReason, profit_pct: float
    ) -> float:
        """Calculate exit confidence

        Returns:
            Confidence between 0.0 ~ 1.0
        """
        # Hard stop / EOD have high confidence
        if reason in (
            ExitReason.STOP_LOSS,
            ExitReason.EOD_CLOSE,
        ):
            return 1.0

        # Trailing stop confidence based on profit
        if reason == ExitReason.TRAILING_STOP:
            if profit_pct >= 0.10:  # 10%+ profit
                return 0.95
            elif profit_pct >= 0.05:  # 5%+ profit
                return 0.90
            return 0.85

        # Momentum decay / VWAP breakdown
        if reason in (ExitReason.MOMENTUM_DECAY, ExitReason.VWAP_BREAKDOWN):
            return 0.85

        # Time cut
        if reason == ExitReason.TIME_CUT:
            return 0.75

        return 0.50

    def get_config(self) -> dict[str, Any]:
        """Get configuration"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.DESCRIPTION,
            **self.config.to_dict(),
        }
