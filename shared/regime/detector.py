"""Stock regime detector."""
import logging
from datetime import datetime

import pandas as pd

from shared.indicators.series import rolling_std, sma
from shared.utils.math import safe_divide

from .models import RegimeConfig, RegimeSignal, RegimeState

logger = logging.getLogger(__name__)


class StockRegimeDetector:
    """Detect market regime based on price action.

    Uses:
    - Moving average crossovers
    - Price momentum
    - Volatility
    """

    def __init__(self, config: RegimeConfig | None = None):
        self.config = config or RegimeConfig()
        self._last_signal: RegimeSignal | None = None

    def detect(self, df: pd.DataFrame) -> RegimeSignal:
        """Detect current market regime.

        Args:
            df: DataFrame with 'datetime' and 'close' columns

        Returns:
            RegimeSignal with detected state and confidence
        """
        if len(df) < self.config.sma_slow:
            return RegimeSignal(
                state=RegimeState.UNKNOWN,
                confidence=0.0,
                timestamp=datetime.now(),
                confidence_threshold=self.config.confidence_threshold,
            )

        # Calculate indicators (series.sma — plain rolling mean convention)
        close = df["close"]
        sma_fast = sma(close, self.config.sma_fast)
        sma_slow = sma(close, self.config.sma_slow)

        # Current values
        current_sma_fast = sma_fast.iloc[-1]
        current_sma_slow = sma_slow.iloc[-1]

        # Calculate trend strength (safe division)
        trend_pct = safe_divide(
            current_sma_fast - current_sma_slow,
            current_sma_slow,
            default=0.0,
        )

        # Calculate volatility (handle empty or all-NaN returns). The dropna()
        # precedes the rolling window (historical convention), so the plain
        # series.rolling_std primitive is used rather than rolling_return_std.
        returns = close.pct_change().dropna()
        if len(returns) < self.config.volatility_window:
            volatility = 0.0
        else:
            vol_series = rolling_std(returns, self.config.volatility_window)
            volatility = (
                vol_series.iloc[-1]
                if len(vol_series) > 0 and pd.notna(vol_series.iloc[-1])
                else 0.0
            )

        # Determine regime
        indicators = {
            "sma_fast": current_sma_fast,
            "sma_slow": current_sma_slow,
            "trend_pct": trend_pct,
            "volatility": volatility,
        }

        if trend_pct > self.config.trend_threshold:
            state = RegimeState.BULL
            confidence = min(1.0, abs(trend_pct) / (self.config.trend_threshold * 2))
        elif trend_pct < -self.config.trend_threshold:
            state = RegimeState.BEAR
            confidence = min(1.0, abs(trend_pct) / (self.config.trend_threshold * 2))
        else:
            state = RegimeState.SIDEWAYS
            confidence = 1.0 - abs(trend_pct) / self.config.trend_threshold

        # Adjust confidence by volatility (using config instead of magic numbers)
        if volatility > self.config.high_volatility_threshold:
            confidence *= self.config.volatility_confidence_adjustment

        signal = RegimeSignal(
            state=state,
            confidence=confidence,
            timestamp=datetime.now(),
            indicators=indicators,
            confidence_threshold=self.config.confidence_threshold,
        )

        self._last_signal = signal
        return signal

    @property
    def last_signal(self) -> RegimeSignal | None:
        """Get last detected signal."""
        return self._last_signal
