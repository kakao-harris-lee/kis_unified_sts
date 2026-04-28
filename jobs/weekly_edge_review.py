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
from typing import Any, ClassVar

from pydantic import Field

from shared.config.base import ServiceConfigBase

logger = logging.getLogger(__name__)


class WeeklyEdgeReviewConfig(ServiceConfigBase):
    """Alert thresholds + window sizes for the weekly edge review job.

    Loaded from ``config/weekly_edge_review.yaml`` under the
    ``weekly_edge_review`` section. Closes the PR #135 review finding that
    operational thresholds (0.5 tick, 7-day window) were hardcoded.
    """

    _default_config_file: ClassVar[str] = "weekly_edge_review.yaml"
    _default_section: ClassVar[str] = "weekly_edge_review"

    current_window_days: int = Field(default=7, ge=1)
    prev_window_days: int = Field(default=14, ge=2)
    slippage_alert_ticks: float = Field(default=0.5, ge=0)
    known_setups: list[str] = Field(
        default_factory=lambda: ["A_gap_reversion", "C_event_reaction"]
    )


def _build_current_week_query(window_days: int) -> str:
    """Spec §5.3 — realized PnL = (exit_price - entry_price) per signal.

    Self-JOIN on signal_id between the entry fill and the exit fill. The
    ``window_days`` is interpolated rather than parameterised because
    aiochclient/CH does not accept bind parameters in INTERVAL clauses.
    Bounds-checked by ``WeeklyEdgeReviewConfig`` (``ge=1``) so injection is
    not a vector here.
    """
    entry_lookback_days = window_days + 1  # entries can fill up to a day before signal
    return f"""
    WITH
        entries AS (
            SELECT signal_id, filled_price AS entry_price, quantity
            FROM kospi.order_fills
            WHERE trade_role = 'entry'
              AND filled_at >= now() - INTERVAL {entry_lookback_days} DAY
        ),
        exits AS (
            SELECT signal_id, filled_price AS exit_price, slippage_ticks
            FROM kospi.order_fills
            WHERE trade_role IN ('stop_loss', 'take_profit', 'force_close')
              AND filled_at >= now() - INTERVAL {window_days} DAY
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
    WHERE s.generated_at >= now() - INTERVAL {window_days} DAY
    GROUP BY s.setup_type
    """


def _build_prev_week_query(prev_window_days: int, current_window_days: int) -> str:
    """Prev-week count of filled signals — INNER JOIN to entry fills so the
    semantics match :func:`_build_current_week_query`.
    """
    return f"""
    SELECT
        s.setup_type,
        count() AS n
    FROM kospi.signals_all s
    INNER JOIN kospi.order_fills o ON s.signal_id = o.signal_id
    WHERE s.generated_at >= now() - INTERVAL {prev_window_days} DAY
      AND s.generated_at < now() - INTERVAL {current_window_days} DAY
      AND o.trade_role = 'entry'
    GROUP BY s.setup_type
    """


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


def _materialise_rows(
    query_result: list,
    *,
    known_setups: list[str] | tuple[str, ...] = ("A_gap_reversion", "C_event_reaction"),
) -> list[EdgeRow]:
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
    for setup in known_setups:
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
    rows: list[EdgeRow],
    *,
    prev_week_rows: list[EdgeRow],
    slippage_alert_ticks: float = 0.5,
) -> list[Alert]:
    """Per spec §5.3 alert thresholds:
    - Negative EV (pnl_krw < 0)
    - Average slippage > slippage_alert_ticks (default 0.5 tick)
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
        if row.avg_slip > slippage_alert_ticks:
            alerts.append(
                Alert(
                    kind="slippage",
                    setup_type=row.setup_type,
                    message=(
                        f"{row.setup_type}: avg slippage {row.avg_slip:.2f} ticks "
                        f"(p95 {row.p95_slip:.2f}) — exceeds "
                        f"{slippage_alert_ticks:.2f} tick threshold"
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
        config: WeeklyEdgeReviewConfig | None = None,
    ) -> None:
        self.ch = ch_client
        self.telegram = telegram_client
        self.config = config or WeeklyEdgeReviewConfig()

    async def run(self) -> None:
        current_query = _build_current_week_query(self.config.current_window_days)
        prev_query = _build_prev_week_query(
            prev_window_days=self.config.prev_window_days,
            current_window_days=self.config.current_window_days,
        )
        try:
            current = await self.ch.fetch(current_query)
        except Exception:
            logger.exception("weekly_edge_review: current-week query failed")
            return
        try:
            prev = await self.ch.fetch(prev_query)
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

        rows = _materialise_rows(current, known_setups=self.config.known_setups)
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

        alerts = classify_alerts(
            rows,
            prev_week_rows=prev_rows,
            slippage_alert_ticks=self.config.slippage_alert_ticks,
        )
        msg = format_telegram_message(rows, alerts=alerts)
        # 05:00 KST cron is outside TelegramNotifier's default 08:30–15:40
        # active window. is_critical=True bypasses that gate so the weekly
        # summary always delivers (per spec §5.3 deliverable).
        try:
            await self.telegram.send_message(msg, is_critical=True)
        except Exception:
            logger.exception("weekly_edge_review: telegram send failed")


async def _build_and_run() -> int:
    """Wire the job from environment + run once. Cron fires this Mon 05:00 KST."""
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

    config = WeeklyEdgeReviewConfig.from_yaml()
    job = WeeklyEdgeReviewJob(
        ch_client=ch_client, telegram_client=telegram, config=config
    )
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
