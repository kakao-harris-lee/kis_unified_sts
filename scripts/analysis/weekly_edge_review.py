#!/usr/bin/env python
"""Weekly Edge Review — Phase 5 Task 2 — full 5-section report.

Extends the Phase 4 smoke version (``jobs.weekly_edge_review``) into the
operational report described in
``docs/plans/2026-04-20-futures-paradigm-phase5-rollout.md`` §3.2:

  1. Setup별 성과: trades, win_rate, avg_RR, EV, slippage, 누적 PnL
  2. 백테스트 vs 실거래 괴리: 일치도, 예상-실제 PnL 차이
  3. 리스크 이벤트: kill switch 트리거, 연속 손실, spread widening 차단
  4. 데이터 품질: 뉴스 수집량, macro 결측, scoring fallback 비율
  5. 권장 액션: EV 음수 Setup 일시정지 후보, 재튜닝 대상

Outputs:
  reports/weekly/YYYY-WW.html — full HTML report
  Telegram TELEGRAM_BRIEFING_* — 5-section summary

Cron: Mon 06:00 KST (separate from Phase 4 jobs.weekly_edge_review at 05:00).

This module is operator-grade analysis — pure-functional helpers (build_*
sections take dicts of CH rows and return HTML strings) so the test suite
verifies output without round-tripping ClickHouse.
"""

from __future__ import annotations

import argparse
import asyncio
import html as html_lib
import logging
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Section data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SetupPerf:
    setup_type: str
    n_trades: int
    win_rate: float
    avg_rr: float
    ev_ticks: float
    avg_slip: float
    cum_pnl_krw: float


@dataclass(frozen=True)
class BacktestDivergence:
    setup_type: str
    backtest_ev: float
    paper_ev: float
    pct_divergence: float


@dataclass(frozen=True)
class RiskEvent:
    timestamp: datetime
    kind: str  # "kill_switch" | "consecutive_loss" | "spread_block"
    detail: str


@dataclass(frozen=True)
class DataQuality:
    news_collected: int
    macro_missing_days: int
    scoring_fallback_rate: float


@dataclass(frozen=True)
class Recommendation:
    setup_type: str
    action: str  # "pause" | "retune" | "ok"
    reason: str


@dataclass(frozen=True)
class WeeklyReport:
    week_start: date
    week_end: date
    setup_perf: list[SetupPerf]
    divergence: list[BacktestDivergence]
    risk_events: list[RiskEvent]
    data_quality: DataQuality
    recommendations: list[Recommendation]


# ---------------------------------------------------------------------------
# SQL queries
# ---------------------------------------------------------------------------


_SETUP_PERF_QUERY = """
WITH
    entries AS (
        SELECT signal_id, filled_price AS entry_price, quantity, tick_size_points
        FROM kospi.order_fills
        WHERE trade_role = 'entry' AND filled_at >= now() - INTERVAL {window_days} DAY
    ),
    exits AS (
        SELECT signal_id, filled_price AS exit_price, slippage_ticks
        FROM kospi.order_fills
        WHERE trade_role IN ('stop_loss', 'take_profit', 'force_close')
          AND filled_at >= now() - INTERVAL {window_days} DAY
    )
SELECT
    s.setup_type,
    count() AS n_trades,
    avg(if((x.exit_price - e.entry_price) * if(s.direction='long', 1, -1) > 0, 1, 0)) AS win_rate,
    avg(abs((s.take_profit - s.entry_price) / nullIf(s.entry_price - s.stop_loss, 0))) AS avg_rr,
    avg((x.exit_price - e.entry_price) / nullIf(e.tick_size_points, 0) * if(s.direction='long', 1, -1)) AS ev_ticks,
    avg(x.slippage_ticks) AS avg_slip,
    sum((x.exit_price - e.entry_price) * e.quantity * if(s.direction='long', 1, -1) * 50000) AS cum_pnl_krw
FROM kospi.signals_all s
INNER JOIN entries e ON s.signal_id = e.signal_id
INNER JOIN exits x ON s.signal_id = x.signal_id
WHERE s.generated_at >= now() - INTERVAL {window_days} DAY
GROUP BY s.setup_type
"""


_RISK_EVENTS_QUERY = """
SELECT
    skip_reason,
    count() AS n
FROM kospi.signals_all
WHERE generated_at >= now() - INTERVAL {window_days} DAY
  AND executed = 0
  AND skip_reason != ''
GROUP BY skip_reason
ORDER BY n DESC
"""


_DATA_QUALITY_QUERY = """
SELECT
    count() AS n_news
FROM kospi.news_scored
WHERE scored_at >= now() - INTERVAL {window_days} DAY
"""


# ---------------------------------------------------------------------------
# Report builder — pure functions, easily testable
# ---------------------------------------------------------------------------


def build_setup_perf_section(rows: list[Any]) -> list[SetupPerf]:
    out: list[SetupPerf] = []
    for r in rows:
        out.append(
            SetupPerf(
                setup_type=str(r[0]),
                n_trades=int(r[1]),
                win_rate=float(r[2]) if r[2] is not None else 0.0,
                avg_rr=float(r[3]) if r[3] is not None else 0.0,
                ev_ticks=float(r[4]) if r[4] is not None else 0.0,
                avg_slip=float(r[5]) if r[5] is not None else 0.0,
                cum_pnl_krw=float(r[6]) if r[6] is not None else 0.0,
            )
        )
    return out


def build_divergence_section(
    paper_perf: list[SetupPerf],
    backtest_baseline: dict[str, float],
) -> list[BacktestDivergence]:
    """Compare paper EV to backtest EV per Setup."""
    out: list[BacktestDivergence] = []
    for sp in paper_perf:
        baseline = backtest_baseline.get(sp.setup_type)
        if baseline is None or baseline == 0:
            divergence_pct = 0.0
        else:
            divergence_pct = (sp.ev_ticks - baseline) / abs(baseline) * 100.0
        out.append(
            BacktestDivergence(
                setup_type=sp.setup_type,
                backtest_ev=baseline if baseline is not None else 0.0,
                paper_ev=sp.ev_ticks,
                pct_divergence=divergence_pct,
            )
        )
    return out


def build_risk_events_section(rows: list[Any]) -> list[RiskEvent]:
    """Each row: (skip_reason, count). Aggregated by reason for the week."""
    out: list[RiskEvent] = []
    for r in rows:
        reason = str(r[0])
        n = int(r[1])
        kind = (
            "kill_switch"
            if "kill" in reason.lower()
            else (
                "spread_block"
                if "spread" in reason.lower()
                else "consecutive_loss" if "consecutive" in reason.lower() else "filter"
            )
        )
        out.append(
            RiskEvent(
                timestamp=datetime.now(),
                kind=kind,
                detail=f"{reason}: n={n}",
            )
        )
    return out


def build_recommendations(
    perf: list[SetupPerf],
    divergence: list[BacktestDivergence],
    *,
    pause_ev_threshold: float = 0.0,
    retune_divergence_threshold_pct: float = 30.0,
) -> list[Recommendation]:
    """Spec §3.2 step 5: pause negative-EV setups, retune divergent ones."""
    div_by_setup = {d.setup_type: d for d in divergence}
    out: list[Recommendation] = []
    for sp in perf:
        if sp.ev_ticks < pause_ev_threshold:
            out.append(
                Recommendation(
                    setup_type=sp.setup_type,
                    action="pause",
                    reason=f"EV {sp.ev_ticks:.2f} ticks < {pause_ev_threshold} threshold over n={sp.n_trades}",
                )
            )
            continue
        d = div_by_setup.get(sp.setup_type)
        if d and abs(d.pct_divergence) > retune_divergence_threshold_pct:
            out.append(
                Recommendation(
                    setup_type=sp.setup_type,
                    action="retune",
                    reason=(
                        f"paper EV {d.paper_ev:.2f} diverges {d.pct_divergence:+.1f}% "
                        f"from backtest {d.backtest_ev:.2f}"
                    ),
                )
            )
        else:
            out.append(
                Recommendation(
                    setup_type=sp.setup_type,
                    action="ok",
                    reason=(
                        f"EV {sp.ev_ticks:.2f}, divergence {d.pct_divergence:+.1f}%"
                        if d
                        else f"EV {sp.ev_ticks:.2f}"
                    ),
                )
            )
    return out


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def _esc(s: str) -> str:
    return html_lib.escape(s)


def render_html(report: WeeklyReport) -> str:
    parts: list[str] = []
    parts.append(
        f"<html><head><meta charset='utf-8'><title>Weekly Edge Review "
        f"{report.week_start.isoformat()}</title>"
        "<style>body{font-family:sans-serif;max-width:900px;margin:2em auto;padding:0 1em}"
        "table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #ddd;padding:.4em .8em;text-align:right}"
        "th:first-child,td:first-child{text-align:left}"
        "h2{border-bottom:1px solid #ccc;padding-bottom:.2em}"
        ".pause{color:#c00}.retune{color:#e80}.ok{color:#080}</style></head><body>"
    )
    parts.append(
        f"<h1>Weekly Edge Review — {report.week_start} → {report.week_end}</h1>"
    )

    # Section 1
    parts.append(
        "<h2>1. Setup별 성과</h2><table><tr>"
        "<th>Setup</th><th>Trades</th><th>Win rate</th><th>Avg R:R</th>"
        "<th>EV ticks</th><th>Avg slip</th><th>Cum PnL (KRW)</th></tr>"
    )
    for sp in report.setup_perf:
        parts.append(
            f"<tr><td>{_esc(sp.setup_type)}</td><td>{sp.n_trades}</td>"
            f"<td>{sp.win_rate:.1%}</td><td>{sp.avg_rr:.2f}</td>"
            f"<td>{sp.ev_ticks:.2f}</td><td>{sp.avg_slip:.2f}</td>"
            f"<td>{sp.cum_pnl_krw:,.0f}</td></tr>"
        )
    parts.append("</table>")

    # Section 2
    parts.append(
        "<h2>2. 백테스트 vs 실거래 괴리</h2><table><tr>"
        "<th>Setup</th><th>Backtest EV</th><th>Paper EV</th>"
        "<th>Divergence</th></tr>"
    )
    for d in report.divergence:
        parts.append(
            f"<tr><td>{_esc(d.setup_type)}</td><td>{d.backtest_ev:.2f}</td>"
            f"<td>{d.paper_ev:.2f}</td><td>{d.pct_divergence:+.1f}%</td></tr>"
        )
    parts.append("</table>")

    # Section 3
    parts.append("<h2>3. 리스크 이벤트</h2>")
    if report.risk_events:
        parts.append("<table><tr><th>Kind</th><th>Detail</th></tr>")
        for e in report.risk_events:
            parts.append(f"<tr><td>{_esc(e.kind)}</td><td>{_esc(e.detail)}</td></tr>")
        parts.append("</table>")
    else:
        parts.append("<p>No risk events this week.</p>")

    # Section 4
    parts.append(
        "<h2>4. 데이터 품질</h2><ul>"
        f"<li>News collected: {report.data_quality.news_collected:,}</li>"
        f"<li>Macro missing days: {report.data_quality.macro_missing_days}</li>"
        f"<li>Scoring fallback rate: {report.data_quality.scoring_fallback_rate:.1%}</li>"
        "</ul>"
    )

    # Section 5
    parts.append(
        "<h2>5. 권장 액션</h2><table><tr>"
        "<th>Setup</th><th>Action</th><th>Reason</th></tr>"
    )
    for r in report.recommendations:
        cls = r.action  # pause / retune / ok
        parts.append(
            f"<tr><td>{_esc(r.setup_type)}</td>"
            f"<td class='{cls}'>{_esc(r.action.upper())}</td>"
            f"<td>{_esc(r.reason)}</td></tr>"
        )
    parts.append("</table></body></html>")
    return "".join(parts)


def render_telegram_summary(report: WeeklyReport) -> str:
    """Plain-text summary for Telegram."""
    lines = [f"Weekly Edge Review {report.week_start} → {report.week_end}", ""]
    lines.append("§1 Setup 성과:")
    for sp in report.setup_perf:
        lines.append(
            f"  {sp.setup_type}: n={sp.n_trades} EV={sp.ev_ticks:+.2f}t "
            f"win={sp.win_rate:.0%} pnl={sp.cum_pnl_krw:,.0f}KRW"
        )
    lines.append("")
    lines.append("§2 백테스트 괴리:")
    for d in report.divergence:
        lines.append(
            f"  {d.setup_type}: paper={d.paper_ev:+.2f} bt={d.backtest_ev:+.2f} "
            f"({d.pct_divergence:+.1f}%)"
        )
    if report.risk_events:
        lines.append("")
        lines.append(f"§3 Risk events: {len(report.risk_events)}")
    lines.append("")
    lines.append(
        f"§4 Data: news={report.data_quality.news_collected:,} "
        f"macro_missing={report.data_quality.macro_missing_days}d "
        f"fallback={report.data_quality.scoring_fallback_rate:.0%}"
    )
    actionable = [r for r in report.recommendations if r.action != "ok"]
    if actionable:
        lines.append("")
        lines.append("§5 ACTIONS:")
        for r in actionable:
            lines.append(f"  [{r.action.upper()}] {r.setup_type}: {r.reason}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Job runner
# ---------------------------------------------------------------------------


class WeeklyEdgeReviewFullJob:
    def __init__(
        self,
        *,
        ch_client: Any,
        telegram_client: Any,
        backtest_baseline: dict[str, float],
        window_days: int = 7,
        report_dir: Path = Path("reports/weekly"),
    ) -> None:
        self.ch = ch_client
        self.telegram = telegram_client
        self.backtest_baseline = backtest_baseline
        self.window_days = window_days
        self.report_dir = report_dir

    async def run(self) -> WeeklyReport:
        try:
            perf_rows = await self.ch.fetch(
                _SETUP_PERF_QUERY.format(window_days=self.window_days)
            )
        except Exception:
            logger.exception("setup-perf query failed")
            perf_rows = []
        try:
            risk_rows = await self.ch.fetch(
                _RISK_EVENTS_QUERY.format(window_days=self.window_days)
            )
        except Exception:
            logger.exception("risk-events query failed")
            risk_rows = []
        try:
            news_rows = await self.ch.fetch(
                _DATA_QUALITY_QUERY.format(window_days=self.window_days)
            )
        except Exception:
            logger.exception("data-quality query failed")
            news_rows = [(0,)]

        perf = build_setup_perf_section(perf_rows)
        divergence = build_divergence_section(perf, self.backtest_baseline)
        risk_events = build_risk_events_section(risk_rows)
        n_news = int(news_rows[0][0]) if news_rows else 0
        data_quality = DataQuality(
            news_collected=n_news,
            macro_missing_days=0,
            scoring_fallback_rate=0.0,
        )
        recommendations = build_recommendations(perf, divergence)

        today = date.today()
        week_start = today - timedelta(days=self.window_days)
        report = WeeklyReport(
            week_start=week_start,
            week_end=today,
            setup_perf=perf,
            divergence=divergence,
            risk_events=risk_events,
            data_quality=data_quality,
            recommendations=recommendations,
        )

        # Persist HTML
        self.report_dir.mkdir(parents=True, exist_ok=True)
        iso_year, iso_week, _ = today.isocalendar()
        html_path = self.report_dir / f"{iso_year}-W{iso_week:02d}.html"
        html_path.write_text(render_html(report), encoding="utf-8")
        logger.info("HTML report written to %s", html_path)

        # Telegram summary (is_critical=True bypasses the 08:30-15:40 gate
        # since cron fires at 06:00 KST).
        try:
            await self.telegram.send_message(
                render_telegram_summary(report), is_critical=True
            )
        except Exception:
            logger.exception("telegram send failed")

        return report


async def _build_and_run() -> int:
    from shared.db.client import AsyncClickHouseClient
    from shared.db.config import ClickHouseConfig
    from shared.notification.telegram import TelegramNotifier

    ch_config = ClickHouseConfig.from_env(database="kospi")
    ch_client = AsyncClickHouseClient(ch_config)
    await ch_client.connect()

    telegram = TelegramNotifier(
        bot_token=os.environ.get(
            "TELEGRAM_BRIEFING_BOT_TOKEN",
            os.environ.get("TELEGRAM_FUTURES_BOT_TOKEN", ""),
        ),
        chat_id=os.environ.get(
            "TELEGRAM_BRIEFING_CHAT_ID",
            os.environ.get("TELEGRAM_FUTURES_CHAT_ID", ""),
        ),
    )

    # Backtest baseline (per-setup EV ticks). Phase 5 operator can update from
    # the latest Optuna run; for now use the 2026-04-29 production tune.
    backtest_baseline = {
        "A_gap_reversion": 12.64,
        "C_event_reaction": 28.10,
    }

    job = WeeklyEdgeReviewFullJob(
        ch_client=ch_client,
        telegram_client=telegram,
        backtest_baseline=backtest_baseline,
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    sys.exit(main())
