"""TRIX Golden Signal Entry Strategy.

5분봉 기준 TRIX 지표를 핵심으로 CCI, MACD, Stochastic을 결합한
'황금신호' 포착 진입 전략.

Entry Conditions (ALL must be true simultaneously):
    1. TRIX Golden Cross: TRIX > TRIX_SIGNAL (was <= previously)
    2. MACD Oscillator > 0: Positive momentum
    3. Stochastic Golden Cross: %K > %D (was <= previously)
    4. CCI < upper threshold: Momentum from non-extreme zone
    5. OBV Filter: Volume confirmation (OBV rising)

Usage:
    config = TrixGoldenConfig(trix_n=12, trix_signal=9, cci_period=9)
    strategy = TrixGoldenEntry(config)
    signal = await strategy.generate(context)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta

import pandas as pd

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator

logger = logging.getLogger(__name__)


@dataclass
class TrixGoldenConfig(ConfigMixin):
    """TRIX Golden Signal 진입 전략 설정.

    Attributes:
        trix_n: TRIX EMA period (default: 12).
        trix_signal: TRIX signal line period (default: 9).
        cci_period: CCI calculation period (default: 9).
        cci_upper: CCI upper threshold — entry only when CCI < this (default: 200).
        macd_fast: MACD fast EMA period (default: 12).
        macd_slow: MACD slow EMA period (default: 26).
        macd_signal: MACD signal line period (default: 9).
        sto_fastk: Stochastic raw %K period (default: 12).
        sto_slowk: Stochastic %K smoothing (default: 5).
        sto_slowd: Stochastic %D smoothing (default: 5).
        obv_filter: Require OBV to be rising (default: True).
        stop_loss_pct: Stop loss percentage for signal metadata (default: 3.0).
        min_candles: Minimum candles for indicator calculation (default: 50).
        timeframe_minutes: Candle timeframe in minutes (default: 5).
        market_open_hour: Market open hour (default: 9).
        market_open_minute: Market open minute (default: 0).
        market_close_hour: Market close hour (default: 15).
        market_close_minute: Market close minute (default: 15).
        skip_market_open_minutes: Skip N minutes after market open (default: 30).
        skip_market_close_minutes: Skip N minutes before close (default: 15).
        signal_cooldown_seconds: Min seconds between signals for same symbol (default: 300).
    """

    # TRIX parameters
    trix_n: int = 12
    trix_signal: int = 9

    # CCI parameters
    cci_period: int = 9
    cci_upper: float = 200.0

    # MACD parameters
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # Stochastic parameters
    sto_fastk: int = 12
    sto_slowk: int = 5
    sto_slowd: int = 5

    # Filters
    obv_filter: bool = True
    stop_loss_pct: float = 3.0
    min_candles: int = 50
    timeframe_minutes: int = 5

    # Time filters
    market_open_hour: int = 9
    market_open_minute: int = 0
    market_close_hour: int = 15
    market_close_minute: int = 15
    skip_market_open_minutes: int = 30
    skip_market_close_minutes: int = 15

    # Cooldown
    signal_cooldown_seconds: int = 300


class TrixGoldenEntry(EntrySignalGenerator[TrixGoldenConfig]):
    """TRIX 5분봉 황금신호 진입 전략.

    4가지 모멘텀 지표(TRIX, MACD, Stochastic, CCI)의 동시 충족 +
    OBV 거래량 필터를 통한 추세 추종 진입.
    """

    CONFIG_CLASS = TrixGoldenConfig

    def __init__(self, config: TrixGoldenConfig):
        super().__init__(config)
        self._last_signal_at: dict[str, datetime] = {}

    def _validate_config(self) -> None:
        """설정 유효성 검증."""
        assert self.config.trix_n > 0, "trix_n must be positive"
        assert self.config.trix_signal > 0, "trix_signal must be positive"
        assert self.config.cci_period > 0, "cci_period must be positive"
        assert self.config.macd_fast > 0, "macd_fast must be positive"
        assert (
            self.config.macd_slow > self.config.macd_fast
        ), "macd_slow must be > macd_fast"
        assert self.config.macd_signal > 0, "macd_signal must be positive"
        assert self.config.sto_fastk > 0, "sto_fastk must be positive"
        assert self.config.sto_slowk > 0, "sto_slowk must be positive"
        assert self.config.sto_slowd > 0, "sto_slowd must be positive"
        assert self.config.min_candles > 0, "min_candles must be positive"
        assert self.config.stop_loss_pct > 0, "stop_loss_pct must be positive"
        assert (
            self.config.signal_cooldown_seconds >= 0
        ), "signal_cooldown_seconds must be >= 0"

    @property
    def name(self) -> str:
        return "trix_golden"

    @property
    def required_indicators(self) -> list[str]:
        return ["momentum_5m"]

    async def generate(self, context: EntryContext) -> Signal | None:
        """Generate TRIX Golden Signal entry.

        Requires 'momentum_5m' in context.indicators, which contains
        a 'df' key with the full DataFrame of momentum indicators.
        """
        data = context.market_data or {}
        indicators = context.indicators or {}

        code = str(data.get("code", "") or "")
        name = str(data.get("name", "") or "")
        if not code:
            return None

        # Time filters
        now = context.timestamp
        if not self._is_trading_time(now):
            return None

        # Cooldown
        if self.config.signal_cooldown_seconds > 0:
            last_time = self._last_signal_at.get(code)
            if last_time:
                elapsed = (now - last_time).total_seconds()
                if elapsed < self.config.signal_cooldown_seconds:
                    return None

        # Get momentum indicators (computed by IndicatorEngine on 5-min candles)
        momentum = indicators.get("momentum_5m") or data.get("momentum_5m")
        if not momentum or not isinstance(momentum, dict):
            logger.debug("No momentum_5m indicators for %s", code)
            return None

        df: pd.DataFrame | None = momentum.get("df")
        if df is None or len(df) < self.config.min_candles:
            logger.debug(
                "Insufficient candles for %s: %d < %d",
                code,
                len(df) if df is not None else 0,
                self.config.min_candles,
            )
            return None

        # Check entry conditions on the latest completed candle
        if not self._check_all_conditions(df):
            return None

        close = float(data.get("close", 0) or df["close"].iloc[-1])

        # Calculate confidence
        confidence = self._calculate_confidence(df)

        logger.info(
            f"TRIX Golden LONG signal: {code} close={close}, "
            f"trix={df['trix'].iloc[-1]:.4f}, "
            f"macd_osc={df['macd_oscillator'].iloc[-1]:.4f}, "
            f"sto_k={df['sto_k'].iloc[-1]:.1f}, "
            f"cci={df['cci'].iloc[-1]:.1f}, "
            f"confidence={confidence:.2f}"
        )

        self._last_signal_at[code] = now

        return Signal(
            code=code,
            name=name,
            signal_type=SignalType.ENTRY,
            price=close,
            timestamp=now,
            strategy="trix_golden",
            confidence=confidence,
            metadata={
                "signal_direction": "long",
                "stop_loss_pct": float(self.config.stop_loss_pct),
                "trix": float(df["trix"].iloc[-1]),
                "trix_signal": float(df["trix_signal"].iloc[-1]),
                "macd_oscillator": float(df["macd_oscillator"].iloc[-1]),
                "sto_k": float(df["sto_k"].iloc[-1]),
                "cci": float(df["cci"].iloc[-1]),
            },
        )

    def _is_trading_time(self, now: datetime) -> bool:
        """Check if current time is within trading window."""
        open_dt = datetime.combine(
            now.date(),
            time(self.config.market_open_hour, self.config.market_open_minute),
            tzinfo=now.tzinfo,
        )
        close_dt = datetime.combine(
            now.date(),
            time(self.config.market_close_hour, self.config.market_close_minute),
            tzinfo=now.tzinfo,
        )

        if now < open_dt or now >= close_dt:
            return False

        if self.config.skip_market_open_minutes > 0:
            open_cutoff = open_dt + timedelta(
                minutes=self.config.skip_market_open_minutes
            )
            if now < open_cutoff:
                return False

        if self.config.skip_market_close_minutes > 0:
            close_cutoff = close_dt - timedelta(
                minutes=self.config.skip_market_close_minutes
            )
            if now >= close_cutoff:
                return False

        return True

    def _check_all_conditions(self, df: pd.DataFrame) -> bool:
        """Check all 4+1 entry conditions on the latest candle.

        Conditions (must all be true):
            1. TRIX Golden Cross
            2. MACD Oscillator > 0
            3. Stochastic Golden Cross
            4. CCI < upper threshold
            5. OBV rising (optional)
        """
        if len(df) < 2:
            return False

        i = -1  # Latest candle
        prev = -2  # Previous candle

        # Required columns check
        required = ["trix", "trix_signal", "macd_oscillator", "sto_k", "sto_d", "cci"]
        for col in required:
            if col not in df.columns:
                logger.debug("Missing indicator column: %s", col)
                return False

        # Condition 1: TRIX Golden Cross
        trix_current = df["trix"].iloc[i]
        trix_signal_current = df["trix_signal"].iloc[i]
        trix_prev = df["trix"].iloc[prev]
        trix_signal_prev = df["trix_signal"].iloc[prev]

        cond_trix_gc = (trix_current > trix_signal_current) and (
            trix_prev <= trix_signal_prev
        )
        if not cond_trix_gc:
            return False

        # Condition 2: MACD Oscillator > 0
        cond_macd_pos = df["macd_oscillator"].iloc[i] > 0
        if not cond_macd_pos:
            return False

        # Condition 3: Stochastic Golden Cross
        sto_k_current = df["sto_k"].iloc[i]
        sto_d_current = df["sto_d"].iloc[i]
        sto_k_prev = df["sto_k"].iloc[prev]
        sto_d_prev = df["sto_d"].iloc[prev]

        cond_sto_gc = (sto_k_current > sto_d_current) and (sto_k_prev <= sto_d_prev)
        if not cond_sto_gc:
            return False

        # Condition 4: CCI < upper threshold
        cond_cci = df["cci"].iloc[i] < self.config.cci_upper
        if not cond_cci:
            return False

        # Condition 5: OBV rising (optional)
        if self.config.obv_filter and "obv" in df.columns and len(df) >= 2:
            cond_obv = df["obv"].iloc[i] > df["obv"].iloc[prev]
            if not cond_obv:
                return False

        return True

    def _calculate_confidence(self, df: pd.DataFrame) -> float:
        """Calculate signal confidence based on indicator strength.

        Components:
            - TRIX-Signal spread: How far above signal (wider = stronger)
            - MACD Oscillator magnitude: Larger positive = more momentum
            - Stochastic %K position: Mid-range (30-70) is ideal zone
            - CCI distance from extreme: Further from 200 = healthier
        """
        i = -1
        scores: list[float] = []

        # TRIX strength: spread normalized
        trix_spread = df["trix"].iloc[i] - df["trix_signal"].iloc[i]
        trix_score = min(
            1.0, max(0.0, abs(trix_spread) * 20)
        )  # Scale ~0.05 spread to 1.0
        scores.append(trix_score)

        # MACD momentum
        macd_osc = df["macd_oscillator"].iloc[i]
        macd_score = min(1.0, max(0.0, macd_osc * 5))  # Scale ~0.2 to 1.0
        scores.append(macd_score)

        # Stochastic position (best in 30-70 zone)
        sto_k = df["sto_k"].iloc[i]
        if 30 <= sto_k <= 70:
            sto_score = 0.8
        elif 20 <= sto_k <= 80:
            sto_score = 0.6
        else:
            sto_score = 0.4
        scores.append(sto_score)

        # CCI health (lower absolute value = more room to run)
        cci = abs(df["cci"].iloc[i])
        cci_score = max(0.2, min(1.0, 1.0 - cci / 300))
        scores.append(cci_score)

        return sum(scores) / len(scores)
