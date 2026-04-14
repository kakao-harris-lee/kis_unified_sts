#!/usr/bin/env python3
"""Generate a daily futures session health report.

This report combines:
1) Closed-trade stats from ClickHouse `rl_trades`
2) Optional matrix execution summary (spread/depth blocks)
3) Redis runtime state sanity checks (stale open positions)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import redis
from clickhouse_driver import Client

from shared.db.config import ClickHouseConfig

KST = ZoneInfo("Asia/Seoul")


@dataclass
class TradeRow:
    strategy: str
    side: str
    entry_date: datetime
    exit_date: datetime
    pnl: float
    pnl_pct: float
    hold_seconds: int
    exit_reason: str
    metadata_json: str


@dataclass
class TradeSummary:
    trade_count: int
    total_pnl: float
    avg_pnl: float
    win_rate: float
    gross_win: float
    gross_loss: float
    eod_count: int
    eod_ratio: float
    late_eod_count: int
    slippage_coverage_count: int
    slippage_coverage_ratio: float
    avg_abs_slippage_ticks: float
    by_exit_reason: dict[str, int]
    by_strategy: dict[str, dict[str, float]]


@dataclass
class MatrixSummary:
    found: bool
    summary_path: str
    signals: int
    entries: int
    exits: int
    blocked_total: int
    blocks_wide_spread: int
    blocks_insufficient_depth: int
    blocks_volatility_cooldown: int
    blocks_cross_asset_wide_spread: int
    fill_rate: float
    spread_block_ratio: float
    top_profile: str
    top_profile_score: float
    abnormal_termination_count: int
    unmatched_entries: int
    incomplete_profiles: list[str]


@dataclass
class RedisSummary:
    state: str
    open_positions_count: int
    open_position_entry_days: dict[str, int]
    signals_count: int
    trades_count: int


@dataclass
class HealthReport:
    report_date: str
    generated_at: str
    issues: list[str]
    notification_sent: bool
    trade_summary: TradeSummary
    matrix_summary: MatrixSummary
    redis_summary: RedisSummary


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, str(int(default))).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily futures session health report")
    parser.add_argument(
        "--date",
        default="",
        help="Report date in YYYY-MM-DD (KST). Default: today in KST.",
    )
    parser.add_argument(
        "--run-dir",
        default="",
        help="Optional matrix run dir (e.g. output/paper_matrix/20260304_session).",
    )
    parser.add_argument(
        "--output-dir",
        default="output/reports/futures",
        help="Directory for generated JSON/MD report files.",
    )
    parser.add_argument(
        "--database",
        default="",
        help="ClickHouse database (default from CLICKHOUSE_FUTURES_DATABASE or 'kospi').",
    )
    parser.add_argument(
        "--notify-on-issues",
        dest="notify_on_issues",
        action="store_true",
        default=_parse_bool_env("FUTURES_HEALTH_NOTIFY_ON_ISSUES", True),
        help="Send Telegram notification only when issues are detected.",
    )
    parser.add_argument(
        "--no-notify-on-issues",
        dest="notify_on_issues",
        action="store_false",
        help="Disable Telegram notification.",
    )
    return parser.parse_args()


def _resolve_report_date(raw: str) -> date:
    if raw:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    return datetime.now(KST).date()


def _build_clickhouse_client(database: str) -> Client:
    cfg = ClickHouseConfig.from_env(database=database)
    return Client(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
        connect_timeout=cfg.connect_timeout,
    )


def _fetch_trade_rows(database: str, report_date: date) -> list[TradeRow]:
    start_dt = datetime.combine(report_date, datetime.min.time())
    end_dt = start_dt + timedelta(days=1)
    client = _build_clickhouse_client(database)

    query = f"""
    SELECT
        strategy,
        side,
        entry_date,
        exit_date,
        pnl,
        pnl_pct,
        hold_seconds,
        exit_reason,
        metadata_json
    FROM {database}.rl_trades
    WHERE asset_class = 'futures'
      AND exit_date >= %(start)s
      AND exit_date < %(end)s
    ORDER BY exit_date
    """
    rows = client.execute(query, {"start": start_dt, "end": end_dt})
    client.disconnect()

    out: list[TradeRow] = []
    for row in rows:
        out.append(
            TradeRow(
                strategy=str(row[0]),
                side=str(row[1]),
                entry_date=row[2],
                exit_date=row[3],
                pnl=float(row[4]),
                pnl_pct=float(row[5]),
                hold_seconds=int(row[6]),
                exit_reason=str(row[7]),
                metadata_json=str(row[8] or ""),
            )
        )
    return out


def _safe_json_loads(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _compute_trade_summary(rows: list[TradeRow]) -> TradeSummary:
    trade_count = len(rows)
    total_pnl = sum(r.pnl for r in rows)
    avg_pnl = (total_pnl / trade_count) if trade_count > 0 else 0.0
    wins = sum(1 for r in rows if r.pnl > 0)
    win_rate = (wins / trade_count * 100.0) if trade_count > 0 else 0.0
    gross_win = sum(r.pnl for r in rows if r.pnl > 0)
    gross_loss = sum(r.pnl for r in rows if r.pnl < 0)

    by_exit_reason: dict[str, int] = {}
    by_strategy_raw: dict[str, dict[str, float]] = {}
    eod_count = 0
    late_eod_count = 0
    slippage_values: list[float] = []

    for row in rows:
        reason = row.exit_reason
        by_exit_reason[reason] = by_exit_reason.get(reason, 0) + 1

        reason_l = reason.lower()
        if reason_l == "eod_close":
            eod_count += 1
            if row.hold_seconds <= 300:
                late_eod_count += 1

        strat = by_strategy_raw.setdefault(
            row.strategy,
            {"trades": 0.0, "wins": 0.0, "total_pnl": 0.0, "eod_trades": 0.0},
        )
        strat["trades"] += 1
        if row.pnl > 0:
            strat["wins"] += 1
        strat["total_pnl"] += row.pnl
        if reason_l == "eod_close":
            strat["eod_trades"] += 1

        meta = _safe_json_loads(row.metadata_json)
        execution = meta.get("execution", {}) if isinstance(meta, dict) else {}
        if isinstance(execution, dict):
            slip = execution.get("slippage_ticks")
            if isinstance(slip, (int, float)):
                slippage_values.append(abs(float(slip)))

    by_strategy: dict[str, dict[str, float]] = {}
    for strategy, stats in by_strategy_raw.items():
        trades = int(stats["trades"])
        wins_n = int(stats["wins"])
        eod_n = int(stats["eod_trades"])
        by_strategy[strategy] = {
            "trades": float(trades),
            "win_rate": (wins_n / trades * 100.0) if trades > 0 else 0.0,
            "total_pnl": float(stats["total_pnl"]),
            "avg_pnl": (stats["total_pnl"] / trades) if trades > 0 else 0.0,
            "eod_ratio": (eod_n / trades * 100.0) if trades > 0 else 0.0,
        }

    slippage_coverage_count = len(slippage_values)
    slippage_coverage_ratio = (
        slippage_coverage_count / trade_count * 100.0 if trade_count > 0 else 0.0
    )
    avg_abs_slippage_ticks = (
        sum(slippage_values) / slippage_coverage_count
        if slippage_coverage_count > 0
        else 0.0
    )

    return TradeSummary(
        trade_count=trade_count,
        total_pnl=round(total_pnl, 2),
        avg_pnl=round(avg_pnl, 2),
        win_rate=round(win_rate, 2),
        gross_win=round(gross_win, 2),
        gross_loss=round(gross_loss, 2),
        eod_count=eod_count,
        eod_ratio=round(
            (eod_count / trade_count * 100.0) if trade_count > 0 else 0.0, 2
        ),
        late_eod_count=late_eod_count,
        slippage_coverage_count=slippage_coverage_count,
        slippage_coverage_ratio=round(slippage_coverage_ratio, 2),
        avg_abs_slippage_ticks=round(avg_abs_slippage_ticks, 4),
        by_exit_reason=by_exit_reason,
        by_strategy=by_strategy,
    )


def _load_matrix_summary(run_dir: str) -> MatrixSummary:
    if not run_dir:
        return MatrixSummary(
            found=False,
            summary_path="",
            signals=0,
            entries=0,
            exits=0,
            blocked_total=0,
            blocks_wide_spread=0,
            blocks_insufficient_depth=0,
            blocks_volatility_cooldown=0,
            blocks_cross_asset_wide_spread=0,
            fill_rate=0.0,
            spread_block_ratio=0.0,
            top_profile="",
            top_profile_score=0.0,
            abnormal_termination_count=0,
            unmatched_entries=0,
            incomplete_profiles=[],
        )

    root = Path(run_dir)
    candidates = sorted(root.glob("paper_profile_matrix_summary_*.json"))
    if not candidates:
        return MatrixSummary(
            found=False,
            summary_path="",
            signals=0,
            entries=0,
            exits=0,
            blocked_total=0,
            blocks_wide_spread=0,
            blocks_insufficient_depth=0,
            blocks_volatility_cooldown=0,
            blocks_cross_asset_wide_spread=0,
            fill_rate=0.0,
            spread_block_ratio=0.0,
            top_profile="",
            top_profile_score=0.0,
            abnormal_termination_count=0,
            unmatched_entries=0,
            incomplete_profiles=[],
        )

    latest = candidates[-1]
    payload = _safe_json_loads(latest.read_text(encoding="utf-8"))
    rows = payload.get("rows", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        rows = []

    signals = 0
    entries = 0
    exits = 0
    blocked_total = 0
    blocks_wide = 0
    blocks_depth = 0
    blocks_vol = 0
    blocks_cross = 0
    abnormal_termination_count = 0
    unmatched_entries = 0
    incomplete_profiles: list[str] = []

    top_profile = ""
    top_profile_score = 0.0
    if rows:
        first = rows[0] if isinstance(rows[0], dict) else {}
        top_profile = str(first.get("profile", ""))
        top_profile_score = float(first.get("uptrend_score", 0.0) or 0.0)

    for row in rows:
        if not isinstance(row, dict):
            continue
        signals += int(row.get("entry_signals", 0) or 0)
        entries += int(row.get("entries", 0) or 0)
        exits += int(row.get("exits", 0) or 0)
        blocked_total += int(row.get("blocked_total", 0) or 0)
        blocks_wide += int(row.get("blocks_wide_spread", 0) or 0)
        blocks_depth += int(row.get("blocks_insufficient_depth", 0) or 0)
        blocks_vol += int(row.get("blocks_volatility_cooldown", 0) or 0)
        blocks_cross += int(row.get("blocks_cross_asset_wide_spread", 0) or 0)
        abnormal_termination_count += int(bool(row.get("abnormal_termination", False)))
        unmatched_entries += int(row.get("unmatched_entries", 0) or 0)
        if (
            bool(row.get("abnormal_termination", False))
            or int(row.get("unmatched_entries", 0) or 0) > 0
            or int(row.get("entries", 0) or 0) != int(row.get("exits", 0) or 0)
        ):
            profile = str(row.get("profile", "")).strip()
            if profile:
                incomplete_profiles.append(profile)

    fill_rate = (entries / signals * 100.0) if signals > 0 else 0.0
    spread_block_ratio = (
        (blocks_wide / blocked_total * 100.0) if blocked_total > 0 else 0.0
    )

    return MatrixSummary(
        found=True,
        summary_path=str(latest),
        signals=signals,
        entries=entries,
        exits=exits,
        blocked_total=blocked_total,
        blocks_wide_spread=blocks_wide,
        blocks_insufficient_depth=blocks_depth,
        blocks_volatility_cooldown=blocks_vol,
        blocks_cross_asset_wide_spread=blocks_cross,
        fill_rate=round(fill_rate, 2),
        spread_block_ratio=round(spread_block_ratio, 2),
        top_profile=top_profile,
        top_profile_score=round(top_profile_score, 4),
        abnormal_termination_count=abnormal_termination_count,
        unmatched_entries=unmatched_entries,
        incomplete_profiles=incomplete_profiles,
    )


def _load_redis_summary() -> RedisSummary:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/1")
    client = redis.Redis.from_url(redis_url, decode_responses=True)

    state = ""
    try:
        state = client.hget("trading:futures:status", "state") or ""
    except Exception:
        state = ""

    open_positions_count = 0
    open_position_entry_days: dict[str, int] = {}
    try:
        raw_positions = client.hgetall("trading:futures:positions")
        open_positions_count = len(raw_positions)
        for payload in raw_positions.values():
            parsed = _safe_json_loads(payload)
            entry_time = str(parsed.get("entry_time", ""))
            day = entry_time[:10] if len(entry_time) >= 10 else "unknown"
            open_position_entry_days[day] = open_position_entry_days.get(day, 0) + 1
    except Exception:
        open_positions_count = 0
        open_position_entry_days = {}

    try:
        signals_count = int(client.llen("trading:futures:signals"))
    except Exception:
        signals_count = 0
    try:
        trades_count = int(client.llen("trading:futures:trades"))
    except Exception:
        trades_count = 0

    return RedisSummary(
        state=state,
        open_positions_count=open_positions_count,
        open_position_entry_days=open_position_entry_days,
        signals_count=signals_count,
        trades_count=trades_count,
    )


def _derive_issues(
    trade_summary: TradeSummary,
    matrix_summary: MatrixSummary,
    redis_summary: RedisSummary,
) -> list[str]:
    issues: list[str] = []

    if trade_summary.trade_count == 0:
        issues.append("No closed futures trades recorded for report date.")
        return issues

    if trade_summary.eod_ratio >= 60.0:
        issues.append(
            f"EOD_CLOSE ratio is high ({trade_summary.eod_ratio:.1f}%). "
            "Exit policy dominates model-driven exits."
        )

    if trade_summary.late_eod_count > 0:
        issues.append(
            f"{trade_summary.late_eod_count} trades were EOD-closed within 5 minutes of entry."
        )

    if trade_summary.slippage_coverage_ratio < 80.0:
        issues.append(
            f"Slippage coverage is low ({trade_summary.slippage_coverage_ratio:.1f}%). "
            "Backfilled trades are missing execution metadata."
        )

    if matrix_summary.found:
        if matrix_summary.fill_rate < 10.0 and matrix_summary.signals >= 10:
            issues.append(
                f"Execution fill rate is low ({matrix_summary.fill_rate:.1f}%) "
                f"for {matrix_summary.signals} signals."
            )
        if (
            matrix_summary.spread_block_ratio >= 80.0
            and matrix_summary.blocked_total >= 10
        ):
            issues.append(
                f"Wide-spread blocks dominate guard rejects "
                f"({matrix_summary.spread_block_ratio:.1f}% of blocked entries)."
            )
        if matrix_summary.abnormal_termination_count > 0:
            issues.append(
                f"{matrix_summary.abnormal_termination_count} matrix profile runs ended abnormally."
            )
        if matrix_summary.unmatched_entries > 0:
            issues.append(
                f"Matrix logs show {matrix_summary.unmatched_entries} unmatched entries without a paired exit."
            )
        if matrix_summary.incomplete_profiles:
            issues.append(
                "Incomplete matrix profiles detected: "
                + ", ".join(matrix_summary.incomplete_profiles[:5])
            )

    if (
        redis_summary.open_positions_count > 0
        and redis_summary.state.lower() == "stopped"
    ):
        issues.append(
            f"Redis shows {redis_summary.open_positions_count} open positions while state=stopped."
        )

    return issues


async def _send_issue_notification(report: HealthReport, md_path: Path) -> bool:
    token = (
        os.getenv("TELEGRAM_FUTURES_BOT_TOKEN", "").strip()
        or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    )
    chat_id = (
        os.getenv("TELEGRAM_FUTURES_CHAT_ID", "").strip()
        or os.getenv("TELEGRAM_CHAT_ID", "").strip()
    )
    if not token or not chat_id:
        print("Telegram credentials missing; skip notification.")
        return False

    try:
        from services.monitoring.notifier import TelegramConfig, TelegramNotifier
    except Exception as exc:
        print(f"Failed to import Telegram notifier; skip notification: {exc}")
        return False

    t = report.trade_summary
    m = report.matrix_summary
    issue_lines = "\n".join(f"- {item}" for item in report.issues[:8])
    msg = (
        "🚨 <b>Futures Session Health Alert</b>\n"
        f"date: <code>{report.report_date}</code>\n"
        f"trades: <code>{t.trade_count}</code>, pnl: <code>{t.total_pnl}</code>, win_rate: <code>{t.win_rate:.1f}%</code>\n"
        f"eod_ratio: <code>{t.eod_ratio:.1f}%</code>, slippage_coverage: <code>{t.slippage_coverage_ratio:.1f}%</code>\n"
        f"fill_rate: <code>{m.fill_rate:.1f}%</code>, spread_block_ratio: <code>{m.spread_block_ratio:.1f}%</code>\n"
        f"abnormal_runs: <code>{m.abnormal_termination_count}</code>, unmatched_entries: <code>{m.unmatched_entries}</code>\n\n"
        f"<b>Issues</b>\n{issue_lines}\n\n"
        f"report: <code>{md_path}</code>"
    )

    notifier = TelegramNotifier(
        TelegramConfig(
            token=token,
            chat_id=chat_id,
            parse_mode="HTML",
            disable_notification=False,
        )
    )
    try:
        return bool(await notifier.send(msg))
    finally:
        await notifier.close()


def _to_markdown(report: HealthReport) -> str:
    t = report.trade_summary
    m = report.matrix_summary
    r = report.redis_summary

    lines = [
        f"# Futures Session Health Report ({report.report_date})",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Notification sent: `{report.notification_sent}`",
        "",
        "## Summary",
        f"- Trades: `{t.trade_count}`",
        f"- Total PnL: `{t.total_pnl}`",
        f"- Win rate: `{t.win_rate:.2f}%`",
        f"- EOD close ratio: `{t.eod_ratio:.2f}%` ({t.eod_count}/{t.trade_count})",
        f"- Slippage coverage: `{t.slippage_coverage_ratio:.2f}%` ({t.slippage_coverage_count}/{t.trade_count})",
        "",
        "## Issues",
    ]
    if report.issues:
        for issue in report.issues:
            lines.append(f"- {issue}")
    else:
        lines.append("- No critical issues detected by automatic checks.")

    lines.extend(
        [
            "",
            "## Exit Reasons",
        ]
    )
    if t.by_exit_reason:
        for reason, count in sorted(
            t.by_exit_reason.items(), key=lambda item: item[1], reverse=True
        ):
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- (none)")

    lines.extend(
        [
            "",
            "## Strategy Breakdown",
        ]
    )
    if t.by_strategy:
        for name, stats in sorted(
            t.by_strategy.items(),
            key=lambda item: item[1].get("total_pnl", 0.0),
            reverse=True,
        ):
            lines.append(
                "- "
                f"{name}: trades={int(stats['trades'])}, "
                f"win_rate={stats['win_rate']:.1f}%, "
                f"total_pnl={stats['total_pnl']:.2f}, "
                f"eod_ratio={stats['eod_ratio']:.1f}%"
            )
    else:
        lines.append("- (none)")

    lines.extend(
        [
            "",
            "## Matrix Summary",
            f"- Found: `{m.found}`",
            f"- Summary path: `{m.summary_path}`",
            f"- Signals/Entries/Exits: `{m.signals}/{m.entries}/{m.exits}`",
            f"- Fill rate: `{m.fill_rate:.2f}%`",
            f"- Blocked total: `{m.blocked_total}`",
            f"- Wide spread blocks: `{m.blocks_wide_spread}` ({m.spread_block_ratio:.2f}%)",
            f"- Abnormal terminations: `{m.abnormal_termination_count}`",
            f"- Unmatched entries: `{m.unmatched_entries}`",
            f"- Top profile: `{m.top_profile}` (score={m.top_profile_score})",
            "",
            "## Redis State",
            f"- State: `{r.state}`",
            f"- Open positions count: `{r.open_positions_count}`",
            f"- Open position entry days: `{r.open_position_entry_days}`",
            f"- Signals list size: `{r.signals_count}`",
            f"- Trades list size: `{r.trades_count}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    report_date = _resolve_report_date(args.date)
    database = args.database or os.getenv("CLICKHOUSE_FUTURES_DATABASE", "kospi")

    trade_rows = _fetch_trade_rows(database=database, report_date=report_date)
    trade_summary = _compute_trade_summary(trade_rows)
    matrix_summary = _load_matrix_summary(args.run_dir)
    redis_summary = _load_redis_summary()
    issues = _derive_issues(trade_summary, matrix_summary, redis_summary)
    notification_sent = False

    report = HealthReport(
        report_date=report_date.isoformat(),
        generated_at=datetime.now(KST).isoformat(),
        issues=issues,
        notification_sent=notification_sent,
        trade_summary=trade_summary,
        matrix_summary=matrix_summary,
        redis_summary=redis_summary,
    )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"futures_session_health_{stamp}.json"
    md_path = out_dir / f"futures_session_health_{stamp}.md"

    if args.notify_on_issues and issues:
        notification_sent = asyncio.run(_send_issue_notification(report, md_path))
        report.notification_sent = notification_sent

    json_payload = asdict(report)
    json_path.write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(_to_markdown(report), encoding="utf-8")

    print(f"Saved JSON: {json_path}")
    print(f"Saved MD: {md_path}")
    if issues:
        print("Detected issues:")
        for item in issues:
            print(f"- {item}")
        if args.notify_on_issues:
            print(
                "Telegram notification: "
                + ("sent" if report.notification_sent else "failed or skipped")
            )
    else:
        print("No critical issues detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
