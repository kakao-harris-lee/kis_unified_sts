"""Mean Reversion Entry Strategy.

Entry strategy based on Bollinger Bands and RSI:
- BUY when price below lower band AND RSI oversold
- SELL when price above upper band AND RSI overbought

Migrated from kospi_mini_sts.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator

logger = logging.getLogger(__name__)


@dataclass
class MeanReversionConfig:
    """Mean Reversion 전략 설정"""

    bb_period: int = 20
    bb_std: float = 2.0
    rsi_period: int = 14
    rsi_oversold: int = 30
    rsi_overbought: int = 70
    # Confidence calculation parameters
    bb_width_scale_factor: float = 0.5

    @classmethod
    def from_dict(cls, data: dict) -> "MeanReversionConfig":
        """Create config from dictionary, ignoring unknown keys."""
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in field_names})


class MeanReversionEntry(EntrySignalGenerator[MeanReversionConfig]):
    """Mean reversion entry strategy.

    Entry conditions:
    - Long: Price < BB lower AND RSI < oversold
    - Short: Price > BB upper AND RSI > overbought
    """

    CONFIG_CLASS = MeanReversionConfig

    def __init__(self, config: MeanReversionConfig):
        super().__init__(config)

    def _validate_config(self):
        """설정 유효성 검증"""
        assert self.config.bb_period > 0, "bb_period must be positive"
        assert self.config.rsi_period > 0, "rsi_period must be positive"
        assert 0 < self.config.rsi_oversold < 50, "rsi_oversold must be between 0 and 50"
        assert 50 < self.config.rsi_overbought < 100, "rsi_overbought must be between 50 and 100"

    @property
    def name(self) -> str:
        return "mean_reversion"

    @property
    def required_indicators(self) -> list[str]:
        return ["bb_lower", "bb_upper", "bb_middle", "rsi"]

    async def generate(self, context: EntryContext) -> Optional[Signal]:
        """Generate entry signal based on mean reversion conditions."""
        data = context.market_data

        close = data.get("close", 0)
        bb_lower = data.get("bb_lower", 0)
        bb_upper = data.get("bb_upper", 0)
        rsi = data.get("rsi", 50)
        code = data.get("code", "")
        name = data.get("name", "")

        # Check for long entry (oversold)
        if close < bb_lower and rsi < self.config.rsi_oversold:
            logger.info(
                f"Mean Reversion LONG signal: {code} close={close}, "
                f"bb_lower={bb_lower}, rsi={rsi}"
            )
            return Signal(
                code=code,
                name=name,
                signal_type=SignalType.ENTRY,
                price=close,
                timestamp=context.timestamp,
                strategy="mean_reversion",
                confidence=self._calculate_confidence(close, bb_lower, bb_upper, rsi, is_long=True),
                metadata={"signal_direction": "long"},
            )

        # Check for short entry (overbought)
        if close > bb_upper and rsi > self.config.rsi_overbought:
            logger.info(
                f"Mean Reversion SHORT signal: {code} close={close}, "
                f"bb_upper={bb_upper}, rsi={rsi}"
            )
            return Signal(
                code=code,
                name=name,
                signal_type=SignalType.ENTRY,
                price=close,
                timestamp=context.timestamp,
                strategy="mean_reversion",
                confidence=self._calculate_confidence(close, bb_lower, bb_upper, rsi, is_long=False),
                metadata={"signal_direction": "short"},
            )

        return None

    def _calculate_confidence(
        self, close: float, bb_lower: float, bb_upper: float, rsi: float, is_long: bool
    ) -> float:
        """Calculate signal confidence 0-1."""
        bb_width = bb_upper - bb_lower
        if bb_width <= 0:
            return 0.5

        if is_long:
            # How far below lower band
            bb_score = min(1, max(0, (bb_lower - close) / (bb_width * self.config.bb_width_scale_factor)))
            # How oversold - guard against division by zero
            if self.config.rsi_oversold <= 0:
                rsi_score = 0.5
            else:
                rsi_score = max(0, (self.config.rsi_oversold - rsi) / self.config.rsi_oversold)
        else:
            # How far above upper band
            bb_score = min(1, max(0, (close - bb_upper) / (bb_width * self.config.bb_width_scale_factor)))
            # How overbought - guard against division by zero
            divisor = 100 - self.config.rsi_overbought
            if divisor <= 0:
                rsi_score = 0.5
            else:
                rsi_score = max(0, (rsi - self.config.rsi_overbought) / divisor)

        return (bb_score + rsi_score) / 2
