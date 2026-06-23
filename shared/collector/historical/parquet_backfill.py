"""Parquet-first historical market-data backfill.

This module keeps KIS fetch/parse logic separate from the storage sink.  It
writes directly to the configured Parquet market-data root and tracks
code/date progress in a small SQLite manifest so ClickHouse is not required for
normal backfill, resume, or status checks.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import httpx

from shared.storage import ParquetMarketDataStore, StorageConfig

from .calendar import (
    MARKET_CLOSE,
    MARKET_OPEN,
    get_trading_days_range,
    is_after_market_close,
    is_trading_day,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Completeness-gate constants (config-driven via env vars)
# ---------------------------------------------------------------------------


# Full KOSPI200-mini regular session bar count, derived from calendar hours:
#   09:00 -> 15:45  = 405 one-minute bars.
def _parse_hhmm(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


MINUTE_SESSION_BARS: int = _parse_hhmm(MARKET_CLOSE) - _parse_hhmm(MARKET_OPEN)

# Fraction of the full session required to call a day "complete".
# Default 0.75 → 303 bars.  Above the KIS single-page cap (102) so a one-page
# fetch is always detected.  Below the full session to absorb late-opening /
# early-closing edge cases (no half-day calendar currently available).
# Override via BACKFILL_MINUTE_COMPLETENESS_FRACTION env var.
_COMPLETENESS_FRACTION: float = float(
    os.getenv("BACKFILL_MINUTE_COMPLETENESS_FRACTION", "0.75")
)
MINUTE_COMPLETENESS_MIN_ROWS: int = max(
    1, int(MINUTE_SESSION_BARS * _COMPLETENESS_FRACTION)
)

# ---------------------------------------------------------------------------
# Price-sanity gate constants (config-driven via env vars)
# ---------------------------------------------------------------------------
# The completeness gate counts bars but cannot see *value* corruption.  The KIS
# duplicate-timestamp divergence bug produced internally-inconsistent
# "Frankenstein" bars (high/close pulled from a phantom parallel series) on days
# that still had 380+ bars — well above the density gate.  The price-sanity gate
# rejects a day if any emitted bar violates OHLC ordering, or if a single bar's
# close-to-close move exceeds an absurd threshold (a phantom-series step shows up
# as a large jump out of and back into the real track).
#
# Tolerance covers limit-up/limit-down futures sessions (KOSPI200 futures price
# limits are wide intraday); the default is deliberately generous so only clearly
# corrupt single-bar steps trip it.  Override via env var.
_MAX_SINGLE_BAR_RETURN: float = float(
    os.getenv("BACKFILL_MINUTE_MAX_BAR_RETURN", "0.08")
)
# Absolute floor on price used to avoid divide-by-zero / nonsense ratios on
# degenerate near-zero closes.
_PRICE_SANITY_MIN_CLOSE: float = 1e-6

AssetClass = Literal["stock", "futures"]
Timeframe = Literal["minute", "daily"]


@dataclass
class ParquetBackfillResult:
    """Backfill execution summary."""

    tasks: int = 0
    skipped: int = 0
    rows: int = 0
    failed: int = 0


class ParquetBackfillState:
    """SQLite manifest for idempotent Parquet backfill tasks."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backfill_tasks (
                    asset_class TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    dataset TEXT NOT NULL,
                    code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    rows INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (
                        asset_class, timeframe, dataset, code, trade_date
                    )
                )
                """)

    def is_completed(
        self,
        *,
        asset_class: AssetClass,
        timeframe: Timeframe,
        dataset: str,
        code: str,
        trade_date: date,
    ) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT status
                FROM backfill_tasks
                WHERE asset_class = ?
                  AND timeframe = ?
                  AND dataset = ?
                  AND code = ?
                  AND trade_date = ?
                """,
                (
                    asset_class,
                    timeframe,
                    dataset,
                    str(code),
                    trade_date.isoformat(),
                ),
            ).fetchone()
        return bool(row and row["status"] == "success")

    def mark_success(
        self,
        *,
        asset_class: AssetClass,
        timeframe: Timeframe,
        dataset: str,
        code: str,
        trade_date: date,
        rows: int,
    ) -> None:
        self._upsert(
            asset_class=asset_class,
            timeframe=timeframe,
            dataset=dataset,
            code=code,
            trade_date=trade_date,
            status="success",
            rows=rows,
            error=None,
        )

    def mark_failed(
        self,
        *,
        asset_class: AssetClass,
        timeframe: Timeframe,
        dataset: str,
        code: str,
        trade_date: date,
        error: str,
    ) -> None:
        self._upsert(
            asset_class=asset_class,
            timeframe=timeframe,
            dataset=dataset,
            code=code,
            trade_date=trade_date,
            status="failed",
            rows=0,
            error=error,
        )

    def _upsert(
        self,
        *,
        asset_class: AssetClass,
        timeframe: Timeframe,
        dataset: str,
        code: str,
        trade_date: date,
        status: str,
        rows: int,
        error: str | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO backfill_tasks (
                    asset_class, timeframe, dataset, code, trade_date,
                    status, rows, error, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (
                    asset_class, timeframe, dataset, code, trade_date
                )
                DO UPDATE SET
                    status = excluded.status,
                    rows = excluded.rows,
                    error = excluded.error,
                    updated_at = excluded.updated_at
                """,
                (
                    asset_class,
                    timeframe,
                    dataset,
                    str(code),
                    trade_date.isoformat(),
                    status,
                    int(rows),
                    error,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

    def summary(self, *, days: int) -> dict[str, Any]:
        end = date.today()
        start = end - timedelta(days=max(days, 1))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    asset_class,
                    timeframe,
                    dataset,
                    status,
                    count(*) AS tasks,
                    sum(rows) AS rows,
                    min(trade_date) AS min_date,
                    max(trade_date) AS max_date
                FROM backfill_tasks
                WHERE trade_date >= ?
                  AND trade_date <= ?
                GROUP BY asset_class, timeframe, dataset, status
                ORDER BY asset_class, timeframe, dataset, status
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        return {
            "period": f"{start} ~ {end}",
            "tasks": [dict(row) for row in rows],
        }


def _resolve_root(root: str | Path | None) -> Path:
    if root is not None:
        return Path(root)
    return Path(StorageConfig.load_or_default().market_data.parquet.root)


def _state_for_root(root: Path) -> ParquetBackfillState:
    return ParquetBackfillState(root / "_metadata" / "backfill_state.sqlite3")


def _is_day_closed(d: date) -> bool:
    """Check if a trading day is fully closed (past or today+after-close).

    A day is closed if it is strictly before today, OR it is today AND the market
    has closed after 15:45 KST.  Used by the completeness gate to decide whether
    to apply the minimum-bar check.  Testable: can be patched.
    """
    return (d < date.today()) or (d == date.today() and is_after_market_close())


def _ohlcv_dicts(rows: Iterable[tuple]) -> list[dict[str, Any]]:
    return [
        {
            "code": row[0],
            "datetime": row[1],
            "open": row[2],
            "high": row[3],
            "low": row[4],
            "close": row[5],
            "volume": row[6],
        }
        for row in rows
    ]


def check_price_sanity(
    rows: list[tuple],
    *,
    max_bar_return: float | None = _MAX_SINGLE_BAR_RETURN,
) -> str | None:
    """Validate OHLC consistency and single-bar return for a day's minute bars.

    Catches *value* corruption that the bar-density (completeness) gate cannot
    see — most importantly the KIS duplicate-timestamp divergence that produced
    internally-inconsistent bars on days with a full bar count.

    Two checks:

    * **OHLC ordering** (always applied): ``high >= max(open, close, low)`` and
      ``low <= min(open, close, high)``.  This is universally valid for any asset
      and also rejects NaN OHLC (NaN comparisons are False, so a NaN field fails
      the explicit ``isfinite`` guard below).
    * **Single-bar return** (only when ``max_bar_return`` is not ``None``): the
      absolute close-to-close move between consecutive bars must not exceed
      ``max_bar_return``.  This is the divergence signature on KOSPI200 futures
      and is *disabled* for assets whose legitimate single-minute moves are wide
      (Korean equities have ±30% daily limits / VI halts), by passing ``None``.

    Rows are ``(code, datetime, open, high, low, close, volume[, value, ...])``;
    the stock minute parser appends a trading-value column, so OHLC is indexed
    positionally rather than unpacked at a fixed arity.  Rows are sorted by
    timestamp first so the result is order-independent.

    Args:
        rows: Parsed OHLCV tuples for one (code, date).
        max_bar_return: Maximum tolerated absolute close-to-close return, or
            ``None`` to skip the return check (OHLC ordering still applies).

    Returns:
        ``None`` if the day is sane, else a short human-readable reason string
        describing the first violation found.
    """
    import math

    if not rows:
        return None

    ordered = sorted(rows, key=lambda r: r[1])
    prev_close: float | None = None
    for row in ordered:
        dt = row[1]
        o, h, l, c = float(row[2]), float(row[3]), float(row[4]), float(row[5])
        # Reject non-finite OHLC (NaN/inf) — comparisons against NaN are False, so
        # without this guard a NaN bar would silently pass both checks.
        if not all(math.isfinite(x) for x in (o, h, l, c)):
            return f"non-finite OHLC at {dt}: o={o} h={h} l={l} c={c}"
        # OHLC ordering: high must dominate open/close/low; low must be dominated.
        if h < max(o, c, l) - 1e-9 or l > min(o, c, h) + 1e-9:
            return f"OHLC inconsistent at {dt}: o={o:.2f} h={h:.2f} l={l:.2f} c={c:.2f}"
        if (
            max_bar_return is not None
            and prev_close is not None
            and abs(prev_close) > _PRICE_SANITY_MIN_CLOSE
        ):
            ret = abs(c - prev_close) / abs(prev_close)
            if ret > max_bar_return:
                return (
                    f"absurd single-bar return at {dt}: "
                    f"{prev_close:.2f} -> {c:.2f} ({ret:.1%} > "
                    f"{max_bar_return:.1%})"
                )
        prev_close = c
    return None


def _df_to_tuples(
    df: Any,
) -> list[tuple[str, datetime, float, float, float, float, int]]:
    rows = []
    for row in df.itertuples(index=False):
        rows.append(
            (
                str(row.code),
                (
                    row.datetime.to_pydatetime()
                    if hasattr(row.datetime, "to_pydatetime")
                    else row.datetime
                ),
                float(row.open),
                float(row.high),
                float(row.low),
                float(row.close),
                int(row.volume),
            )
        )
    return rows


async def _write_minute_tasks(
    *,
    client: httpx.AsyncClient,
    store: ParquetMarketDataStore,
    state: ParquetBackfillState,
    asset_class: AssetClass,
    dataset: str,
    trade_date: date,
    tasks: list[tuple[str, date]],
    fetcher: Callable[..., Any],
    parser: Callable[[str, str, dict], list[tuple]],
    resume: bool,
    verbose: bool,
) -> tuple[ParquetBackfillResult, dict[str, list[tuple]]]:
    result = ParquetBackfillResult()
    fetched_rows: dict[str, list[tuple]] = {}
    pending: list[tuple[str, date]] = []
    for code, day in tasks:
        result.tasks += 1
        if resume and state.is_completed(
            asset_class=asset_class,
            timeframe="minute",
            dataset=dataset,
            code=code,
            trade_date=day,
        ):
            result.skipped += 1
            continue
        pending.append((code, day))

    if not pending:
        return result, fetched_rows

    responses = await _gather_minute_fetches(client, pending, fetcher)
    for code, date_str, data in responses:
        day = datetime.strptime(date_str, "%Y%m%d").date()
        if "error" in data:
            result.failed += 1
            state.mark_failed(
                asset_class=asset_class,
                timeframe="minute",
                dataset=dataset,
                code=code,
                trade_date=day,
                error=str(data["error"]),
            )
            continue

        rows = parser(code, date_str, data)
        rows = [
            row
            for row in rows
            if (
                row[1].date()
                if isinstance(row[1], datetime)
                else datetime.strptime(str(row[1])[:10], "%Y-%m-%d").date()
            )
            == day
        ]
        if not rows:
            result.failed += 1
            state.mark_failed(
                asset_class=asset_class,
                timeframe="minute",
                dataset=dataset,
                code=code,
                trade_date=day,
                error="no parsed rows",
            )
            continue

        # Price-sanity gate: reject value-corrupt days (OHLC ordering violations
        # or absurd single-bar returns) BEFORE persisting them.  This catches the
        # duplicate-timestamp divergence signature that the bar-count completeness
        # gate cannot see (corrupt days had full bar counts).  The single-bar
        # return check is futures-only — Korean equities have ±30% daily limits /
        # VI halts, so an >8% single-minute move is legitimate; for stocks only
        # the universally-valid OHLC-ordering check applies.
        max_bar_return = _MAX_SINGLE_BAR_RETURN if asset_class == "futures" else None
        sanity_error = check_price_sanity(rows, max_bar_return=max_bar_return)
        if sanity_error is not None:
            log.warning(
                "Price-sanity gate: %s %s %s rejected — %s",
                dataset,
                code,
                day,
                sanity_error,
            )
            result.failed += 1
            state.mark_failed(
                asset_class=asset_class,
                timeframe="minute",
                dataset=dataset,
                code=code,
                trade_date=day,
                error=f"price-sanity gate: {sanity_error}",
            )
            continue

        written = store.replace_minute_day(code, day, _ohlcv_dicts(rows))
        fetched_rows[code] = rows
        result.rows += written

        # Completeness gate: only apply to fully closed past days.
        # For in-progress days we cannot know the final bar count yet, so we only
        # apply the gate to fully closed past days.
        if _is_day_closed(day) and written < MINUTE_COMPLETENESS_MIN_ROWS:
            log.warning(
                "Completeness gate: %s %s %s has only %d/%d minute bars — "
                "marking failed so resume re-attempts",
                dataset,
                code,
                day,
                written,
                MINUTE_COMPLETENESS_MIN_ROWS,
            )
            result.failed += 1
            state.mark_failed(
                asset_class=asset_class,
                timeframe="minute",
                dataset=dataset,
                code=code,
                trade_date=day,
                error=(
                    f"completeness gate: {written} bars < "
                    f"expected {MINUTE_COMPLETENESS_MIN_ROWS}"
                ),
            )
        else:
            state.mark_success(
                asset_class=asset_class,
                timeframe="minute",
                dataset=dataset,
                code=code,
                trade_date=day,
                rows=written,
            )
        if verbose:
            print(f"Parquet wrote {dataset} {code} {day}: rows={written}")

    return result, fetched_rows


async def _gather_minute_fetches(
    client: httpx.AsyncClient,
    tasks: list[tuple[str, date]],
    fetcher: Callable[..., Any],
) -> list[tuple[str, str, dict]]:
    coros = [fetcher(client, code, day.strftime("%Y%m%d")) for code, day in tasks]
    return list(await asyncio.gather(*coros))


def _merge_result(target: ParquetBackfillResult, source: ParquetBackfillResult) -> None:
    target.tasks += source.tasks
    target.skipped += source.skipped
    target.rows += source.rows
    target.failed += source.failed


async def backfill_futures_parquet(
    *,
    days: int = 30,
    root: str | Path | None = None,
    all_products: bool = False,
    mini: bool = True,
    index: bool = False,
    futures: bool = False,
    resume: bool = True,
    verbose: bool = True,
    trading_days: list[date] | None = None,
) -> ParquetBackfillResult:
    """Backfill futures/index minute data directly into Parquet."""
    from .backfill import (
        _build_continuous_rows,
        _get_index_symbol,
        _get_kospi200f_codes_for_date,
        fetch_index_minute_async,
        fetch_minute_async,
        parse_ohlcv,
    )
    from .futures import get_active_codes_for_date

    root_path = _resolve_root(root)
    store = ParquetMarketDataStore(root_path, asset_class="futures")
    state = _state_for_root(root_path)
    result = ParquetBackfillResult()

    if trading_days is None:
        end = date.today()
        start = end - timedelta(days=max(days, 1))
        trading_days = get_trading_days_range(start, end)
    selected = {
        "mini": bool(mini),
        "index": bool(index),
        "futures": bool(futures),
    }
    if all_products:
        selected = {"mini": True, "index": True, "futures": True}

    async with httpx.AsyncClient(timeout=30.0) as client:
        for day in reversed(trading_days):
            if selected["mini"]:
                tasks = [(code, day) for code in get_active_codes_for_date(day)]
                partial, _rows = await _write_minute_tasks(
                    client=client,
                    store=store,
                    state=state,
                    asset_class="futures",
                    dataset="kospi_mini_1m",
                    trade_date=day,
                    tasks=tasks,
                    fetcher=fetch_minute_async,
                    parser=parse_ohlcv,
                    resume=resume,
                    verbose=verbose,
                )
                _merge_result(result, partial)

            if selected["index"]:
                tasks = [(_get_index_symbol(), day)]
                partial, _rows = await _write_minute_tasks(
                    client=client,
                    store=store,
                    state=state,
                    asset_class="futures",
                    dataset="kospi200_index_1m",
                    trade_date=day,
                    tasks=tasks,
                    fetcher=fetch_index_minute_async,
                    parser=parse_ohlcv,
                    resume=resume,
                    verbose=verbose,
                )
                _merge_result(result, partial)

            if selected["futures"]:
                codes = _get_kospi200f_codes_for_date(day)
                tasks = [(code, day) for code in codes]
                partial, _rows = await _write_minute_tasks(
                    client=client,
                    store=store,
                    state=state,
                    asset_class="futures",
                    dataset="kospi200f_1m",
                    trade_date=day,
                    tasks=tasks,
                    fetcher=fetch_minute_async,
                    parser=parse_ohlcv,
                    resume=resume,
                    verbose=verbose,
                )
                _merge_result(result, partial)
                _merge_result(
                    result,
                    _rebuild_continuous_futures_day(
                        store=store,
                        state=state,
                        codes=codes,
                        trade_date=day,
                        builder=_build_continuous_rows,
                        resume=resume,
                        verbose=verbose,
                    ),
                )

    return result


def _rebuild_continuous_futures_day(
    *,
    store: ParquetMarketDataStore,
    state: ParquetBackfillState,
    codes: list[str],
    trade_date: date,
    builder: Callable[[list[tuple]], list[tuple]],
    resume: bool,
    verbose: bool,
) -> ParquetBackfillResult:
    result = ParquetBackfillResult(tasks=1)
    code = "101S6000"
    dataset = "kospi200f_continuous_1m"
    if resume and state.is_completed(
        asset_class="futures",
        timeframe="minute",
        dataset=dataset,
        code=code,
        trade_date=trade_date,
    ):
        result.skipped = 1
        return result

    source_rows: list[tuple] = []
    for source_code in codes:
        df = store.get_minute_bars(source_code, start=trade_date, end=trade_date)
        if not df.empty:
            source_rows.extend(_df_to_tuples(df))

    rebuilt = builder(source_rows)
    if not rebuilt:
        result.failed = 1
        state.mark_failed(
            asset_class="futures",
            timeframe="minute",
            dataset=dataset,
            code=code,
            trade_date=trade_date,
            error="no source rows",
        )
        return result

    written = store.replace_minute_day(code, trade_date, _ohlcv_dicts(rebuilt))
    result.rows = written
    state.mark_success(
        asset_class="futures",
        timeframe="minute",
        dataset=dataset,
        code=code,
        trade_date=trade_date,
        rows=written,
    )
    if verbose:
        print(f"Parquet rebuilt {code} {trade_date}: rows={written}")
    return result


async def collect_today_futures_parquet(
    *,
    root: str | Path | None = None,
    all_products: bool = False,
    mini: bool = True,
    index: bool = False,
    futures: bool = False,
    verbose: bool = True,
) -> ParquetBackfillResult:
    """Collect today's futures/index bars after market close."""
    if not is_after_market_close():
        if verbose:
            print("Market is still open. Please run after 15:45 KST.")
        return ParquetBackfillResult()
    return await backfill_futures_parquet(
        days=1,
        root=root,
        all_products=all_products,
        mini=mini,
        index=index,
        futures=futures,
        resume=False,
        verbose=verbose,
        trading_days=[date.today()],
    )


async def backfill_stock_minute_parquet(
    *,
    days: int = 30,
    codes: list[str] | None = None,
    root: str | Path | None = None,
    resume: bool = True,
    verbose: bool = True,
    trading_days: list[date] | None = None,
) -> ParquetBackfillResult:
    """Backfill stock minute bars directly into Parquet."""
    from .stock import (
        STOCK_UNIVERSE,
        fetch_stock_minute_async,
        parse_stock_minute_ohlcv,
    )

    root_path = _resolve_root(root)
    store = ParquetMarketDataStore(root_path, asset_class="stock")
    state = _state_for_root(root_path)
    selected_codes = (
        list(dict.fromkeys(codes))
        if codes
        else [str(stock["code"]) for stock in STOCK_UNIVERSE]
    )
    if trading_days is None:
        end = date.today()
        start = end - timedelta(days=min(max(days, 1), 180))
        trading_days = get_trading_days_range(start, end)
    result = ParquetBackfillResult()

    async with httpx.AsyncClient(timeout=30.0) as client:
        for day in reversed(trading_days):
            tasks = [(code, day) for code in selected_codes]
            partial, _rows = await _write_minute_tasks(
                client=client,
                store=store,
                state=state,
                asset_class="stock",
                dataset="stock_minute",
                trade_date=day,
                tasks=tasks,
                fetcher=fetch_stock_minute_async,
                parser=parse_stock_minute_ohlcv,
                resume=resume,
                verbose=verbose,
            )
            _merge_result(result, partial)
            if len(trading_days) > 30:
                await asyncio.sleep(1.0)

    return result


async def collect_today_stock_minute_parquet(
    *,
    root: str | Path | None = None,
    verbose: bool = True,
) -> ParquetBackfillResult:
    """Collect today's stock minute bars after market close."""
    today = date.today()
    if not is_after_market_close():
        if verbose:
            print("Market is still open. Please run after 15:45 KST.")
        return ParquetBackfillResult()
    if not is_trading_day(today):
        if verbose:
            print("Today is not a trading day.")
        return ParquetBackfillResult()
    return await backfill_stock_minute_parquet(
        days=1,
        root=root,
        resume=False,
        verbose=verbose,
        trading_days=[today],
    )


async def collect_stock_daily_parquet(
    *,
    days: int = 100,
    codes: list[str] | None = None,
    root: str | Path | None = None,
    resume: bool = True,
    verbose: bool = True,
) -> ParquetBackfillResult:
    """Backfill stock daily bars directly into Parquet."""
    from .daily_stock import fetch_daily_candles_async, parse_daily_ohlcv
    from .stock import STOCK_UNIVERSE

    root_path = _resolve_root(root)
    store = ParquetMarketDataStore(root_path, asset_class="stock")
    state = _state_for_root(root_path)
    selected_codes = (
        list(dict.fromkeys(codes))
        if codes
        else [str(stock["code"]) for stock in STOCK_UNIVERSE]
    )
    end = date.today()
    start = end - timedelta(days=max(days, 1))
    trading_days = get_trading_days_range(start, end)
    if not trading_days:
        return ParquetBackfillResult()

    result = ParquetBackfillResult()
    async with httpx.AsyncClient(timeout=30.0) as client:
        responses = await asyncio.gather(
            *[
                fetch_daily_candles_async(
                    client, code, trading_days[0], trading_days[-1]
                )
                for code in selected_codes
            ]
        )

    for code, data in responses:
        result.tasks += 1
        if "error" in data:
            result.failed += 1
            state.mark_failed(
                asset_class="stock",
                timeframe="daily",
                dataset="stock_daily",
                code=code,
                trade_date=trading_days[-1],
                error=str(data["error"]),
            )
            continue

        rows = parse_daily_ohlcv(code, data)
        if not rows:
            result.failed += 1
            state.mark_failed(
                asset_class="stock",
                timeframe="daily",
                dataset="stock_daily",
                code=code,
                trade_date=trading_days[-1],
                error="no parsed rows",
            )
            continue

        for row in rows:
            row_day = row[1]
            if resume and state.is_completed(
                asset_class="stock",
                timeframe="daily",
                dataset="stock_daily",
                code=code,
                trade_date=row_day,
            ):
                result.skipped += 1
                continue
            written = store.replace_daily_day(code, row_day, [_ohlcv_dicts([row])[0]])
            result.rows += written
            state.mark_success(
                asset_class="stock",
                timeframe="daily",
                dataset="stock_daily",
                code=code,
                trade_date=row_day,
                rows=written,
            )
        if verbose:
            print(f"Parquet wrote stock daily {code}: rows={len(rows)}")

    return result


def get_parquet_backfill_status(
    *,
    root: str | Path | None = None,
    days: int = 30,
    asset_class: AssetClass = "futures",
) -> dict[str, Any]:
    """Return Parquet dataset and manifest status."""
    root_path = _resolve_root(root)
    store = ParquetMarketDataStore(root_path, asset_class=asset_class)
    state = _state_for_root(root_path)
    manifest = store.dataset_manifest()
    status = state.summary(days=days)
    status.update(
        {
            "root": str(root_path),
            "asset_class": asset_class,
            "parquet_files": manifest.get("parquet_files", 0),
            "row_count": manifest.get("row_count", 0),
            "min_datetime": manifest.get("min_datetime"),
            "max_datetime": manifest.get("max_datetime"),
        }
    )
    return status
