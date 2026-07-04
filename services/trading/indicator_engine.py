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
from datetime import UTC, datetime
from typing import Any

from services.trading.indicator_calculations import IndicatorCalculationMixin
from services.trading.indicator_candles import (
    Candle,
    CandleAccumulator,
    MultiTimeframeCandleAccumulator,
)
from services.trading.indicator_queries import IndicatorQueryMixin
from shared.indicators.volume import VolumeAccelerationCalculator, VWAPCalculator

logger = logging.getLogger(__name__)


class StreamingIndicatorEngine(IndicatorQueryMixin, IndicatorCalculationMixin):
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
        mtf_warmth_timeframe: int | None = None,
        stochrsi_enabled: bool = False,
        stochrsi_rsi_period: int = 14,
        stochrsi_stoch_period: int = 14,
        stochrsi_k_period: int = 3,
        stochrsi_d_period: int = 3,
    ):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self._candle_maxlen = candle_maxlen
        self._staleness_seconds = staleness_seconds
        self._accumulators: dict[str, CandleAccumulator] = {}
        self._warm_logged: set[str] = set()
        self._ema_periods: list[int] = ema_periods or [5, 20, 60]

        # StochRSI producer (config-gated, default OFF). Emits flat keys
        # stochrsi_k/stochrsi_d/stochrsi_k_prev in get_indicators() only when
        # enabled, so stock / Setup-A/C paths are unchanged and the per-candle
        # DataFrame build is only paid once a StochRSI strategy is activated.
        # min_bars = rsi_period + stoch_period (enough to fill the RSI warmup
        # AND one full stoch normalization window before values are non-neutral).
        self._stochrsi_enabled = stochrsi_enabled
        self._stochrsi_rsi_period = stochrsi_rsi_period
        self._stochrsi_stoch_period = stochrsi_stoch_period
        self._stochrsi_k_period = stochrsi_k_period
        self._stochrsi_d_period = stochrsi_d_period
        self._stochrsi_min_bars = stochrsi_rsi_period + stochrsi_stoch_period

        # Multi-timeframe accumulators: {symbol: {timeframe: accumulator}}
        # Separate 'daily' from numeric timeframes (5, 15, etc.)
        self._mtf_timeframes = mtf_timeframes or []
        self._numeric_mtf_timeframes: list[int] = [
            tf for tf in self._mtf_timeframes if isinstance(tf, int)
        ]
        self._has_daily = "daily" in self._mtf_timeframes
        # Timeframe (minutes) whose closed-candle depth gates is_warm(). Derived
        # from strategy requirements (IndicatorContract.warmth_timeframe), NOT from
        # the broad streaming.yaml accumulation set, so stock engines that only
        # need 1m are not blocked waiting on 15m bars. None => 1m-only warmth.
        self._mtf_warmth_timeframe = mtf_warmth_timeframe
        self._mtf_maxlen = mtf_maxlen
        self._mtf_accumulators: dict[
            str, dict[int, MultiTimeframeCandleAccumulator]
        ] = {}
        self._momentum_cache: dict[tuple[str, int], tuple[int, dict[str, Any]]] = {}
        # Cache for get_indicators_tf(): {(symbol, timeframe): (total_appended, indicators_dict)}
        self._mtf_base_cache: dict[tuple[str, int], tuple[int, dict[str, float]]] = {}

        # Daily candles (loaded from Parquet, not aggregated from 1m)
        # {symbol: deque[Candle]}
        self._daily_candles: dict[str, deque] = {}
        # Monotonic per-symbol count of daily candles ever appended. Same
        # cache-invalidation reason as CandleAccumulator.total_appended:
        # _daily_candles deques are maxlen=200 and len() saturates.
        self._daily_total_appended: dict[str, int] = {}

        # Cache for get_indicators(): {symbol: (candle_count, indicators_dict)}
        self._indicator_cache: dict[str, tuple[int, dict[str, float]]] = {}

        # Cache statistics tracking
        self._indicator_cache_hits: int = 0
        self._indicator_cache_misses: int = 0
        self._momentum_cache_hits: int = 0
        self._momentum_cache_misses: int = 0
        self._mtf_base_cache_hits: int = 0
        self._mtf_base_cache_misses: int = 0

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
        self._intraday_last_close: dict[str, float] = (
            {}
        )  # symbol -> current session last close
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
                # Redis-cached candles carry an HHMM "minute" field but no
                # "datetime"; honor it so MTF bucketing works for Redis seeds
                # instead of collapsing every candle into bucket 0.
                if candle_minute is None:
                    raw_minute = c.get("minute")
                    if raw_minute is not None:
                        candle_minute = int(raw_minute)
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
                acc.add_completed(candle)
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
                mtf_acc.add_completed(candle)
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
                self._daily_total_appended[symbol] = (
                    self._daily_total_appended.get(symbol, 0) + 1
                )
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
            key: value
            for key, value in self._momentum_cache.items()
            if key[0] != symbol
        }
        self._mtf_base_cache = {
            key: value
            for key, value in self._mtf_base_cache.items()
            if key[0] != symbol
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
        """Whether enough candles exist to compute indicators.

        For multi-timeframe strategies (e.g. bb_reversion_15m via
        ``mtf_base_15m``) the 1m accumulator filling first is not enough: the
        strategy's deepest timeframe must also hold ``bb_period`` closed
        candles, else ``get_indicators_tf`` returns ``{}`` and the strategy
        never signals. Reporting warm too early lets the orchestrator prewarm
        short-circuit (``if is_warm(symbol): continue``) and skip the deep
        Parquet load that seeds those higher-timeframe bars.

        The gate uses ``_mtf_warmth_timeframe`` — the deepest *strategy-required*
        intraday timeframe (``IndicatorContract.warmth_timeframe``) — NOT the
        broad streaming.yaml accumulation set. A stock engine that accumulates
        5m/15m for telemetry but whose strategy only needs 1m must not be blocked
        waiting on 15m bars (only ~8 closed from a 120-candle prewarm). When the
        warmth timeframe is unset (1m-only strategy) or not actually accumulated,
        only the 1m depth gates warmth. 'daily' is excluded by the contract — it
        is loaded from Parquet separately, never aggregated from the 1m feed.
        """
        acc = self._accumulators.get(symbol)
        if acc is None or len(acc.candles) < self.bb_period:
            return False
        # Warm unless a strategy-required (and actually accumulated) intraday
        # timeframe is still short of bb_period closed candles.
        warmth_tf = self._mtf_warmth_timeframe
        return not (
            warmth_tf is not None
            and warmth_tf in self._numeric_mtf_timeframes
            and self.mtf_total_appended(symbol, warmth_tf) < self.bb_period
        )

    def get_tick_age_seconds(
        self, symbol: str, now: datetime | None = None
    ) -> float | None:
        """Return seconds elapsed since last tick for symbol, or None if never seen."""
        acc = self._accumulators.get(symbol)
        if acc is None or acc.last_tick_ts is None:
            return None
        last_ts = acc.last_tick_ts
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=UTC)
        _now = now or datetime.now(UTC)
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
            - mtf_base_cache_hits: Number of cache hits for get_indicators_tf()
            - mtf_base_cache_misses: Number of cache misses for get_indicators_tf()
            - indicator_cache_size: Number of cached symbols
            - momentum_cache_size: Number of cached (symbol, timeframe) pairs
            - mtf_base_cache_size: Number of cached (symbol, timeframe) pairs
            - indicator_hit_rate: Percentage of cache hits (0-100)
            - momentum_hit_rate: Percentage of cache hits (0-100)
            - mtf_base_hit_rate: Percentage of cache hits (0-100)
        """
        indicator_total = self._indicator_cache_hits + self._indicator_cache_misses
        momentum_total = self._momentum_cache_hits + self._momentum_cache_misses
        mtf_base_total = self._mtf_base_cache_hits + self._mtf_base_cache_misses

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
        mtf_base_hit_rate = (
            (self._mtf_base_cache_hits / mtf_base_total * 100)
            if mtf_base_total > 0
            else 0.0
        )

        return {
            "indicator_cache_hits": self._indicator_cache_hits,
            "indicator_cache_misses": self._indicator_cache_misses,
            "momentum_cache_hits": self._momentum_cache_hits,
            "momentum_cache_misses": self._momentum_cache_misses,
            "mtf_base_cache_hits": self._mtf_base_cache_hits,
            "mtf_base_cache_misses": self._mtf_base_cache_misses,
            "indicator_cache_size": len(self._indicator_cache),
            "momentum_cache_size": len(self._momentum_cache),
            "mtf_base_cache_size": len(self._mtf_base_cache),
            "indicator_hit_rate": indicator_hit_rate,
            "momentum_hit_rate": momentum_hit_rate,
            "mtf_base_hit_rate": mtf_base_hit_rate,
        }

    # ------------------------------------------------------------------
    # Private computation methods
    # ------------------------------------------------------------------
