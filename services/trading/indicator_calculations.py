"""Pure indicator calculation helpers for StreamingIndicatorEngine."""

from __future__ import annotations

import math
from collections import deque

from .indicator_candles import Candle


class IndicatorCalculationMixin:
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
        """RSI using Wilder smoothing (alpha=1/period), matching the
        M1-certified shared RSICalculator (ewm adjust=False, first-delta seed).

        Converged from the previous rolling-SMA of gains/losses (which diverged
        ~13 RSI points from the batch/backtest path on the M2 parity sample) so
        the streaming oversold/overbought line matches the shared standard.
        """
        if len(closes) < self.rsi_period + 1:
            return 50.0
        period = self.rsi_period
        alpha = 1.0 / period
        one_minus = 1.0 - alpha
        # Seed on the first delta, then Wilder-EMA over the FULL series
        # (adjust=False semantics) — do NOT window to the last period+1 closes,
        # or the exponential warmup is lost and parity with RSICalculator breaks.
        avg_gain = 0.0
        avg_loss = 0.0
        seeded = False
        for i in range(1, len(closes)):
            delta = closes[i] - closes[i - 1]
            gain = delta if delta > 0.0 else 0.0
            loss = -delta if delta < 0.0 else 0.0
            if not seeded:
                avg_gain, avg_loss, seeded = gain, loss, True
            else:
                avg_gain = alpha * gain + one_minus * avg_gain
                avg_loss = alpha * loss + one_minus * avg_loss
        if avg_loss == 0.0:
            return 100.0 if avg_gain > 0.0 else 50.0
        rs = avg_gain / avg_loss
        return 100.0 - 100.0 / (1.0 + rs)

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

    def _update_daily_close(self, symbol: str, close: float, date_str: str) -> None:
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
        """ATR / close normalized by price."""
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
        """Stochastic K and D values."""
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
            minus_di_smooth = (
                minus_di_smooth * (period - 1) + minus_dm_list[i]
            ) / period

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
