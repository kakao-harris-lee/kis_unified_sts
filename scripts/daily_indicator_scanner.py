"""Daily Indicator Scanner — pre-compute daily indicators for paper trading.

Reads daily candles from ClickHouse `market.daily_candles`, computes SMA/RSI/ATR/
Highest High per symbol, and publishes results to Redis for the TradingOrchestrator.
By default, it scans the baseline stock universe plus recent Redis candidates from
the screener/fusion pipeline so dynamic trading targets have daily indicator
coverage before the orchestrator admits them.

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
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from shared.collector.historical.calendar import (
    get_previous_trading_day,
    trading_day_lag,
)
from shared.collector.historical.daily_quality import (
    DailyCandleQualityConfig,
    clean_daily_candle_frame,
    load_daily_quality_config,
    quality_fetch_limit,
)
from shared.collector.historical.stock_universe import STOCK_UNIVERSE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("daily_indicator_scanner")

_REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SYMBOLS = [item["code"] for item in STOCK_UNIVERSE]

REDIS_KEY = "system:daily_indicators:latest"
REDIS_TTL = 86400  # 24h
DEFAULT_REDIS_CANDIDATE_KEYS = (
    "system:trade_targets:latest",
    "system:universe:latest",
    "system:dip_candidates:latest",
    "system:daily_watchlist:latest",
    "system:llm_quality:latest",
)


def _load_repo_env() -> None:
    """Load repo-local .env for standalone cron/manual runs."""
    load_dotenv(_REPO_ROOT / ".env", override=False)


def _dedupe_symbols(symbols: Iterable[str]) -> list[str]:
    """Return symbols in first-seen order, normalized to non-empty strings."""
    seen: set[str] = set()
    deduped: list[str] = []
    for raw in symbols:
        symbol = str(raw).strip()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        deduped.append(symbol)
    return deduped


def _json_loads(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _extend_codes(codes: list[str], values: Any) -> None:
    if not isinstance(values, list):
        return
    for value in values:
        symbol = str(value).strip()
        if symbol:
            codes.append(symbol)


def extract_candidate_symbols(payload: dict[str, Any]) -> list[str]:
    """Extract stock codes from known Redis pipeline snapshot shapes."""
    codes: list[str] = []
    _extend_codes(codes, payload.get("codes"))
    _extend_codes(codes, payload.get("symbols"))
    _extend_codes(codes, payload.get("final_codes"))

    strategies = payload.get("strategies")
    if isinstance(strategies, dict):
        for values in strategies.values():
            _extend_codes(codes, values)

    candidates = payload.get("candidates")
    if isinstance(candidates, list):
        for item in candidates:
            if isinstance(item, dict):
                symbol = str(item.get("code", "")).strip()
                if symbol:
                    codes.append(symbol)
            else:
                symbol = str(item).strip()
                if symbol:
                    codes.append(symbol)

    return _dedupe_symbols(codes)


def load_redis_candidate_symbols(
    *,
    redis_client: Any | None = None,
    keys: Iterable[str] = DEFAULT_REDIS_CANDIDATE_KEYS,
) -> list[str]:
    """Load recent dynamic candidate symbols from Redis snapshots.

    This is best-effort: stale/missing Redis should never block the baseline
    scanner because the fixed universe still provides a safe fallback.
    """
    try:
        if redis_client is None:
            from shared.streaming.client import RedisClient

            redis_client = RedisClient.get_client()
    except Exception as exc:  # noqa: BLE001 - optional runtime dependency
        logger.debug("Redis candidate source unavailable: %s", exc)
        return []

    codes: list[str] = []
    for key in keys:
        key = str(key).strip()
        if not key:
            continue
        try:
            payload = _json_loads(redis_client.get(key))
        except Exception as exc:  # noqa: BLE001 - ignore malformed optional source
            logger.debug("Failed to read Redis candidate key %s: %s", key, exc)
            continue
        codes.extend(extract_candidate_symbols(payload))

    return _dedupe_symbols(codes)


def get_clickhouse_client():
    """Create ClickHouse client from env vars."""
    import clickhouse_connect

    _load_repo_env()
    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
    )


def load_daily_candles(
    client,
    symbol: str,
    days: int = 250,
    quality_config: DailyCandleQualityConfig | None = None,
) -> pd.DataFrame:
    """Load recent daily candles from ClickHouse."""
    quality_config = quality_config or load_daily_quality_config()
    fetch_limit = quality_fetch_limit(days, quality_config)
    query = """
        SELECT
            code,
            date,
            argMax(open, created_at) AS open,
            argMax(high, created_at) AS high,
            argMax(low, created_at) AS low,
            argMax(close, created_at) AS close,
            argMax(volume, created_at) AS volume
        FROM market.daily_candles
        WHERE code = {code:String}
        GROUP BY code, date
        ORDER BY date DESC
        LIMIT {limit:UInt32}
    """
    result = client.query(query, parameters={"code": symbol, "limit": int(fetch_limit)})
    if not result.result_rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        result.result_rows,
        columns=["code", "date", "open", "high", "low", "close", "volume"],
    )
    return clean_daily_candle_frame(df, config=quality_config, limit=days)


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
    volume_lookback: int = 20,
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
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
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
    volume_avg = (
        df["volume"]
        .astype(float)
        .shift(1)
        .rolling(window=max(1, int(volume_lookback)), min_periods=1)
        .mean()
    )
    volume_ratio = safe_float(
        df["volume"].astype(float).iloc[latest] / volume_avg.iloc[latest]
        if volume_avg.iloc[latest] > 0
        else None
    )

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
        "daily_volume_ratio": volume_ratio,
    }

    # Include raw daily series for VR composite strategy (most recent 80 bars)
    series_len = min(len(df), 80)
    result["daily_closes"] = close.iloc[-series_len:].tolist()
    result["daily_volumes"] = df["volume"].astype(int).iloc[-series_len:].tolist()

    # Remove None scalar values (keep lists)
    return {k: v for k, v in result.items() if v is not None}


def publish_to_redis(
    indicators: dict[str, dict],
    redis_client=None,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Publish indicator dict to Redis."""
    if redis_client is None:
        from shared.streaming.client import RedisClient

        redis_client = RedisClient.get_client()

    payload: dict[str, Any] = {
        "indicators": indicators,
        "computed_at": datetime.now().isoformat(),
        "symbol_count": len(indicators),
    }
    if metadata:
        payload.update(metadata)

    payload = json.dumps(
        payload,
        ensure_ascii=False,
    )
    redis_client.set(REDIS_KEY, payload, ex=REDIS_TTL)
    logger.info(
        f"Published daily indicators for {len(indicators)} symbols to Redis ({REDIS_KEY})"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Pre-compute daily indicators for paper trading"
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default="",
        help="Comma-separated symbol codes (default: stock universe)",
    )
    parser.add_argument(
        "--days", type=int, default=250, help="Number of daily bars to load"
    )
    parser.add_argument(
        "--max-stale-trading-days",
        type=int,
        default=int(os.getenv("STOCK_DAILY_MAX_STALE_TRADING_DAYS", "1")),
        help="Maximum allowed trading-day lag versus previous trading day",
    )
    parser.add_argument(
        "--include-redis-candidates",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Include recent Redis candidates from fusion/screener snapshots "
            "(default: true)"
        ),
    )
    parser.add_argument(
        "--redis-candidate-keys",
        type=str,
        default=os.getenv(
            "STOCK_DAILY_REDIS_CANDIDATE_KEYS",
            ",".join(DEFAULT_REDIS_CANDIDATE_KEYS),
        ),
        help="Comma-separated Redis keys to scan for dynamic stock candidates",
    )
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
    baseline_count = len(_dedupe_symbols(symbols))
    redis_candidates: list[str] = []
    if args.include_redis_candidates:
        redis_keys = [k.strip() for k in args.redis_candidate_keys.split(",")]
        redis_candidates = load_redis_candidate_symbols(keys=redis_keys)
        if redis_candidates:
            logger.info(
                "Loaded %d Redis candidate symbols from %d keys",
                len(redis_candidates),
                len([k for k in redis_keys if k]),
            )
    symbols = _dedupe_symbols([*symbols, *redis_candidates])

    expected_latest = get_previous_trading_day()
    logger.info(
        "Computing daily indicators for %d symbols "
        "(baseline=%d redis_candidates=%d, last %d days, expected_latest=%s)",
        len(symbols),
        baseline_count,
        len(redis_candidates),
        args.days,
        expected_latest,
    )

    client = get_clickhouse_client()
    quality_config = load_daily_quality_config()

    results: dict[str, dict] = {}
    errors = 0

    for symbol in symbols:
        try:
            df = load_daily_candles(
                client,
                symbol,
                days=args.days,
                quality_config=quality_config,
            )
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
        publish_to_redis(
            results,
            metadata={
                "requested_symbol_count": len(symbols),
                "baseline_symbol_count": baseline_count,
                "redis_candidate_count": len(redis_candidates),
                "error_count": errors,
                "expected_latest": (
                    expected_latest.isoformat() if expected_latest else None
                ),
                "max_stale_trading_days": args.max_stale_trading_days,
            },
        )
    else:
        logger.warning("No indicators computed — nothing published")

    logger.info(f"Done: {len(results)} OK, {errors} errors")
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
