"""Unit tests for scripts/analysis/phase2_daily_verification.py.

Test coverage
-------------
1. ``_trading_day_bounds`` returns the right UTC window for a KST date
   (and handles the 9-hour offset including the day boundary).
2. Gate evaluation — happy path: all 4 gates PASS.
3. Gate evaluation — Phase 2 shadow_mode failure: rl_trades > 0 → FAIL.
4. Gate evaluation — RL inference dead: shadow rows == 0 → FAIL.
5. Gate evaluation — Setup A missing: signals_a == 0 → FAIL.
6. Gate evaluation — Prometheus drops > 0 → FAIL.
7. Gate evaluation — Prometheus unreachable: gate is OMITTED (not failed).
8. ``_format_telegram`` survives all-pass and all-fail reports.
9. ``_write_archive`` round-trips through JSON.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import scripts.analysis.phase2_daily_verification as _mod
from scripts.analysis.phase2_daily_verification import (
    DailyReport,
    GateResult,
    _format_telegram,
    _trading_day_bounds,
    _write_archive,
    evaluate_gates,
)

# ---------------------------------------------------------------------------
# _trading_day_bounds
# ---------------------------------------------------------------------------


class TestTradingDayBounds:
    def test_returns_24_hour_utc_window(self):
        start, end = _trading_day_bounds(date(2026, 5, 11))
        # KST is UTC+9 → 2026-05-11 00:00 KST = 2026-05-10 15:00 UTC
        assert start == datetime(2026, 5, 10, 15, 0, tzinfo=UTC)
        assert end == datetime(2026, 5, 11, 15, 0, tzinfo=UTC)
        assert (end - start).total_seconds() == 86_400


# ---------------------------------------------------------------------------
# evaluate_gates
# ---------------------------------------------------------------------------


def _stub_client(
    *,
    rl_shadow: int = 100,
    rl_trades: int = 0,
    setup_a: int = 3,
    setup_c: int = 1,
    veto: int = 0,
    cum_setup_executed: int = 0,
    cum_shadow: int = 0,
    har_rv_fits: int = 1,
    vol_forecasts: int = 200,
    event_scores: tuple[int, int] = (0, 0),
    har_rv_param_capture: list | None = None,
) -> MagicMock:
    """Build a MagicMock CH client whose execute() routes by query keyword."""
    client = MagicMock()

    def _execute(query: str, params: dict | None = None) -> list[tuple]:
        q = query.lower()
        if "rl_shadow_predictions" in q and "interval 7 day" in q:
            return [(cum_shadow,)]
        if "rl_shadow_predictions" in q:
            return [(rl_shadow,)]
        if "rl_trades" in q:
            return [(rl_trades,)]
        if "skip_reason = 'llm_veto'" in q:
            return [(veto,)]
        if "interval 30 day" in q:
            return [(cum_setup_executed,)]
        if "setup_type = %(type)s" in q:
            assert params is not None
            return [(setup_a if params["type"] == "A" else setup_c,)]
        if "har_rv_fits" in q:
            if har_rv_param_capture is not None and params is not None:
                har_rv_param_capture.append(dict(params))
            return [(har_rv_fits,)]
        if "vol_forecasts" in q:
            return [(vol_forecasts,)]
        if "event_scores" in q:
            return [event_scores]
        raise AssertionError(f"unexpected query: {query[:80]}")

    client.execute = _execute
    return client


class TestEvaluateGates:
    def test_all_gates_pass(self):
        report = evaluate_gates(
            client=_stub_client(rl_shadow=100, rl_trades=0, setup_a=3),
            trading_date=date(2026, 5, 11),
            prometheus_url=None,
        )
        assert report.all_passed
        names = [g.name for g in report.gates]
        assert "rl_shadow_predictions_today" in names
        assert "rl_trades_today_is_zero" in names
        assert "setup_a_signals_today" in names

    def test_shadow_mode_violation_fails(self):
        """shadow_mode=true must prevent rl_trades — non-zero is critical."""
        report = evaluate_gates(
            client=_stub_client(rl_shadow=100, rl_trades=5, setup_a=3),
            trading_date=date(2026, 5, 11),
            prometheus_url=None,
        )
        assert not report.all_passed
        rl_trades_gate = next(
            g for g in report.gates if g.name == "rl_trades_today_is_zero"
        )
        assert rl_trades_gate.passed is False
        assert rl_trades_gate.actual == 5

    def test_rl_inference_dead_fails(self):
        """No shadow rows → either inference loop dead or DB unreachable."""
        report = evaluate_gates(
            client=_stub_client(rl_shadow=0, rl_trades=0, setup_a=3),
            trading_date=date(2026, 5, 11),
            prometheus_url=None,
        )
        assert not report.all_passed
        gate = next(
            g for g in report.gates if g.name == "rl_shadow_predictions_today"
        )
        assert gate.passed is False

    def test_setup_a_missing_fails(self):
        report = evaluate_gates(
            client=_stub_client(rl_shadow=100, rl_trades=0, setup_a=0),
            trading_date=date(2026, 5, 11),
            prometheus_url=None,
        )
        assert not report.all_passed
        gate = next(g for g in report.gates if g.name == "setup_a_signals_today")
        assert gate.passed is False

    def test_prometheus_drops_fail(self, monkeypatch):
        """Prometheus reports dropped batches → critical FAIL gate."""
        monkeypatch.setattr(
            _mod,
            "_fetch_shadow_logger_drops",
            lambda _url: {"rl_shadow": 2, "llm_veto": 0},
        )
        report = evaluate_gates(
            client=_stub_client(rl_shadow=100, rl_trades=0, setup_a=3),
            trading_date=date(2026, 5, 11),
            prometheus_url="http://prom:9090",
        )
        assert not report.all_passed
        gate = next(
            g for g in report.gates if g.name == "shadow_logger_dropped_batches"
        )
        assert gate.passed is False
        assert gate.actual == 2

    def test_prometheus_unreachable_omits_gate(self, monkeypatch):
        """Empty drop dict (Prometheus down) → gate omitted, not failed."""
        monkeypatch.setattr(_mod, "_fetch_shadow_logger_drops", lambda _url: {})
        report = evaluate_gates(
            client=_stub_client(rl_shadow=100, rl_trades=0, setup_a=3),
            trading_date=date(2026, 5, 11),
            prometheus_url="http://prom:9090",
        )
        names = [g.name for g in report.gates]
        assert "shadow_logger_dropped_batches" not in names
        assert report.all_passed  # other 3 gates pass

    def test_har_rv_gate_passes_date_param_not_datetime(self):
        """Regression: fit_date is a ClickHouse Date column, so the verification
        query must bind a date (not datetime), otherwise ClickHouse raises
        ``Code: 53. Cannot convert string '... HH:MM:SS' to type Date`` and the
        gate fails on every trading day.  Captured param must be a ``date``
        whose value matches the KST trading_date.
        """
        captured: list[dict] = []
        report = evaluate_gates(
            client=_stub_client(
                rl_shadow=100,
                rl_trades=0,
                setup_a=3,
                har_rv_fits=1,
                har_rv_param_capture=captured,
            ),
            trading_date=date(2026, 5, 14),
            prometheus_url=None,
        )
        gate = next(g for g in report.gates if g.name == "har_rv_refit_today")
        assert gate.passed is True
        assert gate.actual == 1
        assert captured, "har_rv_fits query was not executed"
        bound = captured[0]["d"]
        # MUST be a plain date, not a datetime — otherwise ClickHouse rejects
        # the parameter against a Date column.
        assert isinstance(bound, date) and not isinstance(bound, datetime)
        assert bound == date(2026, 5, 14)

    def test_har_rv_gate_fails_when_no_refit(self):
        report = evaluate_gates(
            client=_stub_client(rl_shadow=100, rl_trades=0, setup_a=3, har_rv_fits=0),
            trading_date=date(2026, 5, 14),
            prometheus_url=None,
        )
        gate = next(g for g in report.gates if g.name == "har_rv_refit_today")
        assert gate.passed is False
        assert gate.actual == 0

    def test_info_metrics_populated(self):
        report = evaluate_gates(
            client=_stub_client(setup_c=2, veto=4, cum_setup_executed=12, cum_shadow=350),
            trading_date=date(2026, 5, 11),
            prometheus_url=None,
        )
        assert report.info["setup_c_signals_today"] == 2
        assert report.info["llm_veto_signals_today"] == 4
        assert report.info["phase4_gate_setup_executed_30d"] == 12
        assert report.info["phase4_gate_shadow_predictions_7d"] == 350


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------


class TestFormatTelegram:
    def _report(self, *, all_pass: bool) -> DailyReport:
        return DailyReport(
            trading_date="2026-05-11",
            generated_at="2026-05-11T07:00:00+00:00",
            gates=[
                GateResult(
                    name="rl_shadow_predictions_today",
                    passed=all_pass,
                    actual=100 if all_pass else 0,
                    expected="> 0",
                ),
                GateResult(
                    name="rl_trades_today_is_zero",
                    passed=True,
                    actual=0,
                    expected="== 0",
                ),
                GateResult(
                    name="setup_a_signals_today",
                    passed=True,
                    actual=3,
                    expected=">= 1",
                ),
            ],
            info={
                "setup_c_signals_today": 1,
                "llm_veto_signals_today": 0,
                "phase4_gate_setup_executed_30d": 25,
                "phase4_gate_shadow_predictions_7d": 700,
            },
        )

    def test_all_pass_uses_pass_header(self):
        msg = _format_telegram(self._report(all_pass=True))
        assert "ALL PASS" in msg
        assert "2026-05-11" in msg

    def test_fail_uses_fail_header(self):
        msg = _format_telegram(self._report(all_pass=False))
        assert "FAIL" in msg
        # Failed gate is highlighted with a ❌ bullet
        assert "❌" in msg

    def test_phase4_progress_shown(self):
        msg = _format_telegram(self._report(all_pass=True))
        assert "25" in msg  # setup executed cumulative
        assert "700" in msg  # shadow cumulative
        assert "/ 50" in msg
        assert "/ 1000" in msg


# ---------------------------------------------------------------------------
# _write_archive
# ---------------------------------------------------------------------------


class TestWriteArchive:
    def test_round_trips(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(_mod, "_REPORTS_DIR", tmp_path)
        report = DailyReport(
            trading_date="2026-05-11",
            generated_at="2026-05-11T07:00:00+00:00",
            gates=[
                GateResult(name="g1", passed=True, actual=5, expected="> 0"),
            ],
            info={"key": "value"},
        )
        path = _write_archive(report)
        assert path.exists()
        payload = json.loads(path.read_text())
        assert payload["trading_date"] == "2026-05-11"
        assert payload["all_passed"] is True
        assert payload["gates"][0]["name"] == "g1"
        assert payload["info"] == {"key": "value"}
