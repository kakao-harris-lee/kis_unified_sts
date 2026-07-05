"""Runtime indicator accessors for StreamingIndicatorEngine.

The RSI / Bollinger / MFI / ADX / Stochastic / RVOL math no longer lives here —
it was retired into the engine's :class:`StreamingCompatBackend`
(``shared/indicators/engine/streaming_backend.py``) so the platform has one place
that computes each indicator. These ``_calc_*`` methods are now thin,
value-preserving delegates to :func:`streaming_indicator_engine` (the runtime's
convention set), keeping their exact signatures + None/sentinel contracts so every
call site (``indicator_queries``) is unchanged. Bit-identity to the previous
inline math is pinned by ``test_streaming_backend_golden.py``.

The daily-EMA / high-N / ATR accessors below remain here: ATR already delegates to
the canonical ``reference.ATRCalculator``; the daily trackers are stateful session
aggregators, not window indicators.
"""

from __future__ import annotations

from collections import deque

from shared.indicators.engine import (
    IndicatorSpec,
    OHLCVWindow,
    streaming_indicator_engine,
    window_from_bars,
)
from shared.indicators.reference import ATRCalculator

from .indicator_candles import Candle


def _close_window(closes: list[float]) -> OHLCVWindow:
    """A close-only OHLCV window for close-based indicators (rsi / bollinger)."""
    return OHLCVWindow.from_sequences(
        open=closes, high=closes, low=closes, close=closes, volume=[0.0] * len(closes)
    )


class IndicatorCalculationMixin:
    def _calc_bb(self, closes: list[float]) -> tuple[float, float, float]:
        """Bollinger Bands (sample std, ddof=1) via the streaming-compat engine."""
        flat = (
            streaming_indicator_engine()
            .compute(
                IndicatorSpec.create(
                    "bollinger", {"period": self.bb_period, "std": self.bb_std}
                ),
                _close_window(closes),
            )
            .flat_latest()
        )
        return flat["bb_lower"], flat["bb_middle"], flat["bb_upper"]

    def _calc_rsi(self, closes: list[float]) -> float:
        """Wilder RSI (first-delta seed) via the streaming-compat engine.

        Returns the neutral 50.0 sentinel on insufficient/flat windows (contract
        preserved by the backend).
        """
        flat = (
            streaming_indicator_engine()
            .compute(
                IndicatorSpec.create("rsi", {"period": self.rsi_period}),
                _close_window(closes),
            )
            .flat_latest()
        )
        return flat.get("rsi", 50.0)

    def _calc_rvol(self, candles: list[Candle]) -> float:
        """RVOL = short-window avg / long-window avg volume, via the engine."""
        if not candles:
            return 1.0
        flat = (
            streaming_indicator_engine()
            .compute(
                IndicatorSpec.create(
                    "rvol",
                    {"short_window": self._rvol_short, "long_window": self._rvol_long},
                ),
                window_from_bars(candles),
            )
            .flat_latest()
        )
        return flat.get("rvol", 1.0)

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

    def _update_daily_close(self, symbol: str, close: float, date_str: str) -> None:
        """Track daily closes for daily-scale EMA trend filter.

        On day change, pushes the previous day's last close to the deque.
        Always updates the current intraday last close.

        Uses its own ``_current_close_date`` sentinel rather than the shared
        ``_current_date`` that ``_update_daily_high`` owns and advances first:
        sharing it made this method's day-change branch unreachable, so daily
        closes never accumulated and ``_calc_daily_ema_aligned`` was stuck
        ``False`` on the live streaming path. The independent sentinel makes
        close tracking order-independent (mirrors the backtest adapter's
        per-tracker date).
        """
        prev_date = self._current_close_date.get(symbol)

        if prev_date and prev_date != date_str:
            # Day changed — push previous day's close
            prev_close = self._intraday_last_close.get(symbol, 0.0)
            if prev_close > 0:
                if symbol not in self._daily_closes:
                    self._daily_closes[symbol] = deque(maxlen=60)
                self._daily_closes[symbol].append(prev_close)

        # Always update current intraday close (last seen) and advance sentinel
        self._intraday_last_close[symbol] = close
        self._current_close_date[symbol] = date_str

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
        """Raw ATR value (non-normalized) for edge filters and stop-loss.

        Delegates to the canonical ``reference.ATRCalculator`` (``mode="sma"`` --
        the standalone-ATR convention every consumer already used). Value-identical
        to the previous inline ``sum(trs[-period:]) / period``; the insufficient-data
        ``None`` maps back to this function's historical ``0.0`` contract.
        """
        if len(candles) < period + 1:
            return 0.0
        atr = ATRCalculator(period=period, mode="sma").atr_last(
            [c.high for c in candles],
            [c.low for c in candles],
            [c.close for c in candles],
        )
        return float(atr) if atr is not None else 0.0

    @staticmethod
    def _calc_atr_normalized(candles: list[Candle], period: int = 14) -> float:
        """ATR / close normalized by price (reuses _calc_atr_raw)."""
        if len(candles) < period + 1:
            return 0.0
        atr = IndicatorCalculationMixin._calc_atr_raw(candles, period)
        return atr / (candles[-1].close + 1e-10)

    @staticmethod
    def _calc_stochastic(
        candles: list[Candle], period: int = 14, smooth: int = 3
    ) -> tuple[float, float]:
        """Fast %K / %D (streaming convention) via the streaming-compat engine."""
        if not candles:
            return 50.0, 50.0
        flat = (
            streaming_indicator_engine()
            .compute(
                IndicatorSpec.create(
                    "stochastic", {"k_period": period, "d_period": smooth}
                ),
                window_from_bars(candles),
            )
            .flat_latest()
        )
        return flat["stoch_k"], flat["stoch_d"]

    def _calc_mfi(self, candles: list[Candle], period: int = 14) -> float | None:
        """Money Flow Index via the streaming-compat engine (None if insufficient)."""
        if not candles:
            return None
        flat = (
            streaming_indicator_engine()
            .compute(
                IndicatorSpec.create("mfi", {"period": period}),
                window_from_bars(candles),
            )
            .flat_latest()
        )
        return flat.get("mfi")

    @staticmethod
    def _calc_adx(candles: list[Candle], period: int = 14) -> float | None:
        """Wilder ADX (lenient warmup) via the streaming-compat engine (None if
        insufficient)."""
        if not candles:
            return None
        flat = (
            streaming_indicator_engine()
            .compute(
                IndicatorSpec.create("adx", {"period": period}),
                window_from_bars(candles),
            )
            .flat_latest()
        )
        return flat.get("adx")
