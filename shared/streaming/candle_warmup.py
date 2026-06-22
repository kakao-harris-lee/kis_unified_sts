"""Shared per-symbol indicator-engine warmup (parquet → KIS REST + daily seed).

Used by the decoupled stock daemon (intraday universe-add) and the orchestrator
(startup prewarm). Best-effort: any failure seeds nothing and the symbol warms
from live ticks. REST is rate-limit guarded — see StockPrewarmConfig.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

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
