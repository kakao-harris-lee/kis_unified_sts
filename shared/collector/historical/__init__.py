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

from .backfill import (
    backfill,
    collect_today,
    backfill_kospi200_index,
    collect_today_kospi200_index,
    backfill_kospi200f,
    collect_today_kospi200f,
    backfill_all,
    collect_today_all,
    get_db_client,
    ensure_database,
)
from .calendar import (
    is_trading_day,
    is_after_market_close,
    get_trading_days_range,
    get_kst_now,
)
from .futures import (
    get_active_codes_for_date,
    make_code,
    parse_code,
    KOSPI200F_FRONT_CODE,
)
from .stock import (
    STOCK_UNIVERSE,
    collect_stock_minute_today,
    backfill_stock_minute,
    get_stock_collection_status,
    get_stock_db_client,
    ensure_stock_database,
)

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
    # Stock backfill functions
    "STOCK_UNIVERSE",
    "collect_stock_minute_today",
    "backfill_stock_minute",
    "get_stock_collection_status",
    "get_stock_db_client",
    "ensure_stock_database",
    # Calendar functions
    "is_trading_day",
    "is_after_market_close",
    "get_trading_days_range",
    "get_kst_now",
    # Futures functions
    "get_active_codes_for_date",
    "make_code",
    "parse_code",
    "KOSPI200F_FRONT_CODE",
]
