"""KOSPI200 Futures Daily Settlement Bar Collector — KRX source.

Fetches front-month KOSPI200 futures daily settlement bars from the KRX
정보데이터시스템 Open API (``drv/fut_bydd_trd``) and writes them to the
hive-partitioned Parquet store under ``data/market/futures/daily/``.

This collector complements ``daily_futures.py`` (which uses the KIS REST API
and is limited to data from 2023-12-15).  The KRX source extends coverage back
to **2010-01-04** (~16+ years), providing the multi-regime depth required by
CTA/swing momentum backtests (THESIS B, ≥3 years for 3-fold walk-forward).

Key design decisions
--------------------
* **Partition key**: ``krx_kospi200f_continuous`` — distinct from the
  KIS-sourced ``101S6000`` partition because price levels differ by ~2-5% in
  the overlap period (KRX uses exchange settlement price ``SETL_PRC``; KIS
  A-code FHKIF03020100 returns a different daily close).  Using a separate key
  prevents silent price-level mixing.
* **Front-month selection**: for each trading day, select the
  ``코스피200 선물`` / ``MKT_NM='정규'`` contract with highest ``ACC_TRDVOL``
  (volume-weighted near-month continuous series, no back-adjustment).
* **OHLC fields**: ``TDD_OPNPRC`` / ``TDD_HGPRC`` / ``TDD_LWPRC`` /
  ``TDD_CLSPRC`` (== ``SETL_PRC`` on most days). Volume = ``ACC_TRDVOL``.
* **Single-date API**: KRX does not expose a range endpoint; each call fetches
  one day.  We iterate KST trading days from ``start_date`` to ``end_date``.
* **Rate limiting**: ≤2 rps (conservative; no published KRX limit but matching
  the KIS backfill convention avoids throttling).
* **Idempotent writes**: ``replace_daily_day`` deletes the existing partition
  dir before writing, so re-running is safe.
* **OHLC sanity gate**: same logic as ``daily_futures.py`` — rejects zero
  prices, OHLC inversions, and single-day returns >25%.
* **Holiday / weekend skipping**: uses ``MarketCalendar.is_market_day()`` to
  skip non-trading days (avoids unnecessary API calls that return empty).
* **KST**: settlement dates are Korean exchange dates; all datetime objects
  stored as midnight KST (naive, matching the existing parquet convention).

Usage
-----
CLI::

    sts krx-futures-daily-backfill run --years 16
    sts krx-futures-daily-backfill status

Python::

    from shared.collector.historical.krx_daily_futures import collect_krx_futures_daily
    collect_krx_futures_daily(years=16)
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from shared.calendar import MarketCalendar
from shared.storage import ParquetMarketDataStore, StorageConfig
from shared.strategy.market_time import now_kst as now_kst_fn

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE_URL = os.getenv("KRX_BASE_URL", "https://data-dbg.krx.co.kr/svc/apis")
_ENDPOINT = "drv/fut_bydd_trd"

# Storage symbol for the KRX-sourced continuous series.
# Intentionally distinct from the KIS "101S6000" partition (see module docstring).
_KRX_STORAGE_SYMBOL = os.getenv("KRX_FUTURES_STORAGE_SYMBOL", "krx_kospi200f_continuous")

# KRX data starts on 2010-01-04 (earliest confirmed by probe 2026-06-26).
_KRX_EARLIEST_DATE = date(2010, 1, 4)

# KRX settlement data is published ~1–2h after market close; use 18:00 KST
# as the cutoff to avoid requesting today's not-yet-published data.
_KRX_DATA_CUTOFF_HOUR = 18  # KST

# Rate limiter: ≤2 rps
_MAX_RPS: float = float(os.getenv("KRX_FUTURES_RPS", "2.0"))

# OHLC sanity: reject bars where single-day return exceeds this threshold.
# KOSPI200 futures have ±10% daily price limits; 25% tolerates contract-roll
# gaps while blocking phantom-track contamination.
_MAX_DAILY_RETURN: float = float(os.getenv("KRX_FUTURES_MAX_RETURN", "0.25"))

# Minimum volume to accept a front-month candidate.
# Filters out illiquid far-quarter contracts that occasionally top the sorted list
# during early-session sparse data.
_MIN_FRONT_MONTH_VOLUME = int(os.getenv("KRX_FUTURES_MIN_VOLUME", "1000"))

# Product name and market session filters for front-month selection.
_PROD_NM_FILTER = "코스피200 선물"
_MKT_NM_FILTER = "정규"


# ---------------------------------------------------------------------------
# Rate limiter (sync)
# ---------------------------------------------------------------------------


class _RateLimiter:
    """Simple interval-based rate limiter for synchronous use."""

    def __init__(self, rps: float = _MAX_RPS) -> None:
        self._min_interval = 1.0 / max(rps, 1e-6)
        self._last = time.monotonic() - self._min_interval

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last
        gap = self._min_interval - elapsed
        if gap > 0:
            time.sleep(gap)
        self._last = time.monotonic()


_limiter = _RateLimiter()


# ---------------------------------------------------------------------------
# API fetch
# ---------------------------------------------------------------------------


def _fetch_day(api_key: str, trading_day: date, max_retries: int = 3) -> list[dict[str, Any]]:
    """Fetch all futures contracts for a single KRX trading day.

    Returns the raw ``OutBlock_1`` list, or ``[]`` on any permanent error.
    """
    date_str = trading_day.strftime("%Y%m%d")
    params = {"AUTH_KEY": api_key, "basDd": date_str}

    for attempt in range(max_retries):
        _limiter.wait()
        try:
            resp = requests.get(
                f"{_BASE_URL}/{_ENDPOINT}",
                params=params,
                timeout=15,
            )
            if resp.status_code >= 500:
                logger.warning(
                    "[krx_daily_futures] HTTP %s for %s (attempt %d/%d)",
                    resp.status_code,
                    date_str,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(1.5 * (attempt + 1))
                continue

            try:
                data = resp.json()
            except Exception as json_err:
                logger.warning("[krx_daily_futures] JSON parse error %s: %s", date_str, json_err)
                time.sleep(1.0)
                continue

            # Auth errors are reported in the JSON body
            if isinstance(data, dict) and data.get("respCode") in ("401", "403"):
                logger.error(
                    "[krx_daily_futures] KRX auth error %s: %s",
                    data.get("respCode"),
                    data.get("respMsg", ""),
                )
                return []

            return data.get("OutBlock_1", []) or []

        except (requests.exceptions.RequestException, OSError) as e:
            logger.warning(
                "[krx_daily_futures] Network error %s (attempt %d/%d): %s",
                date_str,
                attempt + 1,
                max_retries,
                e,
            )
            if attempt < max_retries - 1:
                time.sleep(2.0 * (attempt + 1))

    return []


# ---------------------------------------------------------------------------
# Front-month selection
# ---------------------------------------------------------------------------


def _select_front_month(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select the front-month KOSPI200 futures contract from one day's items.

    Filters to ``코스피200 선물`` regular-session (``MKT_NM='정규'``) contracts
    and returns the one with the highest volume.  Returns None if no qualifying
    contract is found or volume is below the minimum threshold.
    """
    candidates = [
        x for x in items
        if x.get("PROD_NM") == _PROD_NM_FILTER
        and x.get("MKT_NM") == _MKT_NM_FILTER
    ]
    if not candidates:
        return None

    # Sort by descending volume; handle missing/empty strings as 0
    def _vol(x: dict) -> int:
        v = x.get("ACC_TRDVOL", "0") or "0"
        try:
            return int(v.replace(",", ""))
        except ValueError:
            return 0

    best = max(candidates, key=_vol)
    if _vol(best) < _MIN_FRONT_MONTH_VOLUME:
        logger.debug(
            "[krx_daily_futures] front-month volume %d < minimum %d — skipping",
            _vol(best),
            _MIN_FRONT_MONTH_VOLUME,
        )
        return None

    return best


# ---------------------------------------------------------------------------
# Parse + sanity gate
# ---------------------------------------------------------------------------


def _parse_bar(raw: dict[str, Any], storage_symbol: str) -> dict[str, Any] | None:
    """Parse a single KRX futures contract dict to the canonical OHLCV dict.

    Returns None if the bar is invalid (zero prices, OHLC inversion).

    Field mapping:
        BAS_DD        → settlement date (YYYYMMDD)
        TDD_OPNPRC    → open
        TDD_HGPRC     → high
        TDD_LWPRC     → low
        TDD_CLSPRC    → close (equals SETL_PRC on settlement days)
        ACC_TRDVOL    → volume
    """
    try:
        date_str = raw.get("BAS_DD", "")
        if not date_str or len(date_str) != 8:
            return None
        bar_date = datetime.strptime(date_str, "%Y%m%d").date()

        def _f(key: str) -> float:
            v = raw.get(key, "0") or "0"
            return float(str(v).replace(",", ""))

        def _i(key: str) -> int:
            v = raw.get(key, "0") or "0"
            try:
                return int(str(v).replace(",", ""))
            except ValueError:
                return 0

        o = _f("TDD_OPNPRC")
        h = _f("TDD_HGPRC")
        lo = _f("TDD_LWPRC")
        c = _f("TDD_CLSPRC")
        v = _i("ACC_TRDVOL")

        # OHLC validity
        if h <= 0 or c <= 0 or o <= 0 or lo <= 0:
            return None
        if not (lo <= o <= h and lo <= c <= h):
            logger.debug(
                "[krx_daily_futures] OHLC violation %s %s: O=%.2f H=%.2f L=%.2f C=%.2f",
                storage_symbol,
                date_str,
                o, h, lo, c,
            )
            return None

        return {
            "code": storage_symbol,
            "datetime": datetime(bar_date.year, bar_date.month, bar_date.day),
            "open": o,
            "high": h,
            "low": lo,
            "close": c,
            "volume": v,
        }

    except (ValueError, TypeError, KeyError) as e:
        logger.debug("[krx_daily_futures] Parse error for bar %s: %s", raw, e)
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
                    "[krx_daily_futures] Price-sanity reject %s %s: return=%.1f%% "
                    "(prev=%.2f curr=%.2f) — exceeds %.0f%% gate",
                    bar["code"],
                    bar["datetime"].date(),
                    ret * 100,
                    last_close,
                    c,
                    _MAX_DAILY_RETURN * 100,
                )
                last_close = c  # update to avoid blocking subsequent bars
                continue
        accepted.append(bar)
        last_close = c
    return accepted, last_close


# ---------------------------------------------------------------------------
# Date-range generation
# ---------------------------------------------------------------------------


def _trading_days_in_range(start: date, end: date) -> list[date]:
    """Return all KRX trading days in [start, end] (inclusive).

    Uses ``MarketCalendar.is_market_day()`` for holiday awareness.
    Weekends are always skipped; Korean public holidays are excluded.
    """
    cal = MarketCalendar()
    days: list[date] = []
    cur = start
    while cur <= end:
        if cal.is_market_day(cur):
            days.append(cur)
        cur += timedelta(days=1)
    return days


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def collect_krx_futures_daily(
    years: int = 16,
    start_date: date | None = None,
    end_date: date | None = None,
    storage_symbol: str = _KRX_STORAGE_SYMBOL,
    data_root: str | Path | None = None,
    api_key: str | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Collect KOSPI200 futures daily settlement bars from KRX and write to Parquet.

    Args:
        years: How many years back from today to collect (default 16 =
            full KRX history from 2010-01-04).
        start_date: Override start of collection window.  Clamped to
            ``_KRX_EARLIEST_DATE`` (2010-01-04).
        end_date: Override end of collection window.  Defaults to yesterday
            to avoid requesting not-yet-published KRX data.
        storage_symbol: Partition key written to parquet (default
            ``krx_kospi200f_continuous``).  Do not change unless you
            intentionally want to mix price levels with the KIS partition.
        data_root: Override the parquet root path.  Defaults to
            ``StorageConfig.from_env().market_data.parquet.root``.
        api_key: KRX OpenAPI key.  Defaults to the ``KRX_API_KEY`` env var.
        verbose: Log progress at INFO level.

    Returns:
        Dict with keys:
            - ``bars_written``: total bar-rows written
            - ``days_attempted``: number of trading days attempted
            - ``days_skipped``: days that returned no qualifying bar
            - ``days_error``: days with API/parse errors
            - ``min_date``: earliest date written (ISO string or None)
            - ``max_date``: latest date written (ISO string or None)
    """
    _api_key = api_key or os.environ.get("KRX_API_KEY", "")
    if not _api_key:
        raise RuntimeError("KRX_API_KEY not set — cannot fetch KRX futures data")

    # Resolve end_date: never include today if before KRX publication cutoff
    if end_date is None:
        _now = now_kst_fn()  # KST-aware; do not use naive datetime.now()
        if _now.hour < _KRX_DATA_CUTOFF_HOUR:
            end_date = _now.date() - timedelta(days=1)
        else:
            end_date = _now.date()

    # Resolve start_date
    if start_date is None:
        start_date = date.today() - timedelta(days=years * 365)
    start_date = max(start_date, _KRX_EARLIEST_DATE)

    if data_root is None:
        cfg = StorageConfig.from_env()
        data_root = cfg.market_data.parquet.root

    store = ParquetMarketDataStore(data_root, asset_class="futures")

    trading_days = _trading_days_in_range(start_date, end_date)

    if verbose:
        logger.info(
            "[krx_daily_futures] Collecting %s [%s → %s]: %d trading days",
            storage_symbol,
            start_date,
            end_date,
            len(trading_days),
        )

    bars_written = 0
    days_attempted = 0
    days_skipped = 0
    days_error = 0
    min_written: date | None = None
    max_written: date | None = None
    prev_close: float | None = None

    for i, trading_day in enumerate(trading_days):
        days_attempted += 1

        items = _fetch_day(_api_key, trading_day)

        if not items:
            # Empty response: either a gap in KRX data or a holiday we missed
            logger.debug("[krx_daily_futures] %s: empty response — skipping", trading_day)
            days_skipped += 1
            continue

        front = _select_front_month(items)
        if front is None:
            logger.debug("[krx_daily_futures] %s: no qualifying front-month — skipping", trading_day)
            days_skipped += 1
            continue

        bar = _parse_bar(front, storage_symbol)
        if bar is None:
            logger.warning("[krx_daily_futures] %s: parse failure — skipping", trading_day)
            days_error += 1
            continue

        # Apply return gate (carries prev_close across days for continuity check)
        accepted, prev_close = _apply_return_gate([bar], prev_close)
        if not accepted:
            days_error += 1
            continue

        n = store.replace_daily_day(storage_symbol, trading_day, accepted)
        bars_written += n

        if min_written is None or trading_day < min_written:
            min_written = trading_day
        if max_written is None or trading_day > max_written:
            max_written = trading_day

        if verbose and (i + 1) % 250 == 0:
            logger.info(
                "[krx_daily_futures] Progress: %d/%d days — %d bars written so far",
                i + 1,
                len(trading_days),
                bars_written,
            )

    result = {
        "bars_written": bars_written,
        "days_attempted": days_attempted,
        "days_skipped": days_skipped,
        "days_error": days_error,
        "min_date": str(min_written) if min_written else None,
        "max_date": str(max_written) if max_written else None,
    }

    if verbose:
        logger.info(
            "[krx_daily_futures] Complete: %d bars written (%d days, %d skipped, %d errors)",
            bars_written,
            days_attempted,
            days_skipped,
            days_error,
        )

    return result


# ---------------------------------------------------------------------------
# Status query
# ---------------------------------------------------------------------------


def get_krx_futures_daily_status(
    data_root: str | Path | None = None,
    symbol: str = _KRX_STORAGE_SYMBOL,
) -> dict[str, Any]:
    """Return coverage stats for the KRX futures daily parquet partition.

    Returns a dict with keys: symbol, bar_count, min_date, max_date,
    and error (if the partition directory does not exist).
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
    "collect_krx_futures_daily",
    "get_krx_futures_daily_status",
]
