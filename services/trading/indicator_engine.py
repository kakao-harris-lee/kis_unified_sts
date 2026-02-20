"""Streaming Indicator Engine for live trading.

Accumulates 1-minute candles from 0.5s price snapshots and computes
Bollinger Bands, RSI, VWAP, RVOL, and volume velocity/acceleration
in pure Python (no pandas/polars needed).

Supports multi-timeframe candle aggregation (e.g., 5-minute) for
momentum-based strategies (TRIX, CCI, MACD, Stochastic).

Usage:
    engine = StreamingIndicatorEngine(bb_period=20, bb_std=2.0, rsi_period=14)

    # Feed ticks from market data loop
    engine.on_tick("005930", {"close": 71000, "high": 71100, "low": 70900, "volume": 100}, now)

    # Read computed indicators
    indicators = engine.get_indicators("005930")
    # {"bb_lower": 70500, "bb_upper": 71500, "bb_middle": 71000, "rsi": 35.2,
    #  "vwap": 71050, "rvol": 2.3, "volume_velocity": 0.15, "volume_acceleration": 0.05,
    #  "high_5": 71500}

    # Multi-timeframe momentum indicators (5-minute)
    momentum = engine.get_momentum_indicators("005930", timeframe=5)
    # {"trix": 0.05, "trix_signal": 0.03, "cci": 45.2, ...}
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from shared.indicators.volume import VolumeAccelerationCalculator, VWAPCalculator

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
        self.last_tick_ts: datetime | None = None

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
        self.last_tick_ts = ts
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


class MultiTimeframeCandleAccumulator:
    """Aggregates 1-minute candles into higher timeframe candles (e.g., 5-minute).

    Called each time a new 1-minute candle is completed. Accumulates into
    N-minute candles based on configurable timeframe.
    """

    def __init__(self, timeframe_minutes: int = 5, maxlen: int = 250):
        """Initialize multi-timeframe accumulator.

        Args:
            timeframe_minutes: Target candle timeframe in minutes.
            maxlen: Maximum number of completed candles to retain.
        """
        self.timeframe = timeframe_minutes
        self.candles: deque[Candle] = deque(maxlen=maxlen)
        self._buffer: list[Candle] = []
        self._current_bucket: int | None = None

    def _get_bucket(self, minute: int) -> int:
        """Compute the time bucket for a given HHMM minute value.

        E.g., with timeframe=5: minute 932 → bucket 930, minute 935 → bucket 935.
        """
        hours = minute // 100
        mins = minute % 100
        total = hours * 60 + mins
        bucket_total = (total // self.timeframe) * self.timeframe
        return (bucket_total // 60) * 100 + (bucket_total % 60)

    def on_1m_candle(self, candle: Candle) -> Candle | None:
        """Process a completed 1-minute candle.

        Returns a completed N-minute candle when the time bucket changes.
        """
        bucket = self._get_bucket(candle.minute)

        if self._current_bucket is None:
            self._current_bucket = bucket
            self._buffer.append(candle)
            return None

        if bucket != self._current_bucket:
            # Finalize previous bucket
            completed = self._finalize_buffer()

            # Start new bucket
            self._current_bucket = bucket
            self._buffer = [candle]

            return completed

        # Same bucket — accumulate
        self._buffer.append(candle)
        return None

    def _finalize_buffer(self) -> Candle | None:
        """Combine buffered 1-min candles into a single higher-TF candle."""
        if not self._buffer:
            return None

        completed = Candle(
            open=self._buffer[0].open,
            high=max(c.high for c in self._buffer),
            low=min(c.low for c in self._buffer),
            close=self._buffer[-1].close,
            volume=sum(c.volume for c in self._buffer),
            minute=self._current_bucket or 0,
        )
        self.candles.append(completed)
        return completed

    def flush(self) -> Candle | None:
        """Force-finalize any buffered candles (e.g., at session end)."""
        if not self._buffer:
            return None
        completed = self._finalize_buffer()
        self._buffer = []
        self._current_bucket = None
        return completed


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
        candle_maxlen: int = 240,
        high_period: int = 5,
        rvol_short: int = 5,
        rvol_long: int = 20,
        staleness_seconds: float = 180.0,
        mtf_timeframes: list[int] | None = None,
        mtf_maxlen: int = 250,
    ):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self._candle_maxlen = candle_maxlen
        self._staleness_seconds = staleness_seconds
        self._accumulators: dict[str, CandleAccumulator] = {}
        self._warm_logged: set[str] = set()

        # Multi-timeframe accumulators: {symbol: {timeframe: accumulator}}
        self._mtf_timeframes = mtf_timeframes or []
        self._mtf_maxlen = mtf_maxlen
        self._mtf_accumulators: dict[
            str, dict[int, MultiTimeframeCandleAccumulator]
        ] = {}
        self._momentum_cache: dict[tuple[str, int], tuple[int, dict[str, Any]]] = {}

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
            self._vwap_calc.add_tick(symbol, candle.close, int(candle.volume), date_str)
            self._vol_accel_calc.add_tick(symbol, int(candle.volume), ts.timestamp())

            # Feed multi-timeframe accumulators
            if self._mtf_timeframes:
                self._feed_mtf_candle(symbol, candle)

        if (
            candle is not None
            and self.is_warm(symbol)
            and symbol not in self._warm_logged
        ):
            self._warm_logged.add(symbol)
            logger.info(
                f"Indicator engine: {symbol} is now warm "
                f"({len(acc.candles)} candles)"
            )

    def seed_candles(
        self, symbol: str, candles: list[dict], minute: int | None = None
    ) -> None:
        """Pre-warm a symbol with historical candle data.

        Each candle dict must have: open, high, low, close, volume.
        Candles should be in chronological order.

        Args:
            symbol: Symbol to seed.
            candles: List of candle dicts.
            minute: Optional HHMM minute value for MTF bucketing.
                    If not provided, uses 0 (no MTF bucket change detection).
        """
        acc = self._accumulators.get(symbol)
        if acc is None:
            acc = CandleAccumulator(maxlen=self._candle_maxlen)
            self._accumulators[symbol] = acc

        seeded = 0
        for c in candles:
            try:
                # Derive minute from datetime if available and not explicitly given
                candle_minute = minute
                if candle_minute is None:
                    dt = c.get("datetime")
                    if dt is not None:
                        if isinstance(dt, str):
                            dt = datetime.fromisoformat(dt)
                        if hasattr(dt, "hour"):
                            candle_minute = dt.hour * 100 + dt.minute
                if candle_minute is None:
                    candle_minute = 0

                candle = Candle(
                    open=float(c["open"]),
                    high=float(c["high"]),
                    low=float(c["low"]),
                    close=float(c["close"]),
                    volume=float(c.get("volume", 0)),
                    minute=candle_minute,
                )
                acc.candles.append(candle)
                seeded += 1

                # Feed multi-timeframe accumulators if configured
                if self._mtf_timeframes:
                    self._feed_mtf_candle(symbol, candle)

            except (KeyError, ValueError):
                continue

        if seeded > 0 and self.is_warm(symbol) and symbol not in self._warm_logged:
            self._warm_logged.add(symbol)
            logger.info(
                f"Indicator engine: {symbol} pre-warmed "
                f"({len(acc.candles)} candles, {seeded} seeded)"
            )

    def seed_mtf_candles(
        self, symbol: str, candles: list[dict], timeframe: int = 5
    ) -> None:
        """Pre-warm multi-timeframe accumulator with historical candle data.

        Each candle dict must have: open, high, low, close, volume.
        Candles should be in chronological order and already aggregated
        to the target timeframe.
        """
        if timeframe not in self._mtf_timeframes:
            self._mtf_timeframes.append(timeframe)

        mtf_map = self._mtf_accumulators.get(symbol)
        if mtf_map is None:
            mtf_map = {}
            self._mtf_accumulators[symbol] = mtf_map

        mtf_acc = mtf_map.get(timeframe)
        if mtf_acc is None:
            mtf_acc = MultiTimeframeCandleAccumulator(
                timeframe_minutes=timeframe, maxlen=self._mtf_maxlen
            )
            mtf_map[timeframe] = mtf_acc

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
                mtf_acc.candles.append(candle)
                seeded += 1
            except (KeyError, ValueError):
                continue

        if seeded > 0:
            logger.info(
                f"Indicator engine: {symbol} {timeframe}m pre-warmed "
                f"({len(mtf_acc.candles)} candles, {seeded} seeded)"
            )

    def remove_symbol(self, symbol: str) -> None:
        """Remove a symbol's accumulator and related state.

        Called when a symbol is evicted from the trading universe to prevent
        stale indicator data from being used on re-entry.
        """
        if symbol in self._accumulators:
            del self._accumulators[symbol]
        if symbol in self._mtf_accumulators:
            del self._mtf_accumulators[symbol]
        self._momentum_cache = {
            key: value for key, value in self._momentum_cache.items() if key[0] != symbol
        }
        self._warm_logged.discard(symbol)
        self._vwap_calc.reset(symbol)
        self._vol_accel_calc.reset(symbol)

    def is_warm(self, symbol: str) -> bool:
        """Whether enough candles exist to compute indicators."""
        acc = self._accumulators.get(symbol)
        if acc is None:
            return False
        return len(acc.candles) >= self.bb_period

    def get_indicators(
        self, symbol: str, now: datetime | None = None
    ) -> dict[str, float]:
        """Compute and return current indicator values.

        Args:
            symbol: The symbol to compute indicators for.
            now: Current timestamp for staleness check. Defaults to datetime.now().

        Returns empty dict if not enough data or data is stale.
        """
        acc = self._accumulators.get(symbol)
        if acc is None or len(acc.candles) < self.bb_period:
            return {}

        # Staleness guard: reject indicators from symbols with no recent ticks
        if acc.last_tick_ts is not None and self._staleness_seconds > 0:
            _now = now or datetime.now()
            age = (_now - acc.last_tick_ts).total_seconds()
            if age > self._staleness_seconds:
                logger.warning(
                    "Indicator data stale for %s (%.0fs since last tick, "
                    "threshold %.0fs) — returning empty",
                    symbol,
                    age,
                    self._staleness_seconds,
                )
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

    def get_recent_candles(
        self, symbol: str, limit: int = 240
    ) -> list[dict[str, float]]:
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

    def _feed_mtf_candle(self, symbol: str, candle: Candle) -> None:
        """Feed a completed 1-minute candle to all multi-timeframe accumulators."""
        mtf_map = self._mtf_accumulators.get(symbol)
        if mtf_map is None:
            mtf_map = {}
            self._mtf_accumulators[symbol] = mtf_map

        for tf in self._mtf_timeframes:
            mtf_acc = mtf_map.get(tf)
            if mtf_acc is None:
                mtf_acc = MultiTimeframeCandleAccumulator(
                    timeframe_minutes=tf, maxlen=self._mtf_maxlen
                )
                mtf_map[tf] = mtf_acc
            mtf_acc.on_1m_candle(candle)

    def get_mtf_candles(
        self, symbol: str, timeframe: int = 5, limit: int = 250
    ) -> list[dict[str, float]]:
        """Return recent completed candles for a multi-timeframe.

        Args:
            symbol: Symbol to get candles for.
            timeframe: Timeframe in minutes.
            limit: Maximum number of candles to return.

        Returns:
            List of candle dicts with open, high, low, close, volume.
        """
        mtf_map = self._mtf_accumulators.get(symbol)
        if not mtf_map:
            return []
        mtf_acc = mtf_map.get(timeframe)
        if not mtf_acc:
            return []
        candles = list(mtf_acc.candles)
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

    def get_momentum_indicators(
        self,
        symbol: str,
        timeframe: int = 5,
        *,
        trix_n: int = 12,
        trix_signal: int = 9,
        cci_period: int = 9,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        sto_fastk: int = 12,
        sto_slowk: int = 5,
        sto_slowd: int = 5,
        rsi_period: int = 14,
        min_candles: int = 50,
    ) -> dict[str, Any]:
        """Compute momentum indicators from multi-timeframe candles.

        Uses pandas-based calculators from shared.indicators.momentum on
        the accumulated N-minute candles.

        Args:
            symbol: Symbol to compute indicators for.
            timeframe: Candle timeframe in minutes.
            **params: Indicator parameters forwarded to calculators.
            min_candles: Minimum candles needed for valid computation.

        Returns:
            Dict with last-bar values for all momentum indicators,
            plus 'df' key containing the full DataFrame for strategy use.
            Empty dict if insufficient data.
        """
        import pandas as pd

        from shared.indicators.momentum import calculate_all_momentum

        candles = self.get_mtf_candles(symbol, timeframe, limit=0)
        if len(candles) < min_candles:
            return {}

        cache_key = (symbol, timeframe)
        cached = self._momentum_cache.get(cache_key)
        if cached and cached[0] == len(candles):
            return cached[1]

        df = pd.DataFrame(candles)

        try:
            df = calculate_all_momentum(
                df,
                trix_n=trix_n,
                trix_signal=trix_signal,
                cci_period=cci_period,
                macd_fast=macd_fast,
                macd_slow=macd_slow,
                macd_signal=macd_signal,
                sto_fastk=sto_fastk,
                sto_slowk=sto_slowk,
                sto_slowd=sto_slowd,
                rsi_period=rsi_period,
            )
        except Exception as e:
            logger.error(f"Momentum indicator calculation failed for {symbol}: {e}")
            return {}

        # Extract last-bar values
        last = df.iloc[-1]
        result: dict[str, Any] = {
            "trix": float(last.get("trix", 0)),
            "trix_signal": float(last.get("trix_signal", 0)),
            "cci": float(last.get("cci", 0)),
            "macd_line": float(last.get("macd_line", 0)),
            "macd_signal": float(last.get("macd_signal", 0)),
            "macd_oscillator": float(last.get("macd_oscillator", 0)),
            "sto_k": float(last.get("sto_k", 50)),
            "sto_d": float(last.get("sto_d", 50)),
            "obv": float(last.get("obv", 0)),
            "rsi": float(last.get("rsi", 50)),
            "timeframe": timeframe,
            "candle_count": len(df),
            "df": df,  # Full DataFrame for divergence detection etc.
        }

        self._momentum_cache[cache_key] = (len(df), result)
        return result

    def get_market_mfi(self, active_symbols: set[str] | None = None) -> float | None:
        """Compute aggregate MFI across warm symbols.

        Args:
            active_symbols: If provided, only include these symbols.
                Otherwise, all accumulators are used.

        Returns the median MFI of warm symbols, or None if insufficient data.
        """
        mfi_values = []
        for symbol, acc in self._accumulators.items():
            if active_symbols is not None and symbol not in active_symbols:
                continue
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
        window = closes[-self.bb_period :]
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
        recent = closes[-(self.rsi_period + 1) :]
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

        recent = candles[-(period + 1) :]
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
