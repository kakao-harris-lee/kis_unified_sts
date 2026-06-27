"""Historical Data Collection Module

과거 1분봉 OHLCV 데이터를 수집합니다.

Usage:
    # CLI - Futures
    sts backfill today
    sts backfill run --days 180
    sts backfill status

    # CLI - Stocks
    sts stock-backfill today
    sts stock-backfill run --days 7
    sts stock-backfill status

    # Python - Futures
    from shared.collector.historical import backfill, collect_today
    await backfill(days=180)
    await collect_today()

    # Python - Stocks
    from shared.collector.historical import backfill_stock_minute, collect_stock_minute_today
    await backfill_stock_minute(days=7)
    await collect_stock_minute_today()
"""

from __future__ import annotations

from .backfill import (
    backfill,
    backfill_all,
    backfill_kospi200_index,
    backfill_kospi200f,
    collect_today,
    collect_today_all,
    collect_today_kospi200_index,
    collect_today_kospi200f,
    ensure_database,
    get_db_client,
    load_futures_minute_from_parquet,
)
from .calendar import (
    get_kst_now,
    get_previous_trading_day,
    get_trading_days_range,
    is_after_market_close,
    is_trading_day,
    trading_day_lag,
)
from .futures import (
    KOSPI200F_FRONT_CODE,
    get_active_codes_for_date,
    make_code,
    parse_code,
)
from .stock import (
    backfill_stock_minute,
    collect_stock_minute_today,
    ensure_stock_database,
    get_stock_codes_from_db,
    get_stock_collection_status,
    get_stock_db_client,
    load_stock_minute_from_parquet,
)
from .stock_universe import STOCK_UNIVERSE

__all__ = [
    # Futures backfill functions
    "backfill",
    "collect_today",
    "backfill_kospi200_index",
    "collect_today_kospi200_index",
    "backfill_kospi200f",
    "collect_today_kospi200f",
    "backfill_all",
    "collect_today_all",
    "get_db_client",
    "ensure_database",
    "load_futures_minute_from_parquet",
    # Stock backfill functions
    "STOCK_UNIVERSE",
    "collect_stock_minute_today",
    "backfill_stock_minute",
    "get_stock_codes_from_db",
    "get_stock_collection_status",
    "get_stock_db_client",
    "ensure_stock_database",
    "load_stock_minute_from_parquet",
    # Calendar functions
    "is_trading_day",
    "is_after_market_close",
    "get_trading_days_range",
    "get_previous_trading_day",
    "trading_day_lag",
    "get_kst_now",
    # Futures functions
    "get_active_codes_for_date",
    "make_code",
    "parse_code",
    "KOSPI200F_FRONT_CODE",
]
