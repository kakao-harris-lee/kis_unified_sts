#!/usr/bin/env python3
"""Weekly counterfactual digest for RegimeGate (spec 2026-05-22 P2-③ T9).

Queries regime_gate_decisions for the last 7 days, computes per-strategy
blocked-vs-allowed cohorts, estimates each cohort's mean realized P&L
over a 15-min look-forward window using kospi200f_1m bars, and posts
a Telegram digest. Mirrors scripts/analysis/counterfactual_weekly_report.py
CLI/Telegram structure.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from shared.strategy.gates.adapter_helper import (  # noqa: E402
    _futures_clickhouse_database,
    futures_clickhouse_client,
)

logger = logging.getLogger(__name__)


def _resolve_window() -> tuple[dt.date, dt.date]:
    today = dt.date.today()
    last_sun = today - dt.timedelta(days=today.weekday() + 1)
    last_mon = last_sun - dt.timedelta(days=6)
    return last_mon, last_sun


def fetch_decisions(start: dt.date, end: dt.date) -> list[tuple]:
    """Return [(ts, strategy, signal_direction, allow), ...] for the window."""
    db = _futures_clickhouse_database()
    client = futures_clickhouse_client()
    if client is None:
        raise RuntimeError("futures_clickhouse_client unavailable")
    cli = client.get_sync_client()
    rows = cli.execute(
        f"SELECT ts, strategy, signal_direction, allow FROM {db}.regime_gate_decisions "
        "WHERE ts >= %(s)s AND ts < %(e)s ORDER BY ts",
        {"s": dt.datetime.combine(start, dt.time.min),
         "e": dt.datetime.combine(end + dt.timedelta(days=1), dt.time.min)},
    )
    return [(r[0], r[1], r[2], int(r[3])) for r in rows]


def group_decisions(decisions: list[tuple]) -> dict[tuple[str, bool], list[tuple]]:
    """Group by (strategy, allow_bool)."""
    grouped: dict[tuple[str, bool], list[tuple]] = defaultdict(list)
    for d in decisions:
        _ts, strategy, _direction, allow = d
        grouped[(strategy, bool(allow))].append(d)
    return grouped


def estimate_cohort_pnl_pct(
    cohort: list[tuple], lookback_min: int, candles_df,
) -> float:
    """Estimate mean realized P&L % over the lookforward window."""
    if not cohort or candles_df is None or len(candles_df) == 0:
        return 0.0
    pnls: list[float] = []
    for ts, _strategy, direction, _allow in cohort:
        ts_n = ts.replace(tzinfo=None) if getattr(ts, "tzinfo", None) else ts
        future_ts = ts_n + dt.timedelta(minutes=lookback_min)
        try:
            row_now = candles_df.loc[candles_df.index <= ts_n].iloc[-1]
            row_future = candles_df.loc[candles_df.index <= future_ts].iloc[-1]
            ret = (row_future["close"] - row_now["close"]) / row_now["close"]
            pnls.append(ret * (1.0 if direction == "long" else -1.0) * 100)
        except (IndexError, KeyError):
            continue
    return sum(pnls) / len(pnls) if pnls else 0.0


def load_candles(start: dt.date, end: dt.date):
    """Load kospi200f_1m candles for the window (uses A01603 clean series)."""
    import pandas as pd

    db = _futures_clickhouse_database()
    client = futures_clickhouse_client()
    if client is None:
        return None
    cli = client.get_sync_client()
    rows = cli.execute(
        f"SELECT datetime, close FROM {db}.kospi200f_1m "
        "WHERE code = 'A01603' AND datetime >= %(s)s AND datetime < %(e)s "
        "ORDER BY datetime",
        {"s": dt.datetime.combine(start, dt.time.min),
         "e": dt.datetime.combine(end + dt.timedelta(days=1), dt.time.min)},
    )
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["datetime", "close"])
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True).dt.tz_localize(None)
    df = df.set_index("datetime")
    return df


def build_summary(decisions, candles_df, lookback_min: int) -> dict:
    grouped = group_decisions(decisions)
    summary: dict[str, dict] = {}
    strategies = sorted({d[1] for d in decisions})
    for strat in strategies:
        blocked = grouped.get((strat, False), [])
        allowed = grouped.get((strat, True), [])
        summary[strat] = {
            "blocked_count": len(blocked),
            "blocked_mean_pnl_pct": estimate_cohort_pnl_pct(
                blocked, lookback_min, candles_df),
            "allowed_count": len(allowed),
            "allowed_mean_pnl_pct": estimate_cohort_pnl_pct(
                allowed, lookback_min, candles_df),
        }
    return summary


def format_telegram_digest(
    summary: dict, start: dt.date, end: dt.date,
) -> str:
    lines = [
        f"📊 RegimeGate weekly counterfactual ({start} → {end})",
        "",
    ]
    if not summary:
        lines.append("  (no decisions logged this week)")
        return "\n".join(lines)
    for strat, s in summary.items():
        if s["blocked_count"] + s["allowed_count"] == 0:
            lines.append(f"  {strat}: 0 / 0 signals (no decisions logged this week)")
            continue
        delta = s["allowed_mean_pnl_pct"] - s["blocked_mean_pnl_pct"]
        lines.append(
            f"  {strat}:\n"
            f"    blocked={s['blocked_count']:>3} mean_pnl={s['blocked_mean_pnl_pct']:+.3f}%\n"
            f"    allowed={s['allowed_count']:>3} mean_pnl={s['allowed_mean_pnl_pct']:+.3f}%\n"
            f"    Δ(allowed - blocked) = {delta:+.3f}%   "
            f"{'(gate adds value ✓)' if delta > 0 else '(gate neutral/negative ⚠)'}"
        )
    return "\n".join(lines)


async def send_telegram(message: str) -> None:
    """Best-effort futures-channel post (mirrors counterfactual_weekly_report)."""
    try:
        from shared.notification.telegram import TelegramNotifier
        bot_token = os.environ.get(
            "TELEGRAM_BRIEFING_BOT_TOKEN",
            os.environ.get("TELEGRAM_FUTURES_BOT_TOKEN", ""))
        chat_id = os.environ.get(
            "TELEGRAM_BRIEFING_CHAT_ID",
            os.environ.get("TELEGRAM_FUTURES_CHAT_ID", ""))
        if not bot_token or not chat_id:
            logger.warning("telegram credentials missing — skipping")
            return
        await TelegramNotifier(bot_token=bot_token, chat_id=chat_id).send_message(
            message, is_critical=False)
    except Exception:
        logger.exception("telegram send failed")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start-date", type=lambda s: dt.date.fromisoformat(s), default=None)
    ap.add_argument("--end-date", type=lambda s: dt.date.fromisoformat(s), default=None)
    ap.add_argument("--lookback-min", type=int, default=15)
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    a = ap.parse_args(argv)

    logging.basicConfig(level=getattr(logging, a.log_level),
                        format="%(asctime)s %(levelname)s %(message)s")

    start, end = (a.start_date, a.end_date) if (a.start_date and a.end_date) else _resolve_window()
    logger.info("regime_gate counterfactual window: %s → %s", start, end)

    decisions = fetch_decisions(start, end)
    candles_df = load_candles(start, end)
    summary = build_summary(decisions, candles_df, a.lookback_min)
    message = format_telegram_digest(summary, start, end)

    print(message)
    if not a.no_telegram:
        asyncio.run(send_telegram(message))
    return 0


if __name__ == "__main__":
    sys.exit(main())
