"""V35 Optimized Entry Strategy.

Multi-indicator entry strategy combining:
- Bollinger Bands (price below lower band)
- RSI (oversold condition)
- MACD (momentum confirmation)
"""
import logging
from dataclasses import dataclass
from typing import Optional

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator

logger = logging.getLogger(__name__)


@dataclass
class V35Config(ConfigMixin):
    """V35 전략 설정"""

    bb_period: int = 20
    bb_std: float = 2.0
    rsi_period: int = 14
    rsi_oversold: int = 30
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    # Confidence calculation parameters
    macd_normalization_factor: float = 0.5


class V35OptimizedEntry(EntrySignalGenerator[V35Config]):
    """V35 optimized entry strategy.

    Entry conditions (all must be true):
    1. Price below BB lower band
    2. RSI < oversold threshold
    3. MACD histogram positive (momentum turning)
    """

    CONFIG_CLASS = V35Config

    def __init__(self, config: V35Config):
        super().__init__(config)

    def _validate_config(self):
        """설정 유효성 검증"""
        assert self.config.bb_period > 0, "bb_period must be positive"
        assert self.config.rsi_period > 0, "rsi_period must be positive"
        assert 0 < self.config.rsi_oversold < 50, "rsi_oversold must be between 0 and 50"

    @property
    def name(self) -> str:
        return "v35_optimized"

    @property
    def required_indicators(self) -> list[str]:
        return ["bb_lower", "bb_upper", "rsi", "macd", "macd_signal", "macd_hist"]

    async def generate(self, context: EntryContext) -> Optional[Signal]:
        """Generate entry signal based on V35 conditions."""
        data = context.market_data

        close = data.get("close", 0)
        bb_lower = data.get("bb_lower", 0)
        rsi = data.get("rsi", 50)
        macd_hist = data.get("macd_hist", 0)

        # Check all conditions
        price_below_bb = close < bb_lower
        rsi_oversold = rsi < self.config.rsi_oversold
        macd_positive = macd_hist > 0

        if price_below_bb and rsi_oversold and macd_positive:
            code = data.get("code", "")
            name = data.get("name", "")

            logger.info(
                f"V35 BUY signal: {code} close={close}, bb_lower={bb_lower}, "
                f"rsi={rsi}, macd_hist={macd_hist}"
            )

            return Signal(
                code=code,
                name=name,
                signal_type=SignalType.ENTRY,
                price=close,
                timestamp=context.timestamp,
                strategy="v35_optimized",
                confidence=self._calculate_confidence(rsi, macd_hist),
            )

        return None

    def _calculate_confidence(self, rsi: float, macd_hist: float) -> float:
        """Calculate signal confidence 0-1."""
        # Guard against division by zero
        if self.config.rsi_oversold <= 0:
            rsi_score = 0.5
        else:
            rsi_score = min(1, max(0, (self.config.rsi_oversold - rsi) / self.config.rsi_oversold))

        macd_score = min(1, max(0, macd_hist / self.config.macd_normalization_factor)) if macd_hist > 0 else 0
        return (rsi_score + macd_score) / 2
