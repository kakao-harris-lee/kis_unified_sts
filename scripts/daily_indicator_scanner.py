"""Daily Indicator Scanner — pre-compute daily indicators for paper trading.

Reads daily candles from ClickHouse `market.daily_candles`, computes SMA/RSI/ATR/
Highest High per symbol, and publishes results to Redis for the TradingOrchestrator.

Usage:
    python scripts/daily_indicator_scanner.py [--symbols 005930,000660]

Cron: 50 8 * * 1-5  (08:50 KST, before market open)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from shared.collector.historical.calendar import (
    get_previous_trading_day,
    trading_day_lag,
)
from shared.collector.historical.stock_universe import STOCK_UNIVERSE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("daily_indicator_scanner")

DEFAULT_SYMBOLS = [item["code"] for item in STOCK_UNIVERSE]

REDIS_KEY = "system:daily_indicators:latest"
REDIS_TTL = 86400  # 24h


def get_clickhouse_client():
    """Create ClickHouse client from env vars."""
    import clickhouse_connect

    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
    )


def load_daily_candles(client, symbol: str, days: int = 250) -> pd.DataFrame:
    """Load recent daily candles from ClickHouse."""
    query = """
        SELECT code, date, open, high, low, close, volume
        FROM market.daily_candles
        WHERE code = {code:String}
        ORDER BY date DESC
        LIMIT {limit:UInt32}
    """
    result = client.query(query, parameters={"code": symbol, "limit": int(days)})
    if not result.result_rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        result.result_rows,
        columns=["code", "date", "open", "high", "low", "close", "volume"],
    )
    df = df.sort_values("date").reset_index(drop=True)
    return df


def latest_candle_date(df: pd.DataFrame) -> date | None:
    """Return the newest daily candle date from a loaded daily DataFrame."""
    if df.empty or "date" not in df:
        return None
    latest = df["date"].max()
    if hasattr(latest, "date"):
        return latest.date()
    return latest


def is_fresh_daily_data(
    df: pd.DataFrame,
    *,
    expected_latest: date | None,
    max_stale_trading_days: int,
) -> bool:
    """Check whether daily candles are fresh enough for pre-market indicators."""
    latest = latest_candle_date(df)
    if latest is None or expected_latest is None:
        return False
    return trading_day_lag(latest, expected_latest) <= max_stale_trading_days


def compute_rsi(series: pd.Series, period: int) -> pd.Series:
    """Compute RSI using Wilder's EMA (same as DailyBacktestAdapter)."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100.0 - (100.0 / (1.0 + rs))


def compute_indicators(
    df: pd.DataFrame,
    sma_long: int = 200,
    sma_short: int = 20,
    sma_mid: int = 60,
    rsi_period: int = 5,
    atr_period: int = 22,
    lookback_period: int = 22,
    mid_trend_lookback: int = 5,
) -> dict[str, float] | None:
    """Compute daily indicators from a DataFrame. Returns latest values or None."""
    if len(df) < sma_long:
        return None

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    # SMA
    sma_200_series = close.rolling(window=sma_long, min_periods=sma_long).mean()
    sma_20_series = close.rolling(window=sma_short, min_periods=sma_short).mean()
    sma_60_series = close.rolling(window=sma_mid, min_periods=sma_mid).mean()

    # RSI
    rsi_series = compute_rsi(close, rsi_period)

    # ATR
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr_series = tr.rolling(window=atr_period, min_periods=atr_period).mean()

    # Highest High
    hh_series = high.rolling(window=lookback_period, min_periods=1).max()

    # Get latest values
    latest = len(df) - 1

    def safe_float(val) -> float | None:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return None
        return float(val)

    sma_200 = safe_float(sma_200_series.iloc[latest])
    sma_20 = safe_float(sma_20_series.iloc[latest])
    sma_60 = safe_float(sma_60_series.iloc[latest])
    sma_60_prev_idx = max(0, latest - mid_trend_lookback)
    sma_60_prev = safe_float(sma_60_series.iloc[sma_60_prev_idx])
    rsi_5 = safe_float(rsi_series.iloc[latest])
    atr = safe_float(atr_series.iloc[latest])
    highest_high = safe_float(hh_series.iloc[latest])
    daily_close = safe_float(close.iloc[latest])

    if sma_200 is None:
        return None

    result: dict[str, Any] = {
        "daily_sma_200": sma_200,
        "daily_sma_20": sma_20,
        "daily_sma_60": sma_60,
        "daily_sma_60_prev": sma_60_prev,
        "daily_rsi_5": rsi_5,
        "daily_atr": atr,
        "daily_highest_high": highest_high,
        "daily_close": daily_close,
    }

    # Include raw daily series for VR composite strategy (most recent 80 bars)
    series_len = min(len(df), 80)
    result["daily_closes"] = close.iloc[-series_len:].tolist()
    result["daily_volumes"] = df["volume"].astype(int).iloc[-series_len:].tolist()

    # Remove None scalar values (keep lists)
    return {k: v for k, v in result.items() if v is not None}


def publish_to_redis(indicators: dict[str, dict], redis_client=None) -> None:
    """Publish indicator dict to Redis."""
    if redis_client is None:
        from shared.streaming.client import RedisClient
        redis_client = RedisClient.get_client()

    payload = json.dumps({
        "indicators": indicators,
        "computed_at": datetime.now().isoformat(),
        "symbol_count": len(indicators),
    })
    redis_client.set(REDIS_KEY, payload, ex=REDIS_TTL)
    logger.info(f"Published daily indicators for {len(indicators)} symbols to Redis ({REDIS_KEY})")


def main():
    parser = argparse.ArgumentParser(description="Pre-compute daily indicators for paper trading")
    parser.add_argument("--symbols", type=str, default="", help="Comma-separated symbol codes (default: stock universe)")
    parser.add_argument("--days", type=int, default=250, help="Number of daily bars to load")
    parser.add_argument(
        "--max-stale-trading-days",
        type=int,
        default=int(os.getenv("STOCK_DAILY_MAX_STALE_TRADING_DAYS", "1")),
        help="Maximum allowed trading-day lag versus previous trading day",
    )
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
    symbols = [s.strip() for s in symbols if s.strip()]

    expected_latest = get_previous_trading_day()
    logger.info(
        "Computing daily indicators for %d symbols (last %d days, expected_latest=%s)",
        len(symbols),
        args.days,
        expected_latest,
    )

    client = get_clickhouse_client()

    results: dict[str, dict] = {}
    errors = 0

    for symbol in symbols:
        try:
            df = load_daily_candles(client, symbol, days=args.days)
            if df.empty:
                logger.warning(f"  {symbol}: no data")
                errors += 1
                continue

            if not is_fresh_daily_data(
                df,
                expected_latest=expected_latest,
                max_stale_trading_days=args.max_stale_trading_days,
            ):
                latest = latest_candle_date(df)
                lag = (
                    trading_day_lag(latest, expected_latest)
                    if latest and expected_latest
                    else None
                )
                logger.warning(
                    "  %s: stale daily candles latest=%s expected=%s lag=%s max=%s",
                    symbol,
                    latest,
                    expected_latest,
                    lag,
                    args.max_stale_trading_days,
                )
                errors += 1
                continue

            indicators = compute_indicators(df)
            if indicators is None:
                logger.warning(f"  {symbol}: insufficient data ({len(df)} bars)")
                errors += 1
                continue

            results[symbol] = indicators
            logger.debug(f"  {symbol}: OK ({len(df)} bars)")

        except Exception as e:
            logger.error(f"  {symbol}: {e}")
            errors += 1

    if results:
        publish_to_redis(results)
    else:
        logger.warning("No indicators computed — nothing published")

    logger.info(f"Done: {len(results)} OK, {errors} errors")
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
