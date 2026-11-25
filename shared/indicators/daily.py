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
import math
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

    # Indicator math is delegated to the daily-convention engine backend
    # (shared/indicators/engine/daily_backend.py) so the platform computes daily
    # SMA/EMA/RSI in one place. The pandas conventions (min_periods SMA,
    # adjust=False EMA, ewm-seeded RSI + zero-gain/loss handling) are reproduced
    # bit-for-bit there; this function keeps only the look-ahead guard, validation,
    # and the {sma,ema,rsi}_{period} labelling / SMA omission contract.
    from shared.indicators.engine import (
        IndicatorSpec,
        OHLCVWindow,
        daily_indicator_engine,
    )

    closes = [float(c) for c in df["close"].tolist()]
    window = OHLCVWindow.from_sequences(
        open=closes, high=closes, low=closes, close=closes, volume=[0.0] * len(closes)
    )
    engine = daily_indicator_engine()

    def _daily(indicator_id: str, period: int) -> float:
        return engine.compute(
            IndicatorSpec.create(indicator_id, {"period": period}), window
        ).latest["value"]

    try:
        # SMA requires a full window (min_periods=period): an under-warmed period
        # comes back NaN and its key is omitted, rather than reporting a partial
        # mean as the full-period SMA. Consumers treat a missing SMA as "no trend
        # confirmation" (PatternPullback defaults to 0.0 and gates on sma > 0).
        for period in sma_periods:
            value = _daily("sma", period)
            if math.isfinite(value):
                result[f"sma_{period}"] = float(value)
        for period in ema_periods:
            result[f"ema_{period}"] = float(_daily("ema", period))
        result[f"rsi_{rsi_period}"] = float(_daily("rsi", rsi_period))
    except (ValueError, KeyError, IndexError, ZeroDivisionError) as e:
        logger.error(f"calculate_daily_indicators: calculation failed: {e}")
        return {}

    return result
