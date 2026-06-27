"""MACD/EMA Crossover Entry Strategy (Trend-Following).

Bidirectional trend-follow:
- LONG  on MACD bullish crossover with EMA-fast > EMA-slow uptrend confirmation.
- SHORT on MACD bearish crossover with EMA-fast < EMA-slow downtrend confirmation.

Uses 15-minute MACD line/signal already produced by IndicatorEngine momentum DF.
EMA-fast/EMA-slow are computed inline from `close` to keep the entry self-contained.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.gates.adapter_helper import (
    acquire_infra_clients,
    apply_regime_gate,
)
from shared.strategy.gates.regime_gate import GateConfig
from shared.strategy.market_time import to_kst

_KST = ZoneInfo("Asia/Seoul")
logger = logging.getLogger(__name__)


@dataclass
class MACDEMACrossoverConfig(ConfigMixin):
    """MACD/EMA crossover entry settings."""

    # MACD (already computed by momentum indicator pack)
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # Trend EMAs (computed inline from close)
    ema_fast_period: int = 20
    ema_slow_period: int = 50

    # Timeframe selector for required indicators (e.g. 15 → momentum_15m)
    timeframe_minutes: int = 15

    # Histogram filter — require macd_oscillator strength above absolute floor
    use_hist_filter: bool = True
    hist_min_abs: float = 0.0  # default 0 = simple sign check

    # Volume confirmation
    volume_confirm: bool = False
    volume_ma_period: int = 20
    volume_threshold: float = 1.0

    # Direction toggle
    allow_short: bool = True

    # Time filters (KST)
    market_open_hour: int = 9
    market_open_minute: int = 0
    market_close_hour: int = 15
    market_close_minute: int = 45
    skip_market_open_minutes: int = 15
    skip_market_close_minutes: int = 30

    # Cooldown between signals per symbol
    signal_cooldown_seconds: int = 0

    # Risk hint for downstream sizing
    stop_loss_pct: float = 1.5

    # Confidence scaling — clamp [0,1] from histogram magnitude
    confidence_hist_scale: float = 200.0

    # Optional market_state filter (LLM regime, etc.)
    market_state_filter: dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": False,
            "allowed_states": [],
            "blocked_states": [],
        }
    )

    # Minimum bars in df before we evaluate (must cover ema_slow + macd_slow + buffer)
    min_candles: int = 60


class MACDEMACrossoverEntry(EntrySignalGenerator[MACDEMACrossoverConfig]):
    """Trend-following entry: MACD crossover gated by EMA-fast/slow regime."""

    CONFIG_CLASS = MACDEMACrossoverConfig

    def __init__(
        self,
        config: MACDEMACrossoverConfig,
        gate_cfg: GateConfig | None = None,
    ):
        super().__init__(config)
        self._last_signal_at: dict[str, datetime] = {}
        self._gate_cfg = gate_cfg

    def _validate_config(self) -> None:
        c = self.config
        assert c.macd_fast > 0 and c.macd_slow > c.macd_fast, "macd_fast/slow invalid"
        assert c.macd_signal > 0, "macd_signal must be positive"
        assert (
            c.ema_fast_period > 0 and c.ema_slow_period > c.ema_fast_period
        ), "ema_fast/slow invalid"
        assert c.timeframe_minutes > 0, "timeframe_minutes must be positive"
        assert c.confidence_hist_scale > 0, "confidence_hist_scale must be positive"
        assert c.min_candles > 0, "min_candles must be positive"

    @property
    def name(self) -> str:
        return "macd_ema_crossover"

    @property
    def _timeframe_token(self) -> str:
        """Match Timeframe.to_token(): 60m→'1h', 120m→'2h', else '{N}m'."""
        tf = self.config.timeframe_minutes
        if tf % 1440 == 0:
            return f"{tf // 1440}d"
        if tf % 60 == 0:
            return f"{tf // 60}h"
        return f"{tf}m"

    @property
    def _momentum_key(self) -> str:
        return f"momentum_{self._timeframe_token}"

    @property
    def required_indicators(self) -> list[str]:
        keys = [self._momentum_key]
        if self.config.timeframe_minutes > 1:
            keys.append(f"mtf_base_{self._timeframe_token}")
        return keys

    async def generate(self, context: EntryContext) -> Signal | None:
        data = context.market_data or {}
        indicators = context.indicators or {}

        code = str(data.get("code", "") or "")
        name = str(data.get("name", "") or "")
        if not code:
            return None

        now = context.timestamp
        if not self._within_trading_window(now):
            return None

        if self.config.signal_cooldown_seconds > 0:
            last = self._last_signal_at.get(code)
            if (
                last
                and (now - last).total_seconds() < self.config.signal_cooldown_seconds
            ):
                return None

        if not self._market_state_allows(context, indicators, data, code):
            return None

        momentum_key = self._momentum_key
        momentum = indicators.get(momentum_key) or data.get(momentum_key)
        if not isinstance(momentum, dict):
            return None
        df: pd.DataFrame | None = momentum.get("df")
        if df is None or len(df) < self.config.min_candles:
            return None

        required_cols = ("close", "macd_line", "macd_signal", "macd_oscillator")
        for col in required_cols:
            if col not in df.columns:
                logger.debug("Missing column %s for %s", col, code)
                return None

        direction = self._detect_signal(df)
        if direction is None:
            return None

        if not self._volume_ok(df):
            return None

        if not self._gate_allows(context, direction):
            return None

        close = float(data.get("close", 0) or df["close"].iloc[-1])
        confidence = self._calculate_confidence(df)
        macd_osc = float(df["macd_oscillator"].iloc[-1])

        logger.info(
            "MACD/EMA %s signal: %s close=%.2f macd_osc=%.4f confidence=%.2f",
            direction.upper(),
            code,
            close,
            macd_osc,
            confidence,
        )

        self._last_signal_at[code] = now
        return Signal(
            code=code,
            name=name,
            signal_type=SignalType.ENTRY,
            price=close,
            timestamp=context.timestamp,
            strategy=self.name,
            confidence=confidence,
            metadata={
                "signal_direction": direction,
                "stop_loss_pct": float(self.config.stop_loss_pct),
                "macd_line": float(df["macd_line"].iloc[-1]),
                "macd_signal": float(df["macd_signal"].iloc[-1]),
                "macd_oscillator": macd_osc,
            },
        )

    def _detect_signal(self, df: pd.DataFrame) -> str | None:
        """Return 'long' | 'short' | None based on MACD crossover + EMA regime."""
        if len(df) < 2:
            return None

        macd_now = float(df["macd_line"].iloc[-1])
        macd_prev = float(df["macd_line"].iloc[-2])
        sig_now = float(df["macd_signal"].iloc[-1])
        sig_prev = float(df["macd_signal"].iloc[-2])
        osc_now = float(df["macd_oscillator"].iloc[-1])

        bullish_cross = macd_now > sig_now and macd_prev <= sig_prev
        bearish_cross = macd_now < sig_now and macd_prev >= sig_prev

        if not (bullish_cross or bearish_cross):
            return None

        if self.config.use_hist_filter and abs(osc_now) < self.config.hist_min_abs:
            return None

        # EMA regime filter
        close_series = df["close"]
        ema_fast = close_series.ewm(
            span=self.config.ema_fast_period, adjust=False
        ).mean()
        ema_slow = close_series.ewm(
            span=self.config.ema_slow_period, adjust=False
        ).mean()
        close_now = float(close_series.iloc[-1])
        ema_fast_now = float(ema_fast.iloc[-1])
        ema_slow_now = float(ema_slow.iloc[-1])

        if bullish_cross and ema_fast_now > ema_slow_now and close_now > ema_slow_now:
            return "long"
        if (
            bearish_cross
            and self.config.allow_short
            and ema_fast_now < ema_slow_now
            and close_now < ema_slow_now
        ):
            return "short"
        return None

    def _volume_ok(self, df: pd.DataFrame) -> bool:
        if not self.config.volume_confirm:
            return True
        if "volume" not in df.columns:
            return True
        period = self.config.volume_ma_period
        if len(df) < period + 1:
            return False
        vol = float(df["volume"].iloc[-1])
        vol_ma = float(df["volume"].rolling(period).mean().iloc[-1])
        if vol_ma <= 0:
            return False
        return vol >= self.config.volume_threshold * vol_ma

    def _market_state_allows(
        self,
        context: EntryContext,
        indicators: dict[str, Any],
        data: dict[str, Any],
        code: str,
    ) -> bool:
        cfg = self.config.market_state_filter or {}
        if not cfg.get("enabled", False):
            return True
        state = (
            context.metadata.get("market_state")
            or indicators.get("market_state")
            or data.get("market_state")
        )
        if state is None:
            logger.debug("Market state missing for %s; skipping", code)
            return False
        state_name = str(state).upper()
        blocked = [s.upper() for s in cfg.get("blocked_states", [])]
        allowed = [s.upper() for s in cfg.get("allowed_states", [])]
        if blocked and state_name in blocked:
            return False
        return not (allowed and state_name not in allowed)

    def _gate_allows(self, context: EntryContext, direction: str) -> bool:
        if self._gate_cfg is None:
            return True
        redis_client, event_reader = acquire_infra_clients()
        if redis_client is None:
            return True  # PERMISSIVE on missing infra
        stand_in = type("X", (), {"metadata": {"signal_direction": direction}})()
        blocked = apply_regime_gate(
            gate_cfg=self._gate_cfg,
            decision_signal=stand_in,
            context=context,
            strategy_name=self.name,
            redis=redis_client,
            event_reader=event_reader,
        )
        return not blocked

    def _within_trading_window(self, now: datetime) -> bool:
        now_kst = to_kst(now)
        open_dt = datetime.combine(
            now_kst.date(),
            time(self.config.market_open_hour, self.config.market_open_minute),
            tzinfo=_KST,
        )
        close_dt = datetime.combine(
            now_kst.date(),
            time(self.config.market_close_hour, self.config.market_close_minute),
            tzinfo=_KST,
        )
        if now_kst < open_dt or now_kst >= close_dt:
            return False
        if self.config.skip_market_open_minutes > 0:
            if now_kst < open_dt + timedelta(
                minutes=self.config.skip_market_open_minutes
            ):
                return False
        if self.config.skip_market_close_minutes > 0:
            if now_kst >= close_dt - timedelta(
                minutes=self.config.skip_market_close_minutes
            ):
                return False
        return True

    def _calculate_confidence(self, df: pd.DataFrame) -> float:
        osc = abs(float(df["macd_oscillator"].iloc[-1]))
        raw = osc * self.config.confidence_hist_scale
        return max(0.3, min(1.0, raw))
