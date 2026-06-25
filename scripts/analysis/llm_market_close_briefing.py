#!/usr/bin/env python3
"""
Market Close Summary Briefing (15:30)

Reads trading state from Redis (published by the stock & futures orchestrators)
and sends a comprehensive end-of-day report via Telegram.

NOTE: futures runs Setup A/C (gap-reversion / event-reaction), NOT RL — RL was
removed 2026-06-03. The report section is labelled "선물 트레이딩 성과" accordingly.

Cron: 30 15 * * 1-5
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.analysis.llm_job_common import configure_logger

logger = configure_logger(__name__)


def _fmt_pnl(pnl: float) -> str:
    sign = "+" if pnl >= 0 else ""
    return f"{sign}{pnl:,.0f}"


def _fmt_pct(pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def _pnl_emoji(pnl: float) -> str:
    return "\U0001f4c8" if pnl >= 0 else "\U0001f4c9"


def _is_today(iso_str: str | None) -> bool:
    """Check if an ISO datetime string is from today."""
    if not iso_str:
        return False
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.date() == datetime.now().date()
    except (ValueError, TypeError):
        return False


def capture_volume_surge_predictions() -> int:
    """Capture the day's volume-surge flags into the scorecard ledger.

    Reads ``system:volume_surge:latest`` (Redis DB1, published by the screener)
    and, when present and non-empty, captures ONLY the ``volume_surge`` facet so
    the 16:35 post-close scorer can score flag-to-close returns. Best-effort and
    observation-only: returns the number of predictions captured (0 on any
    missing feed / error). Never raises.
    """
    try:
        import json as _json

        import shared.llm_scorecard.facets  # noqa: F401 — populates FACET_REGISTRY
        from shared.llm_scorecard.config import ScorecardConfig
        from shared.llm_scorecard.facets.base import CaptureContext
        from shared.llm_scorecard.recorder import capture_predictions
        from shared.storage.config import StorageConfig
        from shared.storage.runtime_ledger import SQLiteRuntimeLedger
        from shared.streaming.trading_state import _get_redis

        redis = _get_redis()
        raw = redis.get("system:volume_surge:latest")
        if not raw:
            return 0
        payload = _json.loads(raw)
        surges = payload.get("surges") if isinstance(payload, dict) else None
        if not isinstance(surges, list) or not surges:
            return 0

        now = datetime.now()
        ctx = CaptureContext(
            date_kst=now.strftime("%Y-%m-%d"),
            now_kst=now,
            market_context=None,
            screener={"volume_surge": surges},
            redis=redis,
        )
        cfg = ScorecardConfig.from_yaml()
        storage = StorageConfig.load_or_default()
        ledger = SQLiteRuntimeLedger(storage.runtime_storage.sqlite)
        n = capture_predictions(ctx, cfg, ledger, only_facets={"volume_surge"})
        logger.info("Scorecard: captured %d volume_surge predictions", n)
        return n
    except Exception as exc:  # noqa: BLE001
        logger.warning("Volume-surge scorecard capture failed (non-fatal): %s", exc)
        return 0


def _build_stock_report(reader) -> str | None:
    """Build stock trading section of the report."""
    status = reader.get_status()
    if not status:
        return None

    config = status.get("config", {})
    pos_summary = status.get("positions", {})
    regime = status.get("regime", "N/A")

    capital = config.get("capital", 0)
    paper = config.get("paper_trading", True)
    mode_str = "Paper" if paper else "Real"

    open_count = pos_summary.get("open_positions", 0)
    unrealized_pnl = float(pos_summary.get("unrealized_pnl", 0))
    closed_pnl = float(pos_summary.get("closed_pnl", 0))
    closed_count = pos_summary.get("closed_count", 0)
    closed_win_rate = float(pos_summary.get("closed_win_rate", 0))
    total_trades = closed_count + open_count

    combined_pnl = closed_pnl + unrealized_pnl
    combined_pct = (combined_pnl / capital * 100) if capital > 0 else 0

    lines = [
        f"<b>\U0001f4ca \uc8fc\uc2dd \ud2b8\ub808\uc774\ub529 \uc131\uacfc</b>",
        f"\u2022 \uc6b4\uc6a9 \uc790\ubcf8: {capital / 1e8:.1f}\uc5b5\uc6d0 ({mode_str})",
        f"\u2022 \uc2dc\uc7a5 \uad6d\uba74: {regime}",
        f"\u2022 \ucd1d \uac70\ub798: {total_trades}\uac74 (\uccad\uc0b0 {closed_count}, \ubcf4\uc720 {open_count})",
        f"\u2022 \uc2e4\ud604 \uc190\uc775: {_pnl_emoji(closed_pnl)} {_fmt_pnl(closed_pnl)}\uc6d0 (\uc2b9\ub960 {closed_win_rate:.1f}%)",
        f"\u2022 \ubbf8\uc2e4\ud604 \uc190\uc775: {_pnl_emoji(unrealized_pnl)} {_fmt_pnl(unrealized_pnl)}\uc6d0",
        f"\u2022 <b>\uc885\ud569 \uc190\uc775: {_pnl_emoji(combined_pnl)} {_fmt_pnl(combined_pnl)}\uc6d0 ({_fmt_pct(combined_pct)})</b>",
    ]

    # Open positions detail
    positions = reader.get_positions()
    if positions:
        lines.append("")
        lines.append(
            f"<b>\U0001f4c8 \ubcf4\uc720 \ud3ec\uc9c0\uc158 ({len(positions)}\uac74)</b>"
        )
        for i, pos in enumerate(positions, 1):
            name = pos.get("name") or pos.get("code", "?")
            code = pos.get("code", "")
            entry_p = float(pos.get("entry_price", 0))
            cur_p = float(pos.get("current_price", 0))
            u_pnl = float(pos.get("unrealized_pnl", 0))
            pnl_pct = float(pos.get("pnl_pct", 0))
            pstate = pos.get("state", "")
            strategy = pos.get("strategy", "")
            lines.append(f"  {i}. {name}({code}) | {entry_p:,.0f}\u2192{cur_p:,.0f}")
            lines.append(
                f"     {_fmt_pnl(u_pnl)}\uc6d0 ({_fmt_pct(pnl_pct)}) | {pstate} | {strategy}"
            )

    # Today's closed trades
    trades = reader.get_trades(count=100)
    today_trades = [t for t in trades if _is_today(t.get("exit_time"))]
    if today_trades:
        lines.append("")
        lines.append(
            f"<b>\U0001f4c9 \uccad\uc0b0 \uac70\ub798 ({len(today_trades)}\uac74)</b>"
        )
        for i, t in enumerate(today_trades, 1):
            name = t.get("name") or t.get("symbol", "?")
            symbol = t.get("symbol", "")
            entry_p = float(t.get("entry_price", 0))
            exit_p = float(t.get("exit_price", 0))
            pnl = float(t.get("pnl", 0))
            pnl_pct = float(t.get("pnl_pct", 0))
            strategy = t.get("strategy", "")
            lines.append(f"  {i}. {name}({symbol}) | {entry_p:,.0f}\u2192{exit_p:,.0f}")
            lines.append(
                f"     {_fmt_pnl(pnl)}\uc6d0 ({_fmt_pct(pnl_pct)}) | {strategy}"
            )

    # Strategy breakdown (by_strategy is {name: count})
    by_strategy = pos_summary.get("by_strategy", {})
    if by_strategy and isinstance(by_strategy, dict):
        lines.append("")
        lines.append("<b>\U0001f3af \uc804\ub7b5\ubcc4 \ubcf4\uc720</b>")
        for strat, val in by_strategy.items():
            cnt = (
                val
                if isinstance(val, int)
                else val.get("count", 0) if isinstance(val, dict) else 0
            )
            lines.append(f"  \u2022 {strat}: {cnt}\uac74")

    return "\n".join(lines)


def _build_futures_report(reader) -> str | None:
    """Build the futures trading section (Setup A/C orchestrator — not RL)."""
    status = reader.get_status()
    if not status:
        return None

    stats = status.get("stats", {})
    pos_summary = status.get("positions", {})
    state = status.get("state", "unknown")

    total_trades = stats.get("total_trades", 0)
    total_pnl = float(stats.get("total_pnl", 0))
    win_rate = float(stats.get("win_rate", 0))
    unrealized_pnl = float(pos_summary.get("unrealized_pnl", 0))
    combined_pnl = total_pnl + unrealized_pnl

    lines = [
        f"<b>\U0001f916 \uc120\ubb3c \ud2b8\ub808\uc774\ub529 \uc131\uacfc</b>",
        f"\u2022 \uc0c1\ud0dc: {state}",
        f"\u2022 \ucd1d \uac70\ub798: {total_trades}\uac74 (\uc2b9\ub960 {win_rate:.1f}%)",
        f"\u2022 \uc2e4\ud604 \uc190\uc775: {_pnl_emoji(total_pnl)} {_fmt_pnl(total_pnl)}\uc6d0",
        f"\u2022 \ubbf8\uc2e4\ud604: {_fmt_pnl(unrealized_pnl)}\uc6d0",
        f"\u2022 <b>\uc885\ud569: {_pnl_emoji(combined_pnl)} {_fmt_pnl(combined_pnl)}\uc6d0</b>",
    ]

    positions = reader.get_positions()
    if positions:
        for pos in positions:
            name = pos.get("name") or pos.get("code", "?")
            side = pos.get("side", "")
            entry_p = float(pos.get("entry_price", 0))
            cur_p = float(pos.get("current_price", 0))
            u_pnl = float(pos.get("unrealized_pnl", 0))
            lines.append(
                f"  \u2192 {name} {side} | {entry_p:,.0f}\u2192{cur_p:,.0f} | {_fmt_pnl(u_pnl)}\uc6d0"
            )

    return "\n".join(lines)


async def main():
    logger.info("Market Close Briefing Started")

    from shared.calendar import is_market_open_today

    if not is_market_open_today():
        logger.info("Market closed today. Skipping.")
        return

    # Best-effort scorecard capture of the day's volume-surge flags.
    # Independent of the briefing report content; no-op if the feed is empty.
    capture_volume_surge_predictions()

    from shared.notification import notifier_for_domain
    from shared.streaming.trading_state import TradingStateReader

    today = datetime.now().strftime("%Y-%m-%d (%a)")

    stock_reader = TradingStateReader("stock")
    futures_reader = TradingStateReader("futures")

    stock_section = _build_stock_report(stock_reader)
    futures_section = _build_futures_report(futures_reader)

    if not stock_section and not futures_section:
        logger.info("No trading data available. Skipping briefing.")
        return

    parts = [
        f"<b>\U0001f514 \uc7a5 \ub9c8\uac10 \uc885\ud569 \ub9ac\ud3ec\ud2b8</b>",
        "\u2501" * 20,
        f"\U0001f4c5 {today}",
        "",
    ]

    if stock_section:
        parts.append(stock_section)

    if futures_section:
        if stock_section:
            parts.append("")
            parts.append("\u2501" * 20)
            parts.append("")
        parts.append(futures_section)

    parts.append("")
    parts.append("\u2501" * 20)
    parts.append(
        "<i>\ub0b4\uc77c\ub3c4 \uc131\uacf5\uc801\uc778 \ud2b8\ub808\uc774\ub529 \ub418\uc138\uc694!</i>"
    )

    message = "\n".join(parts)

    notifier = notifier_for_domain("briefing")
    if notifier is None:
        logger.warning(
            "Briefing Telegram channel not configured; market close briefing skipped"
        )
        return
    await notifier.send_message(message, is_critical=True)
    logger.info("Market close briefing sent")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        raise
