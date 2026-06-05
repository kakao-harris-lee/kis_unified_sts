"""Daily Indicator Scanner — pre-compute daily indicators for paper trading.

Reads daily candles from Parquet market-data files, computes SMA/RSI/ATR/
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
import asyncio
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
from shared.scanner.trade_trend_priority import TradeTrendPriorityRanker
from shared.storage.config import StorageConfig
from shared.storage.market_data_store import ParquetMarketDataStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("daily_indicator_scanner")

_REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SYMBOLS = [item["code"] for item in STOCK_UNIVERSE]

REDIS_KEY = "system:daily_indicators:latest"
DAILY_WATCHLIST_COMPAT_KEY = "system:daily_watchlist:latest"
REDIS_TTL = 86400  # 24h
DEFAULT_REDIS_CANDIDATE_KEYS = (
    "system:trade_targets:latest",
    "system:universe:latest",
    "system:dip_candidates:latest",
    "system:daily_watchlist:latest",
    "system:llm_quality:latest",
)
BACKFILL_RETRYABLE_FAILURES = {"no_data", "stale_data", "insufficient_data"}


def _load_strategy_watchlist_size(default: int = 40) -> int:
    """Load the daily watchlist cap from config, falling back safely."""
    try:
        from shared.config.loader import ConfigLoader

        cfg = ConfigLoader.load("daily_scanner.yaml")
        return int(cfg.get("max_watchlist_size", default))
    except Exception as exc:  # noqa: BLE001 - standalone cron must keep running
        logger.debug("daily strategy watchlist size fallback: %s", exc)
        return default


def _load_repo_env() -> None:
    """Load repo-local .env for standalone cron/manual runs."""
    load_dotenv(_REPO_ROOT / ".env", override=False)


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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


def _normalize_strategy_watchlist(value: Any) -> dict[str, list[str]]:
    """Normalize ``strategies`` payloads to strategy -> unique non-empty codes."""
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, list[str]] = {}
    for strategy_name, values in value.items():
        name = str(strategy_name).strip()
        if not name or not isinstance(values, list):
            continue
        codes = _dedupe_symbols(str(code).strip() for code in values)
        normalized[name] = codes
    return normalized


def _load_existing_daily_watchlist(
    redis_client: Any, today: date
) -> dict[str, list[str]]:
    """Load same-day strategy watchlist so daily indicators do not erase it."""
    try:
        existing = _json_loads(redis_client.get(DAILY_WATCHLIST_COMPAT_KEY))
    except Exception as exc:  # noqa: BLE001 - best-effort compatibility path
        logger.debug("Failed to read existing daily watchlist: %s", exc)
        return {}

    timestamp = str(existing.get("timestamp") or existing.get("as_of_date") or "")
    if timestamp != today.isoformat():
        return {}
    return _normalize_strategy_watchlist(existing.get("strategies"))


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


def load_enabled_daily_strategies() -> list[Any]:
    """Create enabled stock strategies whose configured timeframe is daily."""
    try:
        from shared.config.loader import ConfigLoader
        from shared.strategy.registry import (
            StrategyFactory,
            register_builtin_components,
        )

        register_builtin_components()
        configs = ConfigLoader.load_all_strategies("stock", enabled_only=True)
    except Exception as exc:  # noqa: BLE001 - optional strategy candidate path
        logger.debug("daily strategy configs unavailable: %s", exc)
        return []

    strategies: list[Any] = []
    for config in configs:
        strategy_cfg = config.get("strategy", {}) if isinstance(config, dict) else {}
        if str(strategy_cfg.get("timeframe", "")).lower() != "daily":
            continue
        try:
            strategies.append(StrategyFactory.create(config))
        except Exception as exc:  # noqa: BLE001 - skip one bad strategy
            name = strategy_cfg.get("name", "unknown")
            logger.warning("Failed to create daily strategy %s: %s", name, exc)
    return strategies


async def build_strategy_candidate_watchlist(
    indicators: dict[str, dict[str, Any]],
    *,
    strategies: Iterable[Any] | None = None,
    timestamp: datetime | None = None,
    max_candidates: int | None = None,
) -> dict[str, list[str]]:
    """Evaluate enabled daily strategies against precomputed indicators.

    This reuses the strategy entry logic instead of duplicating strategy gates in
    the scanner. The output is a compact watchlist that the orchestrator can
    merge into its dynamic universe before market open.
    """
    if strategies is None:
        strategies = load_enabled_daily_strategies()

    timestamp = timestamp or datetime.now()
    max_candidates = max_candidates if max_candidates is not None else len(indicators)

    try:
        from shared.strategy.base import EntryContext
    except Exception as exc:  # noqa: BLE001
        logger.debug("EntryContext unavailable for daily strategy watchlist: %s", exc)
        return {}

    watchlist: dict[str, list[str]] = {}
    for strategy in strategies:
        name = str(getattr(strategy, "name", "") or "").strip()
        if not name:
            continue

        candidates: list[str] = []
        for symbol, raw_indicators in indicators.items():
            if not isinstance(raw_indicators, dict):
                continue
            context_data = dict(raw_indicators)
            context_data.setdefault("code", symbol)
            context_data.setdefault("name", symbol)
            if "daily_close" in raw_indicators:
                context_data.setdefault("close", raw_indicators["daily_close"])

            try:
                signal = await strategy.check_entry(
                    EntryContext(
                        market_data=context_data,
                        indicators=dict(raw_indicators),
                        timestamp=timestamp,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - one symbol must not abort
                logger.debug(
                    "daily strategy candidate check failed %s/%s: %s", name, symbol, exc
                )
                continue

            if signal is not None:
                candidates.append(symbol)
                if len(candidates) >= max_candidates:
                    break

        watchlist[name] = candidates

    return watchlist


def get_market_data_store():
    """Return the Parquet market-data store."""
    _load_repo_env()
    storage_config = StorageConfig.load_or_default()
    return ParquetMarketDataStore(
        storage_config.market_data.parquet.root,
        asset_class="stock",
    )


def load_daily_candles(
    client,
    symbol: str,
    days: int = 250,
    quality_config: DailyCandleQualityConfig | None = None,
) -> pd.DataFrame:
    """Load recent daily candles from Parquet."""
    quality_config = quality_config or load_daily_quality_config()
    fetch_limit = quality_fetch_limit(days, quality_config)
    df = client.get_daily_bars(symbol, limit=int(fetch_limit))
    if df.empty:
        return pd.DataFrame()

    df = df.rename(columns={"datetime": "date"})
    return clean_daily_candle_frame(df, config=quality_config, limit=days)


def load_symbol_indicators(
    client: Any,
    symbol: str,
    *,
    days: int,
    quality_config: DailyCandleQualityConfig,
    expected_latest: date | None,
    max_stale_trading_days: int,
) -> tuple[dict[str, Any] | None, str | None]:
    """Load, validate, and compute one symbol's daily indicators."""
    try:
        df = load_daily_candles(
            client,
            symbol,
            days=days,
            quality_config=quality_config,
        )
        if df.empty:
            return None, "no_data"

        if not is_fresh_daily_data(
            df,
            expected_latest=expected_latest,
            max_stale_trading_days=max_stale_trading_days,
        ):
            latest = latest_candle_date(df)
            lag = (
                trading_day_lag(latest, expected_latest)
                if latest and expected_latest
                else None
            )
            return (
                None,
                (
                    "stale_data "
                    f"latest={latest} expected={expected_latest} "
                    f"lag={lag} max={max_stale_trading_days}"
                ),
            )

        indicators = compute_indicators(df)
        if indicators is None:
            return None, f"insufficient_data bars={len(df)}"

        return indicators, None
    except Exception as exc:  # noqa: BLE001 - scanner must aggregate per-symbol errors
        return None, f"error {exc}"


def _failure_category(reason: str | None) -> str:
    return str(reason or "").split(" ", 1)[0]


async def backfill_missing_candidate_candles(
    symbols: list[str],
    *,
    days: int,
    max_symbols: int,
) -> int:
    """Best-effort KIS daily backfill for missing dynamic candidates."""
    limited = _dedupe_symbols(symbols)[: max(0, int(max_symbols))]
    if not limited:
        return 0
    _load_repo_env()
    os.environ.setdefault(
        "STOCK_RATE_LIMIT",
        os.getenv("STOCK_DAILY_BACKFILL_RATE_LIMIT", "1"),
    )
    os.environ.setdefault(
        "STOCK_MAX_CONCURRENCY",
        os.getenv("STOCK_DAILY_BACKFILL_MAX_CONCURRENCY", "1"),
    )
    from shared.collector.historical.daily_stock import collect_daily_candles

    logger.info(
        "Backfilling daily candles for %d Redis candidate symbols "
        "(days=%d, rate=%s/s, concurrency=%s)",
        len(limited),
        days,
        os.getenv("STOCK_RATE_LIMIT"),
        os.getenv("STOCK_MAX_CONCURRENCY"),
    )
    return await collect_daily_candles(
        codes=limited, days=max(1, int(days)), verbose=False
    )


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
    consensus_rsi_period: int = 14,
    atr_period: int = 22,
    lookback_period: int = 22,
    mid_trend_lookback: int = 5,
    volume_lookback: int = 20,
    williams_r_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
) -> dict[str, float] | None:
    """Compute daily indicators from a DataFrame. Returns latest values or None."""
    min_required = max(
        sma_mid,
        rsi_period + 1,
        consensus_rsi_period + 1,
        atr_period + 1,
        lookback_period,
        volume_lookback,
        williams_r_period,
        macd_slow + macd_signal,
    )
    if len(df) < min_required:
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
    consensus_rsi_series = compute_rsi(close, consensus_rsi_period)

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

    williams_high = high.rolling(
        window=max(1, int(williams_r_period)),
        min_periods=max(1, int(williams_r_period)),
    ).max()
    williams_low = low.rolling(
        window=max(1, int(williams_r_period)),
        min_periods=max(1, int(williams_r_period)),
    ).min()
    williams_denominator = (williams_high - williams_low).replace(0, np.nan)
    williams_r_series = (williams_high - close) / williams_denominator * -100.0

    ema_fast = close.ewm(span=max(1, int(macd_fast)), adjust=False).mean()
    ema_slow = close.ewm(span=max(1, int(macd_slow)), adjust=False).mean()
    macd_line = ema_fast - ema_slow
    macd_signal_line = macd_line.ewm(
        span=max(1, int(macd_signal)),
        adjust=False,
    ).mean()
    macd_hist_series = macd_line - macd_signal_line

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
        # Daily-prefixed technical consensus fields avoid clobbering intraday
        # indicators in the orchestrator while still feeding daily strategies.
        "daily_rsi_14": safe_float(consensus_rsi_series.iloc[latest]),
        "daily_prev_rsi_14": (
            safe_float(consensus_rsi_series.iloc[latest - 1]) if latest >= 1 else None
        ),
        "daily_williams_r_14": safe_float(williams_r_series.iloc[latest]),
        "daily_prev_williams_r_14": (
            safe_float(williams_r_series.iloc[latest - 1]) if latest >= 1 else None
        ),
        "daily_macd_hist": safe_float(macd_hist_series.iloc[latest]),
        "daily_prev_macd_hist": (
            safe_float(macd_hist_series.iloc[latest - 1]) if latest >= 1 else None
        ),
    }

    # Include raw daily series for VR composite strategy (most recent 80 bars)
    series_len = min(len(df), 80)
    result["daily_closes"] = close.iloc[-series_len:].tolist()
    result["daily_volumes"] = df["volume"].astype(int).iloc[-series_len:].tolist()

    # Remove None scalar values (keep lists)
    return {k: v for k, v in result.items() if v is not None}


# Futures symbols whose daily indicators feed Setup A/C daily_regime_trend_filter.
# Reads from kospi.kospi200f_1m (1m bars) and aggregates to daily candles inline —
# `market.daily_candles` does not carry futures.
FUTURES_DAILY_SYMBOLS: tuple[str, ...] = ("101S6000",)


def load_futures_daily_candles(
    client: Any, symbol: str, days: int = 250
) -> pd.DataFrame:
    """Aggregate kospi.kospi200f_1m intraday bars to daily candles.

    Returns columns: date, open, high, low, close, volume (one row per session).
    """
    query = """
        SELECT
            toDate(datetime) AS date,
            argMin(open, datetime) AS open,
            max(high) AS high,
            min(low) AS low,
            argMax(close, datetime) AS close,
            sum(volume) AS volume
        FROM kospi.kospi200f_1m
        WHERE code = {code:String}
        GROUP BY date
        ORDER BY date DESC
        LIMIT {limit:UInt32}
    """
    result = client.query(query, parameters={"code": symbol, "limit": int(days)})
    if not result.result_rows:
        return pd.DataFrame()
    df = pd.DataFrame(
        result.result_rows,
        columns=["date", "open", "high", "low", "close", "volume"],
    )
    # Drop intraday-only "phantom days" (single tick before market close):
    # require at least 30 minutes of trading to count as a real session.
    return df.sort_values("date").reset_index(drop=True)


def compute_futures_daily_indicators(df: pd.DataFrame) -> dict[str, float] | None:
    """Compute daily indicators required by daily_regime_trend_filter.

    Only emits the fields the gate actually uses (``daily_close``,
    ``daily_ema_20``, ``daily_ema_20_prev``, ``daily_ema_60``, ``daily_rsi_14``)
    plus a small set of conveniences (``daily_sma_20``, ``daily_sma_60``).
    Returns None when there is not enough history (need >= 60 daily bars).
    """
    if len(df) < 60:
        return None
    close = df["close"].astype(float)
    ema_20 = close.ewm(span=20, adjust=False).mean()
    ema_60 = close.ewm(span=60, adjust=False).mean()
    sma_20 = close.rolling(window=20, min_periods=20).mean()
    sma_60 = close.rolling(window=60, min_periods=60).mean()
    rsi_14 = compute_rsi(close, 14)

    def safe_float(val: Any) -> float | None:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return None
        return float(val)

    latest = len(df) - 1
    result: dict[str, Any] = {
        "daily_close": safe_float(close.iloc[latest]),
        "daily_ema_20": safe_float(ema_20.iloc[latest]),
        "daily_ema_20_prev": (
            safe_float(ema_20.iloc[latest - 1]) if latest >= 1 else None
        ),
        "daily_ema_60": safe_float(ema_60.iloc[latest]),
        "daily_sma_20": safe_float(sma_20.iloc[latest]),
        "daily_sma_60": safe_float(sma_60.iloc[latest]),
        "daily_rsi_14": safe_float(rsi_14.iloc[latest]),
    }
    return {k: v for k, v in result.items() if v is not None}


def scan_futures_symbols(
    client: Any, symbols: Iterable[str]
) -> dict[str, dict[str, Any]]:
    """Compute daily indicators for the configured futures symbols.

    Returns a dict ready to merge into the scanner's stock-symbol payload —
    the orchestrator already keys by symbol, so a single Redis key carries both
    stock and futures daily indicators (~unchanged consumer code path).
    """
    out: dict[str, dict[str, Any]] = {}
    for sym in symbols:
        try:
            df = load_futures_daily_candles(client, sym)
            if df.empty:
                logger.warning("futures daily scan: %s has no 1m history", sym)
                continue
            inds = compute_futures_daily_indicators(df)
            if inds is None:
                logger.warning(
                    "futures daily scan: %s has %d daily bars (<60 minimum)",
                    sym,
                    len(df),
                )
                continue
            out[sym] = inds
            logger.info(
                "futures daily indicators: %s close=%.2f ema20=%.2f ema60=%.2f rsi14=%.1f",
                sym,
                inds.get("daily_close", 0.0),
                inds.get("daily_ema_20", 0.0),
                inds.get("daily_ema_60", 0.0),
                inds.get("daily_rsi_14", 0.0),
            )
        except Exception as exc:  # noqa: BLE001 - per-symbol best effort
            logger.warning("futures daily scan failed for %s: %s", sym, exc)
    return out


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

    strategies = (metadata or {}).get("strategies")
    if isinstance(strategies, dict):
        normalized = _normalize_strategy_watchlist(strategies)
        existing = _load_existing_daily_watchlist(redis_client, datetime.now().date())
        merged = {**existing, **normalized}
        if not merged:
            return

        compat_payload = {
            "timestamp": datetime.now().date().isoformat(),
            "computed_at": json.loads(payload).get("computed_at"),
            "source": REDIS_KEY,
            "strategies": merged,
            "counts": {name: len(codes) for name, codes in merged.items()},
        }
        watchlist_metadata = (metadata or {}).get("metadata")
        if isinstance(watchlist_metadata, dict) and watchlist_metadata:
            compat_payload["metadata"] = watchlist_metadata
        sources = (metadata or {}).get("sources")
        if isinstance(sources, dict) and sources:
            compat_payload["sources"] = sources
        redis_client.set(
            DAILY_WATCHLIST_COMPAT_KEY,
            json.dumps(compat_payload, ensure_ascii=False),
            ex=REDIS_TTL,
        )
        logger.info(
            "Published daily strategy watchlist compatibility payload to Redis (%s)",
            DAILY_WATCHLIST_COMPAT_KEY,
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
    parser.add_argument(
        "--build-strategy-watchlist",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Evaluate enabled daily stock strategies and embed their candidate "
            "watchlists in the Redis payload (default: true)"
        ),
    )
    parser.add_argument(
        "--strategy-watchlist-size",
        type=int,
        default=int(
            os.getenv(
                "STOCK_DAILY_STRATEGY_WATCHLIST_SIZE",
                str(_load_strategy_watchlist_size()),
            )
        ),
        help="Maximum symbols per embedded daily strategy watchlist",
    )
    parser.add_argument(
        "--backfill-missing-candidates",
        action=argparse.BooleanOptionalAction,
        default=_env_flag("STOCK_DAILY_BACKFILL_MISSING_CANDIDATES", True),
        help=(
            "Backfill missing/stale Redis candidate daily candles before publishing "
            "(default: true)"
        ),
    )
    parser.add_argument(
        "--backfill-days",
        type=int,
        default=int(os.getenv("STOCK_DAILY_BACKFILL_DAYS", "100")),
        help="Trading-day lookback for on-demand candidate daily backfill",
    )
    parser.add_argument(
        "--backfill-max-symbols",
        type=int,
        default=int(os.getenv("STOCK_DAILY_BACKFILL_MAX_SYMBOLS", "30")),
        help="Maximum Redis candidate symbols to backfill per scanner run",
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

    client = get_market_data_store()
    quality_config = load_daily_quality_config()

    results: dict[str, dict] = {}
    failures: dict[str, str] = {}

    for symbol in symbols:
        indicators, reason = load_symbol_indicators(
            client,
            symbol,
            days=args.days,
            quality_config=quality_config,
            expected_latest=expected_latest,
            max_stale_trading_days=args.max_stale_trading_days,
        )
        if indicators is not None:
            results[symbol] = indicators
            logger.debug("  %s: OK", symbol)
        else:
            failures[symbol] = reason or "unknown"
            logger.warning("  %s: %s", symbol, failures[symbol])

    backfill_attempted_count = 0
    backfill_rows = 0
    backfill_retry_success_count = 0
    redis_candidate_set = set(redis_candidates)
    backfill_symbols = [
        symbol
        for symbol, reason in failures.items()
        if symbol in redis_candidate_set
        and _failure_category(reason) in BACKFILL_RETRYABLE_FAILURES
    ]
    if args.backfill_missing_candidates and backfill_symbols:
        limited = backfill_symbols[: max(0, args.backfill_max_symbols)]
        backfill_attempted_count = len(limited)
        try:
            backfill_rows = asyncio.run(
                backfill_missing_candidate_candles(
                    limited,
                    days=args.backfill_days,
                    max_symbols=args.backfill_max_symbols,
                )
            )
        except Exception as exc:  # noqa: BLE001 - publish original partial results
            logger.warning("Candidate daily backfill failed: %s", exc)
            backfill_rows = 0

        for symbol in limited:
            indicators, reason = load_symbol_indicators(
                client,
                symbol,
                days=args.days,
                quality_config=quality_config,
                expected_latest=expected_latest,
                max_stale_trading_days=args.max_stale_trading_days,
            )
            if indicators is not None:
                results[symbol] = indicators
                failures.pop(symbol, None)
                backfill_retry_success_count += 1
                logger.info("  %s: OK after daily backfill", symbol)
            else:
                failures[symbol] = reason or "unknown"
                logger.warning(
                    "  %s: still unavailable after backfill: %s",
                    symbol,
                    failures[symbol],
                )

    errors = len(failures)

    strategy_candidates: dict[str, list[str]] = {}
    watchlist_metadata: dict[str, dict[str, Any]] = {}
    trade_trend_priority_summary: dict[str, Any] = {}
    if results and args.build_strategy_watchlist:
        strategy_candidates = asyncio.run(
            build_strategy_candidate_watchlist(
                results,
                max_candidates=max(1, args.strategy_watchlist_size),
            )
        )
        if strategy_candidates:
            logger.info(
                "Built daily strategy watchlists: %s",
                ", ".join(
                    f"{name}={len(codes)}"
                    for name, codes in sorted(strategy_candidates.items())
                ),
            )
            ranker = TradeTrendPriorityRanker.from_default_config()
            (
                strategy_candidates,
                watchlist_metadata,
                trade_trend_priority_summary,
            ) = ranker.rank_watchlists(strategy_candidates)

    # Augment with futures daily indicators (Setup A/C daily_regime_trend_filter
    # consumes daily_close / daily_ema_20 / daily_ema_60 / daily_rsi_14 for
    # KOSPI200 futures; the stock scan above never covers these symbols).
    try:
        futures_results = scan_futures_symbols(client, FUTURES_DAILY_SYMBOLS)
        if futures_results:
            results.update(futures_results)
    except Exception as exc:  # noqa: BLE001 - keep stock publishing on failure
        logger.warning("futures daily scan aborted: %s", exc)

    if results:
        strategy_counts = {k: len(v) for k, v in strategy_candidates.items()}
        publish_to_redis(
            results,
            metadata={
                "requested_symbol_count": len(symbols),
                "baseline_symbol_count": baseline_count,
                "redis_candidate_count": len(redis_candidates),
                "error_count": errors,
                "backfill_missing_candidates": bool(args.backfill_missing_candidates),
                "backfill_attempted_count": backfill_attempted_count,
                "backfill_rows": backfill_rows,
                "backfill_retry_success_count": backfill_retry_success_count,
                "expected_latest": (
                    expected_latest.isoformat() if expected_latest else None
                ),
                "max_stale_trading_days": args.max_stale_trading_days,
                "strategies": strategy_candidates,
                "strategy_counts": strategy_counts,
                "strategy_watchlist_size": max(1, args.strategy_watchlist_size),
                "metadata": watchlist_metadata,
                "sources": {
                    "trade_trend_priority": trade_trend_priority_summary,
                },
            },
        )
    else:
        logger.warning("No indicators computed — nothing published")

    logger.info(f"Done: {len(results)} OK, {errors} errors")
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
