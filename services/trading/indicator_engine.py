"""Streaming Indicator Engine for live trading.

Accumulates 1-minute candles from 0.5s price snapshots and computes
Bollinger Bands and RSI in pure Python (no pandas/polars needed).

Usage:
    engine = StreamingIndicatorEngine(bb_period=20, bb_std=2.0, rsi_period=14)

    # Feed ticks from market data loop
    engine.on_tick("005930", {"close": 71000, "high": 71100, "low": 70900, "volume": 100}, now)

    # Read computed indicators
    indicators = engine.get_indicators("005930")
    # {"bb_lower": 70500, "bb_upper": 71500, "bb_middle": 71000, "rsi": 35.2}
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    """Completed 1-minute candle."""

    open: float
    high: float
    low: float
    close: float
    volume: float
    minute: int  # minute boundary (e.g. 930 for 09:30)


class CandleAccumulator:
    """Accumulates sub-second ticks into 1-minute candles for a single symbol."""

    def __init__(self, maxlen: int = 100):
        self.candles: deque[Candle] = deque(maxlen=maxlen)
        self._current_minute: int | None = None
        self._open: float = 0.0
        self._high: float = 0.0
        self._low: float = 0.0
        self._close: float = 0.0
        self._volume: float = 0.0

    def on_tick(
        self,
        close: float,
        high: float | None = None,
        low: float | None = None,
        volume: float = 0.0,
        timestamp: datetime | None = None,
    ) -> Candle | None:
        """Process a tick. Returns a completed candle when the minute boundary changes."""
        ts = timestamp or datetime.now()
        minute = ts.hour * 100 + ts.minute

        h = high if high is not None else close
        lo = low if low is not None else close

        if self._current_minute is None:
            # First tick
            self._current_minute = minute
            self._open = close
            self._high = h
            self._low = lo
            self._close = close
            self._volume = volume
            return None

        if minute != self._current_minute:
            # Finalize previous candle
            completed = Candle(
                open=self._open,
                high=self._high,
                low=self._low,
                close=self._close,
                volume=self._volume,
                minute=self._current_minute,
            )
            self.candles.append(completed)

            # Start new candle
            self._current_minute = minute
            self._open = close
            self._high = h
            self._low = lo
            self._close = close
            self._volume = volume
            return completed

        # Same minute — update running candle
        self._high = max(self._high, h)
        self._low = min(self._low, lo)
        self._close = close
        self._volume += volume
        return None


class StreamingIndicatorEngine:
    """Computes BB and RSI from streaming 1-minute candles.

    Thread-safe by design: on_tick() and get_indicators() both run on
    the same asyncio event loop. get_indicators() returns a copy.
    """

    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        candle_maxlen: int = 100,
    ):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self._candle_maxlen = candle_maxlen
        self._accumulators: dict[str, CandleAccumulator] = {}
        self._warm_logged: set[str] = set()

    def on_tick(
        self,
        symbol: str,
        price_data: dict,
        timestamp: datetime | None = None,
    ) -> None:
        """Feed a price snapshot from the market data loop."""
        close = price_data.get("close") or price_data.get("price")
        if not close:
            return

        acc = self._accumulators.get(symbol)
        if acc is None:
            acc = CandleAccumulator(maxlen=self._candle_maxlen)
            self._accumulators[symbol] = acc

        candle = acc.on_tick(
            close=float(close),
            high=price_data.get("high"),
            low=price_data.get("low"),
            volume=float(price_data.get("volume", 0)),
            timestamp=timestamp,
        )

        if candle is not None and self.is_warm(symbol) and symbol not in self._warm_logged:
            self._warm_logged.add(symbol)
            logger.info(
                f"Indicator engine: {symbol} is now warm "
                f"({len(acc.candles)} candles)"
            )

    def is_warm(self, symbol: str) -> bool:
        """Whether enough candles exist to compute indicators."""
        acc = self._accumulators.get(symbol)
        if acc is None:
            return False
        return len(acc.candles) >= self.bb_period

    def get_indicators(self, symbol: str) -> dict[str, float]:
        """Compute and return current indicator values.

        Returns empty dict if not enough data.
        """
        acc = self._accumulators.get(symbol)
        if acc is None or len(acc.candles) < self.bb_period:
            return {}

        closes = [c.close for c in acc.candles]

        bb_lower, bb_middle, bb_upper = self._calc_bb(closes)
        rsi = self._calc_rsi(closes)

        return {
            "bb_lower": bb_lower,
            "bb_middle": bb_middle,
            "bb_upper": bb_upper,
            "rsi": rsi,
        }

    def get_stats(self) -> dict:
        """Diagnostic stats."""
        warm = [s for s in self._accumulators if self.is_warm(s)]
        return {
            "total_symbols": len(self._accumulators),
            "warm_symbols": len(warm),
            "warm_list": warm[:10],
        }

    # ------------------------------------------------------------------
    # Private computation methods
    # ------------------------------------------------------------------

    def _calc_bb(self, closes: list[float]) -> tuple[float, float, float]:
        """Bollinger Bands using population std (matching core/indicator_engine.py)."""
        window = closes[-self.bb_period:]
        mean = sum(window) / len(window)

        # Population variance (ddof=0) to match Polars rolling_std default
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        std = math.sqrt(variance)

        upper = mean + self.bb_std * std
        lower = mean - self.bb_std * std
        return lower, mean, upper

    def _calc_rsi(self, closes: list[float]) -> float:
        """RSI using rolling SMA of gains/losses (matching core/indicator_engine.py)."""
        if len(closes) < self.rsi_period + 1:
            return 50.0

        # Use the last rsi_period+1 closes to get rsi_period deltas
        recent = closes[-(self.rsi_period + 1):]
        gains = []
        losses = []
        for i in range(1, len(recent)):
            delta = recent[i] - recent[i - 1]
            gains.append(delta if delta > 0 else 0.0)
            losses.append(-delta if delta < 0 else 0.0)

        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))
