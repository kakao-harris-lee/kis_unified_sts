"""Stock regime detector."""
import logging
from datetime import datetime
from typing import Optional

import pandas as pd
import numpy as np

from .models import RegimeState, RegimeSignal, RegimeConfig

logger = logging.getLogger(__name__)


class StockRegimeDetector:
    """Detect market regime based on price action.

    Uses:
    - Moving average crossovers
    - Price momentum
    - Volatility
    """

    def __init__(self, config: Optional[RegimeConfig] = None):
        self.config = config or RegimeConfig()
        self._last_signal: Optional[RegimeSignal] = None

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
            )

        # Calculate indicators
        close = df["close"]
        sma_fast = close.rolling(self.config.sma_fast).mean()
        sma_slow = close.rolling(self.config.sma_slow).mean()

        # Current values
        current_price = close.iloc[-1]
        current_sma_fast = sma_fast.iloc[-1]
        current_sma_slow = sma_slow.iloc[-1]

        # Calculate trend strength
        trend_pct = (current_sma_fast - current_sma_slow) / current_sma_slow

        # Calculate volatility
        returns = close.pct_change().dropna()
        volatility = returns.rolling(self.config.volatility_window).std().iloc[-1]

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

        # Adjust confidence by volatility
        if volatility > 0.03:  # High volatility reduces confidence
            confidence *= 0.8

        signal = RegimeSignal(
            state=state,
            confidence=confidence,
            timestamp=datetime.now(),
            indicators=indicators,
        )

        self._last_signal = signal
        return signal

    @property
    def last_signal(self) -> Optional[RegimeSignal]:
        """Get last detected signal."""
        return self._last_signal
