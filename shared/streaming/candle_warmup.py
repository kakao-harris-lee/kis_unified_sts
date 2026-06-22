"""Shared per-symbol indicator-engine warmup (parquet → KIS REST + daily seed).

Used by the decoupled stock daemon (intraday universe-add) and the orchestrator
(startup prewarm). Best-effort: any failure seeds nothing and the symbol warms
from live ticks. REST is rate-limit guarded — see StockPrewarmConfig.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)

_CONFIG_FILE = "stock_prewarm.yaml"
_CONFIG_SECTION = "stock_prewarm"


@dataclass(frozen=True)
class StockPrewarmConfig:
    rest_enabled: bool = False
    parquet_minute_limit: int = 120
    daily_limit: int = 252
    rest_count: int = 30
    min_candles: int = 20
    max_prewarm_per_cycle: int = 5
    minute_lookback_days: int = 5
    daily_lookback_days: int = 400

    @classmethod
    def load(cls) -> "StockPrewarmConfig":
        try:
            from shared.config.loader import ConfigLoader

            raw = ConfigLoader.load(_CONFIG_FILE).get(_CONFIG_SECTION, {})
            return cls(
                rest_enabled=bool(raw.get("rest_enabled", cls.rest_enabled)),
                parquet_minute_limit=int(
                    raw.get("parquet_minute_limit", cls.parquet_minute_limit)
                ),
                daily_limit=int(raw.get("daily_limit", cls.daily_limit)),
                rest_count=int(raw.get("rest_count", cls.rest_count)),
                min_candles=int(raw.get("min_candles", cls.min_candles)),
                max_prewarm_per_cycle=int(
                    raw.get("max_prewarm_per_cycle", cls.max_prewarm_per_cycle)
                ),
                minute_lookback_days=int(
                    raw.get("minute_lookback_days", cls.minute_lookback_days)
                ),
                daily_lookback_days=int(
                    raw.get("daily_lookback_days", cls.daily_lookback_days)
                ),
            )
        except Exception:
            logger.warning("stock_prewarm.yaml load failed; using defaults")
            return cls()


class WarmupResult(NamedTuple):
    minute_seeded: int
    daily_seeded: int
    source: str  # "parquet" | "rest" | "none"


def _df_tail_to_candles(df: Any, tail: int) -> list[dict]:
    """Convert the most-recent ``tail`` rows of a bars DataFrame to seed dicts."""
    if df is None or len(df) == 0:
        return []
    df = df.iloc[-tail:]
    return [
        {
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": float(r.get("volume", 0) or 0),
        }
        for _, r in df.iterrows()
    ]


def _seed_daily(engine: Any, store: Any, symbol: str, cfg: StockPrewarmConfig) -> int:
    """Best-effort daily-candle seed (for daily RSI/SMA/MACD indicators)."""
    if store is None:
        return 0
    try:
        start = (
            (datetime.now(UTC) - timedelta(days=cfg.daily_lookback_days))
            .date()
            .isoformat()
        )
        df = store.get_daily_bars(symbol, start=start)
        candles = _df_tail_to_candles(df, cfg.daily_limit)
        if candles:
            engine.seed_daily_candles(symbol, candles)
        return len(candles)
    except Exception:
        logger.warning("daily prewarm read failed for %s", symbol)
        return 0


async def warmup_engine(
    engine: Any,
    symbol: str,
    *,
    store: Any | None = None,
    kis_client: Any | None = None,
    config: StockPrewarmConfig | None = None,
) -> WarmupResult:
    """Warm one symbol: parquet minute → KIS REST minute (guarded), plus daily seed.

    Best-effort and idempotent: already-warm symbols and all failures return
    ``WarmupResult(0, 0, "none")`` and the symbol warms from live ticks.
    """
    cfg = config or StockPrewarmConfig()
    try:
        if engine.is_warm(symbol):
            return WarmupResult(0, 0, "none")
    except Exception:
        return WarmupResult(0, 0, "none")

    minute_seeded = 0
    source = "none"

    # Tier 1: parquet minute bars (no rate limit).
    try:
        if store is not None:
            start = (
                (datetime.now(UTC) - timedelta(days=cfg.minute_lookback_days))
                .date()
                .isoformat()
            )
            candles = _df_tail_to_candles(
                store.get_minute_bars(symbol, start=start), cfg.parquet_minute_limit
            )
            if candles:
                engine.seed_candles(symbol, candles)
                minute_seeded = len(candles)
                source = "parquet"
    except Exception:
        logger.warning("parquet minute prewarm failed for %s", symbol)

    # Tier 2: KIS REST minute bars (only on parquet miss; rate-limit guarded).
    if minute_seeded == 0 and cfg.rest_enabled and kis_client is not None:
        try:
            if getattr(kis_client, "is_rate_limited", False):
                logger.debug("prewarm %s: skip KIS REST (rate limited)", symbol)
            else:
                candles = await asyncio.wait_for(
                    kis_client.get_minute_bars(symbol, count=cfg.rest_count),
                    timeout=5.0,
                )
                await asyncio.sleep(0.3)  # rate-limit pacing
                if candles:
                    engine.seed_candles(symbol, list(candles))
                    minute_seeded = len(candles)
                    source = "rest"
        except Exception:
            logger.warning("KIS REST prewarm failed for %s", symbol)

    if 0 < minute_seeded < cfg.min_candles:
        logger.warning(
            "prewarm %s: only %d minute candles (source=%s); under-initialised",
            symbol,
            minute_seeded,
            source,
        )

    daily_seeded = _seed_daily(engine, store, symbol, cfg)
    return WarmupResult(minute_seeded, daily_seeded, source)
