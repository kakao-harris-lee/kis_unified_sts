"""Tests for scripts/analysis/weekly_edge_review.py — Phase 5 Task 2."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Dynamic import — script is in scripts/, not a package.
spec = importlib.util.spec_from_file_location(
    "weekly_edge_review_full",
    _REPO_ROOT / "scripts" / "analysis" / "weekly_edge_review.py",
)
_module = importlib.util.module_from_spec(spec)
sys.modules["weekly_edge_review_full"] = _module
spec.loader.exec_module(_module)

SetupPerf = _module.SetupPerf
BacktestDivergence = _module.BacktestDivergence
RiskEvent = _module.RiskEvent
DataQuality = _module.DataQuality
Recommendation = _module.Recommendation
WeeklyReport = _module.WeeklyReport
build_setup_perf_section = _module.build_setup_perf_section
build_divergence_section = _module.build_divergence_section
build_risk_events_section = _module.build_risk_events_section
build_recommendations = _module.build_recommendations
render_html = _module.render_html
render_telegram_summary = _module.render_telegram_summary
WeeklyEdgeReviewFullJob = _module.WeeklyEdgeReviewFullJob


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


class TestBuildSetupPerf:
    def test_parses_full_row(self):
        rows = [
            ("A_gap_reversion", 12, 0.42, 1.5, 8.3, 0.25, 1_500_000),
        ]
        result = build_setup_perf_section(rows)
        assert len(result) == 1
        sp = result[0]
        assert sp.setup_type == "A_gap_reversion"
        assert sp.n_trades == 12
        assert sp.win_rate == pytest.approx(0.42)
        assert sp.avg_rr == pytest.approx(1.5)
        assert sp.ev_ticks == pytest.approx(8.3)
        assert sp.avg_slip == pytest.approx(0.25)
        assert sp.cum_pnl_krw == pytest.approx(1_500_000)

    def test_handles_none_aggregates(self):
        rows = [("A_gap_reversion", 0, None, None, None, None, None)]
        result = build_setup_perf_section(rows)
        sp = result[0]
        assert sp.n_trades == 0
        assert sp.win_rate == 0.0
        assert sp.ev_ticks == 0.0


class TestBuildDivergence:
    def test_pct_divergence_against_baseline(self):
        perf = [
            SetupPerf("A_gap_reversion", 10, 0.5, 1.5, 8.0, 0.2, 500_000),
        ]
        baseline = {"A_gap_reversion": 12.64}
        result = build_divergence_section(perf, baseline)
        assert len(result) == 1
        d = result[0]
        # (8 - 12.64) / 12.64 ≈ -36.7%
        assert d.pct_divergence == pytest.approx(-36.71, abs=0.1)

    def test_zero_baseline_avoids_divbyzero(self):
        perf = [SetupPerf("X", 5, 0.5, 1.5, 5.0, 0.2, 0)]
        result = build_divergence_section(perf, {"X": 0.0})
        assert result[0].pct_divergence == 0.0

    def test_missing_baseline_treated_as_zero(self):
        perf = [SetupPerf("X", 5, 0.5, 1.5, 5.0, 0.2, 0)]
        result = build_divergence_section(perf, {})
        assert result[0].backtest_ev == 0.0
        assert result[0].pct_divergence == 0.0


class TestBuildRiskEvents:
    def test_classifies_kill_switch(self):
        rows = [("kill_switch_daily_loss", 1)]
        result = build_risk_events_section(rows)
        assert result[0].kind == "kill_switch"

    def test_classifies_spread_block(self):
        rows = [("spread_too_wide", 5)]
        result = build_risk_events_section(rows)
        assert result[0].kind == "spread_block"

    def test_classifies_consecutive_loss(self):
        rows = [("consecutive_losses_5", 1)]
        result = build_risk_events_section(rows)
        assert result[0].kind == "consecutive_loss"

    def test_unknown_classifies_as_filter(self):
        rows = [("trading_hours", 3)]
        result = build_risk_events_section(rows)
        assert result[0].kind == "filter"


class TestRecommendations:
    def test_negative_ev_setup_recommended_pause(self):
        perf = [SetupPerf("A_gap_reversion", 20, 0.4, 1.5, -3.0, 0.3, -500_000)]
        divergence = [BacktestDivergence("A_gap_reversion", 12.64, -3.0, -123.7)]
        recs = build_recommendations(perf, divergence)
        assert recs[0].action == "pause"

    def test_high_divergence_setup_recommended_retune(self):
        # Positive EV but >30% divergence
        perf = [SetupPerf("A_gap_reversion", 20, 0.6, 1.5, 5.0, 0.3, 500_000)]
        divergence = [BacktestDivergence("A_gap_reversion", 12.64, 5.0, -60.0)]
        recs = build_recommendations(perf, divergence)
        assert recs[0].action == "retune"

    def test_healthy_setup_marked_ok(self):
        perf = [SetupPerf("A_gap_reversion", 20, 0.6, 1.5, 11.0, 0.3, 1_000_000)]
        divergence = [BacktestDivergence("A_gap_reversion", 12.64, 11.0, -13.0)]
        recs = build_recommendations(perf, divergence)
        assert recs[0].action == "ok"

    def test_pause_threshold_configurable(self):
        perf = [SetupPerf("X", 10, 0.5, 1.5, 1.0, 0.3, 100_000)]
        divergence = []
        # Default threshold 0 → ok
        assert build_recommendations(perf, divergence)[0].action == "ok"
        # Higher threshold → pause
        assert (
            build_recommendations(perf, divergence, pause_ev_threshold=2.0)[0].action
            == "pause"
        )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _sample_report() -> WeeklyReport:
    return WeeklyReport(
        week_start=date(2026, 5, 1),
        week_end=date(2026, 5, 8),
        setup_perf=[
            SetupPerf("A_gap_reversion", 10, 0.5, 1.5, 8.0, 0.2, 500_000),
            SetupPerf("C_event_reaction", 3, 0.67, 2.0, 25.0, 0.15, 800_000),
        ],
        divergence=[
            BacktestDivergence("A_gap_reversion", 12.64, 8.0, -36.71),
            BacktestDivergence("C_event_reaction", 28.10, 25.0, -11.03),
        ],
        risk_events=[
            RiskEvent(datetime(2026, 5, 3), "spread_block", "spread_too_wide: n=2"),
        ],
        data_quality=DataQuality(
            news_collected=1234, macro_missing_days=0, scoring_fallback_rate=0.05
        ),
        recommendations=[
            Recommendation("A_gap_reversion", "retune", "paper EV diverges -36.7%"),
            Recommendation("C_event_reaction", "ok", "EV +25.00, divergence -11.0%"),
        ],
    )


class TestRenderHTML:
    def test_contains_all_5_sections(self):
        html = render_html(_sample_report())
        assert "1. Setup별 성과" in html
        assert "2. 백테스트 vs 실거래 괴리" in html
        assert "3. 리스크 이벤트" in html
        assert "4. 데이터 품질" in html
        assert "5. 권장 액션" in html

    def test_setup_rows_present(self):
        html = render_html(_sample_report())
        assert "A_gap_reversion" in html
        assert "C_event_reaction" in html

    def test_action_classes_applied(self):
        html = render_html(_sample_report())
        assert "class='retune'" in html
        assert "class='ok'" in html

    def test_no_risk_events_friendly_message(self):
        report = WeeklyReport(
            week_start=date(2026, 5, 1),
            week_end=date(2026, 5, 8),
            setup_perf=[],
            divergence=[],
            risk_events=[],
            data_quality=DataQuality(0, 0, 0.0),
            recommendations=[],
        )
        html = render_html(report)
        assert "No risk events" in html

    def test_html_is_well_formed(self):
        html = render_html(_sample_report())
        assert html.startswith("<html>")
        assert html.endswith("</body></html>")


class TestRenderTelegramSummary:
    def test_contains_section_markers(self):
        msg = render_telegram_summary(_sample_report())
        assert "§1" in msg
        assert "§2" in msg
        assert "§4" in msg
        assert "§5" in msg

    def test_actions_only_in_summary_when_actionable(self):
        # Sample has retune → §5 ACTIONS present
        assert "§5 ACTIONS:" in render_telegram_summary(_sample_report())

    def test_no_actions_section_when_all_ok(self):
        report = WeeklyReport(
            week_start=date(2026, 5, 1),
            week_end=date(2026, 5, 8),
            setup_perf=[],
            divergence=[],
            risk_events=[],
            data_quality=DataQuality(0, 0, 0.0),
            recommendations=[Recommendation("A", "ok", "fine")],
        )
        msg = render_telegram_summary(report)
        assert "ACTIONS" not in msg


# ---------------------------------------------------------------------------
# Job-level
# ---------------------------------------------------------------------------


class TestJob:
    @pytest.mark.asyncio
    async def test_run_writes_html_and_sends_telegram(self, tmp_path):
        ch = AsyncMock()
        ch.fetch.side_effect = [
            [("A_gap_reversion", 10, 0.5, 1.5, 8.0, 0.2, 500_000)],
            [("trading_hours", 3)],
            [(1234,)],
        ]
        telegram = AsyncMock()
        job = WeeklyEdgeReviewFullJob(
            query_client=ch,
            telegram_client=telegram,
            backtest_baseline={"A_gap_reversion": 12.64},
            window_days=7,
            report_dir=tmp_path / "weekly",
        )

        report = await job.run()

        assert ch.fetch.await_count == 3
        telegram.send_message.assert_awaited_once()
        kwargs = telegram.send_message.call_args.kwargs
        assert kwargs.get("is_critical") is True

        # HTML file written
        html_files = list((tmp_path / "weekly").glob("*.html"))
        assert len(html_files) == 1
        content = html_files[0].read_text()
        assert "Weekly Edge Review" in content
        assert "A_gap_reversion" in content

        # Recommendations populated
        assert len(report.recommendations) == 1
        # 8.0 EV > 0 but |(-36.71)| > 30% divergence → retune
        assert report.recommendations[0].action == "retune"

    @pytest.mark.asyncio
    async def test_run_handles_query_failure_gracefully(self, tmp_path):
        ch = AsyncMock()
        ch.fetch.side_effect = [
            Exception("CH down"),
            Exception("CH down"),
            Exception("CH down"),
        ]
        telegram = AsyncMock()
        job = WeeklyEdgeReviewFullJob(
            query_client=ch,
            telegram_client=telegram,
            backtest_baseline={},
            window_days=7,
            report_dir=tmp_path / "weekly",
        )

        # Should not raise — empty report instead
        report = await job.run()
        assert report.setup_perf == []
        assert report.risk_events == []
        # Telegram still called with empty summary
        telegram.send_message.assert_awaited_once()
