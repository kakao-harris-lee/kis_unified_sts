"""StochRSI Trend Entry Strategy.

Entry strategy based on StochRSI indicator:
- BUY when K crosses above D in oversold zone
- SELL when K crosses below D in overbought zone
"""
import logging
from dataclasses import dataclass

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator

logger = logging.getLogger(__name__)


@dataclass
class StochRSIConfig(ConfigMixin):
    """StochRSI 전략 설정"""

    rsi_period: int = 14
    stoch_period: int = 14
    k_period: int = 3
    d_period: int = 3
    oversold: int = 20
    overbought: int = 80


class StochRSITrendEntry(EntrySignalGenerator[StochRSIConfig]):
    """StochRSI trend entry strategy.

    Entry conditions:
    - Long: K crosses above D in oversold zone (< oversold threshold)
    - Short: K crosses below D in overbought zone (> overbought threshold)
    """

    CONFIG_CLASS = StochRSIConfig

    def __init__(self, config: StochRSIConfig):
        super().__init__(config)

    def _validate_config(self):
        """설정 유효성 검증"""
        assert self.config.rsi_period > 0, "rsi_period must be positive"
        assert self.config.stoch_period > 0, "stoch_period must be positive"
        assert 0 < self.config.oversold < 50, "oversold must be between 0 and 50"
        assert 50 < self.config.overbought < 100, "overbought must be between 50 and 100"

    @property
    def name(self) -> str:
        return "stochrsi_trend"

    @property
    def required_indicators(self) -> list[str]:
        return ["stochrsi_k", "stochrsi_d", "stochrsi_k_prev"]

    async def generate(self, context: EntryContext) -> Signal | None:
        """Generate entry signal based on StochRSI crossover."""
        data = context.market_data

        k = data.get("stochrsi_k", 50)
        d = data.get("stochrsi_d", 50)
        k_prev = data.get("stochrsi_k_prev", 50)
        close = data.get("close", 0)
        code = data.get("code", "")
        name = data.get("name", "")

        # Check for bullish crossover in oversold zone
        if k < self.config.oversold or d < self.config.oversold:
            # K crossing above D (bullish)
            if k > d and k_prev < d:
                logger.info(
                    f"StochRSI BUY signal: {code} K={k}, D={d}, K_prev={k_prev}"
                )
                return Signal(
                    code=code,
                    name=name,
                    signal_type=SignalType.ENTRY,
                    price=close,
                    timestamp=context.timestamp,
                    strategy="stochrsi_trend",
                    confidence=self._calculate_confidence(k, is_buy=True),
                    metadata={"signal_direction": "long"},
                )

        # Check for bearish crossover in overbought zone
        if k > self.config.overbought or d > self.config.overbought:
            # K crossing below D (bearish)
            if k < d and k_prev > d:
                logger.info(
                    f"StochRSI SELL signal: {code} K={k}, D={d}, K_prev={k_prev}"
                )
                return Signal(
                    code=code,
                    name=name,
                    signal_type=SignalType.ENTRY,
                    price=close,
                    timestamp=context.timestamp,
                    strategy="stochrsi_trend",
                    confidence=self._calculate_confidence(k, is_buy=False),
                    metadata={"signal_direction": "short"},
                )

        return None

    def _calculate_confidence(self, k: float, is_buy: bool) -> float:
        """Calculate signal confidence 0-1."""
        if is_buy:
            # More oversold = higher confidence
            if self.config.oversold <= 0:
                return 0.5
            return min(1, max(0, (self.config.oversold - k) / self.config.oversold))
        else:
            # More overbought = higher confidence
            divisor = 100 - self.config.overbought
            if divisor <= 0:
                return 0.5
            return min(1, max(0, (k - self.config.overbought) / divisor))
