"""TRIX Golden Signal Entry Strategy.

5분봉 기준 TRIX 지표를 핵심으로 한 추세 추종 진입 전략.

Two entry modes:
    - "crossover" (legacy): TRIX > TRIX_SIGNAL crossover + MACD/Stoch/CCI/OBV
    - "acceleration" (v2): TRIX 음수→양전환 가속 감지 + 비상관 필터(SMA/CCI/RVOL)

Usage:
    config = TrixGoldenConfig(trix_entry_mode="acceleration")
    strategy = TrixGoldenEntry(config)
    signal = await strategy.generate(context)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any

import pandas as pd

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator

logger = logging.getLogger(__name__)


@dataclass
class TrixGoldenConfig(ConfigMixin):
    """TRIX Golden Signal 진입 전략 설정."""

    # TRIX parameters
    trix_n: int = 12
    trix_signal: int = 9

    # TRIX entry mode: "crossover" (legacy) | "acceleration" (v2)
    trix_entry_mode: str = "acceleration"
    # acceleration mode: TRIX가 최근 N바 이내에 음수였다가 양전환 + 상승 중
    trix_min_negative_bars: int = 3

    # CCI parameters
    cci_period: int = 9
    cci_upper: float = 300.0
    cci_lower: float = 0.0  # CCI 하한 (양의 모멘텀 확인)

    # MACD parameters (crossover 모드에서만 사용)
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # Stochastic parameters (crossover 모드에서만 사용)
    sto_fastk: int = 12
    sto_slowk: int = 5
    sto_slowd: int = 5

    # Filters (crossover 모드)
    obv_filter: bool = True
    stop_loss_pct: float = 3.0
    min_candles: int = 50
    timeframe_minutes: int = 5

    # 비상관 필터 (acceleration 모드)
    use_uncorrelated_filters: bool = True
    require_above_sma: bool = True
    sma_period: int = 20
    rvol_filter: bool = False
    rvol_threshold: float = 1.2

    # 변동성 필터 (고변동 종목 차단)
    max_atr_pct: float = 0.0  # ATR% 상한 (0 = 비활성). 예: 0.008 = ATR이 종가의 0.8% 초과 시 차단
    atr_period: int = 14
    max_return_vol: float = 0.0  # 수익률 변동성 상한 (0 = 비활성). 예: 0.008 = 5분봉 수익률 std > 0.8% 차단
    return_vol_period: int = 60  # rolling window (5분봉 60개 = ~5시간)

    # Market state filter
    market_state_filter: dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": False,
            "allowed_states": [],
            "blocked_states": [],
        }
    )

    # Time filters
    market_open_hour: int = 9
    market_open_minute: int = 0
    market_close_hour: int = 15
    market_close_minute: int = 15
    skip_market_open_minutes: int = 30
    skip_market_close_minutes: int = 15

    # Cooldown
    signal_cooldown_seconds: int = 300

    # 시그널 빈도 제한 (TRIX 과진동 종목 자동 차단)
    max_signals_per_day: int = 3  # 당일 종목당 최대 시그널 수 (0 = 무제한)

    # Confidence scoring params
    trix_spread_scale: float = 20.0  # TRIX spread → score 정규화 계수
    trix_accel_scale: float = 30.0  # TRIX acceleration → score 정규화 계수
    cci_norm_range: float = 300.0  # CCI score 정규화 범위
    sma_dist_base: float = 0.5  # SMA distance score 기본값
    sma_dist_scale: float = 10.0  # SMA distance → score 정규화 계수


class TrixGoldenEntry(EntrySignalGenerator[TrixGoldenConfig]):
    """TRIX 5분봉 황금신호 진입 전략.

    v2 (acceleration 모드): TRIX 음수→양전환 가속 감지 + 비상관 필터로
    모멘텀 소진이 아닌 새 모멘텀 시작 시점 포착.

    v1 (crossover 모드): 기존 TRIX/MACD/Stoch/CCI 4중 동시 충족.
    """

    CONFIG_CLASS = TrixGoldenConfig

    def __init__(self, config: TrixGoldenConfig):
        super().__init__(config)
        self._last_signal_at: dict[str, datetime] = {}
        self._daily_signal_count: dict[str, int] = {}  # "code:date" → count


    def _validate_config(self) -> None:
        """설정 유효성 검증."""
        assert self.config.trix_n > 0, "trix_n must be positive"
        assert self.config.trix_signal > 0, "trix_signal must be positive"
        assert self.config.trix_entry_mode in (
            "crossover",
            "acceleration",
        ), f"Invalid trix_entry_mode: {self.config.trix_entry_mode}"
        assert self.config.cci_period > 0, "cci_period must be positive"
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
        """Generate TRIX Golden Signal entry."""
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

        # Daily signal frequency limit (과진동 종목 자동 차단)
        if self.config.max_signals_per_day > 0:
            day_key = f"{code}:{now.strftime('%Y-%m-%d')}"
            if self._daily_signal_count.get(day_key, 0) >= self.config.max_signals_per_day:
                return None

        # Market state filter
        market_state = context.metadata.get("market_state")
        if market_state is None:
            market_state = indicators.get("market_state")
        if market_state is None:
            market_state = data.get("market_state")

        state_name = str(market_state).upper() if market_state is not None else None
        filter_cfg = self.config.market_state_filter or {}
        if filter_cfg.get("enabled", False):
            allowed_states = [s.upper() for s in filter_cfg.get("allowed_states", [])]
            blocked_states = [s.upper() for s in filter_cfg.get("blocked_states", [])]

            if state_name is None:
                logger.debug("Market state missing for %s; skipping", code)
                return None

            if blocked_states and state_name in blocked_states:
                return None
            if allowed_states and state_name not in allowed_states:
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

        # Check entry conditions based on mode
        if not self._check_all_conditions(df, data):
            return None

        close = float(data.get("close", 0) or df["close"].iloc[-1])
        confidence = self._calculate_confidence(df)

        logger.info(
            "TRIX Golden LONG signal: %s close=%s, mode=%s, "
            "trix=%.4f, cci=%.1f, confidence=%.2f",
            code,
            close,
            self.config.trix_entry_mode,
            df["trix"].iloc[-1],
            df["cci"].iloc[-1],
            confidence,
        )

        self._last_signal_at[code] = now

        # Track daily signal count
        if self.config.max_signals_per_day > 0:
            day_key = f"{code}:{now.strftime('%Y-%m-%d')}"
            self._daily_signal_count[day_key] = self._daily_signal_count.get(day_key, 0) + 1

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
                "entry_mode": self.config.trix_entry_mode,
                "trix": float(df["trix"].iloc[-1]),
                "trix_signal": float(df["trix_signal"].iloc[-1]),
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

    def _check_all_conditions(
        self, df: pd.DataFrame, market_data: dict[str, Any]
    ) -> bool:
        """Check entry conditions based on configured mode."""
        if self.config.trix_entry_mode == "acceleration":
            return self._check_acceleration_conditions(df, market_data)
        return self._check_crossover_conditions(df)

    def _check_acceleration_conditions(
        self, df: pd.DataFrame, market_data: dict[str, Any]
    ) -> bool:
        """Acceleration mode: TRIX 음수→양전환 가속 + 비상관 필터.

        TRIX condition: TRIX > 0 AND rising AND was negative within last N bars.
        This catches NEW momentum starts, not exhausted crossovers.
        """
        n_bars = self.config.trix_min_negative_bars
        if len(df) < max(2, n_bars + 2):
            return False

        # Required columns
        if "trix" not in df.columns or "cci" not in df.columns:
            return False

        trix_current = float(df["trix"].iloc[-1])
        trix_prev = float(df["trix"].iloc[-2])

        # TRIX > 0 and rising
        if trix_current <= 0 or trix_current <= trix_prev:
            return False

        # Was negative within last N+1 bars (excluding current)
        lookback = df["trix"].iloc[-(n_bars + 1) : -1]
        if not (lookback < 0).any():
            return False

        # CCI range filter: lower < CCI < upper
        cci_val = float(df["cci"].iloc[-1])
        if cci_val < self.config.cci_lower or cci_val > self.config.cci_upper:
            return False

        # ATR% volatility filter (고변동 종목 차단)
        if self.config.max_atr_pct > 0 and len(df) >= self.config.atr_period + 1:
            atr_pct = self._calc_atr_pct(df, self.config.atr_period)
            if atr_pct > self.config.max_atr_pct:
                return False

        # 수익률 변동성 필터 (rolling std of returns)
        if self.config.max_return_vol > 0 and len(df) >= self.config.return_vol_period + 1:
            returns = df["close"].pct_change()
            vol = returns.rolling(self.config.return_vol_period).std().iloc[-1]
            if not pd.isna(vol) and vol > self.config.max_return_vol:
                return False

        # Uncorrelated filters
        if self.config.use_uncorrelated_filters:
            # Price > SMA (trend confirmation)
            if self.config.require_above_sma:
                close = float(df["close"].iloc[-1])
                sma = df["close"].rolling(self.config.sma_period).mean()
                if pd.isna(sma.iloc[-1]) or close <= float(sma.iloc[-1]):
                    return False

            # RVOL filter (volume confirmation)
            if self.config.rvol_filter:
                rvol = market_data.get("rvol")
                if rvol is None and "volume" in df.columns:
                    vol_ma = (
                        df["volume"]
                        .rolling(self.config.sma_period)
                        .mean()
                        .iloc[-1]
                    )
                    if vol_ma > 0:
                        rvol = float(df["volume"].iloc[-1]) / float(vol_ma)
                if rvol is not None and float(rvol) < self.config.rvol_threshold:
                    return False

        # OBV filter (optional, kept for both modes)
        if self.config.obv_filter and "obv" in df.columns and len(df) >= 2:
            if df["obv"].iloc[-1] <= df["obv"].iloc[-2]:
                return False

        return True

    def _check_crossover_conditions(self, df: pd.DataFrame) -> bool:
        """Legacy crossover mode: TRIX crossover + MACD/Stoch/CCI/OBV."""
        if len(df) < 2:
            return False

        required = ["trix", "trix_signal", "macd_oscillator", "sto_k", "sto_d", "cci"]
        for col in required:
            if col not in df.columns:
                logger.debug("Missing indicator column: %s", col)
                return False

        # TRIX Golden Cross
        trix_current = df["trix"].iloc[-1]
        trix_signal_current = df["trix_signal"].iloc[-1]
        trix_prev = df["trix"].iloc[-2]
        trix_signal_prev = df["trix_signal"].iloc[-2]

        if not (
            trix_current > trix_signal_current and trix_prev <= trix_signal_prev
        ):
            return False

        # MACD Oscillator > 0
        if df["macd_oscillator"].iloc[-1] <= 0:
            return False

        # Stochastic %K > %D
        if df["sto_k"].iloc[-1] <= df["sto_d"].iloc[-1]:
            return False

        # CCI range
        cci_val = float(df["cci"].iloc[-1])
        if cci_val < self.config.cci_lower or cci_val > self.config.cci_upper:
            return False

        # OBV rising (optional)
        if self.config.obv_filter and "obv" in df.columns:
            if df["obv"].iloc[-1] <= df["obv"].iloc[-2]:
                return False

        return True

    def _calculate_confidence(self, df: pd.DataFrame) -> float:
        """Calculate signal confidence based on indicator strength."""
        i = -1
        scores: list[float] = []

        # TRIX strength: spread normalized
        trix_spread = df["trix"].iloc[i] - df["trix_signal"].iloc[i]
        trix_score = min(1.0, max(0.0, abs(trix_spread) * self.config.trix_spread_scale))
        scores.append(trix_score)

        # TRIX acceleration (positive delta)
        if len(df) >= 2:
            trix_delta = float(df["trix"].iloc[i]) - float(df["trix"].iloc[i - 1])
            accel_score = min(1.0, max(0.0, trix_delta * self.config.trix_accel_scale))
            scores.append(accel_score)

        # CCI health (moderate CCI = more room to run)
        cci = abs(df["cci"].iloc[i])
        cci_score = max(0.2, min(1.0, 1.0 - cci / self.config.cci_norm_range))
        scores.append(cci_score)

        # Price vs SMA (if available)
        if "close" in df.columns and len(df) >= self.config.sma_period:
            close = float(df["close"].iloc[i])
            sma = float(
                df["close"].rolling(self.config.sma_period).mean().iloc[i]
            )
            if sma > 0:
                sma_dist = (close - sma) / sma
                sma_score = min(
                    1.0,
                    max(0.0, self.config.sma_dist_base + sma_dist * self.config.sma_dist_scale),
                )
                scores.append(sma_score)

        return sum(scores) / len(scores) if scores else 0.5

    @staticmethod
    def _calc_atr_pct(df: pd.DataFrame, period: int) -> float:
        """Calculate ATR as percentage of current close (ATR%)."""
        high = df["high"]
        low = df["low"]
        prev_close = df["close"].shift(1)
        tr = pd.concat(
            [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(period).mean().iloc[-1]
        close = float(df["close"].iloc[-1])
        if close <= 0 or pd.isna(atr):
            return 0.0
        return float(atr) / close
