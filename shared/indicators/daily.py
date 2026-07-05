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

import pandas as pd

logger = logging.getLogger(__name__)


def calculate_daily_indicators(
    candles: list[dict[str, Any]],
    *,
    sma_periods: list[int] | None = None,
    ema_periods: list[int] | None = None,
    rsi_period: int = 5,
    lookahead_guard: Any | None = None,
    context_timestamp: Any | None = None,
    context_info: str | None = None,
) -> dict[str, float]:
    """Calculate daily timeframe indicators from candle data.

    Computes SMA, EMA, and RSI indicators on daily candles to provide
    trend context for intraday strategies.

    Args:
        candles: List of candle dicts with OHLCV fields.
        sma_periods: SMA periods to calculate (default: [20, 60, 200]).
        ema_periods: EMA periods to calculate (default: [5, 10, 20]).
        rsi_period: RSI period (default: 5).
        lookahead_guard: Optional backtest guard for timestamped candle arrays.
        context_timestamp: Timestamp used by the optional lookahead guard.
        context_info: Label used in lookahead guard diagnostics.

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

    if lookahead_guard is not None and context_timestamp is not None:
        timestamped = [
            (c["close"], c["timestamp"])
            for c in candles
            if "close" in c and "timestamp" in c
        ]
        if timestamped:
            closes, timestamps = zip(*timestamped)
            lookahead_guard.check(
                list(closes),
                list(timestamps),
                context_timestamp,
                context_info or "daily:candles",
            )

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
        # Calculate SMA for each period. Require a full window (min_periods=period)
        # so an under-warmed period is NaN and its key is omitted, rather than
        # emitting a partial-window mean mislabeled as the full-period SMA (e.g.
        # 30 candles must not report sma_200 = mean of 30). Consumers treat a
        # missing SMA as "no trend confirmation" (PatternPullback defaults to 0.0
        # and gates on sma > 0), so omission is the safe, conservative signal.
        for period in sma_periods:
            sma = df["close"].rolling(window=period, min_periods=period).mean()
            value = sma.iloc[-1]
            if pd.notna(value):
                result[f"sma_{period}"] = float(value)

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
