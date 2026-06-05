"""Shared parquet cold-start warmup helper for streaming indicator engines.

Extracted from services/decision_engine/main.py and
services/stock_strategy/main.py to eliminate duplication (DRY).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def warmup_engine_from_parquet(
    engine: Any, store: Any, symbol: str, *, lookback_minutes: int = 240
) -> None:
    """Seed the engine's 1-min candles from parquet so it is warm at startup.

    Best-effort: on any read error the engine simply warms from live ticks.

    Args:
        engine: :class:`StreamingIndicatorEngine` instance.
        store: :class:`ParquetMarketDataStore` instance (or compatible duck-
               typed store) with ``get_minute_bars(symbol, start=...)``.
        symbol: Symbol to warm (e.g. ``"A05"`` for futures, ``"005930"`` for
                stock).
        lookback_minutes: Number of 1-min bars to seed (default 240 = 4 h).

    Notes:
        ParquetMarketDataStore orders ASC; a bare ``limit=N`` would return the
        OLDEST N bars.  We bound the read to the last few calendar days via the
        ``start`` param and then take the tail (``df.iloc[-lookback_minutes:]``)
        so we always seed the MOST RECENT bars (fixed in #414).
    """
    start_bound = (datetime.now(UTC) - timedelta(days=5)).date().isoformat()
    try:
        df = store.get_minute_bars(symbol, start=start_bound)
    except Exception:
        logger.warning(
            "parquet warmup read failed for %s; warming from live ticks", symbol
        )
        return
    if df is None or len(df) == 0:
        return
    df = df.iloc[-lookback_minutes:]
    candles = [
        {
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": float(r.get("volume", 0) or 0),
        }
        for _, r in df.iterrows()
    ]
    engine.seed_candles(symbol, candles)
