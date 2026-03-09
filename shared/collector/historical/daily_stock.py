"""
Stock Daily Data Collection Module

주식 일봉 데이터를 수집합니다.

Usage:
    # CLI
    sts stock-backfill daily --days 100
    sts stock-backfill daily-status

    # Python
    from shared.collector.historical.daily_stock import collect_daily_candles
    await collect_daily_candles(days=100)
"""
import os
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import List, Tuple, Dict, Any

import httpx
import clickhouse_connect

from shared.config.secrets import SecretsManager
from .calendar import get_trading_days_range
from .stock import (
    StockKISToken,
    _get_rate_limiter,
    _get_semaphore,
    STOCK_UNIVERSE,
    _get_clickhouse_config,
    get_stock_db_client,
    ensure_stock_database,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

MAX_DAILY_DAYS = int(os.getenv("STOCK_DAILY_MAX_DAYS", "100"))


# =============================================================================
# Database Operations
# =============================================================================

def ensure_daily_candles_table():
    """Ensure daily_candles table exists."""
    config = _get_clickhouse_config()
    kwargs = {
        "host": config["host"],
        "port": config["port"],
        "username": config["user"],
        "password": config["password"],
        "secure": config["secure"],
        "verify": config["verify"],
    }
    if config.get("ca_cert"):
        kwargs["ca_cert"] = config["ca_cert"]
    client = clickhouse_connect.get_client(**kwargs)

    # Create database
    client.command(f"CREATE DATABASE IF NOT EXISTS {config['database']}")

    # Switch to database
    client.command(f"USE {config['database']}")

    # Create daily_candles table
    client.command("""
        CREATE TABLE IF NOT EXISTS daily_candles (
            code String,
            date Date,
            open Float64,
            high Float64,
            low Float64,
            close Float64,
            volume UInt64,
            value UInt64,
            change_rate Float64
        ) ENGINE = ReplacingMergeTree()
        ORDER BY (code, date)
        PARTITION BY toYYYYMM(date)
    """)

    client.close()
    logger.debug("Daily candles table ensured")


def insert_daily_candles_batch(db_client, rows: List[Tuple], table_name: str = "daily_candles"):
    """Insert daily candles batch."""
    if not rows:
        return 0

    db_client.insert(
        table_name,
        rows,
        column_names=["code", "date", "open", "high", "low", "close", "volume", "value", "change_rate"],
    )
    return len(rows)


def delete_daily_candles_range(db_client, code: str, start_date: date, end_date: date) -> None:
    """Delete existing rows for a code/date range to avoid duplicates."""
    if not code or not isinstance(start_date, date) or not isinstance(end_date, date):
        return
    if not str(code).isalnum():
        raise ValueError(f"Invalid code: {code}")
    db_client.command(
        "ALTER TABLE daily_candles DELETE "
        "WHERE code = {code:String} AND date >= {start:Date} AND date <= {end:Date}",
        parameters={"code": code, "start": start_date, "end": end_date},
    )


def delete_daily_candles_batch(
    db_client, codes: List[str], start_date: date, end_date: date
) -> None:
    """Batch delete existing rows for multiple codes to avoid N+1 mutations."""
    if not codes or not isinstance(start_date, date) or not isinstance(end_date, date):
        return
    for code in codes:
        if not str(code).isalnum():
            raise ValueError(f"Invalid code: {code}")
    db_client.command(
        "ALTER TABLE daily_candles DELETE "
        "WHERE code IN {codes:Array(String)} AND date >= {start:Date} AND date <= {end:Date}",
        parameters={"codes": codes, "start": start_date, "end": end_date},
    )


# =============================================================================
# API Fetching
# =============================================================================

async def fetch_daily_candles_async(
    client: httpx.AsyncClient,
    code: str,
    start_date: date,
    end_date: date,
    max_retries: int = 3
) -> Tuple[str, dict]:
    """
    Fetch stock daily candles asynchronously.

    Uses 주식일별일봉조회 API (FHKST03010100) for historical daily OHLCV.

    Args:
        client: httpx async client
        code: Stock code (e.g., '005930')
        start_date: Start date
        end_date: End date
        max_retries: Maximum retry attempts

    Returns:
        Tuple of (code, response_data)
    """
    app_key = SecretsManager.kis_app_key("stock") or ""
    app_secret = SecretsManager.kis_app_secret("stock") or ""
    token = StockKISToken.get_instance()
    base_url = "https://openapi.koreainvestment.com:9443"

    # 주식일별일봉조회 API (FHKST03010100)
    url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"

    params = {
        "FID_COND_MRKT_DIV_CODE": "J",  # 주식
        "FID_INPUT_ISCD": code,
        "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
        "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
        "FID_PERIOD_DIV_CODE": "D",  # D: 일봉
    }

    last_error = None
    for attempt in range(max_retries):
        headers = {
            "Authorization": f"Bearer {token.get()}",
            "appkey": app_key,
            "appsecret": app_secret,
            "tr_id": "FHKST03010100",  # 주식일별일봉조회
            "content-type": "application/json; charset=utf-8",
        }

        async with _get_semaphore():
            try:
                await _get_rate_limiter().wait()
                resp = await client.get(url, headers=headers, params=params)

                if resp.status_code >= 500:
                    last_error = f"http {resp.status_code}"
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue

                if not resp.text or resp.text.strip() == "":
                    last_error = f"empty response (status {resp.status_code})"
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue

                try:
                    data = resp.json()
                except Exception as json_err:
                    last_error = f"json parse: {json_err}"
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue

                rt_cd = data.get("rt_cd", "")
                if rt_cd and rt_cd != "0":
                    msg = data.get("msg1", "Unknown error")
                    if "초당 거래건수" in msg or "RATE" in msg.upper():
                        await asyncio.sleep(1.0 * (attempt + 1))
                        continue
                    return (code, {"error": msg})

                return (code, data)

            except Exception as e:
                last_error = e
                logger.warning(f"Fetch error for {code} {start_date} ~ {end_date}: {e}")
                await asyncio.sleep(0.5 * (attempt + 1))

    return (code, {"error": str(last_error)})


def parse_daily_ohlcv(code: str, data: dict) -> List[Tuple]:
    """
    Parse API response to daily OHLCV rows.

    Returns:
        List of tuples (code, date, open, high, low, close, volume, value, change_rate)
    """
    rows = []
    output = data.get("output2", []) or data.get("output1", [])

    if not output:
        return rows

    for item in output:
        if not isinstance(item, dict):
            continue

        try:
            # 날짜 파싱
            bsop_date = item.get("stck_bsop_date", "")
            if not bsop_date:
                continue

            dt = datetime.strptime(bsop_date, "%Y%m%d").date()

            o = float(item.get("stck_oprc", 0))
            h = float(item.get("stck_hgpr", 0))
            l = float(item.get("stck_lwpr", 0))
            c = float(item.get("stck_clpr", 0))
            v = int(item.get("acml_vol", 0))
            val = int(item.get("acml_tr_pbmn", 0))
            change_rate = float(item.get("prdy_ctrt", 0))

            if h > 0:
                rows.append((code, dt, o, h, l, c, v, val, change_rate))

        except (ValueError, KeyError) as e:
            logger.debug(f"Parse error for {code}: {e}")
            continue

    return rows


# =============================================================================
# Main Collection Functions
# =============================================================================

async def collect_daily_candles(
    codes: List[str] = None,
    days: int = 100,
    verbose: bool = True
) -> int:
    """
    Collect daily candles for stock universe.

    Args:
        codes: Specific codes to collect (None = all universe)
        days: Number of trading days to fetch (default 100)
        verbose: Print progress

    Returns:
        Total rows collected
    """
    days = min(days, MAX_DAILY_DAYS)

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # Get trading days range
    trading_days = get_trading_days_range(start_date, end_date)
    if not trading_days:
        if verbose:
            print("No trading days in range")
        return 0

    if verbose:
        _log_daily_collection_header(trading_days)

    ensure_stock_database()
    ensure_daily_candles_table()
    db_client = get_stock_db_client()

    # Select codes
    selected_codes = _select_daily_codes(codes)

    if verbose:
        print(f"Stocks: {len(selected_codes)}")

    total_rows = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        batch_rows, succeeded_codes, failed_codes = await _collect_daily_rows(
            client,
            selected_codes,
            trading_days[0],
            trading_days[-1],
        )

        total_rows = _persist_daily_rows(
            db_client,
            batch_rows,
            succeeded_codes,
            trading_days[0],
            trading_days[-1],
            verbose,
        )

        if failed_codes and verbose:
            print(f"Failed: {len(failed_codes)} stocks")

    db_client.close()

    if verbose:
        print(f"Total: {total_rows} rows collected")

    return total_rows


def _select_daily_codes(codes: List[str] | None) -> List[str]:
    if codes:
        return list(dict.fromkeys(codes))
    return [s["code"] for s in STOCK_UNIVERSE]


def _log_daily_collection_header(trading_days: List[date]) -> None:
    print("Stock Daily Candles Collection")
    print(f"Trading days: {len(trading_days)}")
    print(f"Date range: {trading_days[0]} ~ {trading_days[-1]}")


async def _collect_daily_rows(
    client: httpx.AsyncClient,
    selected_codes: List[str],
    start_date: date,
    end_date: date,
) -> Tuple[List[Tuple], List[str], List[str]]:
    coros = [
        fetch_daily_candles_async(client, code, start_date, end_date)
        for code in selected_codes
    ]
    results = await asyncio.gather(*coros)

    batch_rows: List[Tuple] = []
    succeeded_codes: List[str] = []
    failed_codes: List[str] = []

    for code, data in results:
        if "error" in data:
            logger.warning(f"Fetch failed for {code}: {data['error']}")
            failed_codes.append(code)
            continue

        rows = parse_daily_ohlcv(code, data)
        if not rows:
            logger.warning(f"No data for {code}")
            failed_codes.append(code)
            continue

        batch_rows.extend(rows)
        succeeded_codes.append(code)

    return batch_rows, succeeded_codes, failed_codes


def _persist_daily_rows(
    db_client,
    batch_rows: List[Tuple],
    succeeded_codes: List[str],
    start_date: date,
    end_date: date,
    verbose: bool,
) -> int:
    if not batch_rows:
        return 0

    # Remove existing rows for all succeeded codes in a single mutation
    try:
        delete_daily_candles_batch(db_client, succeeded_codes, start_date, end_date)
    except Exception as e:
        logger.warning(f"Failed to delete existing rows: {e}")

    insert_daily_candles_batch(db_client, batch_rows)
    total_rows = len(batch_rows)

    if verbose:
        print(
            f"Inserted {total_rows} rows from {len(succeeded_codes)} stocks into daily_candles"
        )

    return total_rows


def get_daily_collection_status(days: int = 100) -> Dict[str, Any]:
    """Get daily candles collection status."""
    try:
        db_client = get_stock_db_client()

        start_date = date.today() - timedelta(days=days)
        end_date = date.today()

        query = """
            SELECT
                count(*) as total_rows,
                count(DISTINCT date) as days_collected,
                min(date) as min_date,
                max(date) as max_date,
                count(DISTINCT code) as unique_codes
            FROM daily_candles
            WHERE date >= {start:Date}
            AND date <= {end:Date}
        """

        result = db_client.query(query, parameters={"start": start_date, "end": end_date})
        row = result.first_row if result.result_rows else None

        db_client.close()

        if row:
            return {
                "table": "daily_candles",
                "rows": row[0],
                "days_collected": row[1],
                "min_date": str(row[2]) if row[2] else None,
                "max_date": str(row[3]) if row[3] else None,
                "unique_codes": row[4],
            }

        return {"table": "daily_candles", "rows": 0}

    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        return {"error": str(e)}


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "collect_daily_candles",
    "get_daily_collection_status",
    "ensure_daily_candles_table",
]
