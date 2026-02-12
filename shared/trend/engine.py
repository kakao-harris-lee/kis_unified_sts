"""Trend Engine for Mode B trend following strategy."""
import logging
import time
from typing import Optional, Tuple, List

from .config import TrendConfig
from .models import TrendSignal, TechnicalData
from .technical_calculator import TechnicalCalculator
from .position_manager import TrendPositionManager, TrendPosition

logger = logging.getLogger(__name__)


class TrendEngine:
    """Mode B Trend Following Engine.

    Combines technical analysis with DL predictions for trend following:
    - Uses TechnicalCalculator for indicators (MA, Ichimoku, ATR)
    - Integrates with EnsembleFilter for signal validation
    - Manages positions with ATR-based trailing stops

    Entry Flow:
    1. Update with price data
    2. Check technical conditions (MA, Ichimoku alignment)
    3. Validate with DL probability
    4. Generate signal if conditions met

    Position Management:
    1. Open position with ATR-based stops
    2. Trail stop as price moves favorably
    3. Exit on stop hit, target hit, or signal reversal
    """

    def __init__(self, config: TrendConfig):
        self.config = config
        self.technical_calculator = TechnicalCalculator(config.technical)
        self.position_manager = TrendPositionManager(config)

        # Volume tracking
        self._volume_history: List[float] = []
        self._volume_ma_period = 20

        # Statistics
        self._stats = {
            "total_updates": 0,
            "signals_generated": 0,
            "positions_opened": 0,
            "positions_closed": 0,
        }

    def update(
        self,
        close: float,
        high: float,
        low: float,
        volume: float,
        _timestamp: Optional[float] = None
    ) -> None:
        """Update engine with new price data.

        Args:
            close: Closing price
            high: High price
            low: Low price
            volume: Volume
            timestamp: Optional timestamp
        """
        self._stats["total_updates"] += 1

        # Update technical calculator
        self.technical_calculator.update(close, high, low)

        # Track volume
        self._volume_history.append(volume)
        if len(self._volume_history) > self._volume_ma_period:
            self._volume_history.pop(0)

    def is_ready(self) -> bool:
        """Check if engine has enough data."""
        return self.technical_calculator.is_ready()

    def get_volume_ratio(self) -> float:
        """Get current volume vs average volume."""
        if len(self._volume_history) < 2:
            return 1.0

        avg_volume = sum(self._volume_history[:-1]) / len(self._volume_history[:-1])
        if avg_volume == 0:
            return 1.0

        return self._volume_history[-1] / avg_volume

    def get_technical_data(self, timestamp: Optional[float] = None) -> Optional[TechnicalData]:
        """Get current technical indicator snapshot."""
        timestamp = timestamp or time.time()
        return self.technical_calculator.get_technical_data(timestamp)

    def check_entry(
        self,
        dl_probability: float,
        direction: str,
        timestamp: Optional[float] = None
    ) -> Tuple[bool, Optional[TrendSignal]]:
        """Check if entry conditions are met.

        Args:
            dl_probability: DL model probability for the direction
            direction: "LONG" or "SHORT"
            timestamp: Optional timestamp

        Returns:
            (has_signal, signal)
        """
        if not self.is_ready():
            return False, None

        timestamp = timestamp or time.time()
        tech_data = self.get_technical_data(timestamp)

        if tech_data is None:
            return False, None

        # Check technical alignment
        if direction == "LONG":
            ma_aligned = tech_data.ma_short > tech_data.ma_long
            ichimoku = self.technical_calculator.get_ichimoku()
            ichimoku_aligned = (
                ichimoku is not None and
                ichimoku.tenkan > ichimoku.kijun and
                tech_data.close > max(ichimoku.senkou_a, ichimoku.senkou_b)
            )
        else:
            ma_aligned = tech_data.ma_short < tech_data.ma_long
            ichimoku = self.technical_calculator.get_ichimoku()
            ichimoku_aligned = (
                ichimoku is not None and
                ichimoku.tenkan < ichimoku.kijun and
                tech_data.close < min(ichimoku.senkou_a, ichimoku.senkou_b)
            )

        # Check DL probability threshold
        dl_ok = dl_probability >= self.config.entry_threshold

        # All conditions must be met
        if not (ma_aligned and ichimoku_aligned and dl_ok):
            return False, None

        # Generate signal
        atr = tech_data.atr or 1.0

        if direction == "LONG":
            stop_loss = tech_data.close - (atr * self.config.atr_stop_multiplier)
            take_profit = tech_data.close + (atr * self.config.atr_target_multiplier)
        else:
            stop_loss = tech_data.close + (atr * self.config.atr_stop_multiplier)
            take_profit = tech_data.close - (atr * self.config.atr_target_multiplier)

        signal = TrendSignal(
            timestamp=timestamp,
            direction=direction,
            confidence=dl_probability,
            entry_price=tech_data.close,
            stop_loss=stop_loss,
            take_profit=take_profit,
            technical_data=tech_data,
        )

        self._stats["signals_generated"] += 1

        logger.info(f"Trend signal: {direction} @ {tech_data.close}, confidence={dl_probability:.2f}")

        return True, signal

    def open_position(
        self,
        direction: str,
        entry_price: float,
        size: float,
        timestamp: Optional[float] = None
    ) -> Optional[TrendPosition]:
        """Open a new position.

        Args:
            direction: "LONG" or "SHORT"
            entry_price: Entry price
            size: Position size
            timestamp: Optional timestamp

        Returns:
            TrendPosition or None if not ready
        """
        if not self.is_ready():
            return None

        atr = self.technical_calculator.get_atr()
        if atr is None or atr <= 0:
            atr = 1.0

        position = self.position_manager.open_position(
            direction=direction,
            entry_price=entry_price,
            atr=atr,
            size=size,
            timestamp=timestamp,
        )

        self._stats["positions_opened"] += 1

        return position

    def manage_positions(self, current_price: float) -> List[TrendPosition]:
        """Manage open positions - update trailing stops and check exits.

        Args:
            current_price: Current market price

        Returns:
            List of positions that were closed
        """
        closed = []
        atr = self.technical_calculator.get_atr() or 1.0

        for position in self.position_manager.get_open_positions():
            # Update trailing stop
            self.position_manager.update_trailing_stop(position, current_price, atr)

            # Check stop hit
            if self.position_manager.is_stop_hit(position, current_price):
                self.position_manager.close_position(position, current_price, "STOP_HIT")
                self._stats["positions_closed"] += 1
                closed.append(position)
                continue

            # Check target hit
            if self.position_manager.is_target_hit(position, current_price):
                self.position_manager.close_position(position, current_price, "TARGET_HIT")
                self._stats["positions_closed"] += 1
                closed.append(position)

        return closed

    def get_open_positions(self) -> List[TrendPosition]:
        """Get all open positions."""
        return self.position_manager.get_open_positions()

    def get_stats(self) -> dict:
        """Get engine statistics."""
        return self._stats.copy()

    def reset(self) -> None:
        """Reset engine state."""
        self.technical_calculator.reset()
        self._volume_history.clear()
        self._stats = {
            "total_updates": 0,
            "signals_generated": 0,
            "positions_opened": 0,
            "positions_closed": 0,
        }
