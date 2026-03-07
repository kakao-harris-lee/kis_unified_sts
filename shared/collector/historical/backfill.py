"""
Historical Data Backfill Module

과거 1분봉 OHLCV 데이터를 수집합니다.

사용법:
    # CLI
    sts backfill --days 180
    sts backfill today
    sts backfill status

    # Python
    from shared.collector.historical import backfill, collect_today
    await backfill(days=180)
    await collect_today()
"""
import os
import asyncio
import logging
import re
from datetime import date, datetime, timedelta
from typing import List, Tuple, Set, Dict, Any, Optional

import httpx
import clickhouse_connect

from shared.config.secrets import SecretsManager
from shared.config.tls import get_clickhouse_tls_params
from .calendar import get_trading_days_range, is_after_market_close
from .futures import get_active_codes_for_date

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

def _get_clickhouse_config() -> Dict[str, Any]:
    """Get ClickHouse configuration from environment."""
    tls_params = get_clickhouse_tls_params()

    return {
        "host": os.getenv("CLICKHOUSE_HOST", "localhost"),
        "port": int(os.getenv("CLICKHOUSE_PORT", "8123")),
        "database": os.getenv("CLICKHOUSE_FUTURES_DATABASE", os.getenv("CLICKHOUSE_DATABASE", "kospi")),
        "user": os.getenv("CLICKHOUSE_USER", "default"),
        "password": os.getenv("CLICKHOUSE_PASSWORD", ""),
        **tls_params,
    }


def _get_kis_config() -> Dict[str, str]:
    """Get KIS API configuration from environment."""
    return {
        "app_key": SecretsManager.kis_app_key("futures") or "",
        "app_secret": SecretsManager.kis_app_secret("futures") or "",
    }


def _get_index_symbol() -> str:
    """Get KOSPI200 index symbol."""
    return os.getenv("INDEX_SYMBOL", os.getenv("ARBITRAGE_INDEX_SYMBOL", "0001"))


# =============================================================================
# KIS API Token Management
# =============================================================================

class KISToken:
    """한국투자증권 API 토큰 관리 (도메인별 분리)"""

    _instances: Dict[str, "KISToken"] = {}

    def __init__(self, domain: str = "futures"):
        self._domain = domain
        self._token: Optional[str] = None
        self._expires_at: float = 0
        self._cache_path = os.path.expanduser(f"~/.cache/kis_token_{domain}.json")
        self._load_cache()

    @classmethod
    def get_instance(cls, domain: str = "futures") -> "KISToken":
        """Get singleton instance for domain."""
        if domain not in cls._instances:
            cls._instances[domain] = cls(domain)
        return cls._instances[domain]

    def get(self) -> str:
        """현재 유효한 토큰 반환 (필요시 갱신)"""
        import time

        if self._token and time.time() < self._expires_at - 60:
            return self._token

        self._refresh()
        return self._token

    def _load_cache(self) -> None:
        """Load cached token if present and valid."""
        import json
        try:
            if not self._cache_path or not os.path.exists(self._cache_path):
                return
            with open(self._cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            token = data.get("access_token")
            expires_at = data.get("expires_at", 0)
            if token and expires_at:
                self._token = token
                self._expires_at = float(expires_at)
        except Exception:
            return

    def _save_cache(self) -> None:
        """Persist token to cache for reuse across runs."""
        import json
        if not self._cache_path or not self._token:
            return
        os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
        payload = {"access_token": self._token, "expires_at": self._expires_at}
        try:
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
        except Exception:
            return

    def _refresh(self):
        """토큰 갱신"""
        import requests
        import time

        # 도메인에 따라 키 선택
        app_key = SecretsManager.kis_app_key(self._domain) or ""
        app_secret = SecretsManager.kis_app_secret(self._domain) or ""

        if not app_key or not app_secret:
            raise ValueError(f"KIS API keys not set for domain: {self._domain}")

        url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"

        payload = {
            "grant_type": "client_credentials",
            "appkey": app_key,
            "appsecret": app_secret,
        }

        resp = requests.post(url, json=payload, timeout=30)
        data = resp.json()

        if "access_token" not in data:
            raise ValueError(f"Token refresh failed for {self._domain}: {data}")

        self._token = data["access_token"]
        expires_in = int(data.get("expires_in", 86400))
        self._expires_at = time.time() + expires_in
        self._save_cache()

        logger.info(f"[KISToken:{self._domain}] Token refreshed, expires in {expires_in}s")

    def is_token_valid(self) -> bool:
        """Check if current token is valid."""
        import time
        return bool(self._token and time.time() < self._expires_at - 60)

    def refresh_token(self) -> bool:
        """Refresh the token. Returns True on success."""
        try:
            self._refresh()
            return True
        except Exception as e:
            logger.warning(f"[KISToken:{self._domain}] Token refresh failed: {e}")
            return False


def _get_token(domain: str = "futures") -> KISToken:
    """Get token instance for domain."""
    return KISToken.get_instance(domain)


# =============================================================================
# Rate Limiter
# =============================================================================

class RateLimiter:
    """API Rate Limiter (requests per second)"""

    def __init__(self, rps: float = 20):
        self._min_interval = 1.0 / max(rps, 1e-6)
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0

    async def wait(self):
        loop = asyncio.get_running_loop()
        async with self._lock:
            now = loop.time()
            if now < self._next_allowed:
                await asyncio.sleep(self._next_allowed - now)
                now = loop.time()
            self._next_allowed = now + self._min_interval


_semaphore: Optional[asyncio.Semaphore] = None
_rate_limiter: Optional[RateLimiter] = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(10)
    return _semaphore


def _get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(20)
    return _rate_limiter


# =============================================================================
# API Fetching
# =============================================================================

async def fetch_minute_async(
    client: httpx.AsyncClient,
    code: str,
    date_str: str,
    max_retries: int = 3,
    max_pages: int = 20,
) -> Tuple[str, str, dict]:
    """
    Fetch minute data asynchronously with rate limiting and retry.

    Args:
        client: httpx async client
        code: Futures code (e.g., 'A05601')
        date_str: Date string in YYYYMMDD format
        max_retries: Maximum retry attempts
        max_pages: Maximum pagination pages per request date

    Returns:
        Tuple of (code, date, response_data)
    """
    # Futures API uses futures key
    app_key = SecretsManager.kis_app_key("futures") or ""
    app_secret = SecretsManager.kis_app_secret("futures") or ""
    token = _get_token("futures")
    base_url = "https://openapi.koreainvestment.com:9443"

    url = f"{base_url}/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice"
    hour_cls_code = str(os.getenv("KIS_FUTURES_HOUR_CLS_CODE", "60"))
    params = {
        "FID_COND_MRKT_DIV_CODE": "F",
        "FID_INPUT_ISCD": code,
        "FID_HOUR_CLS_CODE": hour_cls_code,
        "FID_PW_DATA_INCU_YN": "Y",
        "FID_FAKE_TICK_INCU_YN": "N",
        "FID_INPUT_DATE_1": date_str,
        "FID_INPUT_HOUR_1": "",
    }

    # Guard misconfiguration to avoid infinite/expensive loops.
    max_pages = max(1, int(max_pages))

    last_error = None
    for attempt in range(max_retries):
        headers = {
            "Authorization": f"Bearer {token.get()}",
            "appkey": app_key,
            "appsecret": app_secret,
            "tr_id": "FHKIF03020200",
            "content-type": "application/json; charset=utf-8",
        }

        async with _get_semaphore():
            try:
                # First page.
                await _get_rate_limiter().wait()
                resp = await client.get(url, headers=headers, params=params)

                if not resp.text or resp.text.strip() == "":
                    return (code, date_str, {"error": f"empty response (status {resp.status_code})"})

                try:
                    data = resp.json()
                except Exception as json_err:
                    return (code, date_str, {"error": f"json parse: {json_err}"})

                if data.get("rt_cd") != "0":
                    msg = data.get("msg1", "Unknown error")
                    return (code, date_str, {"error": msg})

                output2 = data.get("output2", [])
                if not isinstance(output2, list):
                    output2 = []

                # Paginate backward by FID_INPUT_HOUR_1. KIS responses overlap at
                # page boundaries (next page often starts with prior page's last row).
                merged_rows: list[dict[str, Any]] = []
                for item in output2:
                    if isinstance(item, dict):
                        merged_rows.append(item)

                cursor_hour = ""
                if merged_rows:
                    cursor_hour = str(merged_rows[-1].get("stck_cntg_hour", "") or "")

                pages_fetched = 1
                while cursor_hour and pages_fetched < max_pages:
                    page_params = dict(params)
                    page_params["FID_INPUT_HOUR_1"] = cursor_hour
                    await _get_rate_limiter().wait()
                    page_resp = await client.get(url, headers=headers, params=page_params)

                    if not page_resp.text or page_resp.text.strip() == "":
                        break

                    try:
                        page_data = page_resp.json()
                    except Exception:
                        break

                    if page_data.get("rt_cd") != "0":
                        break

                    page_rows_raw = page_data.get("output2", [])
                    if not isinstance(page_rows_raw, list):
                        break

                    page_rows = [row for row in page_rows_raw if isinstance(row, dict)]
                    if not page_rows:
                        break

                    # Drop overlapped first row if identical to previous page tail.
                    if merged_rows and page_rows and page_rows[0] == merged_rows[-1]:
                        page_rows = page_rows[1:]
                    if not page_rows:
                        break

                    merged_rows.extend(page_rows)
                    next_hour = str(page_rows[-1].get("stck_cntg_hour", "") or "")
                    if not next_hour or next_hour == cursor_hour:
                        break
                    cursor_hour = next_hour
                    pages_fetched += 1

                data["output2"] = merged_rows
                return (code, date_str, data)

            except (httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.ConnectError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"Retry {attempt + 1}/{max_retries} for {code} {date_str}: {e}")
                    await asyncio.sleep(wait_time)
                continue

            except Exception as e:
                logger.error(f"Error fetching {code} {date_str}: {e}")
                return (code, date_str, {"error": str(e)})

    return (code, date_str, {"error": str(last_error)})


async def fetch_index_minute_async(
    client: httpx.AsyncClient,
    index_symbol: str,
    date_str: str,
    max_retries: int = 3,
) -> Tuple[str, str, dict]:
    """
    Fetch KOSPI200 index minute data asynchronously.

    Note: Index API requires STOCK credentials, not futures.

    API: 업종 분봉조회 [v1_국내주식-045]
    - tr_id: FHKUP03500200
    - FID_INPUT_HOUR_1: 60 (1분봉)
    - FID_PW_DATA_INCU_YN: Y (과거 데이터 포함)
    """
    # Index API uses STOCK key (not futures)
    app_key = SecretsManager.kis_app_key("stock") or ""
    app_secret = SecretsManager.kis_app_secret("stock") or ""
    token = _get_token("stock")
    base_url = "https://openapi.koreainvestment.com:9443"

    url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-time-indexchartprice"
    tr_id = "FHKUP03500200"  # 업종 분봉조회

    params = {
        "FID_COND_MRKT_DIV_CODE": "U",
        "FID_ETC_CLS_CODE": "0",  # 0: 기본, 1: 장마감/시간외 제외
        "FID_INPUT_ISCD": index_symbol,  # 0001: 종합(KOSPI)
        "FID_INPUT_HOUR_1": "60",  # 60: 1분봉
        "FID_PW_DATA_INCU_YN": "Y",  # Y: 과거 데이터 포함
    }

    last_error = None
    for attempt in range(max_retries):
        headers = {
            "Authorization": f"Bearer {token.get()}",
            "appkey": app_key,
            "appsecret": app_secret,
            "tr_id": tr_id,
            "content-type": "application/json; charset=utf-8",
        }

        async with _get_semaphore():
            try:
                await _get_rate_limiter().wait()
                resp = await client.get(url, headers=headers, params=params)

                if not resp.text or resp.text.strip() == "":
                    return (index_symbol, date_str, {"error": f"empty response (status {resp.status_code})"})

                try:
                    data = resp.json()
                except Exception as json_err:
                    return (index_symbol, date_str, {"error": f"json parse: {json_err}"})

                if data.get("rt_cd") != "0":
                    msg = data.get("msg1", "Unknown error")
                    return (index_symbol, date_str, {"error": msg})

                return (index_symbol, date_str, data)

            except (httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.ConnectError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"Retry {attempt + 1}/{max_retries} for {index_symbol} {date_str}: {e}")
                    await asyncio.sleep(wait_time)
                continue

            except Exception as e:
                logger.error(f"Error fetching {index_symbol} {date_str}: {e}")
                return (index_symbol, date_str, {"error": str(e)})

    return (index_symbol, date_str, {"error": str(last_error)})


def _first_present(item: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    """Get first present value from dict."""
    for k in keys:
        v = item.get(k)
        if v is not None and (not isinstance(v, str) or v.strip()):
            return v
    return default


def parse_ohlcv(code: str, date_str: str, data: dict) -> List[Tuple]:
    """
    Parse API response to OHLCV rows.

    Args:
        code: Futures code
        date_str: Date string (YYYYMMDD)
        data: API response

    Returns:
        List of tuples (code, datetime, open, high, low, close, volume)
    """
    tick_rows: List[Tuple[datetime, float, float, float, float, int]] = []
    output = data.get("output2", []) or data.get("output1", []) or data.get("output", [])

    if not output:
        return []

    for item in output:
        # Skip non-dict items (API may return strings for invalid contracts)
        if not isinstance(item, dict):
            continue

        try:
            time_str = _first_present(
                item,
                ["stck_cntg_hour", "futs_cntg_hour", "cntg_hour", "bsop_hour", "hour"],
                default="",
            )
            if not time_str:
                continue

            if len(time_str) == 4:
                time_str = f"{time_str}00"

            dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")

            o = _first_present(
                item,
                ["futs_oprc", "open", "stck_oprc", "bstp_nmix_oprc", "oprc"],
                0,
            )
            h = _first_present(
                item,
                ["futs_hgpr", "high", "stck_hgpr", "bstp_nmix_hgpr", "hgpr"],
                0,
            )
            l = _first_present(
                item,
                ["futs_lwpr", "low", "stck_lwpr", "bstp_nmix_lwpr", "lwpr"],
                0,
            )
            c = _first_present(
                item,
                ["futs_prpr", "close", "stck_prpr", "stck_clpr", "bstp_nmix_prpr", "prpr"],
                0,
            )
            v = _first_present(item, ["cntg_vol", "acml_vol", "volume"], 0)

            tick_rows.append(
                (
                    dt,
                    float(o or 0),
                    float(h or 0),
                    float(l or 0),
                    float(c or 0),
                    int(v or 0),
                )
            )
        except (ValueError, TypeError):
            continue

    if not tick_rows:
        return []

    # Normalize raw ticks/seconds to 1-minute OHLCV bars.
    tick_rows.sort(key=lambda row: row[0])
    minute_bars: Dict[datetime, List[float | int]] = {}
    for dt, o, h, l, c, v in tick_rows:
        minute_dt = dt.replace(second=0, microsecond=0)
        if minute_dt not in minute_bars:
            minute_bars[minute_dt] = [o, h, l, c, int(v)]
            continue

        bar = minute_bars[minute_dt]
        # open: keep first
        bar[1] = max(float(bar[1]), h)  # high
        bar[2] = min(float(bar[2]), l)  # low
        bar[3] = c  # close: last tick in minute
        bar[4] = int(bar[4]) + int(v)  # volume sum

    rows: List[Tuple] = []
    for minute_dt in sorted(minute_bars.keys()):
        o, h, l, c, v = minute_bars[minute_dt]
        rows.append((code, minute_dt, float(o), float(h), float(l), float(c), int(v)))
    return rows


# =============================================================================
# Database Operations
# =============================================================================

def get_db_client(database: str = None):
    """Get ClickHouse client."""
    config = _get_clickhouse_config()
    return clickhouse_connect.get_client(
        host=config["host"],
        port=config["port"],
        database=database or config["database"],
        username=config["user"] or None,
        password=config["password"] or None,
        secure=config["secure"],
        verify=config["verify"],
        ca_cert=config["ca_cert"],
    )


def ensure_database():
    """Create database if not exists."""
    config = _get_clickhouse_config()
    client = get_db_client(database=None)
    client.command(f"CREATE DATABASE IF NOT EXISTS {config['database']}")
    client.close()


def ensure_table(client=None, table_name: str = "kospi_mini_1m"):
    """Create table if not exists."""
    if client is None:
        client = get_db_client()

    config = _get_clickhouse_config()
    client.command(f"""
        CREATE TABLE IF NOT EXISTS {config['database']}.{table_name} (
            code String,
            datetime DateTime,
            open Float64,
            high Float64,
            low Float64,
            close Float64,
            volume UInt64
        ) ENGINE = ReplacingMergeTree()
        ORDER BY (code, datetime)
    """)


def ensure_kospi200f_table(client=None):
    """Create KOSPI 200 Futures (full-size) table if not exists."""
    ensure_table(client, table_name="kospi200f_1m")


def ensure_kospi200_index_table(client=None):
    """Create KOSPI 200 Index table if not exists."""
    ensure_table(client, table_name="kospi200_index_1m")


def insert_batch(client, rows: List[Tuple], table_name: str = "kospi_mini_1m"):
    """Batch insert OHLCV data."""
    if not rows:
        return

    values = []
    for row in rows:
        code, dt, open_, high, low, close, volume = row
        dt_str = dt.strftime('%Y-%m-%d %H:%M:%S') if hasattr(dt, 'strftime') else str(dt)
        values.append(f"('{code}', '{dt_str}', {open_}, {high}, {low}, {close}, {volume})")

    sql = f"""
        INSERT INTO {table_name} (code, datetime, open, high, low, close, volume)
        VALUES {', '.join(values)}
    """
    client.command(sql)


def get_collected_pairs_in_range(
    client,
    start: date,
    end: date,
    table_name: str = "kospi_mini_1m",
) -> Set[Tuple[str, date]]:
    """Get collected (code, date) pairs for a date range."""
    result = client.query(
        f"""
        SELECT DISTINCT code, toDate(datetime) as dt
        FROM {table_name}
        WHERE dt >= %(start)s AND dt <= %(end)s
        """,
        parameters={"start": start, "end": end},
    )
    return {(row[0], row[1]) for row in result.result_rows}


def get_data_status(days: int = 30) -> Dict[str, Any]:
    """Get data collection status summary."""
    end = date.today()
    start = end - timedelta(days=days)
    trading_days = get_trading_days_range(start, end)

    status = {
        "period": f"{start} ~ {end}",
        "trading_days": len(trading_days),
        "tables": {},
    }

    try:
        db_client = get_db_client()
        config = _get_clickhouse_config()

        for table_name in ["kospi_mini_1m", "kospi200f_1m", "kospi200_index_1m"]:
            try:
                result = db_client.query(
                    f"""
                    SELECT
                        count() as rows,
                        countDistinct(toDate(datetime)) as days,
                        min(datetime) as min_dt,
                        max(datetime) as max_dt
                    FROM {config['database']}.{table_name}
                    WHERE toDate(datetime) >= %(start)s AND toDate(datetime) <= %(end)s
                    """,
                    parameters={"start": start, "end": end},
                )
                row = result.result_rows[0] if result.result_rows else (0, 0, None, None)
                status["tables"][table_name] = {
                    "rows": row[0],
                    "days_collected": row[1],
                    "min_datetime": str(row[2]) if row[2] else None,
                    "max_datetime": str(row[3]) if row[3] else None,
                }
            except Exception as e:
                status["tables"][table_name] = {"error": str(e)}

        db_client.close()
    except Exception as e:
        status["error"] = str(e)

    return status


def load_futures_minute_from_clickhouse(
    code: str,
    start_date: date | None = None,
    end_date: date | None = None,
    table_name: str | None = None,
) -> "pd.DataFrame":
    """Load futures minute candles from ClickHouse for backtest.

    Args:
        code: Futures symbol (e.g., ``101S6000`` or ``A05603``).
        start_date: Inclusive lower bound (KST date).
        end_date: Inclusive upper bound (KST date).
        table_name: Optional table override. Defaults to ``FUTURES_CANDLE_TABLE``
            environment variable, then ``kospi200f_1m``.

    Returns:
        DataFrame columns: ``code, datetime, open, high, low, close, volume``.

    Raises:
        ValueError: when no rows are found or table name is invalid.
    """
    import pandas as pd

    config = _get_clickhouse_config()
    table = table_name or os.getenv("FUTURES_CANDLE_TABLE", "kospi200f_1m")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table or ""):
        raise ValueError(f"Invalid futures table name: {table!r}")

    db_client = get_db_client()
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
        FROM {config['database']}.{table}
        WHERE {where}
        ORDER BY datetime ASC
    """

    try:
        result = db_client.query(query, parameters=params)
    finally:
        db_client.close()

    if not result.result_rows:
        raise ValueError(
            f"No futures data found for {code} in {config['database']}.{table} "
            f"(range: {start_date} ~ {end_date})"
        )

    df = pd.DataFrame(
        result.result_rows,
        columns=["code", "datetime", "open", "high", "low", "close", "volume"],
    )
    dt = pd.to_datetime(df["datetime"])
    if getattr(dt.dt, "tz", None) is not None:
        dt = dt.dt.tz_localize(None)
    df["datetime"] = dt
    return df


# =============================================================================
# Backfill Functions
# =============================================================================

async def collect_batch(
    client: httpx.AsyncClient,
    db_client,
    tasks: List[Tuple[str, date]],
    table_name: str = "kospi_mini_1m"
) -> int:
    """
    Collect a batch of (code, date) combinations.

    Returns:
        Number of rows inserted
    """
    if not tasks:
        return 0

    max_pages = max(1, int(os.getenv("KIS_FUTURES_MAX_PAGES", "20")))
    coros = [
        fetch_minute_async(client, code, dt.strftime("%Y%m%d"), max_pages=max_pages)
        for code, dt in tasks
    ]

    results = await asyncio.gather(*coros)

    all_rows = []
    for code, date_str, data in results:
        if "error" in data:
            logger.warning(f"Fetch failed for {code} {date_str}: {data['error']}")
            continue
        rows = parse_ohlcv(code, date_str, data)
        all_rows.extend(rows)

    if all_rows:
        insert_batch(db_client, all_rows, table_name=table_name)
        print(f"Inserted {len(all_rows)} rows from {len(tasks)} tasks into {table_name}")

    return len(all_rows)


async def collect_index_batch(
    client: httpx.AsyncClient,
    db_client,
    tasks: List[Tuple[str, date]],
    table_name: str = "kospi200_index_1m",
) -> int:
    """
    Collect a batch of (index_symbol, date) combinations.
    """
    if not tasks:
        return 0

    coros = [
        fetch_index_minute_async(client, symbol, dt.strftime("%Y%m%d"))
        for symbol, dt in tasks
    ]

    results = await asyncio.gather(*coros)

    all_rows = []
    for symbol, date_str, data in results:
        if "error" in data:
            logger.warning(f"Index fetch failed for {symbol} {date_str}: {data['error']}")
            continue
        rows = parse_ohlcv(symbol, date_str, data)
        all_rows.extend(rows)

    if all_rows:
        insert_batch(db_client, all_rows, table_name=table_name)
        print(f"Inserted {len(all_rows)} rows from {len(tasks)} tasks into {table_name}")

    return len(all_rows)


async def backfill(days: int = 365, verbose: bool = True, resume: bool = True):
    """
    Run backfill for the past N days.

    Args:
        days: Number of days to backfill
        verbose: Print progress
    """
    if verbose:
        print("Starting backfill...")

    start = date.today() - timedelta(days=max(days, 1))
    end = date.today()
    trading_days = get_trading_days_range(start, end)

    if verbose:
        print(f"Trading days: {len(trading_days)}")

    ensure_database()
    db_client = get_db_client()
    ensure_table(db_client)

    collected: Set[Tuple[str, date]] = set()
    if resume:
        try:
            collected = get_collected_pairs_in_range(db_client, start, end)
        except Exception as e:
            logger.warning(
                f"Failed to get collected pairs (proceeding with empty set): {e}"
            )

    total_rows = 0
    total_tasks = 0

    trading_days_iter = list(reversed(trading_days))

    async with httpx.AsyncClient(timeout=30.0) as client:
        for idx, day in enumerate(trading_days_iter, start=1):
            codes = get_active_codes_for_date(day)
            day_tasks = [(code, day) for code in codes if (code, day) not in collected]

            if not day_tasks:
                continue

            total_tasks += len(day_tasks)
            if verbose:
                print(f"{idx}/{len(trading_days_iter)} {day} tasks={len(day_tasks)}")

            rows = await collect_batch(client, db_client, day_tasks)
            total_rows += rows

    if verbose:
        print(f"Backfill complete. tasks={total_tasks}, rows={total_rows}")

    return total_rows


async def collect_today(verbose: bool = True):
    """
    Collect today's data (run after market close).
    """
    if not is_after_market_close():
        if verbose:
            print("Market is still open. Please run after 15:45 KST.")
        return 0

    today = date.today()

    if verbose:
        print(f"Collecting data for {today}")

    codes = get_active_codes_for_date(today)

    ensure_database()
    db_client = get_db_client()
    ensure_table(db_client)

    tasks = [(code, today) for code in codes]

    async with httpx.AsyncClient(timeout=30.0) as client:
        rows = await collect_batch(client, db_client, tasks)

    if verbose:
        print(f"Today's collection complete. Rows: {rows}")

    return rows


# =============================================================================
# KOSPI 200 Index Backfill
# =============================================================================

async def backfill_kospi200_index(
    days: int = 365,
    verbose: bool = True,
    resume: bool = True,
):
    """
    Run backfill for KOSPI 200 Index for the past N days.
    """
    if verbose:
        print("Starting KOSPI 200 Index backfill...")

    start = date.today() - timedelta(days=max(days, 1))
    end = date.today()
    trading_days = get_trading_days_range(start, end)

    if verbose:
        print(f"Trading days: {len(trading_days)}")

    ensure_database()
    db_client = get_db_client()
    ensure_kospi200_index_table(db_client)

    collected_dates: Set[date] = set()
    if resume:
        try:
            result = db_client.query(
                """
                SELECT DISTINCT toDate(datetime) as dt
                FROM kospi200_index_1m
                WHERE dt >= %(start)s AND dt <= %(end)s
                """,
                parameters={"start": start, "end": end},
            )
            collected_dates = {row[0] for row in result.result_rows}
        except Exception as e:
            logger.warning(
                f"Failed to get collected dates (proceeding with empty set): {e}"
            )

    total_rows = 0
    trading_days_iter = list(reversed(trading_days))
    index_symbol = _get_index_symbol()

    async with httpx.AsyncClient(timeout=30.0) as client:
        for idx, day in enumerate(trading_days_iter, start=1):
            if day in collected_dates:
                continue

            if verbose:
                print(f"{idx}/{len(trading_days_iter)} {day}")

            tasks = [(index_symbol, day)]
            rows = await collect_index_batch(client, db_client, tasks, table_name="kospi200_index_1m")
            total_rows += rows

    if verbose:
        print(f"KOSPI 200 Index backfill complete. rows={total_rows}")

    return total_rows


async def collect_today_kospi200_index(verbose: bool = True):
    """
    Collect today's KOSPI 200 Index data (run after market close).
    """
    if not is_after_market_close():
        if verbose:
            print("Market is still open. Please run after 15:45 KST.")
        return 0

    today = date.today()

    if verbose:
        print(f"Collecting KOSPI 200 Index data for {today}")

    ensure_database()
    db_client = get_db_client()
    ensure_kospi200_index_table(db_client)

    tasks = [(_get_index_symbol(), today)]

    async with httpx.AsyncClient(timeout=30.0) as client:
        rows = await collect_index_batch(client, db_client, tasks, table_name="kospi200_index_1m")

    if verbose:
        print(f"Today's KOSPI 200 Index collection complete. Rows: {rows}")

    return rows


# =============================================================================
# KOSPI 200 Futures (Full-Size) Backfill
# =============================================================================

def _get_kospi200f_codes_for_date(target_date: date) -> List[str]:
    """
    Get active KOSPI 200 Futures (full-size) codes for a specific date.

    KOSPI 200 Futures have quarterly expiry (Mar, Jun, Sep, Dec).
    Uses legacy A01 prefix format.
    """
    from .futures import get_expiry_date, KOSPI200_LEGACY_PREFIX

    codes = []
    # KOSPI200 Futures are quarterly: Mar(3), Jun(6), Sep(9), Dec(12)
    quarterly_months = [3, 6, 9, 12]

    # Check current year and next year
    for year in [target_date.year, target_date.year + 1]:
        for month in quarterly_months:
            try:
                expiry = get_expiry_date(year, month)
                if target_date <= expiry:
                    # Legacy format: A01{year_digit}{month:02d}
                    year_digit = str(year)[-1]
                    code = f"{KOSPI200_LEGACY_PREFIX}{year_digit}{month:02d}"
                    codes.append(code)
            except Exception:
                continue

    return codes[:4]  # Return up to 4 nearest contracts


async def backfill_kospi200f(
    days: int = 365,
    verbose: bool = True,
    resume: bool = True,
):
    """
    Run backfill for KOSPI 200 Futures (full-size) for the past N days.

    Uses actual contract codes (A01xxx) instead of auto-rolling code.

    Args:
        days: Number of days to backfill
        verbose: Print progress
    """
    if verbose:
        print("Starting KOSPI 200 Futures backfill...")

    start = date.today() - timedelta(days=max(days, 1))
    end = date.today()
    trading_days = get_trading_days_range(start, end)

    if verbose:
        print(f"Trading days: {len(trading_days)}")

    ensure_database()
    db_client = get_db_client()
    ensure_kospi200f_table(db_client)

    # Check what we already have
    collected: Set[Tuple[str, date]] = set()
    if resume:
        try:
            collected = get_collected_pairs_in_range(
                db_client,
                start,
                end,
                table_name="kospi200f_1m",
            )
        except Exception as e:
            logger.warning(
                f"Failed to get collected pairs (proceeding with empty set): {e}"
            )

    total_rows = 0
    total_tasks = 0
    trading_days_iter = list(reversed(trading_days))

    async with httpx.AsyncClient(timeout=30.0) as client:
        for idx, day in enumerate(trading_days_iter, start=1):
            codes = _get_kospi200f_codes_for_date(day)
            day_tasks = [(code, day) for code in codes if (code, day) not in collected]

            if not day_tasks:
                continue

            total_tasks += len(day_tasks)
            if verbose:
                print(f"{idx}/{len(trading_days_iter)} {day} codes={[c for c, _ in day_tasks]}")

            rows = await collect_batch(client, db_client, day_tasks, table_name="kospi200f_1m")
            total_rows += rows

    if verbose:
        print(f"KOSPI 200 Futures backfill complete. tasks={total_tasks}, rows={total_rows}")

    return total_rows


async def collect_today_kospi200f(verbose: bool = True):
    """
    Collect today's KOSPI 200 Futures data (run after market close).
    """
    if not is_after_market_close():
        if verbose:
            print("Market is still open. Please run after 15:45 KST.")
        return 0

    today = date.today()

    if verbose:
        print(f"Collecting KOSPI 200 Futures data for {today}")

    codes = _get_kospi200f_codes_for_date(today)

    if verbose:
        print(f"Active codes: {codes}")

    ensure_database()
    db_client = get_db_client()
    ensure_kospi200f_table(db_client)

    tasks = [(code, today) for code in codes]

    async with httpx.AsyncClient(timeout=30.0) as client:
        rows = await collect_batch(client, db_client, tasks, table_name="kospi200f_1m")

    if verbose:
        print(f"Today's KOSPI 200 Futures collection complete. Rows: {rows}")

    return rows


async def backfill_all(
    days: int = 365,
    verbose: bool = True,
    resume: bool = True,
):
    """
    Backfill all data types: Mini Futures, KOSPI 200 Index, and KOSPI 200 Futures.
    """
    if verbose:
        print("=== Backfilling Mini Futures ===")
    await backfill(days=days, verbose=verbose, resume=resume)

    if verbose:
        print("\n=== Backfilling KOSPI 200 Index ===")
    await backfill_kospi200_index(days=days, verbose=verbose, resume=resume)

    if verbose:
        print("\n=== Backfilling KOSPI 200 Futures ===")
    await backfill_kospi200f(days=days, verbose=verbose, resume=resume)


async def collect_today_all(verbose: bool = True):
    """
    Collect today's data for all types.
    """
    if verbose:
        print("=== Collecting Mini Futures ===")
    await collect_today(verbose=verbose)

    if verbose:
        print("\n=== Collecting KOSPI 200 Index ===")
    await collect_today_kospi200_index(verbose=verbose)

    if verbose:
        print("\n=== Collecting KOSPI 200 Futures ===")
    await collect_today_kospi200f(verbose=verbose)
