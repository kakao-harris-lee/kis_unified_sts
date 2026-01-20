"""Technical indicator calculator for trend analysis."""
import logging
from collections import deque
from typing import Deque, Optional

import numpy as np

from .config import TechnicalConfig
from .models import IchimokuData

logger = logging.getLogger(__name__)


class TechnicalCalculator:
    """Calculate technical indicators for trend following.

    Indicators:
    - Simple Moving Average (SMA)
    - Exponential Moving Average (EMA)
    - Ichimoku Cloud
    - Average True Range (ATR)
    """

    def __init__(self, config: TechnicalConfig):
        self.config = config

        # Price history for calculations
        max_period = max(
            config.ma_long_period,
            config.ichimoku_senkou_b_period,
            config.atr_period * 2
        )
        self._prices: Deque[float] = deque(maxlen=max_period + 52)  # Extra buffer for Ichimoku displacement
        self._highs: Deque[float] = deque(maxlen=max_period + 52)
        self._lows: Deque[float] = deque(maxlen=max_period + 52)

        # EMA state
        self._ema_short: Optional[float] = None
        self._ema_long: Optional[float] = None
        self._ema_short_multiplier = 2 / (config.ma_short_period + 1)
        self._ema_long_multiplier = 2 / (config.ma_long_period + 1)

        # ATR state
        self._atr: Optional[float] = None
        self._prev_close: Optional[float] = None

    def update(self, close: float, high: Optional[float] = None, low: Optional[float] = None) -> None:
        """Update calculator with new price data.

        Args:
            close: Closing price
            high: High price (defaults to close)
            low: Low price (defaults to close)
        """
        high = high or close
        low = low or close

        self._prices.append(close)
        self._highs.append(high)
        self._lows.append(low)

        # Update EMAs
        self._update_ema(close)

        # Update ATR
        self._update_atr(high, low, close)

        self._prev_close = close

    def _update_ema(self, close: float) -> None:
        """Update EMA values."""
        if self._ema_short is None:
            if len(self._prices) >= self.config.ma_short_period:
                # Initialize with SMA
                self._ema_short = np.mean(list(self._prices)[-self.config.ma_short_period:])
        else:
            self._ema_short = close * self._ema_short_multiplier + self._ema_short * (1 - self._ema_short_multiplier)

        if self._ema_long is None:
            if len(self._prices) >= self.config.ma_long_period:
                self._ema_long = np.mean(list(self._prices)[-self.config.ma_long_period:])
        else:
            self._ema_long = close * self._ema_long_multiplier + self._ema_long * (1 - self._ema_long_multiplier)

    def _update_atr(self, high: float, low: float, close: float) -> None:
        """Update ATR value."""
        if self._prev_close is None:
            return

        # True Range
        tr = max(
            high - low,
            abs(high - self._prev_close),
            abs(low - self._prev_close)
        )

        if self._atr is None:
            # Need enough data for initial ATR
            if len(self._prices) >= self.config.atr_period:
                # Calculate initial ATR as average of TR
                trs = []
                prices = list(self._prices)
                highs = list(self._highs)
                lows = list(self._lows)
                for i in range(1, min(self.config.atr_period + 1, len(prices))):
                    tr_i = max(
                        highs[i] - lows[i],
                        abs(highs[i] - prices[i-1]),
                        abs(lows[i] - prices[i-1])
                    )
                    trs.append(tr_i)
                if trs:
                    self._atr = np.mean(trs)
        else:
            # Wilder's smoothing
            self._atr = (self._atr * (self.config.atr_period - 1) + tr) / self.config.atr_period

    def get_ma_short(self) -> Optional[float]:
        """Get short-period simple moving average."""
        if len(self._prices) < self.config.ma_short_period:
            return None
        return float(np.mean(list(self._prices)[-self.config.ma_short_period:]))

    def get_ma_long(self) -> Optional[float]:
        """Get long-period simple moving average."""
        if len(self._prices) < self.config.ma_long_period:
            return None
        return float(np.mean(list(self._prices)[-self.config.ma_long_period:]))

    def get_ema_short(self) -> Optional[float]:
        """Get short-period exponential moving average."""
        return self._ema_short

    def get_ema_long(self) -> Optional[float]:
        """Get long-period exponential moving average."""
        return self._ema_long

    def get_atr(self) -> Optional[float]:
        """Get Average True Range."""
        return self._atr

    def is_ready(self) -> bool:
        """Check if calculator has enough data for all indicators."""
        return len(self._prices) >= self.config.ma_long_period

    # Ichimoku Cloud methods

    def _calc_midpoint(self, period: int) -> Optional[float]:
        """Calculate (highest high + lowest low) / 2 over period."""
        if len(self._highs) < period:
            return None
        highs = list(self._highs)[-period:]
        lows = list(self._lows)[-period:]
        return (max(highs) + min(lows)) / 2

    def get_ichimoku(self) -> Optional[IchimokuData]:
        """Get Ichimoku cloud indicator values.

        Ichimoku Components:
        - Tenkan-sen (Conversion): (9-period high + 9-period low) / 2
        - Kijun-sen (Base): (26-period high + 26-period low) / 2
        - Senkou Span A: (Tenkan + Kijun) / 2, displaced 26 periods forward
        - Senkou Span B: (52-period high + 52-period low) / 2, displaced 26 periods forward
        - Chikou Span: Current close, displaced 26 periods backward
        """
        tenkan = self._calc_midpoint(self.config.ichimoku_tenkan_period)
        kijun = self._calc_midpoint(self.config.ichimoku_kijun_period)

        if tenkan is None or kijun is None:
            return None

        senkou_a = (tenkan + kijun) / 2

        senkou_b = self._calc_midpoint(self.config.ichimoku_senkou_b_period)
        if senkou_b is None:
            # Use kijun period if not enough data for senkou_b
            senkou_b = kijun

        chikou = self._prices[-1] if self._prices else 0.0

        return IchimokuData(
            tenkan=tenkan,
            kijun=kijun,
            senkou_a=senkou_a,
            senkou_b=senkou_b,
            chikou=chikou
        )

    def is_price_above_cloud(self) -> bool:
        """Check if current price is above the Ichimoku cloud."""
        if not self._prices:
            return False

        ichimoku = self.get_ichimoku()
        if ichimoku is None:
            return False

        current_price = self._prices[-1]
        cloud_top = max(ichimoku.senkou_a, ichimoku.senkou_b)

        return current_price > cloud_top

    def is_price_below_cloud(self) -> bool:
        """Check if current price is below the Ichimoku cloud."""
        if not self._prices:
            return False

        ichimoku = self.get_ichimoku()
        if ichimoku is None:
            return False

        current_price = self._prices[-1]
        cloud_bottom = min(ichimoku.senkou_a, ichimoku.senkou_b)

        return current_price < cloud_bottom

    def reset(self) -> None:
        """Reset calculator state."""
        self._prices.clear()
        self._highs.clear()
        self._lows.clear()
        self._ema_short = None
        self._ema_long = None
        self._atr = None
        self._prev_close = None
