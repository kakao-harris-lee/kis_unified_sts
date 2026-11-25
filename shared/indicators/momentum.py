"""모멘텀 지표 계산기

TRIX, CCI, MACD, Stochastic Oscillator, Williams %R 등 모멘텀 지표 계산.
모든 계산은 numpy/pandas로 직접 구현 (TA-Lib 비의존).

Usage:
    import pandas as pd
    from shared.indicators.momentum import (
        TRIXCalculator,
        CCICalculator,
        MACDCalculator,
        StochasticCalculator,
        DivergenceDetector,
    )

    df = pd.DataFrame({"open": ..., "high": ..., "low": ..., "close": ..., "volume": ...})

    # TRIX
    trix = TRIXCalculator(n=12, signal=9)
    df = trix.calculate(df)
    # Adds: trix, trix_signal columns

    # CCI
    cci = CCICalculator(period=9)
    df = cci.calculate(df)
    # Adds: cci column

    # MACD
    macd = MACDCalculator(fast=12, slow=26, signal=9)
    df = macd.calculate(df)
    # Adds: macd_line, macd_signal, macd_oscillator columns

    # Stochastic (Slow)
    stoch = StochasticCalculator(fastk_period=12, slowk_period=5, slowd_period=5)
    df = stoch.calculate(df)
    # Adds: sto_k, sto_d columns

    # Divergence Detection
    detector = DivergenceDetector(lookback=20)
    is_bearish = detector.detect_bearish(df["close"], df["trix"])
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from shared.indicators.engine import (
    IndicatorSpec,
    OHLCVWindow,
    momentum_indicator_engine,
)

logger = logging.getLogger(__name__)


# The indicator math lives in the engine's MomentumCompatBackend
# (shared/indicators/engine/momentum_backend.py) — the exact pandas conventions,
# reproduced bit-for-bit. These calculator classes are thin, value-preserving
# delegates that keep their public API + column names; calculate_all_momentum and
# DivergenceDetector below are unchanged. Pinned by test_momentum_backend_golden.py.


def _window(df: pd.DataFrame) -> OHLCVWindow:
    """Build an engine window from a momentum DataFrame (positional order).

    Falls back to close for a missing high/low and 0 for a missing volume so a
    calculator invoked on a partial frame behaves as before (each backend fn reads
    only the columns its indicator needs)."""
    close = df["close"].tolist()
    high = df["high"].tolist() if "high" in df.columns else close
    low = df["low"].tolist() if "low" in df.columns else close
    volume = df["volume"].tolist() if "volume" in df.columns else [0.0] * len(df)
    open_ = df["open"].tolist() if "open" in df.columns else close
    return OHLCVWindow.from_sequences(
        open=open_, high=high, low=low, close=close, volume=volume
    )


def _series(indicator_id: str, params: dict, df: pd.DataFrame) -> dict:
    """Compute an indicator's full output series via the momentum engine."""
    return (
        momentum_indicator_engine()
        .compute(IndicatorSpec.create(indicator_id, params), _window(df))
        .series
    )


# =============================================================================
# TRIX Calculator
# =============================================================================


@dataclass
class TRIXConfig:
    """TRIX indicator configuration.

    Attributes:
        n: EMA period for triple smoothing (default: 12).
        signal: Signal line EMA period (default: 9).
    """

    n: int = 12
    signal: int = 9


class TRIXCalculator:
    """TRIX (Triple Exponential Moving Average) 지표 계산기.

    EMA 3중 중첩 후 변화율을 계산하여 추세 방향/강도를 측정.
    직접 구현 (TA-Lib TRIX와 HTS 간 미세 차이 방지).

    Formula:
        EMA1 = EMA(close, n)
        EMA2 = EMA(EMA1, n)
        EMA3 = EMA(EMA2, n)
        TRIX = (EMA3 - EMA3[prev]) / EMA3[prev] * 100
        TRIX_SIGNAL = EMA(TRIX, signal)
    """

    def __init__(self, n: int = 12, signal: int = 9):
        self.config = TRIXConfig(n=n, signal=signal)

    def calculate(
        self,
        df: pd.DataFrame,
        *,
        lookahead_guard=None,
        context_timestamp=None,
        context_info: str = None,
    ) -> pd.DataFrame:
        """Calculate TRIX and signal line.

        Adds 'trix' and 'trix_signal' columns to the DataFrame.

        Args:
            df: DataFrame with 'close' column.

        Returns:
            DataFrame with added trix, trix_signal columns.
        """
        close = df["close"]
        n = self.config.n

        # LookaheadGuard: close 시계열 검사
        if lookahead_guard and context_timestamp is not None:
            timestamps = df["timestamp"].tolist() if "timestamp" in df.columns else None
            lookahead_guard.check(
                close.tolist(),
                timestamps,
                context_timestamp,
                context_info or "momentum:trix_close",
            )

        s = _series("trix", {"n": n, "signal": self.config.signal}, df)
        df["trix"] = s["trix"]
        df["trix_signal"] = s["trix_signal"]

        return df


# =============================================================================
# CCI Calculator
# =============================================================================


@dataclass
class CCIConfig:
    """CCI indicator configuration.

    Attributes:
        period: CCI calculation period (default: 9).
        constant: CCI constant divisor (default: 0.015).
    """

    period: int = 9
    constant: float = 0.015


class CCICalculator:
    """CCI (Commodity Channel Index) 계산기.

    Typical Price 기반 과매수/과매도 구간 측정.

    Formula:
        TP = (high + low + close) / 3
        CCI = (TP - SMA(TP, period)) / (constant * MeanDeviation)
    """

    def __init__(self, period: int = 9, constant: float = 0.015):
        self.config = CCIConfig(period=period, constant=constant)

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate CCI.

        Adds 'cci' column to the DataFrame.

        Args:
            df: DataFrame with 'high', 'low', 'close' columns.

        Returns:
            DataFrame with added cci column.
        """
        df["cci"] = _series(
            "cci",
            {"period": self.config.period, "constant": self.config.constant},
            df,
        )["cci"]
        return df


# =============================================================================
# MACD Calculator
# =============================================================================


@dataclass
class MACDConfig:
    """MACD indicator configuration.

    Attributes:
        fast: Fast EMA period (default: 12).
        slow: Slow EMA period (default: 26).
        signal: Signal line EMA period (default: 9).
    """

    fast: int = 12
    slow: int = 26
    signal: int = 9


class MACDCalculator:
    """MACD (Moving Average Convergence Divergence) 계산기.

    Formula:
        MACD Line = EMA(close, fast) - EMA(close, slow)
        MACD Signal = EMA(MACD Line, signal)
        MACD Oscillator = MACD Line - MACD Signal
    """

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.config = MACDConfig(fast=fast, slow=slow, signal=signal)

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate MACD line, signal, and oscillator.

        Adds 'macd_line', 'macd_signal', 'macd_oscillator' columns.

        Args:
            df: DataFrame with 'close' column.

        Returns:
            DataFrame with added MACD columns.
        """
        s = _series(
            "macd",
            {
                "fast": self.config.fast,
                "slow": self.config.slow,
                "signal": self.config.signal,
            },
            df,
        )
        df["macd_line"] = s["macd_line"]
        df["macd_signal"] = s["macd_signal"]
        df["macd_oscillator"] = s["macd_oscillator"]

        return df


# =============================================================================
# Stochastic Calculator
# =============================================================================


@dataclass
class StochasticConfig:
    """Stochastic Oscillator configuration.

    Attributes:
        fastk_period: Lookback period for raw %K (default: 12).
        slowk_period: Smoothing period for %K (default: 5).
        slowd_period: Smoothing period for %D (default: 5).
    """

    fastk_period: int = 12
    slowk_period: int = 5
    slowd_period: int = 5


class StochasticCalculator:
    """Slow Stochastic Oscillator (%K, %D) 계산기.

    Formula:
        Raw %K = (close - LowestLow(n)) / (HighestHigh(n) - LowestLow(n)) * 100
        Slow %K = SMA(Raw %K, slowk_period)
        Slow %D = SMA(Slow %K, slowd_period)
    """

    def __init__(
        self,
        fastk_period: int = 12,
        slowk_period: int = 5,
        slowd_period: int = 5,
    ):
        self.config = StochasticConfig(
            fastk_period=fastk_period,
            slowk_period=slowk_period,
            slowd_period=slowd_period,
        )

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Slow Stochastic %K and %D.

        Adds 'sto_k' and 'sto_d' columns.

        Args:
            df: DataFrame with 'high', 'low', 'close' columns.

        Returns:
            DataFrame with added sto_k, sto_d columns.
        """
        s = _series(
            "stochastic",
            {
                "fastk_period": self.config.fastk_period,
                "slowk_period": self.config.slowk_period,
                "slowd_period": self.config.slowd_period,
            },
            df,
        )
        df["sto_k"] = s["sto_k"]
        df["sto_d"] = s["sto_d"]

        return df


# =============================================================================
# Williams %R Calculator
# =============================================================================


@dataclass
class WilliamsRConfig:
    """Williams %R configuration.

    Attributes:
        period: Lookback period for highest high / lowest low (default: 14).
    """

    period: int = 14


class WilliamsRCalculator:
    """Williams %R 계산기.

    Formula:
        %R = ((Highest High(n) - Close) / (Highest High(n) - Lowest Low(n))) * -100
        Range: -100 ~ 0
        Oversold: < -80, Overbought: > -20
    """

    def __init__(self, period: int = 14):
        self.config = WilliamsRConfig(period=period)

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Williams %R.

        Adds 'williams_r' column.

        Args:
            df: DataFrame with 'high', 'low', 'close' columns.

        Returns:
            DataFrame with added williams_r column.
        """
        df["williams_r"] = _series("williams_r", {"period": self.config.period}, df)[
            "williams_r"
        ]

        return df


# =============================================================================
# RSI Calculator (for exit strategy — TRIX peak-out detection)
# =============================================================================


@dataclass
class RSIConfig:
    """RSI configuration.

    Attributes:
        period: RSI lookback period (default: 14).
    """

    period: int = 14


class RSICalculator:
    """RSI (Relative Strength Index) 계산기.

    Wilder's smoothing (EMA with alpha=1/period).
    """

    def __init__(self, period: int = 14):
        self.config = RSIConfig(period=period)

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate RSI.

        Adds 'rsi' column.

        Args:
            df: DataFrame with 'close' column.

        Returns:
            DataFrame with added rsi column.
        """
        df["rsi"] = _series("rsi", {"period": self.config.period}, df)["rsi"]

        return df


# =============================================================================
# OBV Calculator (DataFrame-based, for batch/backtest)
# =============================================================================


class OBVDataFrameCalculator:
    """OBV (On-Balance Volume) DataFrame 기반 계산기.

    기존 shared/indicators/volume.py의 OBVCalculator는 스트리밍용.
    이 버전은 DataFrame 입력을 받아 벡터화 계산.
    """

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate OBV.

        Adds 'obv' column.

        Args:
            df: DataFrame with 'close' and 'volume' columns.

        Returns:
            DataFrame with added obv column.
        """
        df["obv"] = _series("obv", {}, df)["obv"]
        return df


# =============================================================================
# Divergence Detector
# =============================================================================


class DivergenceDetector:
    """약세/강세 다이버전스 감지기.

    가격과 지표 간의 괴리를 감지하여 추세 반전 시그널 포착.

    - 약세 다이버전스: 가격 고점 상승 + 지표 고점 하락 → 매도 시그널
    - 강세 다이버전스: 가격 저점 하락 + 지표 저점 상승 → 매수 시그널
    """

    def __init__(self, lookback: int = 20, min_peaks: int = 2):
        """Initialize detector.

        Args:
            lookback: Number of bars to search for peaks/troughs.
            min_peaks: Minimum number of peaks to detect divergence (default: 2).
        """
        self.lookback = lookback
        self.min_peaks = min_peaks

    def detect_bearish(
        self,
        price_series: pd.Series,
        indicator_series: pd.Series,
    ) -> bool:
        """Detect bearish divergence (price higher highs, indicator lower highs).

        Args:
            price_series: Price data series (e.g., close prices).
            indicator_series: Indicator series (e.g., TRIX values).

        Returns:
            True if bearish divergence detected.
        """
        if len(price_series) < self.lookback:
            return False

        prices = price_series.iloc[-self.lookback :].values
        indicators = indicator_series.iloc[-self.lookback :].values

        # Find local peaks (simple: higher than both neighbors)
        price_peaks = []
        indicator_peaks = []
        for i in range(1, len(prices) - 1):
            if prices[i] > prices[i - 1] and prices[i] > prices[i + 1]:
                price_peaks.append((i, prices[i]))
                indicator_peaks.append((i, indicators[i]))

        if len(price_peaks) < self.min_peaks:
            return False

        # Check last two peaks: price rising, indicator falling
        last_price = price_peaks[-1][1]
        prev_price = price_peaks[-2][1]
        last_indicator = indicator_peaks[-1][1]
        prev_indicator = indicator_peaks[-2][1]

        return bool(last_price > prev_price and last_indicator < prev_indicator)

    def detect_bullish(
        self,
        price_series: pd.Series,
        indicator_series: pd.Series,
    ) -> bool:
        """Detect bullish divergence (price lower lows, indicator higher lows).

        Args:
            price_series: Price data series (e.g., close prices).
            indicator_series: Indicator series (e.g., TRIX values).

        Returns:
            True if bullish divergence detected.
        """
        if len(price_series) < self.lookback:
            return False

        prices = price_series.iloc[-self.lookback :].values
        indicators = indicator_series.iloc[-self.lookback :].values

        # Find local troughs
        price_troughs = []
        indicator_troughs = []
        for i in range(1, len(prices) - 1):
            if prices[i] < prices[i - 1] and prices[i] < prices[i + 1]:
                price_troughs.append((i, prices[i]))
                indicator_troughs.append((i, indicators[i]))

        if len(price_troughs) < self.min_peaks:
            return False

        # Check last two troughs: price falling, indicator rising
        last_price = price_troughs[-1][1]
        prev_price = price_troughs[-2][1]
        last_indicator = indicator_troughs[-1][1]
        prev_indicator = indicator_troughs[-2][1]

        return bool(last_price < prev_price and last_indicator > prev_indicator)


# =============================================================================
# Convenience: calculate all momentum indicators at once
# =============================================================================


def calculate_all_momentum(
    df: pd.DataFrame,
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
    include_obv: bool = True,
    include_rsi: bool = True,
) -> pd.DataFrame:
    """Calculate all momentum indicators in one call.

    Adds: trix, trix_signal, cci, macd_line, macd_signal, macd_oscillator,
          sto_k, sto_d, williams_r, obv (optional), rsi (optional).

    Args:
        df: DataFrame with 'open', 'high', 'low', 'close', 'volume' columns.
        **params: Indicator parameters.

    Returns:
        DataFrame with all indicator columns added.
    """
    df = TRIXCalculator(n=trix_n, signal=trix_signal).calculate(df)
    df = CCICalculator(period=cci_period).calculate(df)
    df = MACDCalculator(fast=macd_fast, slow=macd_slow, signal=macd_signal).calculate(
        df
    )
    df = StochasticCalculator(
        fastk_period=sto_fastk, slowk_period=sto_slowk, slowd_period=sto_slowd
    ).calculate(df)
    df = WilliamsRCalculator(period=williams_r_period).calculate(df)

    if include_obv:
        df = OBVDataFrameCalculator().calculate(df)

    if include_rsi:
        df = RSICalculator(period=rsi_period).calculate(df)

    return df
