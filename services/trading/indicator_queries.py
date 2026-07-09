"""Read/query methods for StreamingIndicatorEngine."""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from functools import cache
from typing import Any

from shared.exceptions import ValidationError
from shared.indicators.engine.spec import flat_key

from .indicator_candles import Candle, MultiTimeframeCandleAccumulator

logger = logging.getLogger("services.trading.indicator_engine")

# Flat payload key names derived from the shared ``flat_key`` catalog
# (``shared/indicators/engine/spec.py``) — the single naming source of truth
# for both indicator-context paths (P2-b). These ARE the live payload contract
# consumed via StreamingIndicatorResolver; the exact strings are pinned by
# ``tests/unit/trading/test_indicator_payload_key_pins.py`` and the catalog by
# ``tests/unit/indicators/engine/test_flat_key_catalog_golden.py``.
# Runtime-only keys with no engine vocabulary (high_N, ema_aligned,
# ema_daily_aligned, volume_velocity/acceleration, the feature-bundle ratio
# keys) stay literal below.
_KEY_BB_LOWER = flat_key("bollinger", "lower")
_KEY_BB_MIDDLE = flat_key("bollinger", "middle")
_KEY_BB_UPPER = flat_key("bollinger", "upper")
_KEY_RSI = flat_key("rsi")
_KEY_MFI = flat_key("mfi")
_KEY_ADX = flat_key("adx")
_KEY_VWAP = flat_key("vwap")
_KEY_RVOL = flat_key("rvol")
_KEY_ATR = flat_key("atr")
_KEY_VOLUME_MA = flat_key("volume_ma")
_KEY_STOCH_K = flat_key("stochastic", "k")
_KEY_STOCH_D = flat_key("stochastic", "d")
_KEY_STOCHRSI_K = flat_key("stochrsi", "k")
_KEY_STOCHRSI_D = flat_key("stochrsi", "d")
_KEY_MACD = flat_key("macd")
_KEY_MACD_SIGNAL = flat_key("macd", "signal")
_KEY_MACD_HIST = flat_key("macd", "histogram")


@cache
def _ema_key(period: int) -> str:
    """Period-keyed EMA payload key (``ema_5`` / ``ema_20`` / ...).

    Memoized — called per symbol per bar on the hot path, over a small
    config-driven period set.
    """
    return flat_key("ema", params={"period": period})


class IndicatorQueryMixin:
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

        # Check cache: return cached result if no new candle has completed.
        # Use the monotonic counter, not len(acc.candles): once the deque is
        # full len() saturates at maxlen and the cache would never invalidate
        # (indicators freeze ~maxlen bars into the session / backtest).
        candle_count = acc.total_appended
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
            _KEY_BB_LOWER: bb_lower,
            _KEY_BB_MIDDLE: bb_middle,
            _KEY_BB_UPPER: bb_upper,
            _KEY_RSI: rsi,
        }

        # StochRSI producer (flat keys consumed by StochRSITrendEntry). Config-
        # gated (default off) so existing paths are byte-for-byte unchanged and
        # the per-candle DataFrame build is only paid when the strategy is
        # active. `closes` above is built from acc.candles (closed candles only)
        # so this is look-ahead safe (C1) — the in-progress buffer is never read.
        # latest_values() falls back to neutral 50 during warmup, and
        # stochrsi_k_prev is the previous bar's %K derived from the same closed
        # series (no Redis state needed at bar cadence). Import is lazy so the
        # numpy/pandas-free hot path stays import-free when StochRSI is disabled.
        if self._stochrsi_enabled and len(closes) >= self._stochrsi_min_bars:
            import pandas as pd

            from shared.indicators.reference import StochRSICalculator

            sr = StochRSICalculator(
                rsi_period=self._stochrsi_rsi_period,
                stoch_period=self._stochrsi_stoch_period,
                k_period=self._stochrsi_k_period,
                d_period=self._stochrsi_d_period,
            ).latest_values(pd.DataFrame({"close": closes}))
            result[_KEY_STOCHRSI_K] = sr["stochrsi_k"]
            result[_KEY_STOCHRSI_D] = sr["stochrsi_d"]
            result[f"{_KEY_STOCHRSI_K}_prev"] = sr["stochrsi_k_prev"]

        # MFI needs volume data; only compute if candles have volume
        mfi = self._calc_mfi(candles)
        if mfi is not None:
            result[_KEY_MFI] = mfi

        # ADX (Average Directional Index)
        adx = self._calc_adx(candles)
        if adx is not None:
            result[_KEY_ADX] = adx

        # Volume indicators
        current_close = closes[-1]

        # VWAP
        vwap_data = self._vwap_calc.calculate(symbol, current_close)
        result[_KEY_VWAP] = vwap_data.vwap

        # Volume velocity & acceleration
        vol_accel = self._vol_accel_calc.calculate(symbol)
        result["volume_velocity"] = vol_accel.velocity
        result["volume_acceleration"] = vol_accel.acceleration

        # RVOL (from candle volumes, inline — avoids numpy dependency)
        result[_KEY_RVOL] = self._calc_rvol(candles)

        # High over N previous trading days (for breakout detection)
        result[f"high_{self._high_period}"] = self._calc_high_n(symbol, candles)

        # Raw ATR (non-normalized) for edge filters and stop-loss calculations
        result[_KEY_ATR] = self._calc_atr_raw(candles)

        # Volume moving average (20-period SMA of candle volumes)
        volumes = [c.volume for c in candles]
        vol_window = min(self.bb_period, len(volumes))
        if vol_window > 0:
            result[_KEY_VOLUME_MA] = sum(volumes[-vol_window:]) / vol_window
        else:
            result[_KEY_VOLUME_MA] = 0.0

        # EMA absolute values for trend mode (configurable periods)
        n = len(closes)
        for period in self._ema_periods:
            key = _ema_key(period)
            if n >= period:
                result[key] = self._ema_last(closes, period)
            else:
                result[key] = 0.0
        # EMA alignment: fastest > middle > slowest (confirmed uptrend, intraday)
        if len(self._ema_periods) >= 3:
            sorted_periods = sorted(self._ema_periods)
            fast_key = _ema_key(sorted_periods[0])
            mid_key = _ema_key(sorted_periods[1])
            slow_key = _ema_key(sorted_periods[2])
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

    def get_recent_range(
        self, symbol: str, minutes: int = 15
    ) -> tuple[float, float] | None:
        """Return (high, low) over the last ``minutes`` completed 1-min candles.

        Used for Setup C's 15-minute breakout range. Returns ``None`` when the
        symbol has no candle history yet.
        """
        if minutes <= 0:
            return None
        acc = self._accumulators.get(symbol)
        if acc is None:
            return None
        candles = list(acc.candles)
        if not candles:
            return None
        window = candles[-minutes:]
        return (max(c.high for c in window), min(c.low for c in window))

    def get_last_price(self, symbol: str) -> float | None:
        """Return the freshest close price for *symbol*, or ``None`` if no data.

        Prefers the in-progress 1-min candle close (updated every tick via
        ``CandleAccumulator.latest_close``) so the strategy daemon sees the
        most recent price rather than the last *completed* minute's close.
        Falls back to the last completed candle's close when the in-progress
        candle is unavailable (should not happen after the first tick).

        Returns ``None`` for unknown symbols.
        """
        acc = self._accumulators.get(symbol)
        if acc is None:
            return None
        price = acc.latest_close
        if price is not None:
            return price
        # Fallback: last completed candle (e.g. right after seed_candles)
        if acc.candles:
            return acc.candles[-1].close
        return None

    def get_indicator_features(self, symbol: str) -> dict[str, float]:
        """Compute all 25 indicator features from stored candle history (pure Python).

        Uses O(n) pure-Python computation over the candle deque.

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
        result[_KEY_RSI] = self._calc_rsi(closes)

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
        result[_KEY_MACD] = macd_series[-1]
        result[_KEY_MACD_SIGNAL] = macd_sig[-1]
        result[_KEY_MACD_HIST] = macd_series[-1] - macd_sig[-1]

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

        # 22. atr — same flat key as the base payload but NORMALIZED by close
        # (deliberate semantic divergence; the resolver's feature_ prefix rule
        # keeps both reachable when a strategy requests ohlcv + base).
        result[_KEY_ATR] = self._calc_atr_normalized(candles)

        # 23-24. stochastic
        stoch_k, stoch_d = self._calc_stochastic(candles)
        result[_KEY_STOCH_K] = stoch_k
        result[_KEY_STOCH_D] = stoch_d

        # 25. price_change_5
        result["price_change_5"] = (
            (cur_close - closes[-6]) / closes[-6] if n >= 6 and closes[-6] != 0 else 0.0
        )

        return result

    def get_recent_candles(
        self, symbol: str, limit: int = 240
    ) -> list[dict[str, float]]:
        """Return recent completed candles for a symbol.

        Used by feature-heavy strategies that need OHLCV history.
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
        directly from Parquet via seed_daily_candles().
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

        Daily candles are loaded from Parquet (not aggregated from 1m).

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

    def mtf_total_appended(self, symbol: str, timeframe: int) -> int:
        """Monotonic count of CLOSED `timeframe`-min candles for `symbol`
        (0 if none / unknown). The decision-cadence gate watermarks on
        this — never on len(deque) (saturates at maxlen)."""
        mtf_map = self._mtf_accumulators.get(symbol)
        if not mtf_map:
            return 0
        acc = mtf_map.get(timeframe)
        return int(acc.total_appended) if acc is not None else 0

    def get_indicators_tf(self, symbol: str, timeframe: int) -> dict[str, float]:
        """Compute BB and RSI from closed multi-timeframe candles.

        Reads ONLY the closed candles in the MultiTimeframeCandleAccumulator
        (``mtf.candles``).  The in-progress ``_buffer`` is intentionally never
        touched — acting on an incomplete bar would introduce look-ahead bias.

        Args:
            symbol: Symbol to compute indicators for.
            timeframe: Timeframe in minutes (must have been passed via
                ``mtf_timeframes`` at construction time or fed via
                ``_feed_mtf_candle``).

        Returns:
            Dict with keys ``bb_lower``, ``bb_middle``, ``bb_upper``, ``rsi``.
            Returns ``{}`` if the accumulator is missing or has fewer closed
            candles than ``self.bb_period``.
        """
        mtf_map = self._mtf_accumulators.get(symbol)
        if mtf_map is None:
            return {}
        mtf = mtf_map.get(timeframe)
        if mtf is None or len(mtf.candles) < self.bb_period:
            return {}

        # Use the monotonic counter (not len) to invalidate after deque saturates.
        candle_count = mtf.total_appended
        cache_key = (symbol, timeframe)
        cached = self._mtf_base_cache.get(cache_key)
        if cached and cached[0] == candle_count:
            self._mtf_base_cache_hits += 1
            return cached[1].copy()

        self._mtf_base_cache_misses += 1

        # Compute from CLOSED candles only — never read mtf._buffer.
        closes = [c.close for c in mtf.candles]
        bb_lower, bb_middle, bb_upper = self._calc_bb(closes)
        rsi = self._calc_rsi(closes)

        result: dict[str, float] = {
            _KEY_BB_LOWER: bb_lower,
            _KEY_BB_MIDDLE: bb_middle,
            _KEY_BB_UPPER: bb_upper,
            _KEY_RSI: rsi,
        }

        self._mtf_base_cache[cache_key] = (candle_count, result.copy())
        return result

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

        # Warmup guard uses the live buffer size (need >= min_candles actual
        # candles to compute). Cache invalidation uses the monotonic counter
        # so it keeps invalidating after the deque saturates at maxlen.
        if len(mtf_acc.candles) < min_candles:
            return {}
        candle_count = mtf_acc.total_appended

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
        except (
            ValidationError,
            ValueError,
            KeyError,
            IndexError,
            ZeroDivisionError,
        ) as e:
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

        self._momentum_cache[cache_key] = (candle_count, result)
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
        the daily candles loaded from Parquet.

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

        if len(daily_deque) < min_candles:
            return {}
        candle_count = self._daily_total_appended.get(symbol, len(daily_deque))

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
        except (
            ValidationError,
            ValueError,
            KeyError,
            IndexError,
            ZeroDivisionError,
        ) as e:
            logger.error(f"Daily indicator calculation failed for {symbol}: {e}")
            return {}

        # Cache result
        if result:
            self._momentum_cache[cache_key] = (candle_count, result)

        return result

    def get_market_mfi_values(
        self, active_symbols: set[str] | None = None
    ) -> dict[str, float]:
        """Compute per-symbol MFI for warm symbols.

        Args:
            active_symbols: If provided, only include these symbols.
                Otherwise, all accumulators are used.

        Returns:
            Mapping of symbol to MFI. Symbols without enough candles or valid
            MFI are omitted.
        """
        values: dict[str, float] = {}
        for symbol, acc in self._accumulators.items():
            if active_symbols is not None and symbol not in active_symbols:
                continue
            if len(acc.candles) < 14:
                continue
            mfi = self._calc_mfi(list(acc.candles))
            if mfi is not None:
                values[symbol] = mfi

        return values

    def get_market_mfi(self, active_symbols: set[str] | None = None) -> float | None:
        """Compute aggregate MFI across warm symbols.

        Args:
            active_symbols: If provided, only include these symbols.
                Otherwise, all accumulators are used.

        Returns the median MFI of warm symbols, or None if insufficient data.
        """
        mfi_values = sorted(self.get_market_mfi_values(active_symbols).values())

        if not mfi_values:
            return None

        # Median is more robust than mean for market-wide MFI
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
