"""KOSPI200 Futures Daily Bar Collector.

Fetches daily OHLCV settlement bars for KOSPI200 index futures via the KIS
``선물옵션기간별시세(일/주/월/년)`` REST API (tr_id FHKIF03020100) and writes
them to the hive-partitioned Parquet store under
``data/market/futures/daily/``.

Key design decisions
--------------------
* **Symbol format**: The API requires legacy A-code format (e.g. ``A01609``
  for Sep-2026 KOSPI200 futures). The auto-rolling short-code ``101S6000``
  returns empty results.  We collect data for the continuous A01612 code
  (which acts as a near-month continuous series starting Dec 2023) and
  the current front-month A01609-family contracts.
* **Per-call cap**: KIS returns at most 100 bars per call; we reverse-paginate
  by setting FID_INPUT_DATE_2 to (oldest_bar - 1) on each page.
* **Rate limiting**: ≤2 rps to stay well inside the KIS 5 rps limit and match
  the production backfill convention.
* **Idempotent writes**: Uses ``replace_daily_day`` from ParquetMarketDataStore
  so re-running the collector never creates duplicate bars.

.. warning::

   **This partition is RAW, MULTI-CONTRACT, NOT back-adjusted.** Bars are
   stitched from successive discrete-expiry A-codes (A01609 → A01606 → A01612).
   At each contract roll the settlement levels differ by the carry spread, so
   the series carries step discontinuities that look like single-day returns
   (carry spreads are far below the 25% return gate, so they pass ungated; the
   gate also resets across symbols). Downstream consumers that compute returns
   or momentum across roll dates (e.g. a CTA walk-forward) MUST account for
   this — either roll-/back-adjust first, or restrict windows within a single
   contract. Treat ``code=101S6000`` daily as a raw settlement series, not a
   clean continuous instrument. Follow-up: a ratio-adjusted column / sidecar
   metadata (``is_adjusted=False``) before this feeds any production backtest.
* **OHLC sanity gate**: A day is rejected if the bar violates open ≤ high,
  low ≤ close, or shows an extreme single-day return (>25%), consistent with
  the minute-bar price-sanity gate in ``parquet_backfill.py``.
* **No look-ahead**: The collector only fetches bars up to ``end_date``
  (defaults to yesterday); the stored ``datetime`` is KST midnight of the
  settlement date.

Usage
-----
CLI (via sts CLI entrypoint, see cli/main.py integration notes)::

    sts futures-daily-backfill run --days 730
    sts futures-daily-backfill status

Python::

    from shared.collector.historical.daily_futures import collect_futures_daily
    import asyncio
    asyncio.run(collect_futures_daily(days=730))
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from shared.config.secrets import SecretsManager
from shared.storage import ParquetMarketDataStore, StorageConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE_URL = "https://openapi.koreainvestment.com:9443"
_DAILY_CHART_PATH = (
    "/uapi/domestic-futureoption/v1/quotations/inquire-daily-fuopchartprice"
)
_TR_ID = "FHKIF03020100"

# The continuous A01612 code covers data back to 2023-12-15 — the hard
# historical limit of the KIS daily futures API.
# A01609 is the rolling Sep-month contract (current near-month as of Jun 2026).
# Both are used to build the stitched continuous series.
_DEFAULT_SYMBOLS = list(
    dict.fromkeys(
        os.getenv(
            "FUTURES_DAILY_SYMBOLS",
            "A01609,A01606,A01612",
        ).split(",")
    )
)

# Storage symbol name for the continuous daily series in the parquet store.
# We write all source contracts under "101S6000" so downstream readers can
# use the same symbol they use for the minute store.
_STORAGE_SYMBOL = os.getenv("FUTURES_DAILY_STORAGE_SYMBOL", "101S6000")

# KIS hard limit: oldest available daily bar for futures.
_EARLIEST_DATE = date(2023, 12, 15)

# Rate limiter: ≤2 rps (KIS allows 5; keep margin per production convention)
_MAX_RPS: float = float(os.getenv("FUTURES_DAILY_RPS", "2.0"))
_MIN_INTERVAL: float = 1.0 / _MAX_RPS

# Per-call cap from KIS (do not change — the API returns at most 100 bars)
_PAGE_CAP = 100
# Stop paginating when a page returns fewer than this many bars (end of data)
_PAGE_MIN_FULL: int = int(os.getenv("FUTURES_DAILY_PAGE_MIN_FULL", "90"))
# Hard ceiling on pages per symbol to guard against infinite loops
_MAX_PAGES: int = int(os.getenv("FUTURES_DAILY_MAX_PAGES", "30"))

# OHLC sanity: reject days where a single-day return exceeds this threshold.
# KOSPI200 futures have ±10% daily limits; 25% tolerates circuit-breaker days
# while still catching phantom-track contamination.
_MAX_DAILY_RETURN: float = float(
    os.getenv("FUTURES_DAILY_MAX_RETURN", "0.25")
)


# ---------------------------------------------------------------------------
# Token management (reuses the existing futures KISToken singleton)
# ---------------------------------------------------------------------------


def _get_token() -> str:
    from shared.collector.historical.backfill import KISToken

    return KISToken.get_instance("futures").get()


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class _RateLimiter:
    """Simple interval-based rate limiter for sync/sequential use."""

    def __init__(self, rps: float = _MAX_RPS) -> None:
        import time

        self._min_interval = 1.0 / max(rps, 1e-6)
        self._last = time.monotonic() - self._min_interval


_limiter = _RateLimiter()


async def _rate_limited_get(
    client: httpx.AsyncClient, url: str, headers: dict, params: dict
) -> httpx.Response:
    """GET with rate limiting applied."""
    import time

    elapsed = time.monotonic() - _limiter._last
    gap = _limiter._min_interval - elapsed
    if gap > 0:
        await asyncio.sleep(gap)
    _limiter._last = time.monotonic()
    return await client.get(url, headers=headers, params=params, timeout=15)


# ---------------------------------------------------------------------------
# API fetch
# ---------------------------------------------------------------------------


async def _fetch_page(
    client: httpx.AsyncClient,
    symbol: str,
    start_date: date,
    end_date: date,
    app_key: str,
    app_secret: str,
    max_retries: int = 3,
) -> list[dict[str, Any]]:
    """Fetch one page (≤100 bars) of daily futures chart data.

    Returns bars newest-first, as KIS delivers them.  Returns [] on any
    permanent error.
    """
    token = _get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": _TR_ID,
        "content-type": "application/json; charset=utf-8",
    }
    params = {
        "FID_COND_MRKT_DIV_CODE": "F",
        "FID_INPUT_ISCD": symbol,
        "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
        "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
        "FID_PERIOD_DIV_CODE": "D",
    }

    for attempt in range(max_retries):
        try:
            resp = await _rate_limited_get(
                client, f"{_BASE_URL}{_DAILY_CHART_PATH}", headers, params
            )
            if resp.status_code >= 500:
                logger.warning(
                    "[daily_futures] HTTP %s for %s %s→%s (attempt %d/%d)",
                    resp.status_code,
                    symbol,
                    start_date,
                    end_date,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(1.5 * (attempt + 1))
                continue

            try:
                data = resp.json()
            except Exception as json_err:
                logger.warning("[daily_futures] JSON parse error: %s", json_err)
                await asyncio.sleep(1.0)
                continue

            rt_cd = data.get("rt_cd", "")
            if rt_cd and rt_cd != "0":
                msg = data.get("msg1", "")
                if "초당 거래건수" in msg or "RATE" in msg.upper():
                    logger.info("[daily_futures] Rate-limited — backing off")
                    await asyncio.sleep(2.0 * (attempt + 1))
                    continue
                logger.warning(
                    "[daily_futures] API error rt_cd=%s msg=%s for %s %s→%s",
                    rt_cd,
                    msg,
                    symbol,
                    start_date,
                    end_date,
                )
                return []

            bars = data.get("output2", []) or []
            return [b for b in bars if isinstance(b, dict)]

        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadTimeout) as e:
            logger.warning(
                "[daily_futures] Network error (attempt %d/%d): %s",
                attempt + 1,
                max_retries,
                e,
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(2.0 * (attempt + 1))

    return []


# ---------------------------------------------------------------------------
# Parse + sanity gate
# ---------------------------------------------------------------------------


def _parse_bar(raw: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    """Parse a single raw API bar dict to the canonical OHLCV dict.

    Returns None if the bar is invalid (zero prices, OHLC violation).
    """
    try:
        date_str = raw.get("stck_bsop_date", "")
        if not date_str or len(date_str) != 8:
            return None
        bar_date = datetime.strptime(date_str, "%Y%m%d").date()

        o = float(raw.get("futs_oprc", 0) or 0)
        h = float(raw.get("futs_hgpr", 0) or 0)
        lo = float(raw.get("futs_lwpr", 0) or 0)
        c = float(raw.get("futs_prpr", 0) or 0)
        v = int(float(raw.get("acml_vol", 0) or 0))

        # OHLC validity check
        if h <= 0 or c <= 0 or o <= 0 or lo <= 0:
            return None
        if not (lo <= o <= h and lo <= c <= h):
            logger.debug(
                "[daily_futures] OHLC violation %s %s: O=%.2f H=%.2f L=%.2f C=%.2f",
                symbol,
                date_str,
                o,
                h,
                lo,
                c,
            )
            return None

        return {
            "code": symbol,
            "datetime": datetime(bar_date.year, bar_date.month, bar_date.day),
            "open": o,
            "high": h,
            "low": lo,
            "close": c,
            "volume": v,
        }
    except (ValueError, TypeError, KeyError) as e:
        logger.debug("[daily_futures] Parse error for bar %s: %s", raw, e)
        return None


def _apply_return_gate(
    bars: list[dict[str, Any]], prev_close: float | None
) -> tuple[list[dict[str, Any]], float | None]:
    """Filter out bars where day-over-day return exceeds _MAX_DAILY_RETURN.

    Returns (accepted_bars, last_close).
    """
    accepted = []
    last_close = prev_close
    for bar in bars:
        c = bar["close"]
        if last_close is not None and last_close > 0:
            ret = abs(c - last_close) / last_close
            if ret > _MAX_DAILY_RETURN:
                logger.warning(
                    "[daily_futures] Price-sanity reject %s %s: return=%.1f%% "
                    "(prev=%.2f curr=%.2f) — exceeds %.0f%% gate",
                    bar["code"],
                    bar["datetime"].date(),
                    ret * 100,
                    last_close,
                    c,
                    _MAX_DAILY_RETURN * 100,
                )
                last_close = c  # update anyway to avoid blocking subsequent bars
                continue
        accepted.append(bar)
        last_close = c
    return accepted, last_close


# ---------------------------------------------------------------------------
# Full-history sweep for one symbol
# ---------------------------------------------------------------------------


async def _collect_symbol(
    client: httpx.AsyncClient,
    source_symbol: str,
    storage_symbol: str,
    start_date: date,
    end_date: date,
    store: ParquetMarketDataStore,
    app_key: str,
    app_secret: str,
) -> int:
    """Reverse-paginate KIS daily API for source_symbol and write to store.

    Returns the total number of bars written.
    """
    total_written = 0
    current_end = end_date
    pages = 0

    while pages < _MAX_PAGES:
        pages += 1
        raw_bars = await _fetch_page(
            client, source_symbol, start_date, current_end, app_key, app_secret
        )

        if not raw_bars:
            logger.info(
                "[daily_futures] %s page %d → empty (done)", source_symbol, pages
            )
            break

        # Parse and filter
        parsed = []
        for raw in raw_bars:
            bar = _parse_bar(raw, storage_symbol)
            if bar is not None:
                parsed.append(bar)

        # Sort oldest-first for the return-gate pass
        parsed.sort(key=lambda b: b["datetime"])

        # Apply return-gate (no prev_close context across pages — acceptable
        # as the gate targets extreme single-day moves, not roll gaps)
        accepted, _ = _apply_return_gate(parsed, None)

        # Write bar-by-bar per day (replace_daily_day is idempotent)
        days_written = {}
        for bar in accepted:
            d = bar["datetime"].date()
            days_written.setdefault(d, []).append(bar)

        for d, day_bars in sorted(days_written.items()):
            n = store.replace_daily_day(storage_symbol, d, day_bars)
            total_written += n

        logger.info(
            "[daily_futures] %s page %d: %d raw → %d parsed → %d accepted → %d written",
            source_symbol,
            pages,
            len(raw_bars),
            len(parsed),
            len(accepted),
            sum(len(v) for v in days_written.values()),
        )

        # Reverse-paginate: move end to day before oldest bar
        oldest_raw = raw_bars[-1].get("stck_bsop_date", "")
        if not oldest_raw:
            break
        oldest_date = datetime.strptime(oldest_raw, "%Y%m%d").date()

        if oldest_date <= start_date:
            logger.info(
                "[daily_futures] %s reached start_date %s (oldest=%s)",
                source_symbol,
                start_date,
                oldest_date,
            )
            break

        if len(raw_bars) < _PAGE_MIN_FULL:
            logger.info(
                "[daily_futures] %s page %d returned %d < %d bars — end of history",
                source_symbol,
                pages,
                len(raw_bars),
                _PAGE_MIN_FULL,
            )
            break

        current_end = oldest_date - timedelta(days=1)

    return total_written


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def collect_futures_daily(
    days: int = 730,
    symbols: list[str] | None = None,
    storage_symbol: str = _STORAGE_SYMBOL,
    data_root: str | Path | None = None,
    verbose: bool = True,
) -> int:
    """Collect KOSPI200 futures daily bars and write to the Parquet store.

    Args:
        days: How many calendar days back from today to collect (default 730 =
            ~2 years).  Capped at the KIS hard limit (data only available from
            2023-12-15).
        symbols: Source A-code symbols to fetch (default: A01609, A01606,
            A01612).  Results from all symbols are deduplicated and written
            under a single ``storage_symbol``.
        storage_symbol: The code key written to parquet (default ``101S6000``
            to match the minute-store symbol used by the rest of the system).
        data_root: Override the parquet root path.  Defaults to the configured
            ``StorageConfig.market_data_root``.
        verbose: Log progress at INFO level.

    Returns:
        Total bar-rows written across all symbols.
    """
    if symbols is None:
        symbols = _DEFAULT_SYMBOLS

    app_key = SecretsManager.kis_app_key("futures") or ""
    app_secret = SecretsManager.kis_app_secret("futures") or ""
    if not app_key:
        raise RuntimeError(
            "KIS_FUTURES_APP_KEY not set — cannot fetch futures daily data"
        )

    end_date = date.today() - timedelta(days=1)  # never include today (no look-ahead)
    earliest = max(_EARLIEST_DATE, date.today() - timedelta(days=days))
    start_date = earliest

    if verbose:
        logger.info(
            "[daily_futures] Collecting %d symbols: %s  [%s → %s]",
            len(symbols),
            symbols,
            start_date,
            end_date,
        )

    if data_root is None:
        cfg = StorageConfig.from_env()
        data_root = cfg.market_data.parquet.root

    store = ParquetMarketDataStore(data_root, asset_class="futures")

    total_written = 0
    async with httpx.AsyncClient(timeout=20) as client:
        for symbol in symbols:
            if verbose:
                logger.info("[daily_futures] → %s", symbol)
            n = await _collect_symbol(
                client,
                symbol,
                storage_symbol,
                start_date,
                end_date,
                store,
                app_key,
                app_secret,
            )
            total_written += n
            if verbose:
                logger.info("[daily_futures] %s done: %d bars written", symbol, n)

    if verbose:
        logger.info(
            "[daily_futures] Collection complete: %d total bars written", total_written
        )

    return total_written


# ---------------------------------------------------------------------------
# Status query
# ---------------------------------------------------------------------------


def get_futures_daily_status(
    data_root: str | Path | None = None,
    symbol: str = _STORAGE_SYMBOL,
) -> dict[str, Any]:
    """Return coverage stats for the futures daily parquet partition.

    Returns a dict with keys: symbol, bar_count, min_date, max_date,
    missing_days (list of date strings for gaps in the trading calendar).
    """
    import duckdb

    if data_root is None:
        cfg = StorageConfig.from_env()
        data_root = cfg.market_data.parquet.root

    daily_dir = Path(data_root) / "futures" / "daily" / f"code={symbol}"
    if not daily_dir.exists():
        return {
            "symbol": symbol,
            "bar_count": 0,
            "min_date": None,
            "max_date": None,
            "missing_days": [],
            "error": "partition not found",
        }

    glob = str(daily_dir / "**" / "*.parquet")
    con = duckdb.connect()
    try:
        row = con.execute(
            f"""
            SELECT count(*) AS n,
                   min(CAST(datetime AS DATE)) AS min_d,
                   max(CAST(datetime AS DATE)) AS max_d
            FROM read_parquet('{glob}', hive_partitioning=1)
            WHERE code = ?
            """,
            [symbol],
        ).fetchone()
    finally:
        con.close()

    if not row or not row[0]:
        return {
            "symbol": symbol,
            "bar_count": 0,
            "min_date": None,
            "max_date": None,
            "missing_days": [],
        }

    return {
        "symbol": symbol,
        "bar_count": int(row[0]),
        "min_date": str(row[1]) if row[1] else None,
        "max_date": str(row[2]) if row[2] else None,
    }


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "collect_futures_daily",
    "get_futures_daily_status",
]
