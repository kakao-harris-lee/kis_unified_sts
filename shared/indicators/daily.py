"""Daily indicator calculation module

Provides convenience function for calculating common daily timeframe indicators
(SMA, EMA, RSI) from daily candle data. Used by IndicatorEngine.get_daily_indicators()
to provide multi-timeframe trend context to intraday strategies.

Usage:
    from shared.indicators.daily import calculate_daily_indicators

    candles = [
        {"open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000},
        # ... more daily candles
    ]

    indicators = calculate_daily_indicators(
        candles,
        sma_periods=[20, 60, 200],
        ema_periods=[5, 10, 20],
        rsi_period=5,
    )
    # Returns: {
    #     "sma_20": 100.2,
    #     "sma_60": 99.8,
    #     "sma_200": 98.5,
    #     "ema_5": 100.3,
    #     "ema_10": 100.1,
    #     "ema_20": 99.9,
    #     "rsi_5": 55.2,
    # }
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_daily_indicators(
    candles: list[dict[str, Any]],
    *,
    sma_periods: list[int] | None = None,
    ema_periods: list[int] | None = None,
    rsi_period: int = 5,
) -> dict[str, float]:
    """Calculate daily timeframe indicators from candle data.

    Computes SMA, EMA, and RSI indicators on daily candles to provide
    trend context for intraday strategies.

    Args:
        candles: List of candle dicts with OHLCV fields.
        sma_periods: SMA periods to calculate (default: [20, 60, 200]).
        ema_periods: EMA periods to calculate (default: [5, 10, 20]).
        rsi_period: RSI period (default: 5).

    Returns:
        Dict with indicator values from the most recent candle:
        - sma_{period}: SMA values for each period in sma_periods
        - ema_{period}: EMA values for each period in ema_periods
        - rsi_{period}: RSI value

        Returns empty dict if insufficient data.

    Example:
        >>> candles = get_daily_candles("005930", limit=252)
        >>> ind = calculate_daily_indicators(candles)
        >>> print(ind["sma_200"])  # Daily SMA(200)
        100.5
    """

    if sma_periods is None:
        sma_periods = [20, 60, 200]
    if ema_periods is None:
        ema_periods = [5, 10, 20]

    if not candles:
        logger.warning("calculate_daily_indicators: no candles provided")
        return {}

    # LookaheadGuard: 시계열 입력이 배열이면 검사
    if lookahead_guard and context_timestamp is not None:
        timestamps = [c['timestamp'] for c in candles if 'timestamp' in c]
        lookahead_guard.check([c['close'] for c in candles], timestamps, context_timestamp, context_info or "daily:candles")

    # Convert candles to DataFrame
    df = pd.DataFrame(candles)

    # Validate required columns
    required = ["open", "high", "low", "close", "volume"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        logger.error(f"calculate_daily_indicators: missing columns {missing}")
        return {}

    # Check minimum data for largest SMA period
    max_sma = max(sma_periods) if sma_periods else 0
    if len(df) < max_sma:
        logger.warning(
            f"calculate_daily_indicators: insufficient candles "
            f"({len(df)} < {max_sma} for SMA({max_sma}))"
        )
        # Still calculate what we can, but warn
        pass

    result: dict[str, float] = {}

    try:
        # Calculate SMA for each period
        for period in sma_periods:
            sma = df["close"].rolling(window=period, min_periods=1).mean()
            result[f"sma_{period}"] = float(sma.iloc[-1])

        # Calculate EMA for each period
        for period in ema_periods:
            ema = df["close"].ewm(span=period, adjust=False).mean()
            result[f"ema_{period}"] = float(ema.iloc[-1])

        # Calculate RSI
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)

        avg_gain = gain.ewm(
            alpha=1.0 / rsi_period, min_periods=rsi_period, adjust=False
        ).mean()
        avg_loss = loss.ewm(
            alpha=1.0 / rsi_period, min_periods=rsi_period, adjust=False
        ).mean()

        # Handle edge cases for RSI calculation
        zero_loss = avg_loss.iloc[-1] == 0
        zero_gain = avg_gain.iloc[-1] == 0

        if zero_loss and zero_gain:
            rsi_value = 50.0  # Flat market
        elif zero_loss and not zero_gain:
            rsi_value = 100.0  # All gains
        elif zero_gain and not zero_loss:
            rsi_value = 0.0  # All losses
        else:
            rs = avg_gain.iloc[-1] / avg_loss.iloc[-1]
            rsi_value = 100 - (100 / (1 + rs))

        result[f"rsi_{rsi_period}"] = float(rsi_value)

    except (ValueError, KeyError, IndexError, ZeroDivisionError) as e:
        logger.error(f"calculate_daily_indicators: calculation failed: {e}")
        return {}

    return result
