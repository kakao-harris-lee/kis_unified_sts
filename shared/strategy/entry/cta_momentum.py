"""CTA daily/swing time-series momentum entry (long/short symmetric).

Managed-futures (CTA) style **daily-bar** time-series momentum for KOSPI200
index futures. This is a *different timeframe* than the falsified intraday
trend-following: it holds across days in a confirmed multi-day trend regime.

Signal ensemble (both must agree on direction):
  * **TS-momentum** — sign of the roll-aware cumulative log-return over a
    lookback window (default 60 trading days). Long if the trailing return is
    positive beyond a dead-band, short if negative.
  * **MA-cross regime** — fast SMA vs slow SMA (default 20/100). Long only when
    fast > slow, short only when fast < slow. Filters chop where TS-momentum
    flickers around zero.

Roll-aware returns (the unadjusted-series caveat)
-------------------------------------------------
The ``krx_kospi200f_continuous`` series is RAW volume-weighted front-month,
**not** back-adjusted. At quarterly rolls (2nd Thursday of Mar/Jun/Sep/Dec) the
settlement level steps by the carry spread, which would inject a spurious
single-day return into the momentum lookback. We neutralise it: the per-day
log-return on a roll-transition day is **zeroed** before it enters the
cumulative momentum sum, and roll days are blocked as entry days. A roll gap can
therefore never masquerade as momentum.

Self-contained, causal
----------------------
Like the Setup adapters, this entry computes its signal strictly from a trailing
``close`` (and ``datetime``) series carried on the context — no look-ahead, no
dependency on a live daily indicator pack. ``required_indicators`` is empty so
the daily-cadence runtime footgun (``timeframe_minutes>1`` →
``mtf_base_*``/``momentum_*`` phantom requirements) does not apply.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator

logger = logging.getLogger(__name__)


def is_quarterly_roll_day(d: date) -> bool:
    """True if ``d`` is a KOSPI200 futures quarterly expiry/roll day.

    KOSPI200 futures expire on the **2nd Thursday** of Mar/Jun/Sep/Dec; the
    continuous front-month series steps to the next contract around then. We
    treat the expiry day itself as the roll-transition day whose return is
    neutralised (see module docstring).
    """
    if d.month not in (3, 6, 9, 12):
        return False
    # weekday(): Monday=0 .. Thursday=3. The 2nd Thursday is day-of-month 8..14.
    return d.weekday() == 3 and 8 <= d.day <= 14


def roll_aware_log_returns(closes: list[float], dates: list[date]) -> list[float]:
    """Per-step log-returns with roll-transition days zeroed.

    ``out[i]`` is ``log(closes[i] / closes[i-1])`` except that when ``dates[i]``
    is a quarterly roll day the return is forced to ``0.0`` (the carry-spread
    step is not momentum). ``out[0]`` is ``0.0`` by construction. Non-positive
    prices yield ``0.0`` for that step (defensive; real data is positive).
    """
    n = len(closes)
    out = [0.0] * n
    for i in range(1, n):
        if is_quarterly_roll_day(dates[i]):
            continue  # neutralise the roll carry step
        prev, cur = closes[i - 1], closes[i]
        if prev > 0.0 and cur > 0.0:
            out[i] = math.log(cur / prev)
    return out


def _sma(values: list[float], period: int) -> float | None:
    """Simple moving average of the last ``period`` values, or None if short."""
    if period <= 0 or len(values) < period:
        return None
    window = values[-period:]
    return sum(window) / float(period)


@dataclass
class CTAMomentumConfig(ConfigMixin):
    """CTA daily time-series momentum entry settings.

    All thresholds are config-driven (no magic numbers in code). Defaults are
    round operating points for a daily KOSPI200 index-futures CTA.
    """

    # TS-momentum lookback in trading days (the trend horizon).
    momentum_lookback: int = 60
    # Dead-band on cumulative log-return: |sum| must exceed this to signal.
    # Suppresses near-zero flicker. 0.0 = pure sign rule.
    momentum_deadband: float = 0.0

    # MA-cross regime filter (set use_ma_filter False to disable).
    use_ma_filter: bool = True
    ma_fast_period: int = 20
    ma_slow_period: int = 100

    # Direction toggle (futures are bidirectional; keep True for symmetry).
    allow_long: bool = True
    allow_short: bool = True

    # ATR (Wilder, daily) horizon used for the downstream trailing stop. The
    # entry computes ATR at entry and forwards it in metadata (``entry_atr``)
    # and derives the initial protective stop from it.
    atr_period: int = 20
    initial_stop_atr_mult: float = 3.0

    # Minimum daily bars before the entry will evaluate. Must cover the largest
    # of {momentum_lookback+1, ma_slow_period, atr_period+1}.
    min_bars: int = 120

    # Keys on context.market_data carrying the trailing daily series.
    close_series_key: str = "daily_closes"
    high_series_key: str = "daily_highs"
    low_series_key: str = "daily_lows"
    date_series_key: str = "daily_dates"

    # Optional LLM/regime market_state filter (off by default; paper-only).
    market_state_filter: dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": False,
            "allowed_states": [],
            "blocked_states": [],
        }
    )

    def validate(self) -> None:
        if self.momentum_lookback <= 0:
            raise ValueError("momentum_lookback must be positive")
        if self.momentum_deadband < 0:
            raise ValueError("momentum_deadband must be non-negative")
        if self.use_ma_filter and not (0 < self.ma_fast_period < self.ma_slow_period):
            raise ValueError("require 0 < ma_fast_period < ma_slow_period")
        if self.atr_period <= 0:
            raise ValueError("atr_period must be positive")
        if self.initial_stop_atr_mult <= 0:
            raise ValueError("initial_stop_atr_mult must be positive")
        if not (self.allow_long or self.allow_short):
            raise ValueError("at least one of allow_long/allow_short must be True")
        floor = max(
            self.momentum_lookback + 1, self.ma_slow_period, self.atr_period + 1
        )
        if self.min_bars < floor:
            raise ValueError(f"min_bars must be >= {floor}")


class CTAMomentumEntry(EntrySignalGenerator[CTAMomentumConfig]):
    """Daily TS-momentum + MA-cross entry, long/short symmetric, roll-aware."""

    CONFIG_CLASS = CTAMomentumConfig

    def __init__(self, config: CTAMomentumConfig):
        super().__init__(config)

    def _validate_config(self) -> None:
        self.config.validate()

    @property
    def name(self) -> str:
        return "cta_momentum"

    @property
    def required_indicators(self) -> list[str]:
        # Self-contained: reads raw daily OHLC series off the context, not an
        # indicator pack. Empty avoids the daily-cadence mtf_base footgun.
        return []

    # -- signal core (sync, pure) ------------------------------------------

    def evaluate_direction(self, closes: list[float], dates: list[date]) -> str | None:
        """Return 'long' | 'short' | None from the trailing close/date series.

        Pure and causal: consults only the supplied trailing series (the caller
        guarantees the last element is at-or-before the decision timestamp).
        """
        c = self.config
        if len(closes) < c.min_bars or len(dates) != len(closes):
            return None

        # Roll-aware cumulative log-return over the lookback window.
        rets = roll_aware_log_returns(closes, dates)
        mom = sum(rets[-c.momentum_lookback :])
        if abs(mom) <= c.momentum_deadband:
            return None
        ts_dir = "long" if mom > 0 else "short"

        # MA-cross regime confirmation.
        if c.use_ma_filter:
            fast = _sma(closes, c.ma_fast_period)
            slow = _sma(closes, c.ma_slow_period)
            if fast is None or slow is None:
                return None
            ma_dir = "long" if fast > slow else "short" if fast < slow else None
            if ma_dir is None or ma_dir != ts_dir:
                return None

        if ts_dir == "long" and not c.allow_long:
            return None
        if ts_dir == "short" and not c.allow_short:
            return None
        return ts_dir

    def wilder_atr(
        self, highs: list[float], lows: list[float], closes: list[float]
    ) -> float | None:
        """Wilder ATR over ``atr_period`` from trailing daily OHLC, or None."""
        period = self.config.atr_period
        n = len(closes)
        if n < period + 1 or len(highs) != n or len(lows) != n:
            return None
        trs: list[float] = []
        for i in range(1, n):
            hi, lo, prev_close = highs[i], lows[i], closes[i - 1]
            tr = max(hi - lo, abs(hi - prev_close), abs(lo - prev_close))
            trs.append(tr)
        # Wilder smoothing: seed with SMA of first `period` TRs, then recurse.
        atr = sum(trs[:period]) / float(period)
        for tr in trs[period:]:
            atr = (atr * (period - 1) + tr) / float(period)
        return atr

    # -- async entry interface ---------------------------------------------

    async def generate(self, context: EntryContext) -> Signal | None:
        data = context.market_data or {}
        c = self.config

        code = str(data.get("code", "") or "")
        if not code:
            return None
        if not self._market_state_allows(context, data, code):
            return None

        closes = _as_floats(data.get(c.close_series_key))
        dates = _as_dates(data.get(c.date_series_key))
        if closes is None or dates is None:
            return None

        # Block entry on a roll-transition day (the level step is not a trade).
        last_day = dates[-1]
        if is_quarterly_roll_day(last_day):
            return None

        direction = self.evaluate_direction(closes, dates)
        if direction is None:
            return None

        highs = _as_floats(data.get(c.high_series_key)) or closes
        lows = _as_floats(data.get(c.low_series_key)) or closes
        atr = self.wilder_atr(highs, lows, closes)
        if atr is None or atr <= 0:
            return None

        entry_price = float(data.get("close", 0) or closes[-1])
        if entry_price <= 0:
            return None

        stop_distance = c.initial_stop_atr_mult * atr
        if direction == "long":
            stop_loss = entry_price - stop_distance
        else:
            stop_loss = entry_price + stop_distance

        ts = context.timestamp or datetime.now(UTC)
        logger.info(
            "CTA %s signal %s close=%.2f atr=%.3f stop=%.2f mom_lb=%d",
            direction.upper(),
            code,
            entry_price,
            atr,
            stop_loss,
            c.momentum_lookback,
        )
        return Signal(
            code=code,
            name=str(data.get("name", "") or code),
            signal_type=SignalType.ENTRY,
            price=entry_price,
            timestamp=ts,
            strategy=self.name,
            confidence=0.6,
            metadata={
                "signal_direction": direction,
                "direction": direction,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "entry_atr": atr,
                "atr_period": c.atr_period,
            },
        )

    def _market_state_allows(
        self, context: EntryContext, data: dict[str, Any], code: str
    ) -> bool:
        cfg = self.config.market_state_filter or {}
        if not cfg.get("enabled", False):
            return True
        state = (context.metadata or {}).get("market_state") or data.get("market_state")
        if state is None:
            logger.debug("Market state missing for %s; skipping", code)
            return False
        state_name = str(state).upper()
        blocked = [s.upper() for s in cfg.get("blocked_states", [])]
        allowed = [s.upper() for s in cfg.get("allowed_states", [])]
        if blocked and state_name in blocked:
            return False
        return not (allowed and state_name not in allowed)


def _as_floats(value: Any) -> list[float] | None:
    """Coerce a sequence to list[float], or None if empty/None."""
    if value is None:
        return None
    try:
        out = [float(v) for v in value]
    except (TypeError, ValueError):
        return None
    return out or None


def _as_dates(value: Any) -> list[date] | None:
    """Coerce a sequence of date/datetime/ISO-string to list[date], or None."""
    if value is None:
        return None
    out: list[date] = []
    for v in value:
        if isinstance(v, datetime):
            out.append(v.date())
        elif isinstance(v, date):
            out.append(v)
        elif isinstance(v, str):
            try:
                out.append(datetime.fromisoformat(v).date())
            except ValueError:
                return None
        else:
            return None
    return out or None
