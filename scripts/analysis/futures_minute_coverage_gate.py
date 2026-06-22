#!/usr/bin/env python3
"""Futures-minute coverage quality gate (alert on shortfall).

Run AFTER the daily futures-minute backfill (e.g. the 16:05 KST job).  For the
active KOSPI200-mini front-month contract, count one-minute bars per closed
trading day in a lookback window and flag any day below the Task-3 completeness
threshold.  On shortfall, emit a WARNING log + an operator Telegram alert so a
silent ~70%-minute loss never recurs.

READ-ONLY on parquet: this reports/alerts, it never mutates market data.

Threshold reuse: ``min_rows`` defaults to the single source of truth for
"expected bars" -- :data:`MINUTE_COMPLETENESS_MIN_ROWS` from
``shared.collector.historical.parquet_backfill`` (Task 3) -- so the gate and the
backfill never drift to different numbers.

Config: ``daily_data_quality.yaml::futures_minute_coverage``.  Exit codes:
  0 = OK (all closed days covered), 1 = shortfall, 2 = script error.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.collector.historical.calendar import (  # noqa: E402
    get_trading_days_range,
    is_trading_day,
)
from shared.collector.historical.futures import get_front_month_code  # noqa: E402
from shared.collector.historical.parquet_backfill import (  # noqa: E402
    MINUTE_COMPLETENESS_MIN_ROWS,
    MINUTE_SESSION_BARS,
    _is_day_closed,
)
from shared.notification.telegram import notifier_for_domain  # noqa: E402

log = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")
CONFIG_PATH = "daily_data_quality.yaml"

# Half-day / early-close floor: half the full regular session.  A genuine KRX
# early-close (~12:30) still clears this floor and is tolerated, while a
# single-KIS-page-only fetch (~102 bars) falls below it and is flagged.  Days at
# or above this floor (but below ``min_rows``) are tolerated, not flagged.
_DEFAULT_HALF_DAY_MIN_ROWS = max(1, MINUTE_SESSION_BARS // 2)


class MinuteBarCounter(Protocol):
    """Read-only minute-bar count source for one code/day."""

    def count_minute_bars_for_day(self, code: str, day: date) -> int: ...


@dataclass(frozen=True)
class CoverageConfig:
    lookback_days: int = 5
    min_rows: int = MINUTE_COMPLETENESS_MIN_ROWS
    half_day_min_rows: int = _DEFAULT_HALF_DAY_MIN_ROWS
    product: str = "mini"
    notify_on_shortfall: bool = True


@dataclass(frozen=True)
class Shortfall:
    code: str
    day: date
    bars: int
    expected: int


@dataclass
class CoverageReport:
    code: str
    report_date: date
    checked_days: int = 0
    skipped_days: int = 0
    shortfalls: list[Shortfall] = field(default_factory=list)

    @property
    def has_shortfall(self) -> bool:
        return bool(self.shortfalls)


# ---------------------------------------------------------------------------
# Parquet-backed counter (read-only)
# ---------------------------------------------------------------------------


class _ParquetMinuteCounter:
    """Counts minute bars for a code/day via the futures parquet store."""

    def __init__(self) -> None:
        from shared.storage.config import StorageConfig
        from shared.storage.market_data_store import ParquetMarketDataStore

        storage_config = StorageConfig.load_or_default()
        self._store = ParquetMarketDataStore(
            storage_config.market_data.parquet.root,
            asset_class="futures",
        )

    def count_minute_bars_for_day(self, code: str, day: date) -> int:
        start = datetime.combine(day, datetime.min.time())
        end = start + timedelta(days=1) - timedelta(microseconds=1)
        df = self._store.get_minute_bars(code, start=start, end=end)
        return int(len(df))


def _build_store() -> MinuteBarCounter:
    return _ParquetMinuteCounter()


def _front_month_code(report_date: date, *, product: str = "mini") -> str:
    return get_front_month_code(product=product, target_date=report_date)


def _resolve_trading_days(config: CoverageConfig, report_date: date) -> list[date]:
    """Return the trading days in the lookback window ending at ``report_date``."""
    start = report_date - timedelta(days=max(1, config.lookback_days) * 2)
    days = [d for d in get_trading_days_range(start, report_date) if is_trading_day(d)]
    return days[-config.lookback_days :]


# ---------------------------------------------------------------------------
# Core evaluation (pure; testable with a fake counter)
# ---------------------------------------------------------------------------


def evaluate_coverage(
    *,
    store: MinuteBarCounter,
    code: str,
    trading_days: list[date],
    config: CoverageConfig,
    report_date: date | None = None,
) -> CoverageReport:
    """Count minute bars per closed trading day and flag shortfalls.

    A closed day is flagged only when its bar count is below ``half_day_min_rows``
    (the early-close / half-day floor).  Counts at/above the half-day floor but
    below ``min_rows`` are tolerated, not flagged.  In-progress (not-yet-closed)
    days are skipped, never flagged.
    """
    report = CoverageReport(code=code, report_date=report_date or date.today())
    for day in trading_days:
        if not _is_day_closed(day):
            report.skipped_days += 1
            continue
        report.checked_days += 1
        bars = store.count_minute_bars_for_day(code, day)
        if bars >= config.min_rows:
            continue
        if bars >= config.half_day_min_rows:
            # Plausible early-close / half-day; tolerated.
            continue
        report.shortfalls.append(
            Shortfall(code=code, day=day, bars=bars, expected=config.min_rows)
        )
    return report


# ---------------------------------------------------------------------------
# Alerting
# ---------------------------------------------------------------------------


def _format_alert(report: CoverageReport) -> str:
    def code(value: Any) -> str:
        return f"<code>{html.escape(str(value), quote=False)}</code>"

    lines = [
        "<b>Futures-minute coverage SHORTFALL</b>",
        f"front_month: {code(report.code)}",
        f"report_date: {code(report.report_date.isoformat())}",
        f"checked_days: {code(report.checked_days)}, "
        f"shortfall_days: {code(len(report.shortfalls))}",
    ]
    for sf in report.shortfalls[:10]:
        lines.append(
            f"- {code(sf.day.isoformat())}: "
            f"bars={code(sf.bars)} expected>={code(sf.expected)}"
        )
    return "\n".join(lines)


async def _send_alert(report: CoverageReport) -> bool:
    try:
        notifier = notifier_for_domain("briefing")
        if notifier is None:
            return False
        await notifier.send_message(
            _format_alert(report),
            is_critical=True,
            raise_on_error=True,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("futures-minute coverage telegram alert failed: %s", exc)
        return False


def _load_config() -> CoverageConfig:
    from shared.config.loader import ConfigLoader

    try:
        raw = ConfigLoader.load(CONFIG_PATH, use_cache=False)
    except Exception:  # noqa: BLE001 - keep gate runnable on config errors
        raw = {}
    section = (raw or {}).get("futures_minute_coverage", {}) or {}

    def _int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    min_rows = section.get("min_rows")
    env_min = os.getenv("FUTURES_MINUTE_COVERAGE_MIN_ROWS")
    if env_min is not None:
        min_rows = env_min
    half = section.get("half_day_min_rows")
    return CoverageConfig(
        lookback_days=max(1, _int(section.get("lookback_days"), 5)),
        min_rows=max(1, _int(min_rows, MINUTE_COMPLETENESS_MIN_ROWS)),
        half_day_min_rows=max(1, _int(half, _DEFAULT_HALF_DAY_MIN_ROWS)),
        product=str(section.get("product") or "mini"),
        notify_on_shortfall=bool(section.get("notify_on_shortfall", True)),
    )


def run_gate(
    *,
    report_date: date | None = None,
    config: CoverageConfig | None = None,
    notify: bool = True,
) -> int:
    """Run the coverage gate; return 0 OK / 1 shortfall / 2 error."""
    try:
        config = config or _load_config()
        report_date = report_date or datetime.now(KST).date()
        store = _build_store()
        code = _front_month_code(report_date, product=config.product)
        trading_days = _resolve_trading_days(config, report_date)
        report = evaluate_coverage(
            store=store,
            code=code,
            trading_days=trading_days,
            config=config,
            report_date=report_date,
        )
    except Exception as exc:  # noqa: BLE001
        log.error("futures-minute coverage gate failed: %s", exc)
        return 2

    if not report.has_shortfall:
        log.info(
            "futures-minute coverage OK: code=%s checked_days=%d skipped=%d min_rows=%d",
            report.code,
            report.checked_days,
            report.skipped_days,
            config.min_rows,
        )
        print(
            f"OK: {report.code} checked_days={report.checked_days} "
            f"skipped={report.skipped_days} min_rows={config.min_rows}"
        )
        return 0

    for sf in report.shortfalls:
        log.warning(
            "futures-minute coverage SHORTFALL: code=%s day=%s bars=%d expected>=%d",
            sf.code,
            sf.day.isoformat(),
            sf.bars,
            sf.expected,
        )
    print(
        f"SHORTFALL: {report.code} checked_days={report.checked_days} "
        f"shortfall_days={len(report.shortfalls)}"
    )
    if notify and config.notify_on_shortfall:
        asyncio.run(_send_alert(report))
    return 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date", default="", help="KST report date YYYY-MM-DD. Default: today."
    )
    parser.add_argument(
        "--no-telegram", action="store_true", help="Do not send Telegram alerts."
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    args = _parse_args()
    report_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None
    return run_gate(report_date=report_date, notify=not args.no_telegram)


if __name__ == "__main__":
    raise SystemExit(main())
