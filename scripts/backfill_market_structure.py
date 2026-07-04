"""Market-structure daily backfill (unified investment roadmap Phase 0).

Fills ``close`` snapshot rows of the market-structure Parquet dataset from the
spike-confirmed historical sources:

* ``program``  — KIS ``FHPPG04600001`` date range (monthly chunks + tr_cont;
  the per-call row cap is still unconfirmed, roadmap O1 residual probe).
* ``oi``       — KRX Open API ``drv/fut_bydd_trd`` per trading day (front-month
  K200 futures close + open interest). Skipped with a warning when
  ``KRX_API_KEY`` is not configured.
* ``k200``     — KIS ``FHKUP03500100`` (U/2001 daily index), ~100-day chunks.
* ``fx``       — Yahoo chart daily closes (``KRW=X`` + ES/NQ/^SOX change pct;
  symbols come from config/macro_sources.yaml yahoo_symbols).
* ``foreign_futures`` — NOT automatable (KRX login wall); load a manual CSV
  export via ``--from-csv`` (columns: date, net_qty[, net_val]).

Derived columns (cum20 / oi_price_signal / basis_dev / MAs / returns) are
recomputed chronologically after the merge so the historical series matches
the forward collector's schema. Prints before/after row counts and a
trading-day gap report.

Usage:
    python scripts/backfill_market_structure.py --start 2024-07-01 --end 2026-07-01
    python scripts/backfill_market_structure.py --start 2026-01-01 --end 2026-06-30 \
        --components program,k200 --dry-run
    python scripts/backfill_market_structure.py --start 2024-07-01 --end 2026-07-01 \
        --components foreign_futures --from-csv exports/foreign_futures.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import math
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# Direct-invocation support (``python scripts/backfill_market_structure.py``).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.market_structure_collector import derived
from services.market_structure_collector.config import MarketStructureCollectorConfig
from services.market_structure_collector.main import (
    _NON_CARRY_COLUMNS,
    _PROGRAM_ARB_KEYS,
    _PROGRAM_DATE_KEYS,
    _PROGRAM_NONARB_KEYS,
    _PROGRAM_WHOLE_KEYS,
    _coverage,
    _first_number,
    _futures_kis_auth_config,
    _is_present,
    _now_kst,
    _parse_number,
    compute_basis_columns,
)
from shared.calendar import MarketCalendar

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Backfillable components; ``foreign_futures`` additionally requires --from-csv.
BACKFILL_COMPONENTS = ("program", "oi", "k200", "fx", "foreign_futures")
DEFAULT_COMPONENTS = ("program", "oi", "k200", "fx")

_PROGRAM_CHUNK_DAYS = 31  # monthly chunks until the row cap is confirmed
_INDEX_CHUNK_DAYS = 100  # FHKUP03500100 caps a single call at ~100 rows
_HISTORY_BUFFER_DAYS = 150  # calendar-day context for trailing derived values
_CSV_DATE_KEYS = ("date", "trade_date", "일자")
_CSV_QTY_KEYS = ("net_qty", "fut_foreign_net_qty", "qty", "순매수")
_CSV_VAL_KEYS = ("net_val", "fut_foreign_net_val", "val")
# KRX Open API product-name fragments excluded from front-month selection.
_KRX_EXCLUDED_NAME_FRAGMENTS = ("미니", "위클리", "MINI", "WEEKLY", "스프레드")


def _parse_yyyymmdd(value: Any) -> date | None:
    text = str(value or "").strip().replace("-", "").replace("/", "").replace(".", "")
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None


def _chunks(start: date, end: date, days: int) -> list[tuple[date, date]]:
    spans: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=days - 1), end)
        spans.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return spans


# ---------------------------------------------------------------------------
# Component fetchers → {trade_date: {column: value}}
# ---------------------------------------------------------------------------


async def fetch_program_updates(
    kis_client: Any, config: MarketStructureCollectorConfig, start: date, end: date
) -> dict[date, dict[str, Any]]:
    updates: dict[date, dict[str, Any]] = {}
    for chunk_start, chunk_end in _chunks(start, end, _PROGRAM_CHUNK_DAYS):
        rows = await kis_client.fetch_program_trade_daily(
            chunk_start,
            chunk_end,
            market_div=config.kis.program_market_div,
            market_cls=config.kis.program_market_cls,
        )
        for row in rows:
            row_date = next(
                (
                    parsed
                    for key in _PROGRAM_DATE_KEYS
                    if (parsed := _parse_yyyymmdd(row.get(key))) is not None
                ),
                None,
            )
            if row_date is None or not (start <= row_date <= end):
                continue
            whole = _first_number(row, _PROGRAM_WHOLE_KEYS)
            arb = _first_number(row, _PROGRAM_ARB_KEYS)
            nonarb = _first_number(row, _PROGRAM_NONARB_KEYS)
            if whole is None and arb is not None and nonarb is not None:
                whole = arb + nonarb
            if whole is None:
                continue
            updates[row_date] = {
                "prog_net_val": whole,
                "prog_arb_net_val": arb,
                "prog_nonarb_net_val": nonarb,
            }
    return updates


def fetch_oi_updates(
    krx_client: Any, trading_days: list[date]
) -> dict[date, dict[str, Any]]:
    """Front-month K200 futures close + OI from KRX ``drv/fut_bydd_trd``."""
    updates: dict[date, dict[str, Any]] = {}
    for day in trading_days:
        rows = krx_client.get_kospi200_futures(day.strftime("%Y%m%d"))
        candidates = [
            row
            for row in rows
            if not any(
                fragment in str(row.product_name).upper()
                or fragment in str(row.product_name)
                for fragment in _KRX_EXCLUDED_NAME_FRAGMENTS
            )
        ]
        if not candidates:
            continue
        front = max(candidates, key=lambda row: row.volume)
        if front.close_price <= 0:
            continue
        updates[day] = {
            "fut_close": float(front.close_price),
            "fut_oi_qty": float(front.open_interest),
        }
    return updates


async def fetch_k200_updates(
    kis_client: Any, config: MarketStructureCollectorConfig, start: date, end: date
) -> dict[date, dict[str, Any]]:
    updates: dict[date, dict[str, Any]] = {}
    for chunk_start, chunk_end in _chunks(start, end, _INDEX_CHUNK_DAYS):
        rows = await kis_client.fetch_index_daily_candles(
            config.kis.index_code,
            chunk_start,
            chunk_end,
            market_div=config.kis.index_market_div,
        )
        for row in rows:
            row_date = _parse_yyyymmdd(row.get("stck_bsop_date"))
            close = _parse_number(row.get("bstp_nmix_prpr"))
            if row_date is None or close is None or close <= 0:
                continue
            if start <= row_date <= end:
                updates.setdefault(row_date, {})["k200_close"] = close
    return updates


def _default_yahoo_daily(symbol: str, start: date, end: date) -> dict[date, float]:
    """Daily closes via yfinance (bar date → close)."""
    import yfinance as yf

    hist = yf.Ticker(symbol).history(
        start=start.isoformat(), end=(end + timedelta(days=1)).isoformat()
    )
    closes: dict[date, float] = {}
    if getattr(hist, "empty", True):
        return closes
    for stamp, close in hist["Close"].items():
        value = float(close)
        if not math.isnan(value):
            closes[stamp.date()] = value
    return closes


def fetch_fx_updates(
    yahoo_daily: Any,
    yahoo_symbols: dict[str, str],
    trading_days: list[date],
    start: date,
    end: date,
) -> dict[date, dict[str, Any]]:
    """USD/KRW level + overseas overnight change pct per KST trading day.

    For a KST trade date D the "overnight" overseas move is the last US bar
    strictly before D; USD/KRW uses the bar dated D (offshore daily close).
    """
    updates: dict[date, dict[str, Any]] = {}
    fetch_start = start - timedelta(days=10)

    fx_symbol = yahoo_symbols.get("usdkrw_realtime")
    if fx_symbol:
        closes = yahoo_daily(fx_symbol, fetch_start, end)
        for day in trading_days:
            if day in closes:
                updates.setdefault(day, {})["usdkrw"] = closes[day]

    for prefix in ("es_futures", "nq_futures", "sox"):
        symbol = yahoo_symbols.get(prefix)
        if not symbol:
            logger.warning("yahoo symbol map missing %s; skipping", prefix)
            continue
        closes = yahoo_daily(symbol, fetch_start, end)
        ordered = sorted(closes.items())
        for day in trading_days:
            prior = [(d, c) for d, c in ordered if d < day]
            if len(prior) < 2 or prior[-2][1] == 0:
                continue
            change_pct = (prior[-1][1] / prior[-2][1] - 1.0) * 100.0
            updates.setdefault(day, {})[f"{prefix}_change_pct"] = change_pct
    return updates


def load_foreign_futures_csv(
    csv_path: Path, start: date, end: date
) -> dict[date, dict[str, Any]]:
    """Manual KRX CSV export (login wall; see roadmap O1 runbook)."""
    updates: dict[date, dict[str, Any]] = {}
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw_row in reader:
            row = {str(k).strip().lower(): v for k, v in raw_row.items() if k}
            row_date = next(
                (
                    parsed
                    for key in _CSV_DATE_KEYS
                    if (parsed := _parse_yyyymmdd(row.get(key))) is not None
                ),
                None,
            )
            qty = next(
                (
                    parsed
                    for key in _CSV_QTY_KEYS
                    if (parsed := _parse_number(row.get(key))) is not None
                ),
                None,
            )
            if row_date is None or qty is None or not (start <= row_date <= end):
                continue
            val = next(
                (
                    parsed
                    for key in _CSV_VAL_KEYS
                    if (parsed := _parse_number(row.get(key))) is not None
                ),
                None,
            )
            updates[row_date] = {
                "fut_foreign_net_qty": qty,
                "fut_foreign_net_val": val,
            }
    return updates


# ---------------------------------------------------------------------------
# Derived recompute (chronological)
# ---------------------------------------------------------------------------


def _trailing(
    rows: dict[date, dict[str, Any]], days: list[date], column: str
) -> list[float]:
    return derived.clean_series(rows.get(day, {}).get(column) for day in days)


def recompute_derived(
    rows: dict[date, dict[str, Any]],
    target_days: list[date],
    config: MarketStructureCollectorConfig,
) -> None:
    """Recompute derived columns in place for ``target_days`` (sorted asc)."""
    all_days = sorted(rows)
    for day in target_days:
        row = rows.get(day)
        if row is None:
            continue
        upto = [d for d in all_days if d <= day]

        fut_series = _trailing(rows, upto, "fut_close")
        if not _is_present(row.get("fut_change_pct")) and len(fut_series) >= 2:
            row["fut_change_pct"] = derived.pct_return(fut_series, 1)
        k200_series = _trailing(rows, upto, "k200_close")
        if not _is_present(row.get("k200_change_pct")) and len(k200_series) >= 2:
            row["k200_change_pct"] = derived.pct_return(k200_series, 1)
        oi_series = _trailing(rows, upto, "fut_oi_qty")
        if not _is_present(row.get("fut_oi_change")) and len(oi_series) >= 2:
            row["fut_oi_change"] = oi_series[-1] - oi_series[-2]
        row["oi_price_signal"] = derived.oi_price_signal(
            row.get("fut_change_pct"), row.get("fut_oi_change")
        )

        basis_columns = compute_basis_columns(
            fut_close=row.get("fut_close"),
            k200_close=row.get("k200_close"),
            trade_date=day,
            risk_free_rate=config.basis.risk_free_rate,
        )
        row.update(basis_columns)
        if _is_present(row.get("basis_dev")):
            row["basis_dev_ma5"] = derived.moving_average(
                _trailing(rows, upto, "basis_dev"),
                config.derived.basis_dev_ma_days,
            )

        if _is_present(row.get("fut_foreign_net_qty")):
            qty_series = _trailing(rows, upto, "fut_foreign_net_qty")
            window = qty_series[-config.derived.foreign_cum_window_days :]
            row["fut_foreign_net_qty_cum20"] = float(sum(window))

        if _is_present(row.get("usdkrw")):
            row["usdkrw_ret_5d"] = derived.pct_return(
                _trailing(rows, upto, "usdkrw"), config.derived.usdkrw_ret_days
            )

        if _is_present(row.get("k200_close")):
            mas: list[float | None] = []
            for window_days in config.derived.k200_ma_windows:
                ma = derived.moving_average(k200_series, window_days)
                row[f"k200_ma{window_days}"] = ma
                mas.append(ma)
            row["k200_ma_alignment"] = derived.ma_alignment(mas)
            row["k200_ret_20d"] = derived.pct_return(
                k200_series, config.derived.k200_ret_days
            )

        coverage, missing = _coverage(row, config.components)
        row["coverage_ratio"] = coverage
        row["missing_components"] = missing


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _existing_rows(store: Any, start: date, end: date) -> dict[date, dict[str, Any]]:
    frame = store.read_range(start, end, snapshot="close")
    rows: dict[date, dict[str, Any]] = {}
    if frame is None or getattr(frame, "empty", True):
        return rows
    for record in frame.to_dict(orient="records"):
        day = record.get("trade_date")
        if day is None:
            continue
        rows[day] = {
            key: value
            for key, value in record.items()
            if key not in _NON_CARRY_COLUMNS and _is_present(value)
        }
    return rows


async def run_backfill(
    *,
    start: date,
    end: date,
    components: list[str],
    store: Any,
    config: MarketStructureCollectorConfig | None = None,
    kis_client: Any = None,
    krx_client: Any = None,
    yahoo_daily: Any = None,
    csv_path: Path | None = None,
    dry_run: bool = False,
    calendar: MarketCalendar | None = None,
) -> dict[str, Any]:
    """Fetch, merge, derive, and (unless dry-run) write close rows.

    Returns the report dict (also printed by ``main``).
    """
    config = config or MarketStructureCollectorConfig.from_yaml()
    calendar = calendar or MarketCalendar()
    trading_days = calendar.get_trading_days_in_range(start, end)

    manifest_before = store.dataset_manifest()

    buffer_start = start - timedelta(days=_HISTORY_BUFFER_DAYS)
    rows = _existing_rows(store, buffer_start, end)

    component_updates: dict[str, dict[date, dict[str, Any]]] = {}

    if "program" in components:
        if kis_client is None:
            logger.warning("program: no KIS client available; skipping")
        else:
            component_updates["program"] = await fetch_program_updates(
                kis_client, config, start, end
            )
    if "oi" in components:
        if krx_client is None:
            logger.warning(
                "oi: KRX Open API client unavailable (KRX_API_KEY not set?);"
                " skipping"
            )
        else:
            component_updates["oi"] = fetch_oi_updates(krx_client, trading_days)
    if "k200" in components:
        if kis_client is None:
            logger.warning("k200: no KIS client available; skipping")
        else:
            component_updates["k200"] = await fetch_k200_updates(
                kis_client, config, start, end
            )
    if "fx" in components:
        from shared.macro.config import MacroCollectorConfig

        yahoo_symbols = MacroCollectorConfig.from_yaml().yahoo_symbols
        component_updates["fx"] = fetch_fx_updates(
            yahoo_daily or _default_yahoo_daily,
            yahoo_symbols,
            trading_days,
            start,
            end,
        )
    if "foreign_futures" in components:
        if csv_path is None:
            logger.warning(
                "foreign_futures: historical data requires --from-csv (KRX login"
                " wall, roadmap O1); skipping"
            )
        else:
            component_updates["foreign_futures"] = load_foreign_futures_csv(
                csv_path, start, end
            )

    touched: set[date] = set()
    for updates in component_updates.values():
        for day, columns in updates.items():
            rows.setdefault(day, {}).update(
                {key: value for key, value in columns.items() if _is_present(value)}
            )
            touched.add(day)

    target_days = sorted(day for day in rows if start <= day <= end)
    recompute_derived(rows, target_days, config)
    touched.update(target_days)

    written = 0
    if not dry_run:
        for day in sorted(touched):
            if not (start <= day <= end):
                continue
            row = rows.get(day)
            if not row:
                continue
            payload = {k: v for k, v in row.items() if _is_present(v)}
            payload["asof_ts"] = _now_kst()
            store.replace_day(day, "close", payload)
            written += 1

    manifest_after = store.dataset_manifest()

    covered_days = {day for day in rows if start <= day <= end}
    gap_days = [day for day in trading_days if day not in covered_days]
    component_gaps = {
        component: [
            day
            for day in trading_days
            if not any(
                _is_present(rows.get(day, {}).get(column))
                for column in derived_component_columns(component)
            )
        ]
        for component in components
    }

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "components": components,
        "dry_run": dry_run,
        "trading_days": len(trading_days),
        "rows_before": manifest_before["row_count"],
        "rows_after": manifest_after["row_count"],
        "rows_written": written,
        "component_fill_counts": {
            component: len(updates) for component, updates in component_updates.items()
        },
        "gap_days": [day.isoformat() for day in gap_days],
        "component_gap_counts": {
            component: len(days) for component, days in component_gaps.items()
        },
    }


def derived_component_columns(component: str) -> tuple[str, ...]:
    from services.market_structure_collector.main import COMPONENT_COLUMNS

    return COMPONENT_COLUMNS.get(component, (component,))


def _print_report(report: dict[str, Any]) -> None:
    print("=== market-structure backfill report ===")
    print(f"range          : {report['start']} .. {report['end']}")
    print(f"components     : {','.join(report['components'])}")
    print(f"dry_run        : {report['dry_run']}")
    print(f"trading days   : {report['trading_days']}")
    print(f"rows before    : {report['rows_before']}")
    print(f"rows after     : {report['rows_after']}")
    print(f"rows written   : {report['rows_written']}")
    print(f"fills/component: {report['component_fill_counts']}")
    print(f"gaps/component : {report['component_gap_counts']}")
    gaps = report["gap_days"]
    preview = ", ".join(gaps[:10]) + (" ..." if len(gaps) > 10 else "")
    print(f"day gaps       : {len(gaps)}{f' ({preview})' if gaps else ''}")


def _build_krx_client() -> Any | None:
    from shared.config.secrets import SecretsManager

    if not SecretsManager.krx_api_key():
        return None
    from shared.llm.krx_api_client import KRXOpenAPIClient

    return KRXOpenAPIClient()


async def _run_cli(args: argparse.Namespace) -> int:
    from shared.storage.market_structure_store import create_market_structure_store

    components = [c.strip() for c in args.components.split(",") if c.strip()]
    unknown = [c for c in components if c not in BACKFILL_COMPONENTS]
    if unknown:
        logger.error(
            "unknown components: %s (allowed: %s)", unknown, BACKFILL_COMPONENTS
        )
        return 2
    if "foreign_futures" in components and args.from_csv is None:
        logger.error("foreign_futures backfill requires --from-csv (KRX login wall)")
        return 2
    if args.from_csv is not None and "foreign_futures" not in components:
        components.append("foreign_futures")

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if start > end:
        logger.error("--start must be <= --end")
        return 2

    store = create_market_structure_store()

    kis_client = None
    needs_kis = bool({"program", "k200"} & set(components))
    if needs_kis:
        from shared.kis.client import KISClient

        kis_client = KISClient(_futures_kis_auth_config())

    try:
        report = await run_backfill(
            start=start,
            end=end,
            components=components,
            store=store,
            kis_client=kis_client,
            krx_client=_build_krx_client() if "oi" in components else None,
            csv_path=Path(args.from_csv) if args.from_csv else None,
            dry_run=args.dry_run,
        )
    finally:
        if kis_client is not None:
            await kis_client.close()

    _print_report(report)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill market-structure daily close rows"
    )
    parser.add_argument("--start", required=True, help="start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="end date (YYYY-MM-DD)")
    parser.add_argument(
        "--components",
        default=",".join(DEFAULT_COMPONENTS),
        help=f"comma list of {BACKFILL_COMPONENTS} (default: {','.join(DEFAULT_COMPONENTS)})",
    )
    parser.add_argument(
        "--from-csv",
        default=None,
        help="manual foreign-futures CSV export (date,net_qty[,net_val])",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return asyncio.run(_run_cli(args))


if __name__ == "__main__":
    sys.exit(main())
