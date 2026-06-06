"""
Stock Minute Data Collection Module

주식 1분봉 데이터를 수집합니다.

Usage:
    # CLI
    sts stock-backfill today
    sts stock-backfill run --days 7
    sts stock-backfill status

    # Python
    from shared.collector.historical.stock import (
        collect_stock_minute_today,
        backfill_stock_minute,
    )
    await collect_stock_minute_today()
    await backfill_stock_minute(days=7)
"""

import os
import asyncio
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

import httpx

from shared.config.secrets import SecretsManager
from .stock_universe import STOCK_UNIVERSE

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


STATE_FILE = Path(
    os.getenv("STOCK_COLLECTOR_STATE_FILE", "logs/stock_minute_collector_state.json")
)
MAX_MINUTE_PAGES = int(os.getenv("STOCK_MINUTE_MAX_PAGES", "20"))
STOCK_MINUTE_END_HOUR = os.getenv("STOCK_MINUTE_END_HOUR", "153000")


def _normalize_time_str(value: str) -> str:
    if not value:
        return ""
    value = str(value).strip()
    if len(value) == 4:
        return f"{value}00"
    return value


def _minus_one_minute(date_str: str, time_str: str) -> str:
    try:
        time_str = _normalize_time_str(time_str)
        dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
        dt = dt - timedelta(minutes=1)
        return dt.strftime("%H%M%S")
    except Exception:
        return time_str


# =============================================================================
# Token Management (Stock Domain)
# =============================================================================


class StockKISToken:
    """한국투자증권 API 토큰 관리 (주식 도메인)"""

    _instance: Optional["StockKISToken"] = None

    def __init__(self):
        import threading

        self._token: Optional[str] = None
        self._expires_at: float = 0
        self._cache_path = os.path.expanduser("~/.cache/kis_token_stock.json")
        self._refresh_lock = threading.Lock()
        self._load_cache()

    @classmethod
    def get_instance(cls) -> "StockKISToken":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get(self) -> str:
        """현재 유효한 토큰 반환 (필요시 갱신)"""
        import time

        if self._token and time.time() < self._expires_at - 60:
            return self._token

        # 다른 프로세스가 갱신한 캐시 재확인
        self._load_cache()
        if self._token and time.time() < self._expires_at - 60:
            return self._token

        self._refresh()
        return self._token

    def _load_cache(self) -> None:
        """Load cached token."""
        try:
            if not os.path.exists(self._cache_path):
                return
            with open(self._cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                import time

                token = data.get("token") or data.get("access_token")
                expires_at = data.get("expires_at", 0)
                if token and expires_at > time.time() + 60:
                    self._token = token
                    self._expires_at = float(expires_at)
                    logger.debug("Loaded cached stock token")
        except Exception as e:
            logger.debug(f"Failed to load cached token: {e}")

    def _save_cache(self) -> None:
        """Save token to cache."""
        try:
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "token": self._token,
                        "access_token": self._token,
                        "expires_at": self._expires_at,
                    },
                    f,
                )
        except Exception as e:
            logger.debug(f"Failed to save token cache: {e}")

    def _refresh(self) -> None:
        """Refresh token from KIS API."""
        import time

        app_key = SecretsManager.kis_app_key("stock") or ""
        app_secret = SecretsManager.kis_app_secret("stock") or ""

        if not app_key or not app_secret:
            raise ValueError("Stock KIS credentials not configured")

        with self._refresh_lock:
            if self._token and time.time() < self._expires_at - 60:
                return

            url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
            payload = {
                "grant_type": "client_credentials",
                "appkey": app_key,
                "appsecret": app_secret,
            }

            import requests

            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            self._token = data["access_token"]
            expires_in = int(data.get("expires_in", 86400))
            self._expires_at = time.time() + expires_in
            self._save_cache()
            logger.info("Stock KIS token refreshed")


# =============================================================================
# Rate Limiting
# =============================================================================


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, max_per_second: float = 10):
        self._interval = 1.0 / max_per_second
        self._last_call = 0.0
        self._lock = asyncio.Lock()

    async def wait(self):
        import time

        async with self._lock:
            now = time.time()
            elapsed = now - self._last_call
            if elapsed < self._interval:
                await asyncio.sleep(self._interval - elapsed)
            self._last_call = time.time()


_rate_limiter: Optional[RateLimiter] = None
_rate_limit_per_sec = int(os.getenv("STOCK_RATE_LIMIT", "5"))
_max_concurrent_requests = int(os.getenv("STOCK_MAX_CONCURRENCY", "3"))
_semaphore: Optional[asyncio.Semaphore] = None
_rate_limiter_loop: Optional[asyncio.AbstractEventLoop] = None
_semaphore_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_rate_limiter() -> RateLimiter:
    global _rate_limiter, _rate_limiter_loop
    loop = asyncio.get_running_loop()
    if _rate_limiter is None or _rate_limiter_loop is not loop:
        _rate_limiter = RateLimiter(_rate_limit_per_sec)
        _rate_limiter_loop = loop
    return _rate_limiter


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore, _semaphore_loop
    loop = asyncio.get_running_loop()
    if _semaphore is None or _semaphore_loop is not loop:
        _semaphore = asyncio.Semaphore(_max_concurrent_requests)
        _semaphore_loop = loop
    return _semaphore


# =============================================================================
# Database Operations
# =============================================================================


def get_stock_db_client() -> Any:
    """Legacy DB client entrypoint removed; use Parquet stock-backfill commands."""
    raise RuntimeError("Legacy DB sink removed; use Parquet stock-backfill commands")


def ensure_stock_database() -> None:
    """Legacy no-op retained for backward-compatible imports."""
    return None


def insert_stock_minute_batch(
    db_client, rows: List[Tuple], table_name: str = "minute_candles"
) -> int:
    """Insert stock minute data batch."""
    if not rows:
        return 0

    db_client.insert(
        table_name,
        rows,
        column_names=[
            "code",
            "datetime",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "value",
        ],
    )
    return len(rows)


def delete_stock_minute_day(db_client, code: str, day: date) -> None:
    """Delete existing rows for a code/day to avoid duplicates."""
    if not code or not isinstance(day, date):
        return
    if not str(code).isalnum():
        raise ValueError(f"Invalid code: {code}")
    day_str = day.strftime("%Y-%m-%d")
    query = """
        ALTER TABLE minute_candles
        DELETE WHERE code = %(code)s AND toDate(datetime) = %(day)s
    """
    params = {"code": code, "day": day_str}
    db_client.query(query, parameters=params)


# =============================================================================
# API Fetching
# =============================================================================


async def _request_stock_minute_page(
    client: httpx.AsyncClient,
    url: str,
    code: str,
    date_str: str,
    input_hour: str,
    max_retries: int,
    token: "StockKISToken",
    app_key: str,
    app_secret: str,
) -> dict:
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",  # 주식
        "FID_INPUT_ISCD": code,
        "FID_INPUT_DATE_1": date_str,
        "FID_INPUT_HOUR_1": input_hour,
        "FID_PW_DATA_INCU_YN": "Y",  # 과거 데이터 포함
        "FID_FAKE_TICK_INCU_YN": "N",  # 허봉 포함 여부
    }

    last_error = None
    for attempt in range(max_retries):
        headers = {
            "Authorization": f"Bearer {token.get()}",
            "appkey": app_key,
            "appsecret": app_secret,
            "tr_id": "FHKST03010230",  # 주식일별분봉조회
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
                    return {"error": msg}

                return data

            except Exception as e:
                last_error = e
                logger.warning(f"Fetch error for {code} {date_str}: {e}")
                await asyncio.sleep(0.5 * (attempt + 1))

    return {"error": str(last_error)}


async def fetch_stock_minute_async(
    client: httpx.AsyncClient, code: str, date_str: str, max_retries: int = 3
) -> Tuple[str, str, dict]:
    """
    Fetch stock minute data asynchronously.

    Uses 주식일별분봉조회 API (FHKST03010230) for historical minute data.

    Args:
        client: httpx async client
        code: Stock code (e.g., '005930')
        date_str: Date string in YYYYMMDD format
        max_retries: Maximum retry attempts

    Returns:
        Tuple of (code, date, response_data)
    """
    app_key = SecretsManager.kis_app_key("stock") or ""
    app_secret = SecretsManager.kis_app_secret("stock") or ""
    token = StockKISToken.get_instance()
    base_url = "https://openapi.koreainvestment.com:9443"

    # 주식일별분봉조회 API (FHKST03010230)
    # Historical minute data; max 120 rows per call
    url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice"

    all_rows: list[dict] = []
    seen_times: set[str] = set()
    current_hour = STOCK_MINUTE_END_HOUR
    pages = 0
    last_min_time: str | None = None
    base_data: dict | None = None

    while True:
        data = await _request_stock_minute_page(
            client,
            url,
            code,
            date_str,
            current_hour,
            max_retries,
            token,
            app_key,
            app_secret,
        )
        if "error" in data:
            return (code, date_str, {"error": data["error"]})

        if base_data is None:
            base_data = data

        output = data.get("output2", []) or data.get("output1", [])
        if not output:
            break

        times = []
        for item in output:
            time_str = _normalize_time_str(item.get("stck_cntg_hour", ""))
            if not time_str:
                continue
            if time_str in seen_times:
                continue
            seen_times.add(time_str)
            all_rows.append(item)
            times.append(time_str)

        if not times:
            break

        min_time = min(times)
        if last_min_time and min_time >= last_min_time:
            break
        last_min_time = min_time

        if min_time <= "090000":
            break

        current_hour = _minus_one_minute(date_str, min_time)
        pages += 1
        if pages >= MAX_MINUTE_PAGES:
            break

    if base_data is None:
        base_data = {"output2": []}

    base_data["output2"] = all_rows
    return (code, date_str, base_data)


def parse_stock_minute_ohlcv(code: str, _date_str: str, data: dict) -> List[Tuple]:
    """
    Parse API response to OHLCV rows.

    Returns:
        List of tuples (code, datetime, open, high, low, close, volume, value)
    """
    rows = []
    output = data.get("output2", []) or data.get("output1", [])

    if not output:
        return rows

    for item in output:
        if not isinstance(item, dict):
            continue

        try:
            # 날짜+시간 파싱
            bsop_date = item.get("stck_bsop_date", "")
            cntg_hour = item.get("stck_cntg_hour", "")

            if not bsop_date or not cntg_hour:
                continue

            if len(cntg_hour) == 4:
                cntg_hour = f"{cntg_hour}00"

            dt = datetime.strptime(f"{bsop_date}{cntg_hour}", "%Y%m%d%H%M%S")

            o = float(item.get("stck_oprc", 0))
            h = float(item.get("stck_hgpr", 0))
            l = float(item.get("stck_lwpr", 0))
            c = float(item.get("stck_prpr", 0))
            v = int(item.get("cntg_vol", 0))
            val = int(item.get("acml_tr_pbmn", 0))

            if h > 0:
                rows.append((code, dt, o, h, l, c, v, val))

        except (ValueError, KeyError) as e:
            logger.debug(f"Parse error for {code}: {e}")
            continue

    return rows


# =============================================================================
# Collection State Management
# =============================================================================


def load_collection_state() -> Dict:
    """Load collection state from file."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load state file: {e}")
    return {"completed_days": {}, "last_run": None}


def save_collection_state(state: Dict) -> None:
    """Save collection state to file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to save state file: {e}")


# =============================================================================
# Main Collection Functions
# =============================================================================


async def collect_stock_batch(
    client: httpx.AsyncClient,
    db_client,
    tasks: List[Tuple[str, date]],
    retry_rounds: int = 2,
    retry_delay: float = 1.0,
) -> int:
    """
    Collect a batch of (code, date) combinations.

    Returns:
        Number of rows inserted
    """
    if not tasks:
        return 0

    async def _run(
        task_list: List[Tuple[str, date]],
    ) -> Tuple[List[Tuple], List[Tuple[str, date]], List[Tuple[str, date]]]:
        coros = [
            fetch_stock_minute_async(client, code, dt.strftime("%Y%m%d"))
            for code, dt in task_list
        ]

        results = await asyncio.gather(*coros)

        batch_rows: List[Tuple] = []
        failed: List[Tuple[str, date]] = []
        succeeded: List[Tuple[str, date]] = []
        for code, date_str, data in results:
            if "error" in data:
                logger.warning(f"Fetch failed for {code} {date_str}: {data['error']}")
                try:
                    failed.append((code, datetime.strptime(date_str, "%Y%m%d").date()))
                except Exception:
                    continue
                continue
            rows = parse_stock_minute_ohlcv(code, date_str, data)
            if not rows:
                try:
                    failed.append((code, datetime.strptime(date_str, "%Y%m%d").date()))
                except Exception:
                    continue
                continue
            try:
                succeeded.append((code, datetime.strptime(date_str, "%Y%m%d").date()))
            except Exception:
                continue
            batch_rows.extend(rows)

        return batch_rows, failed, succeeded

    all_rows, failed_tasks, succeeded_tasks = await _run(tasks)

    for attempt in range(retry_rounds):
        if not failed_tasks:
            break
        await asyncio.sleep(retry_delay * (attempt + 1))
        retry_rows, failed_tasks, retry_succeeded = await _run(failed_tasks)
        all_rows.extend(retry_rows)
        succeeded_tasks.extend(retry_succeeded)

    if failed_tasks:
        logger.warning(f"Fetch failed after retries: {len(failed_tasks)} tasks")

    if all_rows:
        # Remove existing rows only for successfully fetched code/day
        for code, day in succeeded_tasks:
            try:
                delete_stock_minute_day(db_client, code, day)
            except Exception as e:
                logger.warning(f"Failed to delete existing rows for {code} {day}: {e}")
        insert_stock_minute_batch(db_client, all_rows)
        print(
            f"Inserted {len(all_rows)} rows from {len(tasks)} tasks into minute_candles"
        )

    return len(all_rows)


async def collect_stock_minute_today(verbose: bool = True) -> int:
    """Collect today's stock minute data into Parquet."""
    from shared.collector.historical.parquet_backfill import (
        collect_today_stock_minute_parquet,
    )

    result = await collect_today_stock_minute_parquet(verbose=verbose)
    return result.rows


async def backfill_stock_minute(
    days: int = 30,
    codes: List[str] = None,
    verbose: bool = True,
    resume: bool = True,
) -> int:
    """Backfill stock minute data into Parquet."""
    from shared.collector.historical.parquet_backfill import (
        backfill_stock_minute_parquet,
    )

    result = await backfill_stock_minute_parquet(
        days=days,
        codes=codes,
        resume=resume,
        verbose=verbose,
    )
    return result.rows


def get_stock_codes_from_db(days: Optional[int] = None) -> List[str]:
    """Return configured stock universe codes."""
    _ = days
    return [str(item["code"]) for item in STOCK_UNIVERSE]


def get_stock_collection_status(days: int = 30) -> Dict:
    """Get Parquet stock minute collection status."""
    from shared.collector.historical.parquet_backfill import (
        get_parquet_backfill_status,
    )

    return get_parquet_backfill_status(days=days, asset_class="stock")


def load_stock_minute_from_parquet(
    code: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Any:
    """
    Load stock minute data from the configured Parquet market-data store.

    Args:
        code: Stock code (e.g., '005930')
        start_date: Start date filter (inclusive). None = no lower bound.
        end_date: End date filter (inclusive). None = no upper bound.

    Returns:
        DataFrame with columns: code, datetime, open, high, low, close, volume
        Sorted by datetime ascending.

    Raises:
        ValueError: If no data found for the given code/date range.
    """
    from shared.storage import StorageConfig, load_market_bars_for_backtest

    df = load_market_bars_for_backtest(
        symbol=code,
        asset_class="stock",
        timeframe="minute",
        start=start_date,
        end=end_date,
        config=StorageConfig.load_or_default(),
    )
    if df.empty:
        raise ValueError(
            f"No data found for {code} in Parquet market data "
            f"(range: {start_date} ~ {end_date})"
        )

    return df


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "STOCK_UNIVERSE",
    "collect_stock_minute_today",
    "backfill_stock_minute",
    "get_stock_codes_from_db",
    "get_stock_collection_status",
    "get_stock_db_client",
    "ensure_stock_database",
    "load_stock_minute_from_parquet",
]
