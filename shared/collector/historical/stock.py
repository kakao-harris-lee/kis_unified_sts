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
from dataclasses import dataclass

import httpx
import clickhouse_connect

from shared.config.secrets import SecretsManager
from .calendar import get_trading_days_range, is_after_market_close, is_trading_day

logger = logging.getLogger(__name__)


# =============================================================================
# Stock Universe (30 stocks by market cap tier)
# =============================================================================

STOCK_UNIVERSE = [
    # 대형주 (시가총액 상위)
    {"code": "005930", "name": "삼성전자", "tier": "top"},
    {"code": "000660", "name": "SK하이닉스", "tier": "top"},
    {"code": "207940", "name": "삼성바이오로직스", "tier": "top"},
    {"code": "005380", "name": "현대차", "tier": "top"},
    {"code": "000270", "name": "기아", "tier": "top"},
    {"code": "068270", "name": "셀트리온", "tier": "top"},
    {"code": "035420", "name": "NAVER", "tier": "top"},
    {"code": "005490", "name": "POSCO홀딩스", "tier": "top"},
    {"code": "035720", "name": "카카오", "tier": "top"},
    {"code": "051910", "name": "LG화학", "tier": "top"},

    # 중형주 (시가총액 중간)
    {"code": "006400", "name": "삼성SDI", "tier": "mid"},
    {"code": "028260", "name": "삼성물산", "tier": "mid"},
    {"code": "012330", "name": "현대모비스", "tier": "mid"},
    {"code": "055550", "name": "신한지주", "tier": "mid"},
    {"code": "105560", "name": "KB금융", "tier": "mid"},
    {"code": "034730", "name": "SK", "tier": "mid"},
    {"code": "003550", "name": "LG", "tier": "mid"},
    {"code": "066570", "name": "LG전자", "tier": "mid"},
    {"code": "032830", "name": "삼성생명", "tier": "mid"},
    {"code": "086790", "name": "하나금융지주", "tier": "mid"},

    # 소형주/테마주 (변동성 높음)
    {"code": "247540", "name": "에코프로비엠", "tier": "bottom"},
    {"code": "086520", "name": "에코프로", "tier": "bottom"},
    {"code": "373220", "name": "LG에너지솔루션", "tier": "bottom"},
    {"code": "196170", "name": "알테오젠", "tier": "bottom"},
    {"code": "003670", "name": "포스코퓨처엠", "tier": "bottom"},
    {"code": "009150", "name": "삼성전기", "tier": "bottom"},
    {"code": "000810", "name": "삼성화재", "tier": "bottom"},
    {"code": "018260", "name": "삼성에스디에스", "tier": "bottom"},
    {"code": "033780", "name": "KT&G", "tier": "bottom"},
    {"code": "036570", "name": "엔씨소프트", "tier": "bottom"},
]


# =============================================================================
# Configuration
# =============================================================================

def _get_clickhouse_config() -> Dict[str, Any]:
    """Get ClickHouse configuration for stock database."""
    return {
        "host": os.getenv("CLICKHOUSE_HOST", "localhost"),
        "port": int(os.getenv("CLICKHOUSE_PORT", "8123")),
        "database": os.getenv("CLICKHOUSE_STOCK_DATABASE", "market"),
        "user": os.getenv("CLICKHOUSE_USER", "trading"),
        "password": os.getenv("CLICKHOUSE_PASSWORD", ""),
    }


STATE_FILE = Path(os.getenv("STOCK_COLLECTOR_STATE_FILE", "logs/stock_minute_collector_state.json"))


# =============================================================================
# Token Management (Stock Domain)
# =============================================================================

class StockKISToken:
    """한국투자증권 API 토큰 관리 (주식 도메인)"""

    _instance: Optional["StockKISToken"] = None

    def __init__(self):
        self._token: Optional[str] = None
        self._expires_at: float = 0
        self._cache_path = os.path.expanduser("~/.cache/kis_token_stock.json")
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
                if data.get("expires_at", 0) > time.time() + 60:
                    self._token = data["token"]
                    self._expires_at = data["expires_at"]
                    logger.debug("Loaded cached stock token")
        except Exception as e:
            logger.debug(f"Failed to load cached token: {e}")

    def _save_cache(self) -> None:
        """Save token to cache."""
        try:
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump({
                    "token": self._token,
                    "expires_at": self._expires_at,
                }, f)
        except Exception as e:
            logger.debug(f"Failed to save token cache: {e}")

    def _refresh(self) -> None:
        """Refresh token from KIS API."""
        import time

        app_key = SecretsManager.kis_app_key("stock") or ""
        app_secret = SecretsManager.kis_app_secret("stock") or ""

        if not app_key or not app_secret:
            raise ValueError("Stock KIS credentials not configured")

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
        # Token valid for 24 hours
        self._expires_at = time.time() + 86400 - 300
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
_semaphore: Optional[asyncio.Semaphore] = None


def _get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(10)  # 10 requests per second
    return _rate_limiter


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(5)
    return _semaphore


# =============================================================================
# Database Operations
# =============================================================================

def get_stock_db_client():
    """Get ClickHouse client for stock database."""
    config = _get_clickhouse_config()
    return clickhouse_connect.get_client(
        host=config["host"],
        port=config["port"],
        username=config["user"],
        password=config["password"],
        database=config["database"],
    )


def ensure_stock_database():
    """Ensure stock database and tables exist."""
    config = _get_clickhouse_config()
    client = clickhouse_connect.get_client(
        host=config["host"],
        port=config["port"],
        username=config["user"],
        password=config["password"],
    )

    # Create database
    client.command(f"CREATE DATABASE IF NOT EXISTS {config['database']}")

    # Switch to database
    client.command(f"USE {config['database']}")

    # Create minute_candles table
    client.command("""
        CREATE TABLE IF NOT EXISTS minute_candles (
            code String,
            datetime DateTime('Asia/Seoul'),
            open Float64,
            high Float64,
            low Float64,
            close Float64,
            volume UInt64,
            value UInt64
        ) ENGINE = ReplacingMergeTree()
        ORDER BY (code, datetime)
        PARTITION BY toYYYYMM(datetime)
    """)

    # Create collection_metadata table
    client.command("""
        CREATE TABLE IF NOT EXISTS collection_metadata (
            code String,
            data_type String,
            last_date Date,
            records_count UInt64,
            updated_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree()
        ORDER BY (code, data_type)
    """)

    client.close()
    logger.debug("Stock database schema ensured")


def insert_stock_minute_batch(db_client, rows: List[Tuple], table_name: str = "minute_candles"):
    """Insert stock minute data batch."""
    if not rows:
        return 0

    db_client.insert(
        table_name,
        rows,
        column_names=["code", "datetime", "open", "high", "low", "close", "volume", "value"],
    )
    return len(rows)


# =============================================================================
# API Fetching
# =============================================================================

async def fetch_stock_minute_async(
    client: httpx.AsyncClient,
    code: str,
    date_str: str,
    max_retries: int = 3
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

    # 주식당일분봉조회 API (FHKST03010200)
    # Note: This API only returns data for the specified date, not historical ranges
    url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",  # 주식
        "FID_INPUT_ISCD": code,
        "FID_INPUT_DATE_1": date_str,
        "FID_INPUT_HOUR_1": "",  # 빈 값 = 전체 시간대
        "FID_PW_DATA_INCU_YN": "Y",  # 과거 데이터 포함
    }

    last_error = None
    for attempt in range(max_retries):
        headers = {
            "Authorization": f"Bearer {token.get()}",
            "appkey": app_key,
            "appsecret": app_secret,
            "tr_id": "FHKST03010200",  # 주식당일분봉조회
            "content-type": "application/json; charset=utf-8",
        }

        async with _get_semaphore():
            try:
                await _get_rate_limiter().wait()
                resp = await client.get(url, headers=headers, params=params)

                if not resp.text or resp.text.strip() == "":
                    return (code, date_str, {"error": f"empty response (status {resp.status_code})"})

                try:
                    data = resp.json()
                except Exception as json_err:
                    return (code, date_str, {"error": f"json parse: {json_err}"})

                rt_cd = data.get("rt_cd", "")
                if rt_cd and rt_cd != "0":
                    msg = data.get("msg1", "Unknown error")
                    if "초당 거래건수" in msg or "RATE" in msg.upper():
                        await asyncio.sleep(1.0 * (attempt + 1))
                        continue
                    return (code, date_str, {"error": msg})

                # API may return empty rt_cd with no data - this is OK
                if not rt_cd and not data.get("output2"):
                    logger.debug(f"No minute data for {code} on {date_str}")

                return (code, date_str, data)

            except Exception as e:
                last_error = e
                logger.warning(f"Fetch error for {code} {date_str}: {e}")
                await asyncio.sleep(0.5 * (attempt + 1))

    return (code, date_str, {"error": str(last_error)})


def parse_stock_minute_ohlcv(code: str, date_str: str, data: dict) -> List[Tuple]:
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
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load state file: {e}")
    return {"date": None, "failed": [], "success": []}


def save_collection_state(state: Dict):
    """Save collection state to file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save state file: {e}")


# =============================================================================
# Main Collection Functions
# =============================================================================

async def collect_stock_batch(
    client: httpx.AsyncClient,
    db_client,
    tasks: List[Tuple[str, date]],
) -> int:
    """
    Collect a batch of (code, date) combinations.

    Returns:
        Number of rows inserted
    """
    if not tasks:
        return 0

    coros = [
        fetch_stock_minute_async(client, code, dt.strftime("%Y%m%d"))
        for code, dt in tasks
    ]

    results = await asyncio.gather(*coros)

    all_rows = []
    for code, date_str, data in results:
        if "error" in data:
            logger.warning(f"Fetch failed for {code} {date_str}: {data['error']}")
            continue
        rows = parse_stock_minute_ohlcv(code, date_str, data)
        all_rows.extend(rows)

    if all_rows:
        insert_stock_minute_batch(db_client, all_rows)
        print(f"Inserted {len(all_rows)} rows from {len(tasks)} tasks into minute_candles")

    return len(all_rows)


async def collect_stock_minute_today(verbose: bool = True) -> int:
    """
    Collect today's stock minute data (run after market close).
    """
    if not is_after_market_close():
        if verbose:
            print("Market is still open. Please run after 15:45 KST.")
        return 0

    today = date.today()
    if not is_trading_day(today):
        if verbose:
            print("Today is not a trading day.")
        return 0

    if verbose:
        print(f"Collecting stock minute data for {today}")
        print(f"Universe: {len(STOCK_UNIVERSE)} stocks")

    ensure_stock_database()
    db_client = get_stock_db_client()

    tasks = [(stock["code"], today) for stock in STOCK_UNIVERSE]

    total_rows = 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Process in batches of 10
        batch_size = 10
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            if verbose:
                codes = [t[0] for t in batch]
                print(f"Batch {i // batch_size + 1}: {codes}")
            rows = await collect_stock_batch(client, db_client, batch)
            total_rows += rows

    db_client.close()

    if verbose:
        print(f"Total: {total_rows} rows collected")

    return total_rows


async def backfill_stock_minute(
    days: int = 30,
    codes: List[str] = None,
    verbose: bool = True
) -> int:
    """
    Backfill stock minute data for specified days.

    Args:
        days: Number of days to backfill (max 30 for minute data)
        codes: Specific codes to backfill (None = all universe)
        verbose: Print progress

    Returns:
        Total rows collected
    """
    # KIS API limits minute data to 30 days
    days = min(days, 30)

    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    trading_days = get_trading_days_range(start_date, end_date)
    if not trading_days:
        if verbose:
            print("No trading days in range")
        return 0

    if verbose:
        print(f"Stock Minute Backfill")
        print(f"Trading days: {len(trading_days)}")
        print(f"Date range: {trading_days[0]} ~ {trading_days[-1]}")

    ensure_stock_database()
    db_client = get_stock_db_client()

    # Select stocks
    if codes:
        stocks = [s for s in STOCK_UNIVERSE if s["code"] in codes]
    else:
        stocks = STOCK_UNIVERSE

    if verbose:
        print(f"Stocks: {len(stocks)}")

    total_rows = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for day_idx, day in enumerate(reversed(trading_days), start=1):
            tasks = [(stock["code"], day) for stock in stocks]

            if verbose:
                print(f"{day_idx}/{len(trading_days)} {day} stocks={len(tasks)}")

            rows = await collect_stock_batch(client, db_client, tasks)
            total_rows += rows

    db_client.close()

    if verbose:
        print(f"Backfill complete. Total rows: {total_rows}")

    return total_rows


def get_stock_collection_status(days: int = 30) -> Dict[str, Any]:
    """Get stock minute collection status."""
    try:
        db_client = get_stock_db_client()

        start_date = date.today() - timedelta(days=days)
        end_date = date.today()

        query = f"""
            SELECT
                count(*) as total_rows,
                count(DISTINCT toDate(datetime)) as days_collected,
                min(datetime) as min_datetime,
                max(datetime) as max_datetime,
                count(DISTINCT code) as unique_codes
            FROM minute_candles
            WHERE toDate(datetime) >= '{start_date}'
            AND toDate(datetime) <= '{end_date}'
        """

        result = db_client.query(query)
        row = result.first_row if result.result_rows else None

        db_client.close()

        if row:
            return {
                "table": "minute_candles",
                "rows": row[0],
                "days_collected": row[1],
                "min_datetime": str(row[2]) if row[2] else None,
                "max_datetime": str(row[3]) if row[3] else None,
                "unique_codes": row[4],
            }

        return {"table": "minute_candles", "rows": 0}

    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        return {"error": str(e)}


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "STOCK_UNIVERSE",
    "collect_stock_minute_today",
    "backfill_stock_minute",
    "get_stock_collection_status",
    "get_stock_db_client",
    "ensure_stock_database",
]
