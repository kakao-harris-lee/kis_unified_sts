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
from datetime import date, datetime
from typing import List, Tuple, Dict, Any

import httpx

from shared.config.secrets import SecretsManager
from .stock import (
    StockKISToken,
    _get_rate_limiter,
    _get_semaphore,
    STOCK_UNIVERSE,
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
    """Legacy no-op retained for backward-compatible imports."""
    return None


def insert_daily_candles_batch(
    db_client, rows: List[Tuple], table_name: str = "daily_candles"
):
    """Legacy DB sink entrypoint removed; use Parquet stock daily collection."""
    raise RuntimeError("Legacy DB sink removed; use Parquet stock daily collection")


def delete_daily_candles_range(
    db_client, code: str, start_date: date, end_date: date
) -> None:
    """Legacy DB sink entrypoint removed; use Parquet stock daily collection."""
    raise RuntimeError("Legacy DB sink removed; use Parquet stock daily collection")


def delete_daily_candles_batch(
    db_client, codes: List[str], start_date: date, end_date: date
) -> None:
    """Legacy DB sink entrypoint removed; use Parquet stock daily collection."""
    raise RuntimeError("Legacy DB sink removed; use Parquet stock daily collection")


# =============================================================================
# API Fetching
# =============================================================================


async def fetch_daily_candles_async(
    client: httpx.AsyncClient,
    code: str,
    start_date: date,
    end_date: date,
    max_retries: int = 3,
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
        "FID_ORG_ADJ_PRC": os.getenv("KIS_DAILY_ORG_ADJ_PRC", "0"),
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
    codes: List[str] = None, days: int = 100, verbose: bool = True
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
    from .parquet_backfill import collect_stock_daily_parquet

    result = await collect_stock_daily_parquet(
        codes=codes,
        days=min(days, MAX_DAILY_DAYS),
        verbose=verbose,
    )
    return result.rows


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
    raise RuntimeError("Legacy DB sink removed; use Parquet stock daily collection")


def get_daily_collection_status(days: int = 100) -> Dict[str, Any]:
    """Get daily candles collection status."""
    from .parquet_backfill import get_parquet_backfill_status

    return get_parquet_backfill_status(days=days, asset_class="stock")


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "collect_daily_candles",
    "get_daily_collection_status",
    "ensure_daily_candles_table",
]
