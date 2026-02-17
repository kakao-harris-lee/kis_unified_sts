"""Streaming Indicator Engine for live trading.

Accumulates 1-minute candles from 0.5s price snapshots and computes
Bollinger Bands, RSI, VWAP, RVOL, and volume velocity/acceleration
in pure Python (no pandas/polars needed).

Usage:
    engine = StreamingIndicatorEngine(bb_period=20, bb_std=2.0, rsi_period=14)

    # Feed ticks from market data loop
    engine.on_tick("005930", {"close": 71000, "high": 71100, "low": 70900, "volume": 100}, now)

    # Read computed indicators
    indicators = engine.get_indicators("005930")
    # {"bb_lower": 70500, "bb_upper": 71500, "bb_middle": 71000, "rsi": 35.2,
    #  "vwap": 71050, "rvol": 2.3, "volume_velocity": 0.15, "volume_acceleration": 0.05,
    #  "high_5": 71500}
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from shared.indicators.volume import VWAPCalculator, VolumeAccelerationCalculator

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
        high_period: int = 5,
        rvol_short: int = 5,
        rvol_long: int = 20,
    ):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self._candle_maxlen = candle_maxlen
        self._accumulators: dict[str, CandleAccumulator] = {}
        self._warm_logged: set[str] = set()

        # Volume indicators
        self._high_period = high_period
        self._rvol_short = rvol_short
        self._rvol_long = rvol_long
        self._vwap_calc = VWAPCalculator()
        self._vol_accel_calc = VolumeAccelerationCalculator()

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

        close_f = float(close)
        volume_f = float(price_data.get("volume", 0))

        # Guard against inf/nan/negative values
        if not math.isfinite(close_f) or close_f <= 0:
            return
        if not math.isfinite(volume_f) or volume_f < 0:
            volume_f = 0.0

        # Resolve timestamp once for all consumers
        ts = timestamp or datetime.now()

        acc = self._accumulators.get(symbol)
        if acc is None:
            acc = CandleAccumulator(maxlen=self._candle_maxlen)
            self._accumulators[symbol] = acc

        candle = acc.on_tick(
            close=close_f,
            high=price_data.get("high"),
            low=price_data.get("low"),
            volume=volume_f,
            timestamp=ts,
        )

        # Feed volume calculators only on candle completion to avoid
        # double-counting volume from repeated 0.5s polling snapshots.
        if candle is not None:
            date_str = ts.strftime("%Y%m%d")
            self._vwap_calc.add_tick(
                symbol, candle.close, int(candle.volume), date_str
            )
            self._vol_accel_calc.add_tick(
                symbol, int(candle.volume), ts.timestamp()
            )

        if candle is not None and self.is_warm(symbol) and symbol not in self._warm_logged:
            self._warm_logged.add(symbol)
            logger.info(
                f"Indicator engine: {symbol} is now warm "
                f"({len(acc.candles)} candles)"
            )

    def seed_candles(self, symbol: str, candles: list[dict]) -> None:
        """Pre-warm a symbol with historical candle data.

        Each candle dict must have: open, high, low, close, volume.
        Candles should be in chronological order.
        """
        acc = self._accumulators.get(symbol)
        if acc is None:
            acc = CandleAccumulator(maxlen=self._candle_maxlen)
            self._accumulators[symbol] = acc

        seeded = 0
        for c in candles:
            try:
                candle = Candle(
                    open=float(c["open"]),
                    high=float(c["high"]),
                    low=float(c["low"]),
                    close=float(c["close"]),
                    volume=float(c.get("volume", 0)),
                    minute=0,
                )
                acc.candles.append(candle)
                seeded += 1
            except (KeyError, ValueError):
                continue

        if seeded > 0 and self.is_warm(symbol) and symbol not in self._warm_logged:
            self._warm_logged.add(symbol)
            logger.info(
                f"Indicator engine: {symbol} pre-warmed "
                f"({len(acc.candles)} candles, {seeded} seeded)"
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

        candles = list(acc.candles)
        closes = [c.close for c in candles]

        bb_lower, bb_middle, bb_upper = self._calc_bb(closes)
        rsi = self._calc_rsi(closes)

        result: dict[str, float] = {
            "bb_lower": bb_lower,
            "bb_middle": bb_middle,
            "bb_upper": bb_upper,
            "rsi": rsi,
        }

        # MFI needs volume data; only compute if candles have volume
        mfi = self._calc_mfi(candles)
        if mfi is not None:
            result["mfi"] = mfi

        # Volume indicators
        current_close = closes[-1]

        # VWAP
        vwap_data = self._vwap_calc.calculate(symbol, current_close)
        result["vwap"] = vwap_data.vwap

        # Volume velocity & acceleration
        vol_accel = self._vol_accel_calc.calculate(symbol)
        result["volume_velocity"] = vol_accel.velocity
        result["volume_acceleration"] = vol_accel.acceleration

        # RVOL (from candle volumes, inline — avoids numpy dependency)
        result["rvol"] = self._calc_rvol(candles)

        # High over N periods
        result[f"high_{self._high_period}"] = self._calc_high_n(candles)

        return result

    def get_recent_candles(self, symbol: str, limit: int = 240) -> list[dict[str, float]]:
        """Return recent completed candles for a symbol.

        Used by feature-heavy strategies (e.g., RL) that need OHLCV history.
        """
        acc = self._accumulators.get(symbol)
        if acc is None:
            return []
        candles = list(acc.candles)
        if limit > 0:
            candles = candles[-limit:]
        return [
            {
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ]

    def get_market_mfi(self) -> float | None:
        """Compute aggregate MFI across all warm symbols.

        Returns the median MFI of all warm symbols, or None if insufficient data.
        """
        mfi_values = []
        for symbol, acc in self._accumulators.items():
            if len(acc.candles) < 14:
                continue
            mfi = self._calc_mfi(list(acc.candles))
            if mfi is not None:
                mfi_values.append(mfi)

        if not mfi_values:
            return None

        # Median is more robust than mean for market-wide MFI
        mfi_values.sort()
        n = len(mfi_values)
        if n % 2 == 0:
            return (mfi_values[n // 2 - 1] + mfi_values[n // 2]) / 2
        return mfi_values[n // 2]

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
        """Bollinger Bands using sample std (ddof=1, matching Polars rolling_std)."""
        window = closes[-self.bb_period:]
        n = len(window)
        mean = sum(window) / n

        # Sample variance (ddof=1) to match Polars rolling_std default
        variance = sum((x - mean) ** 2 for x in window) / (n - 1)
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

    def _calc_rvol(self, candles: list[Candle]) -> float:
        """RVOL = short-window avg volume / long-window avg volume.

        Intentionally numpy-free (unlike shared.indicators.volume.RVOLCalculator)
        to keep indicator_engine dependency-light for the hot path.
        """
        n = len(candles)
        sw = min(self._rvol_short, n)
        lw = min(self._rvol_long, n)

        if lw == 0 or sw == 0:
            return 1.0

        short_avg = sum(c.volume for c in candles[-sw:]) / sw
        long_avg = sum(c.volume for c in candles[-lw:]) / lw

        if long_avg == 0:
            return 1.0

        return short_avg / long_avg

    def _calc_high_n(self, candles: list[Candle]) -> float:
        """Highest high over the last N candles."""
        period = min(self._high_period, len(candles))
        if period == 0:
            return 0.0
        return max(c.high for c in candles[-period:])

    def _calc_mfi(self, candles: list[Candle], period: int = 14) -> float | None:
        """Money Flow Index (14-period).

        MFI = 100 - 100 / (1 + positive_flow / negative_flow)
        Typical Price = (high + low + close) / 3
        Raw Money Flow = Typical Price * Volume
        """
        if len(candles) < period + 1:
            return None

        recent = candles[-(period + 1):]
        positive_flow = 0.0
        negative_flow = 0.0

        for i in range(1, len(recent)):
            tp_prev = (recent[i - 1].high + recent[i - 1].low + recent[i - 1].close) / 3
            tp_curr = (recent[i].high + recent[i].low + recent[i].close) / 3
            raw_flow = tp_curr * recent[i].volume

            if tp_curr > tp_prev:
                positive_flow += raw_flow
            elif tp_curr < tp_prev:
                negative_flow += raw_flow

        if negative_flow == 0:
            return 100.0 if positive_flow > 0 else 50.0

        money_ratio = positive_flow / negative_flow
        return 100.0 - (100.0 / (1.0 + money_ratio))
