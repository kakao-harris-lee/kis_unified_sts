"""Opening-Range Breakout trend-day entry (futures).

Captures the rare *strong intraday trend* day that mean-reversion setups
(Setup A gap-reversion, Setup C event-reaction) structurally miss, while staying
flat on the many chop days that bankrupted prior naive trend strategies
(macd_ema, williams_r-as-trend, momentum).

The crux is the GATE, not the breakout. A bar may only fire an entry when ALL of:

1. The opening range (first ``opening_range_minutes`` of the session) has formed and
   we are inside the entry window (after the range, before ``no_entry_after_minutes``).
2. Vol-expansion: the opening-range height is a real ATR-scaled move and the session
   is not comatose (``min_or_atr_mult``, ``min_atr_norm``).
3. Trend-efficiency: the Kaufman efficiency ratio over the recent window clears
   ``min_efficiency`` — the single most direct "is today actually trending?" filter.
   This is what rejects chop days regardless of price level.
4. A decisive break of the opening range (buffer in ATR units).
5. Direction agreement: MFI regime (do not fade money flow), MACD slope, and an
   optional daily-bias hook all agree with the break direction.

Long/short symmetric (futures bidirectional). Config-driven, KST-native. The
opening-range anchor is derived from the first bar of each session so it adapts to
the actual futures open (08:45 KST) rather than a hardcoded clock.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.market_time import to_kst

logger = logging.getLogger(__name__)


@dataclass
class _DayState:
    """Per-session opening-range + entry bookkeeping (one trading day)."""

    trading_day: date
    session_open: datetime  # KST timestamp of the day's first observed bar
    or_high: float = 0.0
    or_low: float = float("inf")
    or_locked: bool = False
    entered_long: bool = False
    entered_short: bool = False


@dataclass
class OpeningRangeBreakoutTrendConfig(ConfigMixin):
    """Configuration for the ORB trend-day entry."""

    # Decision cadence — N-minute closed bars (1 = every bar). Futures intraday
    # trend reads cleaner on 5m bars; the adapter's DecisionCadenceGate enforces it.
    timeframe_minutes: int = 5

    # Opening-range window, measured from the session open (KST).
    opening_range_minutes: int = 30
    # No new entries after this many minutes since the session open (runway guard).
    no_entry_after_minutes: int = 300  # ~14:00 KST for an 08:45 open + buffer

    # Vol-expansion gate.
    min_or_atr_mult: float = 0.8  # opening-range height >= this * ATR
    min_atr_norm: float = 0.0008  # ATR/price floor (session must be alive)

    # Trend-efficiency gate (Kaufman efficiency ratio over recent closes).
    efficiency_window: int = 12  # number of decision bars (~60 min on 5m)
    min_efficiency: float = 0.35

    # Decisive-break buffer in ATR units beyond the opening-range edge.
    breakout_buffer_atr_mult: float = 0.25

    # Direction-agreement gates.
    use_mfi_gate: bool = True
    long_blocked_states: list[str] = field(
        default_factory=lambda: ["BEAR_STRONG", "BEAR_MODERATE"]
    )
    short_blocked_states: list[str] = field(
        default_factory=lambda: ["BULL_STRONG", "BULL_MODERATE"]
    )
    use_macd_slope_gate: bool = True
    # Optional daily-bias hook (Redis trading:futures:daily_bias). Permissive when
    # the bias is null/flat so the strategy is usable while the LLM bias is absent.
    daily_bias_filter_enabled: bool = False

    # Session open (KST) used only as a fallback / sanity reference. The actual
    # anchor is the first observed bar of each day, so this need not be exact.
    market_open_hour: int = 8
    market_open_minute: int = 45

    # Risk parameters embedded in the entry signal for the exit/sizer to consume.
    stop_atr_mult: float = 1.5

    # Long/short symmetry. Set False to force long-only (e.g. directional regime test).
    allow_long: bool = True
    allow_short: bool = True

    def validate(self) -> None:
        assert self.opening_range_minutes > 0, "opening_range_minutes must be positive"
        assert (
            self.no_entry_after_minutes > self.opening_range_minutes
        ), "no_entry_after_minutes must be after the opening range"
        assert self.min_or_atr_mult >= 0, "min_or_atr_mult must be >= 0"
        assert self.efficiency_window >= 2, "efficiency_window must be >= 2"
        assert 0.0 <= self.min_efficiency <= 1.0, "min_efficiency must be in [0, 1]"
        assert (
            self.breakout_buffer_atr_mult >= 0
        ), "breakout_buffer_atr_mult must be >= 0"
        assert self.stop_atr_mult > 0, "stop_atr_mult must be positive"
        assert self.allow_long or self.allow_short, "at least one side must be allowed"


class OpeningRangeBreakoutTrendEntry(
    EntrySignalGenerator[OpeningRangeBreakoutTrendConfig]
):
    """Regime/efficiency-gated opening-range breakout (long/short symmetric)."""

    CONFIG_CLASS = OpeningRangeBreakoutTrendConfig

    def __init__(self, config: OpeningRangeBreakoutTrendConfig):
        super().__init__(config)
        # Per-symbol day state and rolling closes for the efficiency ratio.
        self._day: dict[str, _DayState] = {}
        self._closes: dict[str, list[float]] = {}

    def _validate_config(self) -> None:
        self.config.validate()

    @property
    def name(self) -> str:
        return "orb_trend_day"

    @property
    def required_indicators(self) -> list[str]:
        # `atr` (base raw ATR) + the feature bundle (macd_hist, normalized atr) are
        # provided once the engine is warm; `mfi` drives the market_state gate.
        keys = ["atr", "macd_hist"]
        if self.config.use_mfi_gate:
            keys.append("mfi")
        # Declaring an MTF base timeframe makes the engine build the N-min bucket so
        # the DecisionCadenceGate fires on closed N-min bars (parity with williams_r).
        # Without this the cadence gate never sees a closed bucket and the strategy
        # is silently never evaluated (timeframe_minutes > 1).
        tf = self.config.timeframe_minutes
        if tf > 1:
            keys.append(f"mtf_base_{tf}m")
        return keys

    # ---- helpers -------------------------------------------------------------

    @staticmethod
    def _efficiency_ratio(closes: list[float], window: int) -> float:
        """Kaufman efficiency ratio over the last ``window`` closes.

        ER = |close_t - close_{t-window}| / sum(|close_i - close_{i-1}|).
        1.0 = perfectly directional, 0.0 = pure chop. Returns 0.0 when the path
        length is degenerate (no movement) so a dead-flat window cannot pass.
        """
        if len(closes) < window + 1:
            return 0.0
        segment = closes[-(window + 1) :]
        net = abs(segment[-1] - segment[0])
        path = sum(abs(segment[i] - segment[i - 1]) for i in range(1, len(segment)))
        if path <= 0:
            return 0.0
        return net / path

    def _get_day_state(self, code: str, ts_kst: datetime) -> _DayState:
        """Return the per-day state, resetting on a new trading day."""
        trading_day = ts_kst.date()
        state = self._day.get(code)
        if state is None or state.trading_day != trading_day:
            state = _DayState(trading_day=trading_day, session_open=ts_kst)
            self._day[code] = state
            self._closes[code] = []
        return state

    @staticmethod
    def _atr_points(indicators: dict[str, Any], close: float) -> float:
        """Resolve ATR in price points.

        The base engine exposes raw ATR under `atr`; the feature bundle's
        close-normalized ATR is stored as `feature_atr` by the resolver on key
        collision. Prefer raw points; fall back to normalized * price.
        """
        raw = indicators.get("atr")
        if raw is not None:
            atr = float(raw)
            # Heuristic: a value < 0.5 on an index ~hundreds of points is a
            # normalized ratio, not points — scale it back.
            if atr > 0 and atr < 0.5 and close > 0:
                return atr * close
            if atr > 0:
                return atr
        norm = indicators.get("feature_atr")
        if norm is not None and close > 0:
            return float(norm) * close
        return 0.0

    # ---- main ----------------------------------------------------------------

    async def generate(self, context: EntryContext) -> Signal | None:
        data = context.market_data or {}
        indicators = context.indicators or {}

        code = str(data.get("code", "") or "")
        name = str(data.get("name", "") or code)
        close = float(indicators.get("close", data.get("close", 0)) or 0)
        high = float(data.get("high", close) or close)
        low = float(data.get("low", close) or close)
        if not code or close <= 0:
            return None

        now = context.timestamp
        ts_kst = to_kst(now)

        state = self._get_day_state(code, ts_kst)

        # Track rolling closes for the efficiency ratio (cap memory).
        closes = self._closes.setdefault(code, [])
        closes.append(close)
        if len(closes) > self.config.efficiency_window + 5:
            del closes[: -(self.config.efficiency_window + 5)]

        minutes_since_open = (ts_kst - state.session_open).total_seconds() / 60.0

        # --- Opening-range construction (incremental, no look-ahead) ---
        if minutes_since_open < self.config.opening_range_minutes:
            state.or_high = max(state.or_high, high)
            state.or_low = min(state.or_low, low)
            return None  # still forming the range
        if not state.or_locked:
            state.or_locked = True

        # --- Session-time window gate ---
        if minutes_since_open > self.config.no_entry_after_minutes:
            return None
        if state.or_high <= 0 or state.or_low == float("inf"):
            return None

        atr = self._atr_points(indicators, close)
        if atr <= 0:
            return None

        # --- Vol-expansion gate ---
        if close > 0 and (atr / close) < self.config.min_atr_norm:
            return None
        or_height = state.or_high - state.or_low
        if or_height < self.config.min_or_atr_mult * atr:
            return None

        # --- Trend-efficiency gate (the crux) ---
        er = self._efficiency_ratio(closes, self.config.efficiency_window)
        if er < self.config.min_efficiency:
            return None

        # --- Decisive break + direction ---
        buffer = self.config.breakout_buffer_atr_mult * atr
        long_break = close > state.or_high + buffer
        short_break = close < state.or_low - buffer

        direction: str | None = None
        if long_break and self.config.allow_long and not state.entered_long:
            direction = "long"
        elif short_break and self.config.allow_short and not state.entered_short:
            direction = "short"
        if direction is None:
            return None

        # --- Direction-agreement gates ---
        if self.config.use_mfi_gate:
            market_state = str(context.metadata.get("market_state", "UNKNOWN"))
            blocked = (
                self.config.long_blocked_states
                if direction == "long"
                else self.config.short_blocked_states
            )
            if market_state in blocked:
                return None

        if self.config.use_macd_slope_gate:
            macd_hist = indicators.get("macd_hist")
            if macd_hist is not None:
                mh = float(macd_hist)
                if direction == "long" and mh <= 0:
                    return None
                if direction == "short" and mh >= 0:
                    return None

        if self.config.daily_bias_filter_enabled:
            bias = self._daily_bias(context)
            if bias in ("long", "short") and bias != direction:
                return None

        # --- Build signal ---
        if direction == "long":
            state.entered_long = True
            stop = close - self.config.stop_atr_mult * atr
        else:
            state.entered_short = True
            stop = close + self.config.stop_atr_mult * atr

        # Confidence scales with efficiency and break decisiveness.
        edge = state.or_high if direction == "long" else state.or_low
        decisiveness = abs(close - edge) / atr if atr > 0 else 0.0
        confidence = max(0.1, min(1.0, 0.4 + 0.4 * er + 0.1 * min(decisiveness, 2.0)))

        logger.info(
            "[orb_trend_day] %s %s break: close=%.2f OR=[%.2f,%.2f] ATR=%.2f "
            "ER=%.2f conf=%.2f",
            code,
            direction,
            close,
            state.or_low,
            state.or_high,
            atr,
            er,
            confidence,
        )

        return Signal(
            code=code,
            name=name,
            signal_type=SignalType.ENTRY,
            price=close,
            timestamp=now,
            strategy=self.name,
            confidence=confidence,
            metadata={
                "signal_direction": direction,
                "setup_type": "orb_trend_day",
                "stop_loss": stop,
                "entry_atr": atr,
                "efficiency_ratio": er,
                "opening_range_high": state.or_high,
                "opening_range_low": state.or_low,
                # Exit-strategy hint: ATR-multiple stop (consumed by TrendTrailExit).
                "exit_stop_atr_multiplier": self.config.stop_atr_mult,
            },
        )

    def _daily_bias(self, context: EntryContext) -> str:
        """Optional daily directional bias.

        Reads ``context.metadata['daily_bias']`` if present (the orchestrator
        injects it); returns "flat" otherwise. Kept dependency-free so the entry
        stays hermetic and usable while the LLM bias is null.
        """
        bias = context.metadata.get("daily_bias")
        if bias in ("long", "short", "flat"):
            return str(bias)
        return "flat"
