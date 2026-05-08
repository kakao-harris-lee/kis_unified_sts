"""Unit tests for scripts/analysis/phase2_preflight_check.py.

Test coverage
-------------
1. ``_check_shadow_mode`` PASS / FAIL paths from a temp YAML.
2. ``_check_setup_strategies_enabled`` PASS / FAIL paths.
3. ``_check_futures_live_disabled`` reads nested ``futures_live.enabled``.
4. ``_check_telegram_credentials`` env var resolution (BRIEFING > FUTURES).
5. ``_check_crontab_entries`` parses crontab output.
6. ``_check_prometheus_alerts`` parses /api/v1/rules JSON.
7. ``run`` aggregates checks and ``all_critical_pass`` flag is correct.
8. Output renderers produce the expected human / JSON shapes.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import scripts.analysis.phase2_preflight_check as _mod
from scripts.analysis.phase2_preflight_check import (
    CheckResult,
    PreflightReport,
    _render_human,
    _render_json,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _report_with(result: CheckResult) -> PreflightReport:
    r = PreflightReport()
    r.checks.append(result)
    return r


# ---------------------------------------------------------------------------
# all_critical_pass
# ---------------------------------------------------------------------------


class TestAllCriticalPass:
    def test_empty_report_is_pass(self):
        assert PreflightReport().all_critical_pass is True

    def test_pass_only_is_pass(self):
        r = _report_with(CheckResult("a", "PASS", "x", "x"))
        assert r.all_critical_pass is True

    def test_warn_only_is_pass(self):
        """WARN does not block — only FAIL does."""
        r = _report_with(CheckResult("a", "WARN", "x", "x"))
        assert r.all_critical_pass is True

    def test_fail_blocks(self):
        r = _report_with(CheckResult("a", "FAIL", "x", "x"))
        assert r.all_critical_pass is False


# ---------------------------------------------------------------------------
# _check_telegram_credentials
# ---------------------------------------------------------------------------


class TestTelegramCredentials:
    def test_briefing_creds_pass(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BRIEFING_BOT_TOKEN", "abc")
        monkeypatch.setenv("TELEGRAM_BRIEFING_CHAT_ID", "123")
        report = PreflightReport()
        _mod._check_telegram_credentials(report)
        assert report.checks[0].status == "PASS"

    def test_futures_creds_fallback_pass(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BRIEFING_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_BRIEFING_CHAT_ID", raising=False)
        monkeypatch.setenv("TELEGRAM_FUTURES_BOT_TOKEN", "fb")
        monkeypatch.setenv("TELEGRAM_FUTURES_CHAT_ID", "789")
        report = PreflightReport()
        _mod._check_telegram_credentials(report)
        assert report.checks[0].status == "PASS"

    def test_no_creds_fail(self, monkeypatch):
        for k in (
            "TELEGRAM_BRIEFING_BOT_TOKEN",
            "TELEGRAM_BRIEFING_CHAT_ID",
            "TELEGRAM_FUTURES_BOT_TOKEN",
            "TELEGRAM_FUTURES_CHAT_ID",
        ):
            monkeypatch.delenv(k, raising=False)
        report = PreflightReport()
        _mod._check_telegram_credentials(report)
        assert report.checks[0].status == "FAIL"
        assert "MISSING" in report.checks[0].observed


# ---------------------------------------------------------------------------
# _check_shadow_mode
# ---------------------------------------------------------------------------


class TestShadowMode:
    def test_shadow_mode_true_pass(self, tmp_path: Path, monkeypatch):
        cfg = tmp_path / "rl_mppo.yaml"
        cfg.write_text("entry:\n  params:\n      shadow_mode: true\n")
        monkeypatch.setattr(_mod, "_REPO_ROOT", tmp_path.parent)
        # _check_shadow_mode hard-codes path: config/strategies/futures/rl_mppo.yaml
        # so we lay out the directory structure under tmp_path.parent.
        target = tmp_path.parent / "config" / "strategies" / "futures"
        target.mkdir(parents=True, exist_ok=True)
        (target / "rl_mppo.yaml").write_text(
            "entry:\n  params:\n      shadow_mode: true\n"
        )
        report = PreflightReport()
        _mod._check_shadow_mode(report)
        assert report.checks[0].status == "PASS"

    def test_shadow_mode_false_fail(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(_mod, "_REPO_ROOT", tmp_path)
        target = tmp_path / "config" / "strategies" / "futures"
        target.mkdir(parents=True, exist_ok=True)
        (target / "rl_mppo.yaml").write_text(
            "entry:\n  params:\n      shadow_mode: false\n"
        )
        report = PreflightReport()
        _mod._check_shadow_mode(report)
        assert report.checks[0].status == "FAIL"


# ---------------------------------------------------------------------------
# _check_futures_live_disabled
# ---------------------------------------------------------------------------


class TestFuturesLiveDisabled:
    def test_nested_enabled_false_pass(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(_mod, "_REPO_ROOT", tmp_path)
        target = tmp_path / "config"
        target.mkdir(parents=True, exist_ok=True)
        (target / "futures_live.yaml").write_text(
            "futures_live:\n  enabled: false\n  max_position_size_contracts: 1\n"
        )
        report = PreflightReport()
        _mod._check_futures_live_disabled(report)
        assert report.checks[0].status == "PASS"

    def test_nested_enabled_true_fail(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(_mod, "_REPO_ROOT", tmp_path)
        target = tmp_path / "config"
        target.mkdir(parents=True, exist_ok=True)
        (target / "futures_live.yaml").write_text(
            "futures_live:\n  enabled: true\n"
        )
        report = PreflightReport()
        _mod._check_futures_live_disabled(report)
        assert report.checks[0].status == "FAIL"


# ---------------------------------------------------------------------------
# _check_setup_strategies_enabled
# ---------------------------------------------------------------------------


class TestSetupStrategiesEnabled:
    def test_both_enabled_pass(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(_mod, "_REPO_ROOT", tmp_path)
        target = tmp_path / "config" / "strategies" / "futures"
        target.mkdir(parents=True, exist_ok=True)
        for name in ("setup_a_gap_reversion.yaml", "setup_c_event_reaction.yaml"):
            (target / name).write_text("strategy:\n  enabled: true\n")
        report = PreflightReport()
        _mod._check_setup_strategies_enabled(report)
        assert all(c.status == "PASS" for c in report.checks)
        assert len(report.checks) == 2

    def test_one_disabled_partial_fail(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(_mod, "_REPO_ROOT", tmp_path)
        target = tmp_path / "config" / "strategies" / "futures"
        target.mkdir(parents=True, exist_ok=True)
        (target / "setup_a_gap_reversion.yaml").write_text(
            "strategy:\n  enabled: true\n"
        )
        (target / "setup_c_event_reaction.yaml").write_text(
            "strategy:\n  enabled: false\n"
        )
        report = PreflightReport()
        _mod._check_setup_strategies_enabled(report)
        statuses = {c.name: c.status for c in report.checks}
        assert statuses["strategy_enabled_setup_a_gap_reversion"] == "PASS"
        assert statuses["strategy_enabled_setup_c_event_reaction"] == "FAIL"


# ---------------------------------------------------------------------------
# _check_crontab_entries
# ---------------------------------------------------------------------------


class TestCrontabEntries:
    def test_both_present_pass(self):
        crontab_output = (
            "0 7 * * 1 /repo/scripts/cron/counterfactual_weekly.sh\n"
            "0 16 * * 1-5 /repo/scripts/cron/phase2_daily_verification.sh\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=crontab_output, stderr=""
            )
            report = PreflightReport()
            _mod._check_crontab_entries(report)
        assert report.checks[0].status == "PASS"

    def test_one_missing_fail(self):
        crontab_output = "0 7 * * 1 /repo/scripts/cron/counterfactual_weekly.sh\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=crontab_output, stderr=""
            )
            report = PreflightReport()
            _mod._check_crontab_entries(report)
        assert report.checks[0].status == "FAIL"
        assert "daily_verification" in report.checks[0].observed


# ---------------------------------------------------------------------------
# _check_prometheus_alerts
# ---------------------------------------------------------------------------


class TestPrometheusAlerts:
    def test_all_4_loaded_pass(self):
        api_response = json.dumps({
            "data": {
                "groups": [
                    {
                        "name": "shadow_loggers",
                        "rules": [
                            {"name": "ShadowLoggerBatchesDropped"},
                            {"name": "ShadowLoggerFlushStale"},
                            {"name": "ShadowLoggerBufferFillingUp"},
                            {"name": "ShadowLoggerBufferNearOverflow"},
                        ],
                    }
                ]
            }
        }).encode("utf-8")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__ = MagicMock(
                return_value=MagicMock(read=MagicMock(return_value=api_response))
            )
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
            report = PreflightReport()
            _mod._check_prometheus_alerts(report)
        assert report.checks[0].status == "PASS"

    def test_one_missing_fail(self):
        api_response = json.dumps({
            "data": {
                "groups": [
                    {
                        "name": "shadow_loggers",
                        "rules": [
                            {"name": "ShadowLoggerBatchesDropped"},
                            {"name": "ShadowLoggerFlushStale"},
                            # missing 2 alerts
                        ],
                    }
                ]
            }
        }).encode("utf-8")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__ = MagicMock(
                return_value=MagicMock(read=MagicMock(return_value=api_response))
            )
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
            report = PreflightReport()
            _mod._check_prometheus_alerts(report)
        assert report.checks[0].status == "FAIL"


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------


class TestOutputRenderers:
    def _populated(self) -> PreflightReport:
        r = PreflightReport()
        r.checks.append(CheckResult("a", "PASS", "true", "true"))
        r.checks.append(CheckResult("b", "FAIL", "false", "true", detail="fix me"))
        return r

    def test_render_human_includes_status(self):
        text = _render_human(self._populated())
        assert "ALL PASS" not in text  # has FAIL
        assert "FAIL" in text
        assert "✅" in text
        assert "❌" in text

    def test_render_human_passes_only(self):
        r = PreflightReport()
        r.checks.append(CheckResult("a", "PASS", "x", "x"))
        text = _render_human(r)
        assert "ALL PASS" in text

    def test_render_json_round_trips(self):
        text = _render_json(self._populated())
        parsed = json.loads(text)
        assert parsed["all_critical_pass"] is False
        assert len(parsed["checks"]) == 2
        assert parsed["checks"][0]["name"] == "a"
        assert parsed["checks"][1]["status"] == "FAIL"
