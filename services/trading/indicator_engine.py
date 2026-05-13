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
from datetime import UTC, datetime
from typing import Any

from shared.exceptions import ValidationError
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
        # tz-aware UTC by default. Caller-supplied ts MAY be tz-naive; we
        # store as-is but the staleness guard normalizes both sides.
        ts = timestamp or datetime.now(UTC)
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
        mtf_timeframes: list[int | str] | None = None,
        mtf_maxlen: int = 250,
        ema_periods: list[int] | None = None,
        daily_ema_periods: list[int] | None = None,
    ):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self._candle_maxlen = candle_maxlen
        self._staleness_seconds = staleness_seconds
        self._accumulators: dict[str, CandleAccumulator] = {}
        self._warm_logged: set[str] = set()
        self._ema_periods: list[int] = ema_periods or [5, 20, 60]

        # Multi-timeframe accumulators: {symbol: {timeframe: accumulator}}
        # Separate 'daily' from numeric timeframes (5, 15, etc.)
        self._mtf_timeframes = mtf_timeframes or []
        self._numeric_mtf_timeframes: list[int] = [
            tf for tf in self._mtf_timeframes if isinstance(tf, int)
        ]
        self._has_daily = 'daily' in self._mtf_timeframes
        self._mtf_maxlen = mtf_maxlen
        self._mtf_accumulators: dict[
            str, dict[int, MultiTimeframeCandleAccumulator]
        ] = {}
        self._momentum_cache: dict[tuple[str, int], tuple[int, dict[str, Any]]] = {}

        # Daily candles (loaded from ClickHouse, not aggregated from 1m)
        # {symbol: deque[Candle]}
        self._daily_candles: dict[str, deque] = {}

        # Cache for get_indicators(): {symbol: (candle_count, indicators_dict)}
        self._indicator_cache: dict[str, tuple[int, dict[str, float]]] = {}

        # Cache statistics tracking
        self._indicator_cache_hits: int = 0
        self._indicator_cache_misses: int = 0
        self._momentum_cache_hits: int = 0
        self._momentum_cache_misses: int = 0

        # Volume indicators
        self._high_period = high_period
        self._rvol_short = rvol_short
        self._rvol_long = rvol_long
        self._vwap_calc = VWAPCalculator()
        self._vol_accel_calc = VolumeAccelerationCalculator()

        # Daily high tracking for multi-day breakout detection (high_N).
        # Stores per-symbol deque of previous session highs (not including today).
        # On day change, current day's high is pushed to the deque.
        self._daily_highs: dict[str, deque] = {}  # symbol -> deque of daily highs
        self._intraday_high: dict[str, float] = {}  # symbol -> current session high
        self._current_date: dict[str, str] = {}  # symbol -> current date string

        # Daily close tracking for daily-scale EMA trend filter.
        # Stores per-symbol deque of previous session closes.
        # On day change, previous day's last close is pushed to the deque.
        self._daily_closes: dict[str, deque] = {}  # symbol -> deque of daily closes
        self._intraday_last_close: dict[str, float] = {}  # symbol -> current session last close
        self._daily_ema_periods: list[int] = daily_ema_periods or [5, 10, 20]

        # Cumulative volume → delta conversion
        # WebSocket feeds (H0STCNT0, H0IFCNT0) send cumulative daily volume.
        # We track the last cumulative value per symbol to compute per-tick deltas.
        self._last_cumulative_volume: dict[str, float] = {}

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
        raw_volume = float(price_data.get("volume", 0))

        # Guard against inf/nan/negative values
        if not math.isfinite(close_f) or close_f <= 0:
            return
        if not math.isfinite(raw_volume) or raw_volume < 0:
            raw_volume = 0.0

        # Cumulative → delta volume conversion.
        # WebSocket feeds send cumulative daily volume (ACML_VOL).
        # CandleAccumulator expects per-tick deltas to sum into candles.
        # Skip conversion if volume is already per-tick (e.g. futures tick_volume fallback).
        if price_data.get("volume_is_cumulative") is False:
            delta_volume = raw_volume
        else:
            prev_cum = self._last_cumulative_volume.get(symbol, 0.0)
            if raw_volume >= prev_cum:
                delta_volume = raw_volume - prev_cum
            else:
                # Volume decreased: new trading day or data reset
                delta_volume = raw_volume
            self._last_cumulative_volume[symbol] = raw_volume

        # Resolve timestamp once for all consumers (tz-aware UTC by default).
        ts = timestamp or datetime.now(UTC)

        acc = self._accumulators.get(symbol)
        if acc is None:
            acc = CandleAccumulator(maxlen=self._candle_maxlen)
            self._accumulators[symbol] = acc

        candle = acc.on_tick(
            close=close_f,
            high=price_data.get("high"),
            low=price_data.get("low"),
            volume=delta_volume,
            timestamp=ts,
        )

        # Feed volume calculators only on candle completion to avoid
        # double-counting volume from repeated 0.5s polling snapshots.
        if candle is not None:
            date_str = ts.strftime("%Y%m%d")
            self._vwap_calc.add_tick(symbol, candle.close, int(candle.volume), date_str)
            self._vol_accel_calc.add_tick(symbol, int(candle.volume), ts.timestamp())

            # Track daily highs for multi-day breakout (high_N)
            # NOTE: _update_daily_high must be called before _update_daily_close
            # because both use self._current_date for day-change detection,
            # and _update_daily_high is responsible for updating it.
            self._update_daily_high(symbol, candle.high, date_str)

            # Track daily closes for daily-scale EMA trend filter
            self._update_daily_close(symbol, candle.close, date_str)

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

                # Track daily highs and closes for multi-day breakout & EMA
                dt = c.get("datetime")
                if dt is not None:
                    if isinstance(dt, str):
                        dt = datetime.fromisoformat(dt)
                    if hasattr(dt, "strftime"):
                        ds = dt.strftime("%Y%m%d")
                        self._update_daily_high(symbol, candle.high, ds)
                        self._update_daily_close(symbol, candle.close, ds)

                # Feed multi-timeframe accumulators if configured
                if self._mtf_timeframes:
                    self._feed_mtf_candle(symbol, candle)

            except (KeyError, ValueError):
                continue

        # Clear cumulative volume baseline so first real tick after seeding
        # establishes a fresh baseline (avoids stale prev_cum from before seed).
        self._last_cumulative_volume.pop(symbol, None)

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
        if timeframe not in self._numeric_mtf_timeframes:
            self._numeric_mtf_timeframes.append(timeframe)

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

    def seed_daily_candles(self, symbol: str, candles: list[dict]) -> None:
        """Pre-warm daily candle buffer with historical data.

        Each candle dict must have: open, high, low, close, volume.
        Candles should be in chronological order (oldest first).

        Args:
            symbol: Stock/futures symbol.
            candles: List of daily candle dicts with OHLCV data.
        """
        if symbol not in self._daily_candles:
            self._daily_candles[symbol] = deque(maxlen=200)

        daily_deque = self._daily_candles[symbol]
        seeded = 0

        for c in candles:
            try:
                candle = Candle(
                    open=float(c["open"]),
                    high=float(c["high"]),
                    low=float(c["low"]),
                    close=float(c["close"]),
                    volume=float(c.get("volume", 0)),
                    minute=0,  # Not used for daily candles
                )
                daily_deque.append(candle)
                seeded += 1
            except (KeyError, ValueError):
                continue

        if seeded > 0:
            logger.info(
                f"Indicator engine: {symbol} daily candles pre-warmed "
                f"({len(daily_deque)} total, {seeded} seeded)"
            )

    def set_volume_baseline(self, symbol: str, cumulative_volume: float) -> None:
        """Pre-set cumulative volume baseline for a symbol.

        Call this before the first real on_tick() to prevent the first tick's
        full cumulative volume from inflating the first candle.  Typical usage:
        the orchestrator calls this when a symbol is added mid-session.
        """
        if cumulative_volume >= 0:
            self._last_cumulative_volume[symbol] = cumulative_volume

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
        self._indicator_cache.pop(symbol, None)
        self._warm_logged.discard(symbol)
        self._vwap_calc.reset(symbol)
        self._vol_accel_calc.reset(symbol)
        self._last_cumulative_volume.pop(symbol, None)

    def cleanup_orphans(self, active_symbols: set[str]) -> int:
        """Remove accumulators for symbols not in the active set.

        Prevents unbounded growth of ``_accumulators`` when symbols are
        evicted from the trading universe but their accumulators linger
        (e.g. from stale prewarm tasks or dip-candidate churn).
        """
        orphans = [s for s in self._accumulators if s not in active_symbols]
        for s in orphans:
            self.remove_symbol(s)
        return len(orphans)

    def is_warm(self, symbol: str) -> bool:
        """Whether enough candles exist to compute indicators."""
        acc = self._accumulators.get(symbol)
        if acc is None:
            return False
        return len(acc.candles) >= self.bb_period

    def get_tick_age_seconds(self, symbol: str, now: datetime | None = None) -> float | None:
        """Return seconds elapsed since last tick for symbol, or None if never seen."""
        acc = self._accumulators.get(symbol)
        if acc is None or acc.last_tick_ts is None:
            return None
        last_ts = acc.last_tick_ts
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=UTC)
        _now = (now or datetime.now(UTC))
        if _now.tzinfo is None:
            _now = _now.replace(tzinfo=UTC)
        return (_now - last_ts).total_seconds()

    def warmup_progress(self, symbol: str) -> float:
        """Return warmup progress as a ratio in [0.0, 1.0]."""
        acc = self._accumulators.get(symbol)
        if acc is None or self.bb_period == 0:
            return 0.0
        return min(len(acc.candles) / self.bb_period, 1.0)

    def get_cache_stats(self) -> dict[str, Any]:
        """Return cache statistics for performance monitoring.

        Returns:
            Dict with cache hit/miss counts and cache sizes:
            - indicator_cache_hits: Number of cache hits for get_indicators()
            - indicator_cache_misses: Number of cache misses for get_indicators()
            - momentum_cache_hits: Number of cache hits for get_momentum_indicators()
            - momentum_cache_misses: Number of cache misses for get_momentum_indicators()
            - indicator_cache_size: Number of cached symbols
            - momentum_cache_size: Number of cached (symbol, timeframe) pairs
            - indicator_hit_rate: Percentage of cache hits (0-100)
            - momentum_hit_rate: Percentage of cache hits (0-100)
        """
        indicator_total = self._indicator_cache_hits + self._indicator_cache_misses
        momentum_total = self._momentum_cache_hits + self._momentum_cache_misses

        indicator_hit_rate = (
            (self._indicator_cache_hits / indicator_total * 100)
            if indicator_total > 0
            else 0.0
        )
        momentum_hit_rate = (
            (self._momentum_cache_hits / momentum_total * 100)
            if momentum_total > 0
            else 0.0
        )

        return {
            "indicator_cache_hits": self._indicator_cache_hits,
            "indicator_cache_misses": self._indicator_cache_misses,
            "momentum_cache_hits": self._momentum_cache_hits,
            "momentum_cache_misses": self._momentum_cache_misses,
            "indicator_cache_size": len(self._indicator_cache),
            "momentum_cache_size": len(self._momentum_cache),
            "indicator_hit_rate": indicator_hit_rate,
            "momentum_hit_rate": momentum_hit_rate,
        }

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

        # Staleness guard: reject indicators from symbols with no recent ticks.
        # Normalize both sides to UTC tz-aware so a legacy tz-mixed pair
        # (e.g., naive on_tick fallback + tz-aware caller) doesn't raise
        # "can't compare offset-naive and offset-aware" inside the
        # pipeline retry loop, silently dropping signals.
        if acc.last_tick_ts is not None and self._staleness_seconds > 0:
            last_ts = acc.last_tick_ts
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=UTC)
            _now = now or datetime.now(UTC)
            if _now.tzinfo is None:
                _now = _now.replace(tzinfo=UTC)
            age = (_now - last_ts).total_seconds()
            if age > self._staleness_seconds:
                logger.warning(
                    "Indicator data stale for %s (%.0fs since last tick, "
                    "threshold %.0fs) — returning empty",
                    symbol,
                    age,
                    self._staleness_seconds,
                )
                return {}

        # Check cache: return cached result if candle count hasn't changed
        candle_count = len(acc.candles)
        cached = self._indicator_cache.get(symbol)
        if cached and cached[0] == candle_count:
            self._indicator_cache_hits += 1
            return cached[1].copy()

        self._indicator_cache_misses += 1

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

        # ADX (Average Directional Index)
        adx = self._calc_adx(candles)
        if adx is not None:
            result["adx"] = adx

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

        # High over N previous trading days (for breakout detection)
        result[f"high_{self._high_period}"] = self._calc_high_n(symbol, candles)

        # Raw ATR (non-normalized) for edge filters and stop-loss calculations
        result["atr"] = self._calc_atr_raw(candles)

        # Volume moving average (20-period SMA of candle volumes)
        volumes = [c.volume for c in candles]
        vol_window = min(self.bb_period, len(volumes))
        if vol_window > 0:
            result["volume_ma"] = sum(volumes[-vol_window:]) / vol_window
        else:
            result["volume_ma"] = 0.0

        # EMA absolute values for trend mode (configurable periods)
        n = len(closes)
        for period in self._ema_periods:
            key = f"ema_{period}"
            if n >= period:
                result[key] = self._ema_last(closes, period)
            else:
                result[key] = 0.0
        # EMA alignment: fastest > middle > slowest (confirmed uptrend, intraday)
        if len(self._ema_periods) >= 3:
            sorted_periods = sorted(self._ema_periods)
            fast_key = f"ema_{sorted_periods[0]}"
            mid_key = f"ema_{sorted_periods[1]}"
            slow_key = f"ema_{sorted_periods[2]}"
            result["ema_aligned"] = (
                result[slow_key] > 0
                and result[fast_key] > result[mid_key] > result[slow_key]
            )
        else:
            result["ema_aligned"] = False

        # Daily EMA alignment: EMA(5d) > EMA(10d) > EMA(20d) — multi-day uptrend
        result["ema_daily_aligned"] = self._calc_daily_ema_aligned(symbol)

        # Update cache (store a copy so callers can safely mutate result)
        self._indicator_cache[symbol] = (candle_count, result.copy())

        return result

    def get_rl_features(self, symbol: str) -> dict[str, float]:
        """Compute all 25 RL features from stored candle history (pure Python).

        Replaces per-bar derive_features_from_ohlcv() (~20ms DataFrame allocation)
        with O(n) pure-Python computation over the candle deque (~0.5ms).

        Returns empty dict if insufficient candles (<26 for MACD slow period).
        """
        acc = self._accumulators.get(symbol)
        if acc is None or len(acc.candles) < 26:
            return {}

        candles = list(acc.candles)
        n = len(candles)
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        opens = [c.open for c in candles]
        volumes = [c.volume for c in candles]

        cur_close = closes[-1]
        cur_high = highs[-1]
        cur_low = lows[-1]
        cur_open = opens[-1]
        cur_vol = volumes[-1]

        result: dict[str, float] = {}

        # 1. returns
        result["returns"] = (
            (cur_close - closes[-2]) / closes[-2] if n >= 2 and closes[-2] != 0 else 0.0
        )

        # 2-4. ma_ratio_5, 10, 20 (reference: close / ma, no epsilon)
        for w in (5, 10, 20):
            if n >= w:
                sma = sum(closes[-w:]) / w
                result[f"ma_ratio_{w}"] = cur_close / (sma + 1e-10)
            else:
                result[f"ma_ratio_{w}"] = 1.0

        # 5. rsi (reuse existing method)
        result["rsi"] = self._calc_rsi(closes)

        # 6. bb_position (reference: / (bb_upper - bb_lower + 1e-10))
        bb_lower, bb_middle, bb_upper = self._calc_bb(closes)
        result["bb_position"] = (cur_close - bb_lower) / (bb_upper - bb_lower + 1e-10)

        # 7. volume_ratio
        if n >= 20:
            vol_avg = sum(volumes[-20:]) / 20
            result["volume_ratio"] = cur_vol / (vol_avg + 1)
        else:
            result["volume_ratio"] = 1.0

        # 8. volatility (rolling std of returns, 20 period)
        if n >= 21:
            rets = []
            for i in range(max(1, n - 20), n):
                if closes[i - 1] != 0:
                    rets.append((closes[i] - closes[i - 1]) / closes[i - 1])
            if len(rets) >= 2:
                mean_r = sum(rets) / len(rets)
                var = sum((r - mean_r) ** 2 for r in rets) / (len(rets) - 1)
                result["volatility"] = math.sqrt(var)
            else:
                result["volatility"] = 0.0
        else:
            result["volatility"] = 0.0

        # 9. hl_range (reference: (high - low) / close, no epsilon)
        result["hl_range"] = (cur_high - cur_low) / (cur_close + 1e-10)

        # 10. candle_body
        hl_diff = cur_high - cur_low
        result["candle_body"] = (cur_close - cur_open) / (hl_diff + 1e-10)

        # 11-13. MACD (EMA 12/26, signal 9)
        ema12 = self._ema_series(closes, 12)
        ema26 = self._ema_series(closes, 26)
        macd_series = [f - s for f, s in zip(ema12, ema26)]
        macd_sig = self._ema_series(macd_series, 9)
        result["macd"] = macd_series[-1]
        result["macd_signal"] = macd_sig[-1]
        result["macd_hist"] = macd_series[-1] - macd_sig[-1]

        # 14-15. sma_ratio_60, 120
        for w in (60, 120):
            if n >= w:
                sma = sum(closes[-w:]) / w
                result[f"sma_ratio_{w}"] = cur_close / (sma + 1e-10)
            else:
                result[f"sma_ratio_{w}"] = 1.0

        # 16-18. ema_ratio_5, 10, 20
        for w in (5, 10, 20):
            ema_val = self._ema_last(closes, w)
            result[f"ema_ratio_{w}"] = cur_close / (ema_val + 1e-10)

        # 19-21. BB extended
        result["bb_upper_dist"] = (bb_upper - cur_close) / (cur_close + 1e-10)
        result["bb_lower_dist"] = (cur_close - bb_lower) / (cur_close + 1e-10)
        result["bb_width"] = (bb_upper - bb_lower) / (bb_middle + 1e-10)

        # 22. atr (normalized by close)
        result["atr"] = self._calc_atr_normalized(candles)

        # 23-24. stochastic
        stoch_k, stoch_d = self._calc_stochastic(candles)
        result["stoch_k"] = stoch_k
        result["stoch_d"] = stoch_d

        # 25. price_change_5
        result["price_change_5"] = (
            (cur_close - closes[-6]) / closes[-6]
            if n >= 6 and closes[-6] != 0
            else 0.0
        )

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
        """Feed a completed 1-minute candle to all multi-timeframe accumulators.

        Note: 'daily' timeframe is NOT fed here — daily candles are loaded
        directly from ClickHouse via seed_daily_candles().
        """
        mtf_map = self._mtf_accumulators.get(symbol)
        if mtf_map is None:
            mtf_map = {}
            self._mtf_accumulators[symbol] = mtf_map

        for tf in self._numeric_mtf_timeframes:
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

    def get_daily_candles(
        self, symbol: str, limit: int = 200
    ) -> list[dict[str, float]]:
        """Return recent daily candles for a symbol.

        Daily candles are loaded from ClickHouse (not aggregated from 1m).

        Args:
            symbol: Symbol to get candles for.
            limit: Maximum number of candles to return.

        Returns:
            List of candle dicts with open, high, low, close, volume.
        """
        daily_deque = self._daily_candles.get(symbol)
        if not daily_deque:
            return []
        candles = list(daily_deque)
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
        williams_r_period: int = 14,
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

        # Check candle count directly from accumulator to avoid expensive dict conversion
        mtf_map = self._mtf_accumulators.get(symbol)
        if not mtf_map:
            return {}
        mtf_acc = mtf_map.get(timeframe)
        if not mtf_acc:
            return {}

        candle_count = len(mtf_acc.candles)
        if candle_count < min_candles:
            return {}

        # Check cache before expensive dict conversion and DataFrame construction
        cache_key = (symbol, timeframe)
        cached = self._momentum_cache.get(cache_key)
        if cached and cached[0] == candle_count:
            self._momentum_cache_hits += 1
            return cached[1]

        self._momentum_cache_misses += 1
        # Cache miss: convert candles to dicts for DataFrame construction
        candles = self.get_mtf_candles(symbol, timeframe, limit=0)
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
                williams_r_period=williams_r_period,
            )
        except (ValidationError, ValueError, KeyError, IndexError, ZeroDivisionError) as e:
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
            "williams_r": float(last.get("williams_r", -50)),
            "timeframe": timeframe,
            "candle_count": len(df),
            "df": df,  # Full DataFrame for divergence detection etc.
        }

        self._momentum_cache[cache_key] = (len(df), result)
        return result

    def get_daily_indicators(
        self,
        symbol: str,
        *,
        sma_periods: list[int] | None = None,
        ema_periods: list[int] | None = None,
        rsi_period: int = 5,
        min_candles: int = 50,
    ) -> dict[str, Any]:
        """Compute daily timeframe indicators from daily candles.

        Uses pandas-based calculators from shared.indicators.daily on
        the daily candles loaded from ClickHouse.

        Args:
            symbol: Symbol to compute indicators for.
            sma_periods: SMA periods to calculate (default: [20, 60, 200]).
            ema_periods: EMA periods to calculate (default: [5, 10, 20]).
            rsi_period: RSI period (default: 5).
            min_candles: Minimum candles needed for valid computation.

        Returns:
            Dict with daily indicator values (sma_20, sma_60, sma_200,
            ema_5, ema_10, ema_20, rsi_5).
            Empty dict if insufficient data.
        """
        from shared.indicators.daily import calculate_daily_indicators

        if sma_periods is None:
            sma_periods = [20, 60, 200]
        if ema_periods is None:
            ema_periods = [5, 10, 20]

        # Check candle count directly from accumulator to avoid expensive dict conversion
        daily_deque = self._daily_candles.get(symbol)
        if not daily_deque:
            return {}

        candle_count = len(daily_deque)
        if candle_count < min_candles:
            return {}

        # Check cache before expensive dict conversion
        cache_key = (symbol, "daily")
        cached = self._momentum_cache.get(cache_key)
        if cached and cached[0] == candle_count:
            self._momentum_cache_hits += 1
            return cached[1]

        self._momentum_cache_misses += 1
        # Cache miss: convert candles to dicts for calculation
        candles = self.get_daily_candles(symbol, limit=0)

        try:
            result = calculate_daily_indicators(
                candles,
                sma_periods=sma_periods,
                ema_periods=ema_periods,
                rsi_period=rsi_period,
            )
        except (ValidationError, ValueError, KeyError, IndexError, ZeroDivisionError) as e:
            logger.error(f"Daily indicator calculation failed for {symbol}: {e}")
            return {}

        # Cache result
        if result:
            self._momentum_cache[cache_key] = (candle_count, result)

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

    def _update_daily_high(self, symbol: str, high: float, date_str: str) -> None:
        """Track intraday high and roll over on day change."""
        prev_date = self._current_date.get(symbol)

        if prev_date and prev_date != date_str:
            # Day changed — push previous day's high to daily_highs deque
            prev_high = self._intraday_high.get(symbol, 0.0)
            if prev_high > 0:
                if symbol not in self._daily_highs:
                    self._daily_highs[symbol] = deque(maxlen=30)
                self._daily_highs[symbol].append(prev_high)
            # Reset intraday high for the new day
            self._intraday_high[symbol] = high
        else:
            # Same day — update intraday high
            self._intraday_high[symbol] = max(
                self._intraday_high.get(symbol, 0.0), high
            )

        self._current_date[symbol] = date_str

    def _update_daily_close(
        self, symbol: str, close: float, date_str: str
    ) -> None:
        """Track daily closes for daily-scale EMA trend filter.

        On day change, pushes the previous day's last close to the deque.
        Always updates the current intraday last close.
        """
        prev_date = self._current_date.get(symbol)

        if prev_date and prev_date != date_str:
            # Day changed — push previous day's close
            prev_close = self._intraday_last_close.get(symbol, 0.0)
            if prev_close > 0:
                if symbol not in self._daily_closes:
                    self._daily_closes[symbol] = deque(maxlen=60)
                self._daily_closes[symbol].append(prev_close)

        # Always update current intraday close (last seen)
        self._intraday_last_close[symbol] = close

    def _calc_daily_ema_aligned(self, symbol: str) -> bool:
        """Check if daily EMA(5) > EMA(10) > EMA(20) — multi-day uptrend.

        Uses daily close prices tracked by _update_daily_close().
        Includes today's last close for responsiveness.
        Returns False if insufficient daily data.
        """
        daily = self._daily_closes.get(symbol)
        if not daily:
            return False

        # Build closes: historical daily + today's running close
        closes = list(daily)
        today_close = self._intraday_last_close.get(symbol, 0.0)
        if today_close > 0:
            closes.append(today_close)

        max_period = max(self._daily_ema_periods)
        if len(closes) < max_period:
            return False

        # Compute EMA for each period
        ema_values: dict[int, float] = {}
        for period in self._daily_ema_periods:
            alpha = 2.0 / (period + 1)
            ema_val = closes[0]
            for price in closes[1:]:
                ema_val = alpha * price + (1 - alpha) * ema_val
            ema_values[period] = ema_val

        sorted_periods = sorted(self._daily_ema_periods)
        fast = ema_values[sorted_periods[0]]
        mid = ema_values[sorted_periods[1]]
        slow = ema_values[sorted_periods[2]]
        return slow > 0 and fast > mid > slow

    def _calc_high_n(self, symbol: str, candles: list[Candle]) -> float:
        """Highest high over the last N trading days (excluding today).

        Uses daily session highs tracked by _update_daily_high().
        Falls back to intraday candle high if insufficient daily history.
        """
        daily = self._daily_highs.get(symbol)
        if daily and len(daily) > 0:
            period = min(self._high_period, len(daily))
            return max(list(daily)[-period:])

        # Fallback: use intraday candle highs (e.g. during first day)
        period = min(self._high_period, len(candles))
        if period == 0:
            return 0.0
        return max(c.high for c in candles[-period:])

    @staticmethod
    def _ema_series(values: list[float], span: int) -> list[float]:
        """EMA series matching pandas ewm(span=span, adjust=False)."""
        alpha = 2.0 / (span + 1)
        result = [values[0]]
        for v in values[1:]:
            result.append(alpha * v + (1 - alpha) * result[-1])
        return result

    @staticmethod
    def _ema_last(values: list[float], span: int) -> float:
        """Last EMA value only (avoids list allocation)."""
        alpha = 2.0 / (span + 1)
        ema = values[0]
        for v in values[1:]:
            ema = alpha * v + (1 - alpha) * ema
        return ema

    @staticmethod
    def _calc_atr_raw(candles: list[Candle], period: int = 14) -> float:
        """Raw ATR value (non-normalized) for edge filters and stop-loss."""
        n = len(candles)
        if n < period + 1:
            return 0.0
        trs: list[float] = []
        for i in range(1, n):
            h, lo, pc = candles[i].high, candles[i].low, candles[i - 1].close
            trs.append(max(h - lo, abs(h - pc), abs(lo - pc)))
        return sum(trs[-period:]) / period

    @staticmethod
    def _calc_atr_normalized(candles: list[Candle], period: int = 14) -> float:
        """ATR / close (normalized, matching RLFeatureCalculator)."""
        n = len(candles)
        if n < period + 1:
            return 0.0
        trs: list[float] = []
        for i in range(1, n):
            h, lo, pc = candles[i].high, candles[i].low, candles[i - 1].close
            trs.append(max(h - lo, abs(h - pc), abs(lo - pc)))
        atr = sum(trs[-period:]) / period
        close = candles[-1].close
        return atr / (close + 1e-10)

    @staticmethod
    def _calc_stochastic(
        candles: list[Candle], period: int = 14, smooth: int = 3
    ) -> tuple[float, float]:
        """Stochastic K and D (matching RLFeatureCalculator)."""
        n = len(candles)
        if n < period:
            return 50.0, 50.0
        # Compute K for recent bars (enough for D smoothing)
        start = max(period - 1, n - smooth - 2)
        k_vals: list[float] = []
        for i in range(start, n):
            ws = i - period + 1
            low_min = min(candles[j].low for j in range(ws, i + 1))
            high_max = max(candles[j].high for j in range(ws, i + 1))
            denom = high_max - low_min
            k_vals.append(100 * (candles[i].close - low_min) / (denom + 1e-10))
        stoch_k = k_vals[-1]
        stoch_d = sum(k_vals[-smooth:]) / min(smooth, len(k_vals))
        return stoch_k, stoch_d

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

    @staticmethod
    def _calc_adx(candles: list[Candle], period: int = 14) -> float | None:
        """ADX (Average Directional Index) using Wilder smoothing.

        Returns None if insufficient data (need period*2 + 1 candles).
        """
        n = len(candles)
        if n < period + 1:
            return None

        # Compute True Range, +DM, -DM
        tr_list: list[float] = []
        plus_dm_list: list[float] = []
        minus_dm_list: list[float] = []

        for i in range(1, n):
            h = candles[i].high
            lo = candles[i].low
            pc = candles[i - 1].close
            ph = candles[i - 1].high
            pl = candles[i - 1].low

            tr = max(h - lo, abs(h - pc), abs(lo - pc))
            up_move = h - ph
            down_move = pl - lo

            plus_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
            minus_dm = down_move if (down_move > up_move and down_move > 0) else 0.0

            tr_list.append(tr)
            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)

        if len(tr_list) < period:
            return None

        # Wilder smoothing: first value = SMA, then EMA-like
        atr = sum(tr_list[:period]) / period
        plus_di_smooth = sum(plus_dm_list[:period]) / period
        minus_di_smooth = sum(minus_dm_list[:period]) / period

        dx_values: list[float] = []

        for i in range(period, len(tr_list)):
            atr = (atr * (period - 1) + tr_list[i]) / period
            plus_di_smooth = (plus_di_smooth * (period - 1) + plus_dm_list[i]) / period
            minus_di_smooth = (minus_di_smooth * (period - 1) + minus_dm_list[i]) / period

            if atr > 0:
                plus_di = 100 * plus_di_smooth / atr
                minus_di = 100 * minus_di_smooth / atr
            else:
                plus_di = 0.0
                minus_di = 0.0

            di_sum = plus_di + minus_di
            if di_sum > 0:
                dx_values.append(100 * abs(plus_di - minus_di) / di_sum)

        if len(dx_values) < period:
            # Not enough DX values; return simple average if we have any
            return sum(dx_values) / len(dx_values) if dx_values else None

        # ADX = Wilder-smoothed DX
        adx = sum(dx_values[:period]) / period
        for dx in dx_values[period:]:
            adx = (adx * (period - 1) + dx) / period

        return adx
