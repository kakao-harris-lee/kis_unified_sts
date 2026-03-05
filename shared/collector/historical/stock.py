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
                json.dump({
                    "token": self._token,
                    "access_token": self._token,
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


def _get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(_rate_limit_per_sec)
    return _rate_limiter


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(_max_concurrent_requests)
    return _semaphore


# =============================================================================
# Database Operations
# =============================================================================

def get_stock_db_client() -> clickhouse_connect.driver.client.Client:
    """Get ClickHouse client for stock database."""
    config = _get_clickhouse_config()
    return clickhouse_connect.get_client(
        host=config["host"],
        port=config["port"],
        username=config["user"],
        password=config["password"],
        database=config["database"],
    )


def ensure_stock_database() -> None:
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


def insert_stock_minute_batch(db_client, rows: List[Tuple], table_name: str = "minute_candles") -> int:
    """Insert stock minute data batch."""
    if not rows:
        return 0

    db_client.insert(
        table_name,
        rows,
        column_names=["code", "datetime", "open", "high", "low", "close", "volume", "value"],
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
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load state file: {e}")
    return {"completed_days": {}, "last_run": None}


def save_collection_state(state: Dict) -> None:
    """Save collection state to file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(STATE_FILE, 'w') as f:
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
        task_list: List[Tuple[str, date]]
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
    verbose: bool = True,
    resume: bool = True,
) -> int:
    """
    Backfill stock minute data for specified days.

    Args:
        days: Number of days to backfill (max 180)
        codes: Specific codes to backfill (None = all universe)
        verbose: Print progress
        resume: Skip already-collected days (for long backfills)

    Returns:
        Total rows collected
    """
    days = min(days, 180)

    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    trading_days = get_trading_days_range(start_date, end_date)
    if not trading_days:
        if verbose:
            print("No trading days in range")
        return 0

    # Select codes
    if codes:
        selected_codes = list(dict.fromkeys(codes))
    else:
        selected_codes = [s["code"] for s in STOCK_UNIVERSE]

    # Resume: load state and skip completed days
    state = load_collection_state() if resume else {"completed_days": {}}
    completed = state.get("completed_days", {})
    codes_key = ",".join(sorted(selected_codes))

    if resume:
        original_count = len(trading_days)
        trading_days = [
            d for d in trading_days
            if f"{d.isoformat()}:{codes_key}" not in completed
        ]
        skipped = original_count - len(trading_days)
        if skipped > 0 and verbose:
            print(f"Resuming: skipping {skipped} already-collected days")

    if not trading_days:
        if verbose:
            print("All days already collected (use --no-resume to force re-collect)")
        return 0

    if verbose:
        print(f"Stock Minute Backfill")
        print(f"Trading days: {len(trading_days)}")
        print(f"Date range: {trading_days[0]} ~ {trading_days[-1]}")
        print(f"Stocks: {len(selected_codes)}")

    ensure_stock_database()
    db_client = get_stock_db_client()

    total_rows = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for day_idx, day in enumerate(reversed(trading_days), start=1):
            tasks = [(code, day) for code in selected_codes]

            if verbose:
                print(f"{day_idx}/{len(trading_days)} {day} stocks={len(tasks)}")

            rows = await collect_stock_batch(client, db_client, tasks)
            total_rows += rows

            # Mark day as completed and save state
            if resume and rows > 0:
                completed[f"{day.isoformat()}:{codes_key}"] = True
                state["completed_days"] = completed
                state["last_run"] = datetime.now().isoformat()
                save_collection_state(state)

            # Throttle between days for long backfills
            if len(trading_days) > 30:
                await asyncio.sleep(1.0)

    db_client.close()

    if verbose:
        print(f"Backfill complete. Total rows: {total_rows}")

    return total_rows


def get_stock_codes_from_db(days: Optional[int] = None) -> List[str]:
    """Get distinct stock codes from ClickHouse minute_candles."""
    db_client = get_stock_db_client()
    try:
        if days:
            start_date = date.today() - timedelta(days=days)
            query = """
                SELECT DISTINCT code
                FROM minute_candles
                WHERE toDate(datetime) >= {start:Date}
                ORDER BY code
            """
            result = db_client.query(query, parameters={"start": start_date})
        else:
            query = """
                SELECT DISTINCT code
                FROM minute_candles
                ORDER BY code
            """
            result = db_client.query(query)

        return [row[0] for row in result.result_rows]
    finally:
        db_client.close()


def get_stock_collection_status(days: int = 30) -> Dict:
    """Get collection status with per-stock detail."""
    try:
        db_client = get_stock_db_client()

        start_date = date.today() - timedelta(days=days)
        result = db_client.query("""
            SELECT
                count(*) as rows,
                count(DISTINCT toDate(datetime)) as days_collected,
                count(DISTINCT code) as unique_codes,
                min(datetime) as min_datetime,
                max(datetime) as max_datetime
            FROM minute_candles
            WHERE datetime >= {start:Date}
        """, parameters={"start": start_date})

        row = result.result_rows[0] if result.result_rows else (0, 0, 0, None, None)

        per_stock = db_client.query("""
            SELECT
                code,
                count(*) as bars,
                count(DISTINCT toDate(datetime)) as trading_days,
                min(datetime) as earliest,
                max(datetime) as latest
            FROM minute_candles
            WHERE datetime >= {start:Date}
            GROUP BY code
            ORDER BY bars DESC
        """, parameters={"start": start_date})

        stocks_detail = []
        for sr in per_stock.result_rows:
            stocks_detail.append({
                "code": sr[0],
                "bars": sr[1],
                "trading_days": sr[2],
                "earliest": str(sr[3]) if sr[3] else None,
                "latest": str(sr[4]) if sr[4] else None,
            })

        db_client.close()

        return {
            "table": "minute_candles",
            "rows": row[0],
            "days_collected": row[1],
            "unique_codes": row[2],
            "min_datetime": str(row[3]) if row[3] else None,
            "max_datetime": str(row[4]) if row[4] else None,
            "stocks": stocks_detail,
        }
    except Exception as e:
        return {"error": str(e)}


def load_stock_minute_from_clickhouse(
    code: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> "pd.DataFrame":
    """
    Load stock minute data from ClickHouse as a DataFrame suitable for BacktestEngine.

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
    import pandas as pd

    db_client = get_stock_db_client()

    conditions = ["code = %(code)s"]
    params: Dict[str, Any] = {"code": code}
    if start_date:
        conditions.append("datetime >= %(start)s")
        params["start"] = start_date
    if end_date:
        conditions.append("datetime <= %(end)s")
        params["end"] = datetime.combine(end_date, datetime.max.time())

    where = " AND ".join(conditions)
    query = f"""
        SELECT code, datetime, open, high, low, close, volume
        FROM minute_candles
        WHERE {where}
        ORDER BY datetime ASC
    """

    result = db_client.query(query, parameters=params)
    db_client.close()

    if not result.result_rows:
        raise ValueError(f"No data found for {code} in ClickHouse (range: {start_date} ~ {end_date})")

    df = pd.DataFrame(
        result.result_rows,
        columns=["code", "datetime", "open", "high", "low", "close", "volume"],
    )

    # Ensure datetime is pandas Timestamp (ClickHouse returns Python datetime)
    df["datetime"] = pd.to_datetime(df["datetime"])

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
    "load_stock_minute_from_clickhouse",
]
