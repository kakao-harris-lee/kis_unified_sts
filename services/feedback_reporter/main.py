"""Unified performance feedback report runner (Phase 6A — read-only batch).

One-shot cron entrypoint (deploy/scheduler.crontab), mirroring the
``services/portfolio_monitor`` one-shot pattern. Roadmap:
docs/plans/2026-07-02-unified-investment-system-roadmap.md §Phase 6; design doc
§8 / §8.2.

Per run it assembles already-persisted runtime data (RuntimeLedger v4
track-tagged trades/fills, ``portfolio_equity_daily``, ``hedge_advice``;
market_structure_daily close rows; the newest ``experiment run`` artifact) and
turns it into a report via the pure ``shared.reports.feedback`` engine, then:

1. writes ``{reports_root}/{kind}/<period_label>.{md,json}`` (idempotent
   overwrite — the durable record and the FIXED 6B-UI file contract);
2. publishes the ``portfolio:feedback:latest`` Redis freshness pointer (hash,
   config TTL) for the 6B UI lane;
3. sends ONE Telegram headline through the existing notifier channel.

This batch NEVER touches any strategy/execution/gate path — its only side
effects are report files, the Redis pointer, and the Telegram headline.
``--dry-run`` computes + logs only (no file/Redis/Telegram writes). Same-period
re-runs overwrite the files and re-publish the pointer (fully idempotent).
"""

from __future__ import annotations

import argparse
import asyncio
import calendar
import json
import logging
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from shared.portfolio.config import TRACK_CORE, TRACK_FUTURES, TRACK_STOCK
from shared.reports.config import FeedbackReportsConfig
from shared.reports.feedback import (
    MonthlyInput,
    QuarterlyInput,
    QuarterlyTrackAInput,
    QuarterlyTrackBInput,
    QuarterlyTrackCInput,
    WeeklyInput,
    build_headline,
    compute_monthly,
    compute_quarterly,
    compute_slippage,
    compute_weekly,
    headline_text,
    load_backtest_expectation,
    render_markdown,
    to_json,
)

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

VALID_KINDS = ("weekly", "monthly", "quarterly")

#: (start, end) -> market_structure_daily close rows as plain dicts.
MarketRowsProvider = Callable[[date, date], Sequence[Mapping[str, Any]]]
#: reports_dir -> backtest-expectation dict (or None).
ExpectationLoader = Callable[[str], Mapping[str, Any] | None]


def _now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


def _end_iso(day: date) -> str:
    """Inclusive upper bound for ``exit_time``/``filled_at`` string filters."""
    return f"{day.isoformat()}T23:59:59"


def _last_day_of_month(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _month_first(d: date, months_back: int) -> date:
    """First day of the month ``months_back`` months before ``d``'s month."""
    total = d.year * 12 + (d.month - 1) - months_back
    return date(total // 12, total % 12 + 1, 1)


# ---------------------------------------------------------------------------
# Period resolution (KST-clock defaults + explicit --period override)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Period:
    label: str
    start: date
    end: date


def resolve_period(kind: str, period: str | None, now: datetime) -> Period:
    """Resolve (label, start, end) for a report kind.

    Defaults follow the cron cadence: weekly → the week's last trading day
    (Friday on/before the Saturday run), monthly → the previous KST month,
    quarterly → the previous quarter. ``period`` overrides the default.
    """
    if kind == "weekly":
        if period:
            label_date = date.fromisoformat(period)
        else:
            today = now.date()
            # Most recent Friday on/before today (Saturday run → yesterday).
            label_date = today - timedelta(days=(today.weekday() - 4) % 7)
        return Period(
            label_date.isoformat(), label_date - timedelta(days=6), label_date
        )

    if kind == "monthly":
        if period:
            year, month = (int(x) for x in period.split("-")[:2])
        else:
            prev = now.date().replace(day=1) - timedelta(days=1)
            year, month = prev.year, prev.month
        return Period(
            f"{year:04d}-{month:02d}",
            date(year, month, 1),
            _last_day_of_month(year, month),
        )

    if kind == "quarterly":
        if period:
            upper = period.upper()
            if "Q" in upper:
                year_s, quarter_s = upper.split("-Q")
                year, quarter = int(year_s), int(quarter_s)
            else:
                year, month = (int(x) for x in period.split("-")[:2])
                quarter = (month - 1) // 3 + 1
        else:
            quarter = (now.month - 1) // 3
            year = now.year
            if quarter == 0:
                quarter, year = 4, year - 1
        start_month = (quarter - 1) * 3 + 1
        return Period(
            f"{year:04d}-Q{quarter}",
            date(year, start_month, 1),
            _last_day_of_month(year, start_month + 2),
        )

    raise ValueError(f"unknown report kind: {kind!r}")


# ---------------------------------------------------------------------------
# Ledger loading helpers
# ---------------------------------------------------------------------------

_TRACK_IDS = (TRACK_STOCK, TRACK_FUTURES, TRACK_CORE)


def _load_track_trades(
    ledger: Any, track_id: str, start: date, end: date
) -> list[dict[str, Any]]:
    return ledger.query_trades(
        {
            "track_id": track_id,
            "start": start.isoformat(),
            "end": _end_iso(end),
            "limit": 0,
        }
    )


def _load_track_fills(
    ledger: Any, track_id: str, start: date, end: date
) -> list[dict[str, Any]]:
    return ledger.query_fills(
        {
            "track_id": track_id,
            "start": start.isoformat(),
            "end": _end_iso(end),
            "limit": 0,
        }
    )


def _load_tracks(
    ledger: Any, start: date, end: date
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    trades = {t: _load_track_trades(ledger, t, start, end) for t in _TRACK_IDS}
    fills = {t: _load_track_fills(ledger, t, start, end) for t in _TRACK_IDS}
    return trades, fills


def _track_c_inception(ledger: Any) -> date | None:
    """Earliest Track C trade exit date (Track C EV inception)."""
    trades = ledger.query_trades({"track_id": TRACK_FUTURES, "limit": 0})
    exits = [str(t.get("exit_time")) for t in trades if t.get("exit_time")]
    days: list[date] = []
    for value in exits:
        try:
            days.append(date.fromisoformat(value[:10]))
        except ValueError:
            continue
    return min(days) if days else None


# ---------------------------------------------------------------------------
# Default production data providers (injectable in tests)
# ---------------------------------------------------------------------------


def _default_market_rows_provider() -> MarketRowsProvider:
    def _read(start: date, end: date) -> list[dict[str, Any]]:
        from shared.storage.market_structure_store import (
            create_market_structure_store,
        )

        frame = create_market_structure_store().read_range(
            start=start, end=end, snapshot="close"
        )
        if frame is None or getattr(frame, "empty", True):
            return []
        return frame.to_dict("records")

    return _read


def _default_expectation_loader() -> ExpectationLoader:
    def _load(reports_dir: str) -> Mapping[str, Any] | None:
        return load_backtest_expectation(reports_dir)

    return _load


# ---------------------------------------------------------------------------
# Report assembly per kind
# ---------------------------------------------------------------------------


def _build_weekly(*, ledger: Any, period: Period, generated_at: str) -> dict[str, Any]:
    trades, fills = _load_tracks(ledger, period.start, period.end)
    return compute_weekly(
        WeeklyInput(
            period_label=period.label,
            start=period.start,
            end=period.end,
            generated_at=generated_at,
            tracks_trades=trades,
            tracks_fills=fills,
        )
    )


def _build_monthly(
    *,
    ledger: Any,
    config: FeedbackReportsConfig,
    period: Period,
    generated_at: str,
    market_rows_provider: MarketRowsProvider,
) -> dict[str, Any]:
    trades, fills = _load_tracks(ledger, period.start, period.end)
    equity_rows = ledger.query_portfolio_equity_daily(
        {"month": period.label, "limit": 0}
    )
    hedge_rows = ledger.query_hedge_advice(
        {"start": period.start.isoformat(), "end": period.end.isoformat(), "limit": 0}
    )
    market_rows = list(market_rows_provider(period.start, period.end))
    return compute_monthly(
        MonthlyInput(
            period_label=period.label,
            start=period.start,
            end=period.end,
            generated_at=generated_at,
            tracks_trades=trades,
            tracks_fills=fills,
            equity_rows=equity_rows,
            market_rows=market_rows,
            hedge_rows=hedge_rows,
            risk_band_column=config.monthly.risk_band_column,
            risk_score_column=config.monthly.risk_score_column,
        )
    )


def _build_quarterly(
    *,
    ledger: Any,
    config: FeedbackReportsConfig,
    period: Period,
    generated_at: str,
    market_rows_provider: MarketRowsProvider,
    expectation_loader: ExpectationLoader,
    capital_base_b: float | None,
) -> dict[str, Any]:
    trades, fills = _load_tracks(ledger, period.start, period.end)

    # Track B — 6-month rolling realized vs backtest expectation (§8.2).
    tb_cfg = config.quarterly.track_b
    rolling_start = _month_first(period.end, tb_cfg.rolling_months - 1)
    b_trades = _load_track_trades(ledger, TRACK_STOCK, rolling_start, period.end)
    b_fills = _load_track_fills(ledger, TRACK_STOCK, rolling_start, period.end)
    realized_pnl = sum(float(t["pnl"]) for t in b_trades if t.get("pnl") is not None)
    slippage = compute_slippage(b_fills)
    track_b = QuarterlyTrackBInput(
        rolling_months=tb_cfg.rolling_months,
        backtest_ratio=tb_cfg.backtest_ratio,
        realized_pnl=realized_pnl if b_trades else None,
        slippage_total_cost=(slippage or {}).get("total_cost") if slippage else None,
        capital_base=capital_base_b,
        expectation=expectation_loader(tb_cfg.experiment_reports_dir),
    )

    # Track C — cumulative EV over the full track history (§8.2).
    tc_cfg = config.quarterly.track_c
    c_trades_all = ledger.query_trades({"track_id": TRACK_FUTURES, "limit": 0})
    track_c = QuarterlyTrackCInput(
        trades=c_trades_all,
        inception=_track_c_inception(ledger),
        period_end=period.end,
        breakeven_months=tc_cfg.breakeven_months,
        ev_checkpoint_months=tc_cfg.ev_checkpoint_months,
        ev_final_months=tc_cfg.ev_final_months,
    )

    # Track A — benchmark-relative; <min_history_years → deferred (§8.2).
    ta_cfg = config.quarterly.track_a
    equity_rows = ledger.query_portfolio_equity_daily({"limit": 0})
    a_dates = [
        str(r.get("trade_date"))
        for r in equity_rows
        if r.get("track_a_equity") is not None
    ]
    bench_start = (
        date.fromisoformat(min(a_dates)) if a_dates else period.end - timedelta(days=1)
    )
    benchmark_rows = list(market_rows_provider(bench_start, period.end))
    track_a = QuarterlyTrackAInput(
        equity_rows=equity_rows,
        benchmark_rows=benchmark_rows,
        benchmark_column=ta_cfg.benchmark_column,
        min_history_years=ta_cfg.min_history_years,
        period_end=period.end,
    )

    return compute_quarterly(
        QuarterlyInput(
            period_label=period.label,
            start=period.start,
            end=period.end,
            generated_at=generated_at,
            tracks_trades=trades,
            tracks_fills=fills,
            track_b=track_b,
            track_c=track_c,
            track_a=track_a,
        )
    )


# ---------------------------------------------------------------------------
# Output side effects (files + Redis pointer + Telegram)
# ---------------------------------------------------------------------------


@dataclass
class ReportRun:
    """Result of one report run (paths are ``None`` for a dry-run)."""

    report: dict[str, Any]
    json_path: Path | None
    md_path: Path | None


def write_report_files(
    report: Mapping[str, Any], reports_root: str
) -> tuple[Path, Path]:
    """Write ``<reports_root>/<kind>/<label>.{json,md}`` (idempotent overwrite).

    File layout is the FIXED 6B UI-lane contract — do not rename.
    """
    kind = str(report["kind"])
    label = str(report["period_label"])
    directory = Path(reports_root) / kind
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / f"{label}.json"
    md_path = directory / f"{label}.md"
    json_path.write_text(to_json(report) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def publish_pointer(
    redis: Any,
    config: FeedbackReportsConfig,
    report: Mapping[str, Any],
    json_path: Path,
    md_path: Path,
) -> None:
    """Publish ``portfolio:feedback:latest`` — FIXED 6B-UI hash, do not rename."""
    fields = {
        "kind": str(report["kind"]),
        "period_label": str(report["period_label"]),
        "generated_at": str(report.get("generated_at", "")),
        "json_path": str(json_path),
        "md_path": str(md_path),
        "headline": json.dumps(build_headline(report), ensure_ascii=False),
    }
    # delete-then-hset so stale fields from a previous publish never linger.
    redis.delete(config.redis.latest_key)
    redis.hset(config.redis.latest_key, mapping=fields)
    redis.expire(config.redis.latest_key, config.redis.latest_ttl_seconds)


def _dispatch_headline(notifier: Any, report: Mapping[str, Any]) -> None:
    if notifier is None:
        return

    async def _send() -> None:
        await notifier.send_message(headline_text(report), is_critical=False)

    try:
        asyncio.run(_send())
    except Exception as exc:  # noqa: BLE001 — alerts must not fail the run
        logger.warning("feedback-report telegram headline failed: %s", exc)


# ---------------------------------------------------------------------------
# One-shot run
# ---------------------------------------------------------------------------


def run_report(
    *,
    kind: str,
    config: FeedbackReportsConfig,
    ledger: Any,
    redis: Any,
    period: str | None = None,
    now: datetime | None = None,
    dry_run: bool = False,
    notifier: Any = None,
    market_rows_provider: MarketRowsProvider | None = None,
    expectation_loader: ExpectationLoader | None = None,
    capital_base_b: float | None = None,
) -> ReportRun:
    """Compute one report and (unless dry-run) persist + publish + alert it.

    All external data sources are injectable so the run is hermetic-testable
    with a tmp ledger, fakeredis, and in-memory market/expectation providers.
    """
    if kind not in VALID_KINDS:
        raise ValueError(f"unknown report kind: {kind!r} (expected {VALID_KINDS})")
    current = now or _now_kst()
    period_res = resolve_period(kind, period, current)
    generated_at = current.isoformat()
    market_provider = market_rows_provider or _default_market_rows_provider()
    expect_loader = expectation_loader or _default_expectation_loader()

    if kind == "weekly":
        report = _build_weekly(
            ledger=ledger, period=period_res, generated_at=generated_at
        )
    elif kind == "monthly":
        report = _build_monthly(
            ledger=ledger,
            config=config,
            period=period_res,
            generated_at=generated_at,
            market_rows_provider=market_provider,
        )
    else:  # quarterly
        if capital_base_b is None:
            capital_base_b = _default_capital_base_b()
        report = _build_quarterly(
            ledger=ledger,
            config=config,
            period=period_res,
            generated_at=generated_at,
            market_rows_provider=market_provider,
            expectation_loader=expect_loader,
            capital_base_b=capital_base_b,
        )

    logger.info(
        "feedback report %s %s: tracks B/C trades=%s/%s missing=%s%s",
        kind,
        period_res.label,
        report["tracks"].get(TRACK_STOCK, {}).get("trades"),
        report["tracks"].get(TRACK_FUTURES, {}).get("trades"),
        report.get("missing"),
        " (dry-run)" if dry_run else "",
    )

    if dry_run:
        return ReportRun(report=report, json_path=None, md_path=None)

    json_path, md_path = write_report_files(report, config.reports_root)
    try:
        publish_pointer(redis, config, report, json_path, md_path)
    except Exception as exc:  # noqa: BLE001 — the files are the durable record
        logger.warning("feedback pointer publish failed: %s", exc)
    if config.alerts.enabled:
        _dispatch_headline(notifier, report)

    return ReportRun(report=report, json_path=json_path, md_path=md_path)


# ---------------------------------------------------------------------------
# CLI glue (production defaults)
# ---------------------------------------------------------------------------


def _default_ledger() -> Any:
    from shared.storage import SQLiteRuntimeLedger
    from shared.storage.config import StorageConfig

    storage = StorageConfig.load_or_default()
    return SQLiteRuntimeLedger(storage.runtime_storage.sqlite)


def _default_capital_base_b() -> float | None:
    from shared.portfolio.config import PortfolioConfig

    try:
        return PortfolioConfig.load_or_default().capital_base.track_b_stock_krw
    except Exception as exc:  # noqa: BLE001 — missing YAML → engine reports missing
        logger.warning("portfolio capital base unavailable: %s", exc)
        return None


def _default_notifier(config: FeedbackReportsConfig) -> Any | None:
    if not config.alerts.enabled:
        return None
    try:
        from shared.notification.telegram import notifier_for_domain

        return notifier_for_domain(config.alerts.domain)
    except Exception as exc:  # noqa: BLE001 — alerts must not block the run
        logger.warning("telegram notifier unavailable: %s", exc)
        return None


def _cli(args: argparse.Namespace) -> int:
    import redis as redis_lib

    from shared.config.runtime_defaults import redis_url_from_env

    config = FeedbackReportsConfig.load_or_default()
    ledger = _default_ledger()
    redis_client = redis_lib.Redis.from_url(redis_url_from_env(), decode_responses=True)
    try:
        run_report(
            kind=args.kind,
            config=config,
            ledger=ledger,
            redis=redis_client,
            period=args.period,
            dry_run=args.dry_run,
            notifier=_default_notifier(config),
        )
        return 0
    finally:
        redis_client.close()
        ledger.close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Unified performance feedback report runner (read-only)"
    )
    parser.add_argument("kind", choices=VALID_KINDS, help="report cadence")
    parser.add_argument(
        "--period",
        help=(
            "period override — weekly YYYY-MM-DD (week last trading day), "
            "monthly YYYY-MM, quarterly YYYY-QN (default: previous period)"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="compute + log only; no file write, Redis publish, or Telegram",
    )
    return _cli(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
