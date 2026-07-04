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

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

logger = logging.getLogger(__name__)


# =============================================================================
# EMA Utility
# =============================================================================


def ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential Moving Average (adjust=False for HTS compatibility).

    Args:
        series: Input price series.
        span: EMA period.

    Returns:
        EMA series of same length.
    """
    return series.ewm(span=span, adjust=False).mean()


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

        ema1 = ema(close, n)
        ema2 = ema(ema1, n)
        ema3 = ema(ema2, n)

        # TRIX = rate of change of EMA3 as percentage. Ratio runs in numpy to
        # avoid Series-alignment overhead; the .ewm signal stays in pandas.
        ema3_arr = ema3.to_numpy()
        ema3_prev = ema3.shift(1).to_numpy()
        with np.errstate(divide="ignore", invalid="ignore"):
            trix = np.where(
                ema3_prev != 0, (ema3_arr - ema3_prev) / ema3_prev * 100.0, 0.0
            )
        df["trix"] = trix
        df["trix_signal"] = ema(pd.Series(trix, index=df.index), self.config.signal)

        return df


# =============================================================================
# CCI Calculator
# =============================================================================


def _rolling_mad(values: np.ndarray, period: int) -> np.ndarray:
    """Rolling mean-absolute-deviation with pandas ``min_periods=1`` semantics.

    ``mad[i] = mean(|w - mean(w)|)`` over ``w = values[max(0, i-period+1) : i+1]``.

    The ramp-up rows (``i < period-1``) use the expanding window; the full
    windows are computed in a single vectorized pass via a strided view, which
    avoids the per-window Python callback that ``Series.rolling().apply()``
    incurs (the dominant cost of the previous CCI implementation).

    Args:
        values: 1-D float array (typical price).
        period: rolling window length.

    Returns:
        Array of the same length as ``values`` with the rolling MAD.
    """
    n = values.shape[0]
    out = np.empty(n, dtype=float)
    ramp = min(period - 1, n)
    for i in range(ramp):  # expanding window; length is period-1 (constant), not O(n)
        w = values[: i + 1]
        out[i] = np.abs(w - w.mean()).mean()
    if n >= period:
        windows = sliding_window_view(values, period)  # (n-period+1, period)
        out[period - 1 :] = np.abs(windows - windows.mean(axis=1, keepdims=True)).mean(
            axis=1
        )
    return out


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
        tp = (df["high"] + df["low"] + df["close"]) / 3
        tp_sma = tp.rolling(window=self.config.period, min_periods=1).mean()

        # Mean Deviation = mean of |TP - SMA(TP)|. Vectorized (sliding-window
        # view) to avoid a per-window Python callback; see _rolling_mad.
        mean_dev = pd.Series(
            _rolling_mad(tp.to_numpy(dtype=float), self.config.period),
            index=tp.index,
        )

        # Avoid division by zero
        denominator = self.config.constant * mean_dev
        df["cci"] = np.where(
            denominator != 0,
            (tp - tp_sma) / denominator,
            0.0,
        )

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
        close = df["close"]
        fast_ema = ema(close, self.config.fast)
        slow_ema = ema(close, self.config.slow)

        df["macd_line"] = fast_ema - slow_ema
        df["macd_signal"] = ema(df["macd_line"], self.config.signal)
        df["macd_oscillator"] = df["macd_line"] - df["macd_signal"]

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
        n = self.config.fastk_period
        # rolling min/max stay in pandas (deque O(n) beats sliding-window O(n*w));
        # the raw-%K arithmetic runs in numpy to avoid Series-alignment overhead.
        lowest_low = df["low"].rolling(window=n, min_periods=1).min().to_numpy()
        highest_high = df["high"].rolling(window=n, min_periods=1).max().to_numpy()
        close = df["close"].to_numpy()

        # Raw (fast) %K
        denominator = highest_high - lowest_low
        with np.errstate(divide="ignore", invalid="ignore"):
            raw_k = np.where(
                denominator != 0,
                (close - lowest_low) / denominator * 100.0,
                50.0,  # When range is zero, neutral
            )
        raw_k_series = pd.Series(raw_k, index=df.index)

        # Slow %K = SMA of raw %K
        df["sto_k"] = raw_k_series.rolling(
            window=self.config.slowk_period, min_periods=1
        ).mean()

        # Slow %D = SMA of Slow %K
        df["sto_d"] = (
            df["sto_k"].rolling(window=self.config.slowd_period, min_periods=1).mean()
        )

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
        n = self.config.period
        # rolling max/min stay in pandas; the %R arithmetic runs in numpy.
        highest_high = df["high"].rolling(window=n, min_periods=1).max().to_numpy()
        lowest_low = df["low"].rolling(window=n, min_periods=1).min().to_numpy()
        close = df["close"].to_numpy()

        denominator = highest_high - lowest_low
        with np.errstate(divide="ignore", invalid="ignore"):
            df["williams_r"] = np.where(
                denominator != 0,
                ((highest_high - close) / denominator) * -100.0,
                -50.0,  # Neutral when range is zero
            )

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
        period = self.config.period
        # Wilder smoothing stays in pandas (.ewm handles NaN / min_periods); the
        # gain/loss split and edge-case selection run in one numpy pass to avoid
        # the .clip / chained .where / .fillna Series overhead.
        delta = df["close"].diff().to_numpy()
        gain = np.maximum(delta, 0.0)  # == delta.clip(lower=0), NaN-preserving
        loss = np.maximum(-delta, 0.0)  # == (-delta).clip(lower=0)

        alpha = 1.0 / period
        avg_gain = (
            pd.Series(gain, index=df.index)
            .ewm(alpha=alpha, min_periods=period, adjust=False)
            .mean()
            .to_numpy()
        )
        avg_loss = (
            pd.Series(loss, index=df.index)
            .ewm(alpha=alpha, min_periods=period, adjust=False)
            .mean()
            .to_numpy()
        )

        # When avg_loss=0 and avg_gain=0 (flat), RSI=50
        # When avg_loss=0 and avg_gain>0 (all gains), RSI=100
        # When avg_gain=0 and avg_loss>0 (all losses), RSI=0
        zero_loss = avg_loss == 0.0
        zero_gain = avg_gain == 0.0
        with np.errstate(divide="ignore", invalid="ignore"):
            rs = avg_gain / np.where(zero_loss, np.nan, avg_loss)  # replace(0, nan)
            rsi = 100.0 - 100.0 / (1.0 + rs)
        rsi = np.where(zero_loss & zero_gain, 50.0, rsi)
        rsi = np.where(zero_loss & ~zero_gain, 100.0, rsi)
        rsi = np.where(zero_gain & ~zero_loss, 0.0, rsi)
        # Fill initial NaN (min_periods warmup) with neutral 50
        rsi = np.where(np.isnan(rsi), 50.0, rsi)
        df["rsi"] = rsi

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
        direction = np.sign(df["close"].diff().fillna(0))
        df["obv"] = (direction * df["volume"]).cumsum()
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
