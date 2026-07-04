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

import asyncio
import logging
import os
from datetime import date, datetime
from typing import Any

import httpx

from shared.collector.historical.ohlcv_parser import (
    _DIVERGENCE_MAX_STEP_FRACTION as _DIVERGENCE_MAX_STEP_FRACTION,
)
from shared.collector.historical.ohlcv_parser import (
    _first_present as _first_present,
)
from shared.collector.historical.ohlcv_parser import (
    _resolve_minute_bars as _resolve_minute_bars,
)
from shared.collector.historical.ohlcv_parser import (
    parse_ohlcv as parse_ohlcv,
)
from shared.config.secrets import SecretsManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pagination retry constants (per-page, not the whole-request retry)
# ---------------------------------------------------------------------------
# On HTTP 500 / rt_cd != "0" for page 2+, retry up to PAGE_MAX_RETRIES times
# before breaking and returning whatever rows have been gathered so far.
PAGE_MAX_RETRIES: int = 3
PAGE_RETRY_BACKOFF_BASE: float = 2.0  # seconds; multiplied by attempt number


# =============================================================================
# Configuration
# =============================================================================


def _get_kis_config() -> dict[str, str]:
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

    _instances: dict[str, "KISToken"] = {}

    def __init__(self, domain: str = "futures"):
        self._domain = domain
        self._token: str | None = None
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
            with open(self._cache_path, encoding="utf-8") as f:
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
        import time

        import requests

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

        logger.info(
            f"[KISToken:{self._domain}] Token refreshed, expires in {expires_in}s"
        )

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


_semaphore: asyncio.Semaphore | None = None
_rate_limiter: RateLimiter | None = None
_semaphore_loop: asyncio.AbstractEventLoop | None = None
_rate_limiter_loop: asyncio.AbstractEventLoop | None = None


def _get_semaphore() -> asyncio.Semaphore:
    # KIS allows ~5 req/s; bursting at 10-concurrent triggered the 500 cascade.
    # Override via BACKFILL_CONCURRENCY env var (default: 3).
    global _semaphore, _semaphore_loop
    loop = asyncio.get_running_loop()
    if _semaphore is None or _semaphore_loop is not loop:
        concurrency = int(os.getenv("BACKFILL_CONCURRENCY", "3"))
        _semaphore = asyncio.Semaphore(concurrency)
        _semaphore_loop = loop
    return _semaphore


def _get_rate_limiter() -> RateLimiter:
    # KIS allows ~5 req/s; bursting at 20 rps triggered the 500 cascade.
    # Override via BACKFILL_RPS env var (default: 5).
    global _rate_limiter, _rate_limiter_loop
    loop = asyncio.get_running_loop()
    if _rate_limiter is None or _rate_limiter_loop is not loop:
        rps = int(os.getenv("BACKFILL_RPS", "5"))
        _rate_limiter = RateLimiter(rps)
        _rate_limiter_loop = loop
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
) -> tuple[str, str, dict]:
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
                    return (
                        code,
                        date_str,
                        {"error": f"empty response (status {resp.status_code})"},
                    )

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

                    # Per-page retry: on transient error (rt_cd != "0") OR network
                    # exception (Timeout, ConnectError, etc.), retry the SAME cursor
                    # up to PAGE_MAX_RETRIES times before giving up.
                    # Genuinely terminal conditions (empty page, cursor non-advance)
                    # are handled AFTER a successful (rt_cd == "0") response and are
                    # NOT retried — they exit the while-loop normally.
                    page_rows: list[dict] = []
                    page_fetch_ok = False
                    for page_attempt in range(PAGE_MAX_RETRIES):
                        try:
                            await _get_rate_limiter().wait()
                            page_resp = await client.get(
                                url, headers=headers, params=page_params
                            )
                        except (
                            httpx.TimeoutException,
                            httpx.ReadTimeout,
                            httpx.ConnectError,
                            httpx.RemoteProtocolError,
                        ) as net_err:
                            # Transient network error on this page — retry same cursor.
                            if page_attempt < PAGE_MAX_RETRIES - 1:
                                wait_s = PAGE_RETRY_BACKOFF_BASE * (page_attempt + 1)
                                logger.warning(
                                    "Page %d for %s %s network error (%s); "
                                    "retry %d/%d in %.1fs",
                                    pages_fetched + 1,
                                    code,
                                    date_str,
                                    net_err,
                                    page_attempt + 1,
                                    PAGE_MAX_RETRIES,
                                    wait_s,
                                )
                                await asyncio.sleep(wait_s)
                            continue  # retry same cursor

                        if not page_resp.text or page_resp.text.strip() == "":
                            # Empty HTTP body — treat as terminal, not retryable.
                            break

                        try:
                            page_data = page_resp.json()
                        except Exception:
                            # Unparseable response — treat as terminal.
                            break

                        if page_data.get("rt_cd") != "0":
                            # Transient KIS error (e.g. HTTP 500 wrapper or EGW error).
                            # Retry with backoff unless retries are exhausted.
                            if page_attempt < PAGE_MAX_RETRIES - 1:
                                wait_s = PAGE_RETRY_BACKOFF_BASE * (page_attempt + 1)
                                logger.warning(
                                    "Page %d for %s %s returned rt_cd=%s; "
                                    "retry %d/%d in %.1fs",
                                    pages_fetched + 1,
                                    code,
                                    date_str,
                                    page_data.get("rt_cd"),
                                    page_attempt + 1,
                                    PAGE_MAX_RETRIES,
                                    wait_s,
                                )
                                await asyncio.sleep(wait_s)
                            continue  # retry same cursor

                        # rt_cd == "0": parse rows and decide whether to continue
                        page_rows_raw = page_data.get("output2", [])
                        if not isinstance(page_rows_raw, list):
                            break  # malformed — treat as terminal

                        page_rows = [
                            row for row in page_rows_raw if isinstance(row, dict)
                        ]
                        page_fetch_ok = True
                        break  # successful fetch; exit retry loop

                    if not page_fetch_ok:
                        # All retries exhausted or a terminal condition hit.
                        # Return whatever rows we have gathered so far (best-effort).
                        break

                    if not page_rows:
                        # rt_cd == "0" but no rows → genuine end-of-data.
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

            except (
                httpx.RemoteProtocolError,
                httpx.ReadTimeout,
                httpx.ConnectError,
            ) as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {code} {date_str}: {e}"
                    )
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
) -> tuple[str, str, dict]:
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
                    return (
                        index_symbol,
                        date_str,
                        {"error": f"empty response (status {resp.status_code})"},
                    )

                try:
                    data = resp.json()
                except Exception as json_err:
                    return (
                        index_symbol,
                        date_str,
                        {"error": f"json parse: {json_err}"},
                    )

                if data.get("rt_cd") != "0":
                    msg = data.get("msg1", "Unknown error")
                    return (index_symbol, date_str, {"error": msg})

                return (index_symbol, date_str, data)

            except (
                httpx.RemoteProtocolError,
                httpx.ReadTimeout,
                httpx.ConnectError,
            ) as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {index_symbol} {date_str}: {e}"
                    )
                    await asyncio.sleep(wait_time)
                continue

            except Exception as e:
                logger.error(f"Error fetching {index_symbol} {date_str}: {e}")
                return (index_symbol, date_str, {"error": str(e)})

    return (index_symbol, date_str, {"error": str(last_error)})


# =============================================================================
# Database Operations
# =============================================================================


def get_db_client(database: str = None):
    """Legacy DB client entrypoint removed; use Parquet backfill commands."""
    _ = database
    raise RuntimeError("Legacy DB sink removed; use Parquet backfill/status commands")


def ensure_database():
    """Legacy no-op retained for backward-compatible imports."""
    return None


def ensure_table(client=None, table_name: str = "kospi_mini_1m"):
    """Legacy no-op retained for backward-compatible imports."""
    _ = client, table_name
    return None


def ensure_kospi200f_table(client=None):
    """Create KOSPI 200 Futures (full-size) table if not exists."""
    ensure_table(client, table_name="kospi200f_1m")


def ensure_kospi200_index_table(client=None):
    """Create KOSPI 200 Index table if not exists."""
    ensure_table(client, table_name="kospi200_index_1m")


def insert_batch(client, rows: list[tuple], table_name: str = "kospi_mini_1m"):
    """Legacy DB insert removed."""
    _ = client, rows, table_name
    raise RuntimeError("Legacy DB inserts have been removed; write Parquet instead")


def _load_continuous_source_rows(
    client,
    start: date,
    end: date,
    table_name: str = "kospi200f_1m",
) -> list[tuple[str, datetime, float, float, float, float, int]]:
    """Load A01* full-size futures rows for continuous-contract reconstruction."""
    result = client.query(
        f"""
        SELECT
            code,
            datetime,
            open,
            high,
            low,
            close,
            volume
        FROM {table_name} FINAL
        WHERE code LIKE 'A01%%'
          AND toDate(datetime) >= %(start)s
          AND toDate(datetime) <= %(end)s
        ORDER BY datetime, code
        """,
        parameters={"start": start, "end": end},
    )
    return list(result.result_rows)


def _build_continuous_rows(
    rows: list[tuple[str, datetime, float, float, float, float, int]],
) -> list[tuple[str, datetime, float, float, float, float, int]]:
    """Build 101S6000 rows by selecting the dominant contract for each day."""
    if not rows:
        return []

    daily_volume: dict[date, dict[str, int]] = {}
    for code, dt, _open, _high, _low, _close, volume in rows:
        daily_contracts = daily_volume.setdefault(dt.date(), {})
        daily_contracts[code] = daily_contracts.get(code, 0) + int(volume or 0)

    dominant_contract_by_day: dict[date, str] = {}
    for day, contract_volume in daily_volume.items():
        dominant_contract_by_day[day] = sorted(
            contract_volume.items(),
            key=lambda item: (-item[1], item[0]),
        )[0][0]

    rebuilt_rows: list[tuple[str, datetime, float, float, float, float, int]] = []
    for code, dt, open_, high, low, close, volume in rows:
        if dominant_contract_by_day.get(dt.date()) != code:
            continue
        rebuilt_rows.append(
            (
                "101S6000",
                dt,
                float(open_),
                float(high),
                float(low),
                float(close),
                int(volume),
            )
        )

    return rebuilt_rows


def rebuild_continuous_kospi200f(
    client,
    start: date,
    end: date,
    *,
    table_name: str = "kospi200f_1m",
    verbose: bool = True,
) -> int:
    """Rebuild continuous KOSPI200 futures code 101S6000 from A01* contracts."""
    source_rows = _load_continuous_source_rows(
        client, start, end, table_name=table_name
    )
    rebuilt_rows = _build_continuous_rows(source_rows)
    if not rebuilt_rows:
        if verbose:
            print("Continuous 101S6000 rebuild skipped. No source rows found.")
        return 0

    client.command(
        f"""
        ALTER TABLE {table_name}
        DELETE WHERE code = '101S6000'
          AND toDate(datetime) >= %(start)s
          AND toDate(datetime) <= %(end)s
        """,
        parameters={"start": start, "end": end},
    )
    insert_batch(client, rebuilt_rows, table_name=table_name)

    if verbose:
        print(
            "Rebuilt continuous 101S6000 rows: "
            f"{len(rebuilt_rows)} ({start} ~ {end})"
        )

    return len(rebuilt_rows)


def get_collected_pairs_in_range(
    client,
    start: date,
    end: date,
    table_name: str = "kospi_mini_1m",
) -> set[tuple[str, date]]:
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


def get_data_status(days: int = 30) -> dict[str, Any]:
    """Get Parquet data collection status summary."""
    from shared.collector.historical.parquet_backfill import (
        get_parquet_backfill_status,
    )

    return get_parquet_backfill_status(days=days, asset_class="futures")


def load_futures_minute_from_parquet(
    code: str,
    start_date: date | None = None,
    end_date: date | None = None,
    table_name: str | None = None,
) -> Any:
    """Load futures minute candles from the configured Parquet market-data store.

    Args:
        code: Futures symbol (e.g., ``101S6000`` or ``A05603``).
        start_date: Inclusive lower bound (KST date).
        end_date: Inclusive upper bound (KST date).
        table_name: Accepted for backward compatibility; ignored for Parquet.

    Returns:
        DataFrame columns: ``code, datetime, open, high, low, close, volume``.

    Raises:
        ValueError: when no rows are found.
    """
    _ = table_name
    from shared.storage import StorageConfig, load_market_bars_for_backtest

    df = load_market_bars_for_backtest(
        symbol=code,
        asset_class="futures",
        timeframe="minute",
        start=start_date,
        end=end_date,
        config=StorageConfig.load_or_default(),
    )
    if df.empty:
        raise ValueError(
            f"No futures data found for {code} in Parquet market data "
            f"(range: {start_date} ~ {end_date})"
        )
    return df


# =============================================================================
# Backfill Functions
# =============================================================================


async def collect_batch(
    client: httpx.AsyncClient,
    db_client,
    tasks: list[tuple[str, date]],
    table_name: str = "kospi_mini_1m",
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
        print(
            f"Inserted {len(all_rows)} rows from {len(tasks)} tasks into {table_name}"
        )

    return len(all_rows)


async def collect_index_batch(
    client: httpx.AsyncClient,
    db_client,
    tasks: list[tuple[str, date]],
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
            logger.warning(
                f"Index fetch failed for {symbol} {date_str}: {data['error']}"
            )
            continue
        rows = parse_ohlcv(symbol, date_str, data)
        all_rows.extend(rows)

    if all_rows:
        insert_batch(db_client, all_rows, table_name=table_name)
        print(
            f"Inserted {len(all_rows)} rows from {len(tasks)} tasks into {table_name}"
        )

    return len(all_rows)


async def backfill(days: int = 365, verbose: bool = True, resume: bool = True):
    """Run mini KOSPI200 futures backfill into Parquet."""
    from shared.collector.historical.parquet_backfill import (
        backfill_futures_parquet,
    )

    result = await backfill_futures_parquet(
        days=days,
        mini=True,
        index=False,
        futures=False,
        resume=resume,
        verbose=verbose,
    )
    return result.rows


async def collect_today(verbose: bool = True):
    """Collect today's mini KOSPI200 futures bars into Parquet."""
    from shared.collector.historical.parquet_backfill import (
        collect_today_futures_parquet,
    )

    result = await collect_today_futures_parquet(
        mini=True,
        index=False,
        futures=False,
        verbose=verbose,
    )
    return result.rows


# =============================================================================
# KOSPI 200 Index Backfill
# =============================================================================


async def backfill_kospi200_index(
    days: int = 365,
    verbose: bool = True,
    resume: bool = True,
):
    """Run KOSPI200 index backfill into Parquet."""
    from shared.collector.historical.parquet_backfill import (
        backfill_futures_parquet,
    )

    result = await backfill_futures_parquet(
        days=days,
        mini=False,
        index=True,
        futures=False,
        resume=resume,
        verbose=verbose,
    )
    return result.rows


async def collect_today_kospi200_index(verbose: bool = True):
    """Collect today's KOSPI200 index bars into Parquet."""
    from shared.collector.historical.parquet_backfill import (
        collect_today_futures_parquet,
    )

    result = await collect_today_futures_parquet(
        mini=False,
        index=True,
        futures=False,
        verbose=verbose,
    )
    return result.rows


# =============================================================================
# KOSPI 200 Futures (Full-Size) Backfill
# =============================================================================


def _get_kospi200f_codes_for_date(target_date: date) -> list[str]:
    """
    Get active KOSPI 200 Futures (full-size) codes for a specific date.

    KOSPI 200 Futures have quarterly expiry (Mar, Jun, Sep, Dec).
    Uses legacy A01 prefix format.
    """
    from .futures import KOSPI200_LEGACY_PREFIX, get_expiry_date

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
    """Run KOSPI200 full-size futures backfill into Parquet."""
    from shared.collector.historical.parquet_backfill import (
        backfill_futures_parquet,
    )

    result = await backfill_futures_parquet(
        days=days,
        mini=False,
        index=False,
        futures=True,
        resume=resume,
        verbose=verbose,
    )
    return result.rows


async def collect_today_kospi200f(verbose: bool = True):
    """Collect today's KOSPI200 full-size futures bars into Parquet."""
    from shared.collector.historical.parquet_backfill import (
        collect_today_futures_parquet,
    )

    result = await collect_today_futures_parquet(
        mini=False,
        index=False,
        futures=True,
        verbose=verbose,
    )
    return result.rows


async def backfill_all(
    days: int = 365,
    verbose: bool = True,
    resume: bool = True,
):
    """Backfill mini futures, KOSPI200 index, and full-size futures to Parquet."""
    from shared.collector.historical.parquet_backfill import (
        backfill_futures_parquet,
    )

    result = await backfill_futures_parquet(
        days=days,
        all_products=True,
        resume=resume,
        verbose=verbose,
    )
    return result.rows


async def collect_today_all(verbose: bool = True):
    """Collect today's mini futures, index, and full-size futures to Parquet."""
    from shared.collector.historical.parquet_backfill import (
        collect_today_futures_parquet,
    )

    result = await collect_today_futures_parquet(
        all_products=True,
        verbose=verbose,
    )
    return result.rows
