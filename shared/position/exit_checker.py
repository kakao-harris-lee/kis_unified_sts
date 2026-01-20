"""Exit condition checker implementing 3-Stage state machine."""
import logging
from typing import Tuple
from pydantic import BaseModel, ConfigDict, Field

from shared.models.position import Position, PositionState, PositionSide

logger = logging.getLogger(__name__)


class ExitConfig(BaseModel):
    """Configuration for exit conditions.

    Loaded from YAML config, no hardcoded values.
    """

    model_config = ConfigDict(frozen=True)

    # Stage 1: SURVIVAL
    hard_stop_pct: float = Field(default=2.0, description="Hard stop loss %")

    # Stage 2: BREAKEVEN
    breakeven_threshold_pct: float = Field(
        default=2.0, description="Profit % to trigger breakeven"
    )
    breakeven_buffer_pct: float = Field(
        default=0.1, description="Buffer above entry for breakeven stop"
    )

    # Stage 3: MAXIMIZE
    maximize_threshold_pct: float = Field(
        default=5.0, description="Profit % to trigger maximize"
    )
    trailing_stop_pct: float = Field(
        default=3.0, description="Trailing stop distance from high %"
    )
    tight_trailing_pct: float = Field(
        default=1.5, description="Tighter trailing stop %"
    )
    tight_trailing_trigger_pct: float = Field(
        default=10.0, description="Profit % to trigger tight trailing"
    )

    # Time-based exit
    max_hold_minutes: int = Field(
        default=0, description="Max hold time in minutes (0 = disabled)"
    )


class ExitChecker:
    """Checks exit conditions using 3-Stage state machine.

    Stage 1 (SURVIVAL): Hard stop loss protection
    Stage 2 (BREAKEVEN): Lock in breakeven after profit threshold
    Stage 3 (MAXIMIZE): Trailing stop to maximize gains

    All thresholds are loaded from config - NO HARDCODING.
    """

    def __init__(self, config: ExitConfig):
        """Initialize with config.

        Args:
            config: Exit configuration
        """
        self.config = config
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate configuration values."""
        c = self.config
        assert c.hard_stop_pct > 0, "hard_stop_pct must be positive"
        assert c.breakeven_threshold_pct > 0, "breakeven_threshold_pct must be positive"
        assert (
            c.maximize_threshold_pct > c.breakeven_threshold_pct
        ), "maximize_threshold_pct must be > breakeven_threshold_pct"
        assert c.trailing_stop_pct > 0, "trailing_stop_pct must be positive"

    def check(self, position: Position) -> Tuple[bool, str]:
        """Check if position should exit.

        Args:
            position: Position to check

        Returns:
            (should_exit, reason) tuple
        """
        # First update state based on current profit
        self.update_state(position)

        # Then check exit conditions based on current state
        if position.state == PositionState.SURVIVAL:
            return self._check_survival(position)
        elif position.state == PositionState.BREAKEVEN:
            return self._check_breakeven(position)
        elif position.state == PositionState.MAXIMIZE:
            return self._check_maximize(position)

        return False, ""

    def update_state(self, position: Position) -> None:
        """Update position state based on profit.

        State transitions:
        SURVIVAL -> BREAKEVEN: when profit >= breakeven_threshold
        BREAKEVEN -> MAXIMIZE: when profit >= maximize_threshold
        """
        profit_pct = position.profit_pct  # percentage (e.g., 5.0 for 5%)

        if position.state == PositionState.SURVIVAL:
            if profit_pct >= self.config.breakeven_threshold_pct:
                position.state = PositionState.BREAKEVEN
                logger.info(
                    f"Position {position.id} transitioned to BREAKEVEN "
                    f"(profit: {profit_pct:.2f}%)"
                )

        if position.state == PositionState.BREAKEVEN:
            if profit_pct >= self.config.maximize_threshold_pct:
                position.state = PositionState.MAXIMIZE
                logger.info(
                    f"Position {position.id} transitioned to MAXIMIZE "
                    f"(profit: {profit_pct:.2f}%)"
                )

    def _check_survival(self, position: Position) -> Tuple[bool, str]:
        """Check SURVIVAL stage exit conditions.

        Exit if: loss >= hard_stop_pct
        """
        profit_pct = position.profit_pct

        if profit_pct <= -self.config.hard_stop_pct:
            return True, f"HARD_STOP (loss: {profit_pct:.2f}%)"

        # Time-based exit
        if self.config.max_hold_minutes > 0:
            hold_minutes = position.get_hold_duration()
            if hold_minutes >= self.config.max_hold_minutes:
                return True, f"TIME_EXIT (held: {hold_minutes:.1f} min)"

        return False, ""

    def _check_breakeven(self, position: Position) -> Tuple[bool, str]:
        """Check BREAKEVEN stage exit conditions.

        Exit if: profit drops below breakeven_buffer
        """
        profit_pct = position.profit_pct

        if profit_pct <= self.config.breakeven_buffer_pct:
            return True, f"BREAKEVEN_STOP (profit: {profit_pct:.2f}%)"

        return False, ""

    def _check_maximize(self, position: Position) -> Tuple[bool, str]:
        """Check MAXIMIZE stage exit conditions.

        Exit if: price drops trailing_stop_pct from highest
        """
        # Calculate drop from highest price
        if position.highest_price <= 0:
            return False, ""

        drop_from_high_pct = (
            (position.highest_price - position.current_price)
            / position.highest_price
            * 100
        )

        # Use tighter trailing stop if profit is very high
        trailing_pct = self.config.trailing_stop_pct
        if position.profit_pct >= self.config.tight_trailing_trigger_pct:
            trailing_pct = self.config.tight_trailing_pct

        if drop_from_high_pct >= trailing_pct:
            return True, (
                f"TRAILING_STOP (drop: {drop_from_high_pct:.2f}%, "
                f"trail: {trailing_pct:.1f}%)"
            )

        return False, ""

    def get_stop_price(self, position: Position) -> float:
        """Calculate current stop price.

        Args:
            position: Position to calculate stop for

        Returns:
            Stop price
        """
        if position.state == PositionState.SURVIVAL:
            # Hard stop
            if position.side == PositionSide.LONG:
                return position.entry_price * (1 - self.config.hard_stop_pct / 100)
            else:
                return position.entry_price * (1 + self.config.hard_stop_pct / 100)

        elif position.state == PositionState.BREAKEVEN:
            # Breakeven stop
            if position.side == PositionSide.LONG:
                return position.entry_price * (1 + self.config.breakeven_buffer_pct / 100)
            else:
                return position.entry_price * (1 - self.config.breakeven_buffer_pct / 100)

        elif position.state == PositionState.MAXIMIZE:
            # Trailing stop
            trailing_pct = self.config.trailing_stop_pct
            if position.profit_pct >= self.config.tight_trailing_trigger_pct:
                trailing_pct = self.config.tight_trailing_pct

            if position.side == PositionSide.LONG:
                return position.highest_price * (1 - trailing_pct / 100)
            else:
                return position.lowest_price * (1 + trailing_pct / 100)

        return 0.0
