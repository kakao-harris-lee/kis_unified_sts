#!/usr/bin/env python3
"""Counterfactual Weekly Report — §10.2 cron wrapper.

Runs ``scripts/analysis/setup_vs_rl_shadow_counterfactual.py`` over the past
ISO week (Mon-Sun) and posts a Telegram summary to the briefing channel.
Persists the full JSON report under
``reports/counterfactual/YYYY-WNN.json`` for archival.

Designed for cron execution (Mon 07:00 KST — see
``scripts/cron/counterfactual_weekly.sh``).  Idempotent:
- The same window can be re-run safely; the script is read-only against
  ClickHouse and overwrites the JSON archive of that ISO week.
- Telegram delivery failure does not fail the job (the JSON archive is
  always written first).

This wrapper exists so the existing CLI tool (PR #178) can be scheduled
without polluting its argparse interface with cron-specific concerns
(Telegram, archive paths, ISO-week resolution).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.analysis.setup_vs_rl_shadow_counterfactual import (  # noqa: E402
    CounterfactualReport,
    _report_to_dict,
    run_analysis,
)

logger = logging.getLogger(__name__)

_REPORTS_DIR = _REPO_ROOT / "reports" / "counterfactual"
_DEFAULT_SYMBOL = "101S6000"


def _resolve_window(today: date | None = None) -> tuple[date, date]:
    """Return the (Mon, Sun) window of the previous ISO week.

    Cron is expected to fire on Mon 07:00 KST → previous week is fully closed.
    Operators running ad-hoc on Wed/Thu still get the most recently closed
    week.

    Args:
        today: Override for the reference date (test injection).

    Returns:
        ``(start, end)`` where both are inclusive dates and end is the Sunday
        immediately before ``today``.
    """
    today = today or datetime.now(UTC).date()
    end_of_prev_week = today - timedelta(days=today.weekday() + 1)
    start_of_prev_week = end_of_prev_week - timedelta(days=6)
    return start_of_prev_week, end_of_prev_week


def _archive_path(start_date: date) -> Path:
    """Path for the week's archived JSON report."""
    iso_year, iso_week, _ = start_date.isocalendar()
    return _REPORTS_DIR / f"{iso_year}-W{iso_week:02d}.json"


def _format_telegram_message(report: CounterfactualReport) -> str:
    """Render a concise Telegram summary from the full report.

    Keep under Telegram's 4096-char limit; show: window, totals, agreement
    matrix, phase 4 gate progress, top 3 disagreement-cost days.
    """
    rl = report.rl_shadow
    setup = report.setup_actual
    am = report.agreement
    gate = report.phase4_gate

    lines: list[str] = []
    lines.append("📊 *Counterfactual Weekly Report*")
    lines.append(f"`{report.start_date} → {report.end_date}` (`{report.symbol}`)")
    lines.append("")
    lines.append("*Volume / PnL*")
    lines.append(
        f"• Setup A/C executed: `{setup.trade_count}` trades, "
        f"PnL `{setup.gross_pnl_krw:,.0f}` KRW (WR `{setup.win_rate:.1%}`)"
    )
    lines.append(
        f"• RL shadow virtual:  `{rl.trade_count}` trades, "
        f"PnL `{rl.gross_pnl_krw:,.0f}` KRW (WR `{rl.win_rate:.1%}`)"
    )
    if rl.eod_estimated_count:
        lines.append(
            f"  ↳ RL EOD-estimated exits: `{rl.eod_estimated_count}` "
            f"({100.0 * rl.eod_estimated_count / rl.trade_count:.0f}%)"
        )
    if setup.eod_estimated_count:
        lines.append(
            f"  ↳ Setup EOD-estimated exits: `{setup.eod_estimated_count}` "
            f"({100.0 * setup.eod_estimated_count / setup.trade_count:.0f}%)"
        )
    lines.append("")
    lines.append("*Directional agreement (RL × Setup, both fired same bar)*")
    lines.append("```")
    lines.append("           Setup_LONG  Setup_SHORT")
    lines.append(f"RL_LONG    {am.long_long:>10d}  {am.long_short:>11d}")
    lines.append(f"RL_SHORT   {am.short_long:>10d}  {am.short_short:>11d}")
    lines.append("```")
    if am.total:
        lines.append(
            f"Agreement: `{am.agreement_count}/{am.total}` "
            f"(`{am.agreement_pct:.0f}%`)"
        )
    else:
        lines.append("Agreement: no co-occurring signals this window.")
    lines.append("")

    if report.per_day:
        sorted_days = sorted(
            report.per_day, key=lambda d: abs(d.delta_krw), reverse=True
        )
        lines.append("*Top 3 disagreement days (|RL − Setup| KRW)*")
        for d in sorted_days[:3]:
            lines.append(
                f"• `{d.date}`: Δ=`{d.delta_krw:+,.0f}` "
                f"(Setup=`{d.setup_pnl_krw:,.0f}` RL=`{d.rl_pnl_krw:,.0f}`)"
            )
        lines.append("")

    lines.append("*Phase 4 gate progress (this window)*")
    lines.append(
        f"• Setup executed: `{gate.setup_executed_trades}` / "
        f"{gate.setup_target} {'✅' if gate.setup_gate_met else '⏳'}"
    )
    lines.append(
        f"• RL shadow:      `{gate.rl_shadow_count}` / "
        f"{gate.rl_shadow_target} {'✅' if gate.rl_shadow_gate_met else '⏳'}"
    )

    return "\n".join(lines)


def _write_archive(report: CounterfactualReport, path: Path) -> None:
    """Persist the full report as JSON for later analysis."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _report_to_dict(report)
    payload["archived_at"] = datetime.now(UTC).isoformat()
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("archived counterfactual report → %s", path)


async def _send_telegram(message: str) -> None:
    """Best-effort Telegram delivery (briefing channel)."""
    try:
        from shared.notification.telegram import TelegramNotifier

        bot_token = os.environ.get(
            "TELEGRAM_BRIEFING_BOT_TOKEN",
            os.environ.get("TELEGRAM_FUTURES_BOT_TOKEN", ""),
        )
        chat_id = os.environ.get(
            "TELEGRAM_BRIEFING_CHAT_ID",
            os.environ.get("TELEGRAM_FUTURES_CHAT_ID", ""),
        )
        if not bot_token or not chat_id:
            logger.warning("telegram credentials missing — skipping notification")
            return
        notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
        await notifier.send_message(message, is_critical=False)
        logger.info("telegram report delivered")
    except Exception:
        logger.exception("telegram send failed — report archived to disk only")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Counterfactual weekly report — schedules the §10.2 analysis "
            "script and posts a Telegram summary."
        )
    )
    parser.add_argument(
        "--symbol",
        default=_DEFAULT_SYMBOL,
        help=f"Futures symbol (default: {_DEFAULT_SYMBOL}).",
    )
    parser.add_argument(
        "--start-date",
        type=lambda s: date.fromisoformat(s),
        default=None,
        help="Override start date (YYYY-MM-DD). Default: previous ISO week Mon.",
    )
    parser.add_argument(
        "--end-date",
        type=lambda s: date.fromisoformat(s),
        default=None,
        help="Override end date (YYYY-MM-DD). Default: previous ISO week Sun.",
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="Skip Telegram notification (archive only).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.start_date and args.end_date:
        start, end = args.start_date, args.end_date
    else:
        start, end = _resolve_window()
    logger.info("counterfactual window: %s → %s (%s)", start, end, args.symbol)

    try:
        report = run_analysis(
            start_date=start,
            end_date=end,
            symbol=args.symbol,
            commission_bps=None,  # config fallback
            slippage_ticks=None,
        )
    except ValueError as e:
        logger.error("run_analysis rejected window: %s", e)
        return 2
    except Exception:
        logger.exception("run_analysis crashed")
        return 1

    archive_path = _archive_path(start)
    _write_archive(report, archive_path)

    if args.no_telegram:
        logger.info("--no-telegram set; skipping notification")
        return 0

    message = _format_telegram_message(report)
    asyncio.run(_send_telegram(message))
    return 0


if __name__ == "__main__":
    sys.exit(main())
