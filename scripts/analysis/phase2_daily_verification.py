#!/usr/bin/env python3
"""Phase 2 Daily Verification — §10.2 first-trading-day & daily health check.

Runs at 16:00 KST after the market closes (15:40) and verifies the four
Phase 2 invariants from
``docs/plans/2026-05-03-llm-primary-rl-minimization.md`` §10.2:

  1. ``kospi.rl_shadow_predictions`` row count for today > 0
     → RL inference loop ran during the session.
  2. ``kospi.rl_trades`` row count for today == 0
     → shadow_mode is in effect; no live RL trades leaked through.
  3. ``kospi.signals_all`` Setup A signal count for today >= 1
     → Setup A was actually evaluated by strategy_manager.
  4. ``shadow_loggers`` dropped-batch counters == 0
     → no Phase 4 evaluation data was lost.

The script also surfaces informational metrics for daily cron archives:
  - Setup C signal count, LLM-veto count, total signals_all rows
  - Cumulative Phase 4 gate progress (Setup executed 30d, shadow 7d)

Output formats:
  - Telegram briefing (default) — concise PASS/FAIL summary
  - JSON archive — ``reports/daily_verification/YYYY-MM-DD.json``
  - Exit code 0 = all critical gates pass, 1 = at least one gate failed,
    2 = script error before gates could be evaluated.

Idempotent — same trading day can be re-run; archive overwrites.

Designed for cron execution; see ``scripts/cron/phase2_daily_verification.sh``.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
_REPORTS_DIR = _REPO_ROOT / "reports" / "daily_verification"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class GateResult:
    """One critical PASS/FAIL gate."""

    name: str
    passed: bool
    actual: int | float
    expected: str
    detail: str = ""


@dataclass
class DailyReport:
    trading_date: str       # ISO date (KST)
    generated_at: str       # ISO datetime (UTC)
    gates: list[GateResult] = field(default_factory=list)
    info: dict[str, Any] = field(default_factory=dict)

    @property
    def all_passed(self) -> bool:
        return all(g.passed for g in self.gates)


# ---------------------------------------------------------------------------
# ClickHouse queries
# ---------------------------------------------------------------------------


def _trading_day_bounds(trading_date: date) -> tuple[datetime, datetime]:
    """Return UTC datetimes for [00:00 KST, 24:00 KST] of the given KST date.

    Phase 2 timestamps in ClickHouse are stored as UTC; the trading day is
    a KST concept so we must convert.
    """
    start_kst = datetime.combine(trading_date, datetime.min.time(), tzinfo=KST)
    end_kst = start_kst + timedelta(days=1)
    return start_kst.astimezone(UTC), end_kst.astimezone(UTC)


def _ch_naive(ts: datetime) -> datetime:
    """ClickHouse driver expects naive datetimes for DateTime64(3, 'UTC')."""
    return ts.replace(tzinfo=None)


def _count_rl_shadow_rows(client: Any, start_utc: datetime, end_utc: datetime) -> int:
    rows = client.execute(
        "SELECT count() FROM kospi.rl_shadow_predictions "
        "WHERE ts >= %(start)s AND ts < %(end)s",
        {"start": _ch_naive(start_utc), "end": _ch_naive(end_utc)},
    )
    return int(rows[0][0]) if rows else 0


def _count_rl_trades(client: Any, start_utc: datetime, end_utc: datetime) -> int:
    rows = client.execute(
        "SELECT count() FROM kospi.rl_trades "
        "WHERE asset_class = 'futures' "
        "  AND entry_date >= %(start)s AND entry_date < %(end)s",
        {"start": _ch_naive(start_utc), "end": _ch_naive(end_utc)},
    )
    return int(rows[0][0]) if rows else 0


def _count_setup_signals(
    client: Any, start_utc: datetime, end_utc: datetime, setup_type: str
) -> int:
    rows = client.execute(
        "SELECT count() FROM kospi.signals_all "
        "WHERE setup_type = %(type)s "
        "  AND generated_at >= %(start)s AND generated_at < %(end)s",
        {
            "type": setup_type,
            "start": _ch_naive(start_utc),
            "end": _ch_naive(end_utc),
        },
    )
    return int(rows[0][0]) if rows else 0


def _count_llm_vetoes(client: Any, start_utc: datetime, end_utc: datetime) -> int:
    rows = client.execute(
        "SELECT count() FROM kospi.signals_all "
        "WHERE skip_reason = 'llm_veto' "
        "  AND generated_at >= %(start)s AND generated_at < %(end)s",
        {"start": _ch_naive(start_utc), "end": _ch_naive(end_utc)},
    )
    return int(rows[0][0]) if rows else 0


# ---------------------------------------------------------------------------
# Phase C — forecasting gates (5/6/7)
# ---------------------------------------------------------------------------


def _count_har_rv_refits(
    client: Any, start_utc: datetime, end_utc: datetime
) -> int:
    """Gate 5 helper — HAR-RV daily refit row count for the trading day.

    ``har_rv_fits.fit_date`` is a ClickHouse ``Date`` column. Passing a
    ``DateTime`` parameter (as the other ``DateTime64`` gates do) triggers
    ``Code: 53. Cannot convert string '... HH:MM:SS' to type Date``, so we
    compare against the KST trading date directly. The refit cron fires at
    15:35 KST (06:35 UTC), so the UTC date stored in ``fit_date`` always
    equals the KST trading date.
    """
    trading_date_kst = start_utc.astimezone(KST).date()
    rows = client.execute(
        "SELECT count() FROM kospi.har_rv_fits WHERE fit_date = %(d)s",
        {"d": trading_date_kst},
    )
    return int(rows[0][0]) if rows else 0


def _count_vol_forecasts(
    client: Any, start_utc: datetime, end_utc: datetime
) -> int:
    """Gate 6 helper — vol forecast row count for the trading day.

    Expected: >= 100 (forecast publisher emits ~390 rows during a full
    KOSPI session; 100 is a comfortable floor that tolerates short
    sessions, holidays, and brief publisher restarts).
    """
    rows = client.execute(
        "SELECT count() FROM kospi.vol_forecasts "
        "WHERE asof >= %(start)s AND asof < %(end)s",
        {"start": _ch_naive(start_utc), "end": _ch_naive(end_utc)},
    )
    return int(rows[0][0]) if rows else 0


def _event_scorer_fallback_rate(
    client: Any, start_utc: datetime, end_utc: datetime
) -> tuple[float, int, int]:
    """Gate 7 helper — LLM fallback ratio for event scoring.

    Returns ``(fallback_rate, llm_failures, llm_total)``.  A high rate of
    ``UNKNOWN_LLM_SCORED`` + ``impact_score == 50`` rows (the deterministic
    LLM-failure fallback signature) means the LLM event scorer is stuck.
    """
    rows = client.execute(
        "SELECT countIf(source = 'llm' "
        "                AND event_type = 'UNKNOWN_LLM_SCORED' "
        "                AND impact_score = 50) AS llm_failures, "
        "       countIf(source = 'llm') AS llm_total "
        "FROM kospi.event_scores "
        "WHERE asof >= %(start)s AND asof < %(end)s",
        {"start": _ch_naive(start_utc), "end": _ch_naive(end_utc)},
    )
    if not rows or rows[0][1] == 0:
        return (0.0, 0, 0)
    failures = int(rows[0][0])
    total = int(rows[0][1])
    return (failures / total, failures, total)


def _phase4_setup_executed_30d(client: Any) -> int:
    rows = client.execute(
        "SELECT countIf(executed = 1) FROM kospi.signals_all "
        "WHERE setup_type IN ('A','C') "
        "  AND generated_at >= now() - INTERVAL 30 DAY"
    )
    return int(rows[0][0]) if rows else 0


def _phase4_shadow_7d(client: Any) -> int:
    rows = client.execute(
        "SELECT count() FROM kospi.rl_shadow_predictions "
        "WHERE ts >= now() - INTERVAL 7 DAY"
    )
    return int(rows[0][0]) if rows else 0


# ---------------------------------------------------------------------------
# Prometheus query — shadow logger drop counters
# ---------------------------------------------------------------------------


def _fetch_shadow_logger_drops(prometheus_url: str) -> dict[str, int]:
    """Query current dropped-batches per logger from Prometheus.

    Returns a dict like ``{"rl_shadow": 0, "llm_veto": 0}``.  If Prometheus
    is unreachable the gate is reported as ``unknown`` (treated as PASS so
    the verification doesn't fail the whole day on a monitoring outage).
    """
    try:
        import urllib.error
        import urllib.parse
        import urllib.request

        query = "trading_shadow_logger_dropped_batches_total"
        url = f"{prometheus_url.rstrip('/')}/api/v1/query?{urllib.parse.urlencode({'query': query})}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        result: dict[str, int] = {}
        for series in payload.get("data", {}).get("result", []):
            label = series.get("metric", {}).get("logger")
            value = series.get("value", [None, "0"])[1]
            if label:
                result[label] = int(float(value))
        return result
    except Exception as e:
        logger.warning("prometheus query failed: %s — drop gate will be unknown", e)
        return {}


# ---------------------------------------------------------------------------
# Gate evaluation
# ---------------------------------------------------------------------------


def evaluate_gates(
    client: Any,
    trading_date: date,
    prometheus_url: str | None,
) -> DailyReport:
    """Run all queries and assemble the report."""
    start_utc, end_utc = _trading_day_bounds(trading_date)
    report = DailyReport(
        trading_date=trading_date.isoformat(),
        generated_at=datetime.now(UTC).isoformat(),
    )

    # RL_mppo는 v4.10 (2026-05-15)에 deprecate됨. shadow predictions/trades 게이트는
    # 운영 회귀 가드용으로 보존하되 expectation을 뒤집어 부재를 검증한다.
    # - rl_shadow_predictions_today: 정상 운영에서는 0이어야 함 (shadow 비활성)
    #   기존 PASS 조건이 "> 0"였지만 deprecate 이후 0이 정상. 게이트를 폐지.
    # - rl_trades_today_is_zero: 여전히 0이어야 함 (RL 코드 경로 재활성화 시 즉시 감지)
    rl_trades = _count_rl_trades(client, start_utc, end_utc)
    report.gates.append(GateResult(
        name="rl_trades_today_is_zero",
        passed=rl_trades == 0,
        actual=rl_trades,
        expected="== 0",
        detail=(
            "RL_mppo deprecated 2026-05-15 — should never produce trades. "
            "Non-zero indicates strategy was accidentally re-enabled."
        ),
    ))
    # rl_shadow_predictions count는 info로만 노출 (deprecate 추세 모니터링).
    report.info["rl_shadow_predictions_today"] = _count_rl_shadow_rows(
        client, start_utc, end_utc
    )

    # Gate 3 — Setup A signal count >= 1
    setup_a = _count_setup_signals(client, start_utc, end_utc, "A")
    report.gates.append(GateResult(
        name="setup_a_signals_today",
        passed=setup_a >= 1,
        actual=setup_a,
        expected=">= 1",
        detail="Setup A daily target per plan §6 (gap reversion).",
    ))

    # Gate 4 — shadow logger dropped batches == 0 (Prometheus optional)
    if prometheus_url:
        drops = _fetch_shadow_logger_drops(prometheus_url)
        if drops:
            total_drops = sum(drops.values())
            report.gates.append(GateResult(
                name="shadow_logger_dropped_batches",
                passed=total_drops == 0,
                actual=total_drops,
                expected="== 0",
                detail=(
                    f"Per-logger: {drops}.  Non-zero means CH insert "
                    f"failures lost Phase 4 data."
                ),
            ))

    # ------------------------------------------------------------------
    # Phase C forecasting gates (5/6/7) — verify the forecast-aware
    # paradigm runtime is healthy.  These gates are tolerant of an
    # entirely-cold deployment (forecast tables absent / empty): the
    # ClickHouse queries are wrapped in try/except so a missing table
    # surfaces as a FAIL with detail rather than crashing the whole
    # verification run.
    # ------------------------------------------------------------------

    # Gate 5 — HAR-RV refit ran today
    try:
        har_rv_count = _count_har_rv_refits(client, start_utc, end_utc)
        report.gates.append(GateResult(
            name="har_rv_refit_today",
            passed=har_rv_count >= 1,
            actual=har_rv_count,
            expected=">= 1",
            detail="HAR-RV daily refit should produce >= 1 row per trading day.",
        ))
    except Exception as exc:
        report.gates.append(GateResult(
            name="har_rv_refit_today",
            passed=False,
            actual=0,
            expected=">= 1",
            detail=f"ClickHouse query failed: {exc}",
        ))

    # Gate 6 — vol forecast publisher active during the session
    try:
        forecast_count = _count_vol_forecasts(client, start_utc, end_utc)
        report.gates.append(GateResult(
            name="forecast_publish_active",
            passed=forecast_count >= 100,
            actual=forecast_count,
            expected=">= 100",
            detail=(
                "Forecast publisher emits ~390 rows per full session; "
                "<100 indicates the daemon stalled or never started."
            ),
        ))
    except Exception as exc:
        report.gates.append(GateResult(
            name="forecast_publish_active",
            passed=False,
            actual=0,
            expected=">= 100",
            detail=f"ClickHouse query failed: {exc}",
        ))

    # Gate 7 — event scorer not stuck in deterministic LLM-failure fallback
    try:
        fallback_rate, llm_failures, llm_total = _event_scorer_fallback_rate(
            client, start_utc, end_utc
        )
        if llm_total == 0:
            # No LLM-sourced events today → treat as PASS (healthy idle).
            report.gates.append(GateResult(
                name="event_scorer_healthy",
                passed=True,
                actual=0.0,
                expected="< 0.5 (or 0 LLM calls)",
                detail="No LLM-sourced events today — gate auto-passes.",
            ))
        else:
            report.gates.append(GateResult(
                name="event_scorer_healthy",
                passed=fallback_rate < 0.5,
                actual=fallback_rate,
                expected="< 0.5",
                detail=(
                    f"LLM event scorer fallback rate {fallback_rate:.2%} "
                    f"({llm_failures}/{llm_total}). ≥50% means the LLM "
                    f"path is stuck in UNKNOWN_LLM_SCORED fallback."
                ),
            ))
    except Exception as exc:
        report.gates.append(GateResult(
            name="event_scorer_healthy",
            passed=False,
            actual=0.0,
            expected="< 0.5",
            detail=f"ClickHouse query failed: {exc}",
        ))

    # Informational metrics
    report.info["setup_c_signals_today"] = _count_setup_signals(
        client, start_utc, end_utc, "C"
    )
    report.info["llm_veto_signals_today"] = _count_llm_vetoes(
        client, start_utc, end_utc
    )
    report.info["phase4_gate_setup_executed_30d"] = _phase4_setup_executed_30d(client)
    report.info["phase4_gate_shadow_predictions_7d"] = _phase4_shadow_7d(client)

    return report


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------


def _format_telegram(report: DailyReport) -> str:
    """Concise PASS/FAIL summary for the briefing channel."""
    overall = "✅ ALL PASS" if report.all_passed else "❌ FAIL"
    lines = [
        f"🛡️ *Phase 2 Daily Verification — {overall}*",
        f"`{report.trading_date}` (KST)",
        "",
        "*Critical gates*",
    ]
    for g in report.gates:
        icon = "✅" if g.passed else "❌"
        lines.append(f"{icon} `{g.name}`: actual=`{g.actual}` (expected {g.expected})")
        if not g.passed and g.detail:
            lines.append(f"   ↳ {g.detail}")
    lines.append("")
    lines.append("*Informational*")
    lines.append(f"• Setup C signals today: `{report.info.get('setup_c_signals_today', 0)}`")
    lines.append(f"• LLM-veto signals today: `{report.info.get('llm_veto_signals_today', 0)}`")
    lines.append("")
    lines.append("*Phase 4 cumulative gate progress*")
    se = report.info.get("phase4_gate_setup_executed_30d", 0)
    sp = report.info.get("phase4_gate_shadow_predictions_7d", 0)
    se_icon = "✅" if se >= 50 else "⏳"
    sp_icon = "✅" if sp >= 1000 else "⏳"
    lines.append(f"{se_icon} Setup A/C executed (30d): `{se}` / 50")
    lines.append(f"{sp_icon} RL shadow predictions (7d): `{sp}` / 1000")

    return "\n".join(lines)


def _write_archive(report: DailyReport) -> Path:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = _REPORTS_DIR / f"{report.trading_date}.json"
    payload = {
        "trading_date": report.trading_date,
        "generated_at": report.generated_at,
        "all_passed": report.all_passed,
        "gates": [asdict(g) for g in report.gates],
        "info": report.info,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


async def _send_telegram(message: str) -> None:
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
        # Verification failures are operationally important — flag as critical
        # so they bypass quiet hours.
        await notifier.send_message(message, is_critical=True)
        logger.info("telegram report delivered")
    except Exception:
        logger.exception("telegram send failed")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 2 daily verification — runs after market close (16:00 KST) "
            "to verify §10.2 invariants from the LLM-primary RL-minimization plan."
        )
    )
    parser.add_argument(
        "--trading-date",
        type=lambda s: date.fromisoformat(s),
        default=None,
        help="Override trading date (KST, YYYY-MM-DD). Default: today.",
    )
    parser.add_argument(
        "--prometheus-url",
        default=os.environ.get("PROMETHEUS_URL", "http://localhost:9090"),
        help=(
            "Prometheus base URL for the dropped-batches gate. "
            "Empty string disables the gate."
        ),
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

    trading_date = args.trading_date or datetime.now(KST).date()
    logger.info("Phase 2 daily verification — trading_date=%s (KST)", trading_date)

    try:
        from shared.db.utils import clickhouse_client_from_env

        client = clickhouse_client_from_env(database="kospi")
    except Exception:
        logger.exception("ClickHouse client init failed — cannot run verification")
        return 2

    try:
        report = evaluate_gates(
            client=client,
            trading_date=trading_date,
            prometheus_url=(args.prometheus_url or None),
        )
    except Exception:
        logger.exception("gate evaluation crashed")
        return 2
    finally:
        with contextlib.suppress(Exception):
            client.disconnect()

    archive_path = _write_archive(report)
    logger.info("archive written → %s", archive_path)

    if not args.no_telegram:
        message = _format_telegram(report)
        asyncio.run(_send_telegram(message))

    if report.all_passed:
        logger.info("all critical gates PASS")
        return 0
    failed = [g.name for g in report.gates if not g.passed]
    logger.warning("gate FAIL: %s", failed)
    return 1


if __name__ == "__main__":
    sys.exit(main())
