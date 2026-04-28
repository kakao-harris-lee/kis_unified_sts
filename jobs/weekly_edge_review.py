"""Weekly Edge Review — Phase 4 Task 15.

Cron entry point: ``scripts/cron/weekly_edge_review.sh`` runs ``main()``
every Monday at 05:00 KST. Aggregates the past 7 days from
``kospi.signals_all`` × ``kospi.order_fills`` per Setup A/C, classifies
alerts (negative EV, high slippage, two-week zero-trades), and posts a
Telegram summary to the futures briefing channel.

Spec source: docs/plans/2026-04-20-futures-paradigm-phase4-execution.md §5.3
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Spec §5.3 — realized PnL needs (exit_price - entry_price) per signal.
# Self-JOIN on signal_id between the entry fill (trade_role='entry') and the
# exit fill (stop_loss/take_profit/force_close). Direction taken from
# kospi.signals_all so the sign is the entry direction, not the closing side.
_QUERY_CURRENT_WEEK = """
WITH
    entries AS (
        SELECT signal_id, filled_price AS entry_price, quantity
        FROM kospi.order_fills
        WHERE trade_role = 'entry'
          AND filled_at >= now() - INTERVAL 8 DAY
    ),
    exits AS (
        SELECT signal_id, filled_price AS exit_price, slippage_ticks
        FROM kospi.order_fills
        WHERE trade_role IN ('stop_loss', 'take_profit', 'force_close')
          AND filled_at >= now() - INTERVAL 7 DAY
    )
SELECT
    s.setup_type,
    count() AS n,
    avg(x.slippage_ticks) AS avg_slip,
    quantile(0.95)(x.slippage_ticks) AS p95_slip,
    sum(
        (x.exit_price - e.entry_price) * e.quantity
        * if(s.direction = 'long', 1, -1)
    ) AS pnl_krw,
    avg(if((x.exit_price - e.entry_price) * if(s.direction = 'long', 1, -1) > 0, 1, 0)) AS win_rate
FROM kospi.signals_all s
INNER JOIN entries e ON s.signal_id = e.signal_id
INNER JOIN exits x ON s.signal_id = x.signal_id
WHERE s.generated_at >= now() - INTERVAL 7 DAY
GROUP BY s.setup_type
"""

# Prev-week: count only filled signals (matching CURRENT_WEEK semantics) so
# the no_trades_2w alert compares like-for-like. Returns one row per setup
# that had >= 1 fill last week; setups with zero fills do NOT appear here,
# which is what the alert wants — it's checking for n=0 in BOTH lists.
_QUERY_PREV_WEEK = """
SELECT
    s.setup_type,
    count() AS n
FROM kospi.signals_all s
INNER JOIN kospi.order_fills o ON s.signal_id = o.signal_id
WHERE s.generated_at >= now() - INTERVAL 14 DAY
  AND s.generated_at < now() - INTERVAL 7 DAY
  AND o.trade_role = 'entry'
GROUP BY s.setup_type
"""

# Setups expected in production. Used to materialise n=0 rows when an
# INNER-JOIN-based aggregate skips the row entirely. Phase 4 spec §5.3
# alert "Setup A/C 중 하나가 2주 연속 trades = 0" requires the comparison.
_KNOWN_SETUPS = ("A_gap_reversion", "C_event_reaction")


@dataclass(frozen=True)
class EdgeRow:
    setup_type: str
    n: int
    avg_slip: float
    p95_slip: float
    pnl_krw: float
    win_rate: float


@dataclass(frozen=True)
class Alert:
    kind: str
    setup_type: str
    message: str


def _materialise_rows(query_result: list) -> list[EdgeRow]:
    """Convert raw query rows to EdgeRow + emit n=0 rows for setups missing
    from the INNER-JOIN aggregate. Without this, ``no_trades_2w`` could not
    fire because the SQL would silently drop zero-fill setups.
    """
    seen: set[str] = set()
    rows: list[EdgeRow] = []
    for r in query_result:
        rows.append(
            EdgeRow(
                setup_type=str(r[0]),
                n=int(r[1]),
                avg_slip=float(r[2]) if r[2] is not None else 0.0,
                p95_slip=float(r[3]) if r[3] is not None else 0.0,
                pnl_krw=float(r[4]) if r[4] is not None else 0.0,
                win_rate=float(r[5]) if r[5] is not None else 0.0,
            )
        )
        seen.add(str(r[0]))
    for setup in _KNOWN_SETUPS:
        if setup not in seen:
            rows.append(
                EdgeRow(
                    setup_type=setup,
                    n=0,
                    avg_slip=0.0,
                    p95_slip=0.0,
                    pnl_krw=0.0,
                    win_rate=0.0,
                )
            )
    return rows


def classify_alerts(
    rows: list[EdgeRow], *, prev_week_rows: list[EdgeRow]
) -> list[Alert]:
    """Per spec §5.3 alert thresholds:
    - Negative EV (pnl_krw < 0)
    - Average slippage > 0.5 tick
    - Two consecutive weeks with n=0 for the same setup
    """
    prev_n = {r.setup_type: r.n for r in prev_week_rows}
    alerts: list[Alert] = []
    for row in rows:
        if row.pnl_krw < 0:
            alerts.append(
                Alert(
                    kind="negative_ev",
                    setup_type=row.setup_type,
                    message=(
                        f"{row.setup_type}: PnL {row.pnl_krw:,.0f} KRW over "
                        f"n={row.n} trades"
                    ),
                )
            )
        if row.avg_slip > 0.5:
            alerts.append(
                Alert(
                    kind="slippage",
                    setup_type=row.setup_type,
                    message=(
                        f"{row.setup_type}: avg slippage {row.avg_slip:.2f} ticks "
                        f"(p95 {row.p95_slip:.2f}) — exceeds 0.5 tick threshold"
                    ),
                )
            )
        if row.n == 0 and prev_n.get(row.setup_type, -1) == 0:
            alerts.append(
                Alert(
                    kind="no_trades_2w",
                    setup_type=row.setup_type,
                    message=(
                        f"{row.setup_type}: zero trades for two consecutive weeks"
                    ),
                )
            )
    return alerts


def format_telegram_message(rows: list[EdgeRow], *, alerts: list[Alert]) -> str:
    """Plain-text Telegram body (no Markdown — keeps the message robust to
    future formatting bugs in the bot library)."""
    lines = ["Weekly Edge Review (past 7 days)\n"]
    for row in rows:
        lines.append(
            f"  {row.setup_type}: n={row.n} avg_slip={row.avg_slip:.2f} "
            f"p95={row.p95_slip:.2f} pnl={row.pnl_krw:,.0f} KRW "
            f"win_rate={row.win_rate:.1%}"
        )
    if alerts:
        lines.append("\nALERTS:")
        for a in alerts:
            lines.append(f"  [{a.kind}] {a.message}")
    return "\n".join(lines)


class WeeklyEdgeReviewJob:
    def __init__(
        self,
        *,
        ch_client: Any,
        telegram_client: Any,
    ) -> None:
        self.ch = ch_client
        self.telegram = telegram_client

    async def run(self) -> None:
        try:
            current = await self.ch.fetch(_QUERY_CURRENT_WEEK)
        except Exception:
            logger.exception("weekly_edge_review: current-week query failed")
            return
        try:
            prev = await self.ch.fetch(_QUERY_PREV_WEEK)
        except Exception:
            logger.exception("weekly_edge_review: prev-week query failed")
            prev = []

        # Bootstrap short-circuit: when BOTH weeks are empty (no signals_all
        # data ever ingested), suppress the report entirely. Once the system
        # produces signals, every week reports — including weeks with n=0
        # (so the no_trades_2w alert can fire as the spec requires).
        if not current and not prev:
            logger.info("weekly_edge_review: no data either week — skipping telegram")
            return

        rows = _materialise_rows(current)
        # prev returns (setup_type, n) tuples — only the count matters.
        prev_rows = [
            EdgeRow(
                setup_type=str(r[0]),
                n=int(r[1]),
                avg_slip=0.0,
                p95_slip=0.0,
                pnl_krw=0.0,
                win_rate=0.0,
            )
            for r in prev
        ]

        alerts = classify_alerts(rows, prev_week_rows=prev_rows)
        msg = format_telegram_message(rows, alerts=alerts)
        # 05:00 KST cron is outside TelegramNotifier's default 08:30–15:40
        # active window. is_critical=True bypasses that gate so the weekly
        # summary always delivers (per spec §5.3 deliverable).
        try:
            await self.telegram.send_message(msg, is_critical=True)
        except Exception:
            logger.exception("weekly_edge_review: telegram send failed")


async def _build_and_run() -> int:
    """Wire the job from environment + run once. Cron fires this daily at
    Mon 05:00 KST per ``scripts/cron/weekly_edge_review.sh``."""
    import os

    from shared.db.client import AsyncClickHouseClient
    from shared.db.config import ClickHouseConfig
    from shared.notification.telegram import TelegramNotifier

    ch_config = ClickHouseConfig.from_env(database="kospi")
    ch_client = AsyncClickHouseClient(ch_config)
    await ch_client.connect()

    telegram = TelegramNotifier(
        bot_token=os.environ["TELEGRAM_FUTURES_BOT_TOKEN"],
        chat_id=os.environ["TELEGRAM_FUTURES_CHAT_ID"],
    )

    job = WeeklyEdgeReviewJob(ch_client=ch_client, telegram_client=telegram)
    try:
        await job.run()
    finally:
        await ch_client.close()
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
