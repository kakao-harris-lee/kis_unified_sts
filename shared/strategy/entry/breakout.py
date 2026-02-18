"""Breakout Entry Strategy.

Entry strategy based on N-period high/low breakout:
- BUY when price breaks above N-period high with volume confirmation
- SELL when price breaks below N-period low with volume confirmation

Migrated from kospi_mini_sts.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator

logger = logging.getLogger(__name__)


@dataclass
class BreakoutConfig(ConfigMixin):
    """Breakout 전략 설정"""

    lookback_period: int = 20
    volume_confirm: bool = True
    volume_threshold: float = 1.5  # Volume must be this multiple of MA
    # Confidence calculation parameters
    breakout_scale_factor: float = 5.0


class BreakoutEntry(EntrySignalGenerator[BreakoutConfig]):
    """Breakout entry strategy.

    Entry conditions:
    - Long: Price > N-period high AND volume > threshold * volume_ma
    - Short: Price < N-period low AND volume > threshold * volume_ma
    """

    CONFIG_CLASS = BreakoutConfig

    def __init__(self, config: BreakoutConfig):
        super().__init__(config)

    def _validate_config(self):
        """설정 유효성 검증"""
        assert self.config.lookback_period > 0, "lookback_period must be positive"
        assert self.config.volume_threshold > 0, "volume_threshold must be positive"

    @property
    def name(self) -> str:
        return "breakout"

    @property
    def required_indicators(self) -> list[str]:
        period = self.config.lookback_period
        return [f"high_{period}", f"low_{period}", "volume", "volume_ma"]

    async def generate(self, context: EntryContext) -> Optional[Signal]:
        """Generate entry signal based on breakout conditions."""
        data = context.market_data
        period = self.config.lookback_period

        close = data.get("close", 0)
        high_n = data.get(f"high_{period}", 0)
        low_n = data.get(f"low_{period}", 0)
        volume = data.get("volume", 0)
        volume_ma = data.get("volume_ma", 1)
        code = data.get("code", "")
        name = data.get("name", "")

        # Volume confirmation
        volume_confirmed = True
        if self.config.volume_confirm:
            volume_confirmed = volume >= (self.config.volume_threshold * volume_ma)

        # Check for long breakout
        vol_ratio = volume / volume_ma if volume_ma else 0.0
        if close > high_n and volume_confirmed:
            logger.info(
                f"Breakout LONG signal: {code} close={close}, "
                f"high_{period}={high_n}, volume_ratio={vol_ratio:.2f}"
            )
            return Signal(
                code=code,
                name=name,
                signal_type=SignalType.ENTRY,
                price=close,
                timestamp=context.timestamp,
                strategy="breakout",
                confidence=self._calculate_confidence(close, high_n, low_n, volume, volume_ma, is_long=True),
                metadata={"signal_direction": "long"},
            )

        # Check for short breakout
        if close < low_n and volume_confirmed:
            logger.info(
                f"Breakout SHORT signal: {code} close={close}, "
                f"low_{period}={low_n}, volume_ratio={vol_ratio:.2f}"
            )
            return Signal(
                code=code,
                name=name,
                signal_type=SignalType.ENTRY,
                price=close,
                timestamp=context.timestamp,
                strategy="breakout",
                confidence=self._calculate_confidence(close, high_n, low_n, volume, volume_ma, is_long=False),
                metadata={"signal_direction": "short"},
            )

        return None

    def _calculate_confidence(
        self, close: float, high_n: float, low_n: float,
        volume: float, volume_ma: float, is_long: bool
    ) -> float:
        """Calculate signal confidence 0-1."""
        range_size = high_n - low_n
        if range_size <= 0:
            return 0.5

        # Breakout strength
        if is_long:
            breakout_pct = (close - high_n) / range_size
        else:
            breakout_pct = (low_n - close) / range_size

        breakout_score = min(1, max(0, breakout_pct * self.config.breakout_scale_factor))

        # Volume strength - guard against division by zero
        if volume_ma <= 0:
            volume_ratio = 1.0
        else:
            volume_ratio = volume / volume_ma

        # Guard against division by zero in volume_threshold
        if self.config.volume_threshold <= 0:
            volume_score = 0.5
        else:
            volume_score = min(1, max(0, (volume_ratio - 1) / self.config.volume_threshold))

        return (breakout_score + volume_score) / 2
