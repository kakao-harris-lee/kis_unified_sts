"""Runtime indicator accessors for StreamingIndicatorEngine.

The RSI / Bollinger / MFI / ADX / Stochastic / RVOL math no longer lives here —
it was retired into the engine's :class:`StreamingCompatBackend`
(``shared/indicators/engine/streaming_backend.py``) so the platform has one place
that computes each indicator. These ``_calc_*`` methods are thin delegates to
:func:`runtime_indicator_engine`, keeping their exact signatures + None/sentinel
contracts so every call site (``indicator_queries``) is unchanged.

:func:`runtime_indicator_engine` is the Phase C convention gate: by default it
returns :func:`streaming_indicator_engine` (historical live values, bit-identity
pinned by ``test_streaming_backend_golden.py``); with
``STS_INDICATOR_CONVENTION=talib`` it returns :func:`default_engine` (TA-Lib
standard, converged with the no-code builder). The flag is off by default so live
values are unchanged until the data-server backtest gate
(``docs/runbooks/streaming-talib-convergence-gate.md``) passes.

The daily-EMA / high-N / ATR accessors below remain here as thin shells: ATR
delegates to the canonical ``reference.ATRCalculator``; the EMA math
(``_ema_series`` / ``_ema_last`` / ``_calc_daily_ema_aligned``) and the
trailing-max math (``_calc_high_n``) delegate to ``shared.indicators.series``
(P1-b item 3; ``series.ema`` is empirically bit-identical to the manual
``alpha = 2/(span+1)`` loop these methods carried — pinned by
``tests/unit/trading/test_p1b3_trading_residuals_golden.py``). Only the
stateful session aggregation (day rollover of highs/closes) stays here.
"""

from __future__ import annotations

from collections import deque

import pandas as pd

from shared.indicators.engine import (
    IndicatorSpec,
    OHLCVWindow,
    runtime_indicator_engine,
    window_from_bars,
)
from shared.indicators.reference import ATRCalculator
from shared.indicators.series import ema as series_ema
from shared.indicators.series import trailing_max

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
            runtime_indicator_engine()
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
        if not closes:  # legacy _calc_rsi([]) -> 50.0 (len < period+1 branch)
            return 50.0
        flat = (
            runtime_indicator_engine()
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
            runtime_indicator_engine()
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

        EMA math delegates to ``series.ema`` (bit-identical to the manual
        loop this method carried); only the session-close assembly and the
        alignment gate stay here.
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

        closes_series = pd.Series(closes)
        ema_values: dict[int, float] = {
            period: float(series_ema(closes_series, period).iloc[-1])
            for period in self._daily_ema_periods
        }

        sorted_periods = sorted(self._daily_ema_periods)
        fast = ema_values[sorted_periods[0]]
        mid = ema_values[sorted_periods[1]]
        slow = ema_values[sorted_periods[2]]
        return slow > 0 and fast > mid > slow

    def _calc_high_n(self, symbol: str, candles: list[Candle]) -> float:
        """Highest high over the last N trading days (excluding today).

        Uses daily session highs tracked by _update_daily_high().
        Falls back to intraday candle high if insufficient daily history.
        Window max delegates to ``series.trailing_max``.
        """
        daily = self._daily_highs.get(symbol)
        if daily and len(daily) > 0:
            value = trailing_max(list(daily), self._high_period)
            return float(value) if value is not None else 0.0

        # Fallback: use intraday candle highs (e.g. during first day)
        value = trailing_max([c.high for c in candles], self._high_period)
        return float(value) if value is not None else 0.0

    @staticmethod
    def _ema_series(values: list[float], span: int) -> list[float]:
        """EMA series (``series.ema``, i.e. pandas ewm(span=span, adjust=False))."""
        return series_ema(pd.Series(values), span).tolist()

    @staticmethod
    def _ema_last(values: list[float], span: int) -> float:
        """Last EMA value only (``series.ema`` tail)."""
        return float(series_ema(pd.Series(values), span).iloc[-1])

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
            runtime_indicator_engine()
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
            runtime_indicator_engine()
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
            runtime_indicator_engine()
            .compute(
                IndicatorSpec.create("adx", {"period": period}),
                window_from_bars(candles),
            )
            .flat_latest()
        )
        return flat.get("adx")
