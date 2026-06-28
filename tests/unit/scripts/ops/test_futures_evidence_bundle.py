"""F-9 evidence bundle validator/compiler tests."""

from __future__ import annotations

import importlib
import json

import pytest
import yaml


def _complete_bundle() -> dict[str, object]:
    return {
        "trading_dates": ["2026-06-22", "2026-06-23", "2026-06-24"],
        "restart_loop_ok": True,
        "backlog_ok": True,
        "dashboard_ok": True,
        "direction_comparison_ok": True,
        "kill_switch_drill_ok": True,
        "signal_count": 117,
        "backtest_tracking_error_pct": 2.4,
        "max_drawdown_ok": True,
        "slippage_ok": True,
        "operator_approval_ref": "ops-approval-2026-06-24.md",
    }


def _write_bundle(tmp_path, bundle: dict[str, object] | None = None):
    bundle_path = tmp_path / "complete-f9-evidence.yaml"
    bundle_path.write_text(yaml.safe_dump(bundle or _complete_bundle()), encoding="utf-8")
    return bundle_path


def _enable_setup_d_with_tmp_root(module, tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config/strategies/futures/setup_d_vwap_reversion.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "strategy": {
                    "name": "setup_d_vwap_reversion",
                    "enabled": True,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "_SETUP_D_CONFIG_PATH", config_path)


def _write_setup_d_report(tmp_path, payload: object | str) -> None:
    report_path = tmp_path / "reports/futures/setup_d/latest.json"
    report_path.parent.mkdir(parents=True)
    if isinstance(payload, str):
        report_path.write_text(payload, encoding="utf-8")
        return
    report_path.write_text(json.dumps(payload), encoding="utf-8")


def test_complete_bundle_passes_and_reports_per_gate_sections(tmp_path, capsys) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    bundle_path = _write_bundle(tmp_path)

    rc = module.main([str(bundle_path), "--json"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert report["status"] == "pass"
    assert report["missing_evidence"] == []
    assert report["f9_gate1"]["status"] == "pass"
    assert report["f9_gate2"]["status"] == "pass"
    assert report["phase5_small_live"]["status"] == "pass"
    assert report["phase5_small_live"]["signal_count"] == 117
    assert report["setup_d_observation"] == {
        "required": True,
        "path": "reports/futures/setup_d/latest.json",
    }
    assert report["f9_gate1"]["trading_dates"] == [
        "2026-06-22",
        "2026-06-23",
        "2026-06-24",
    ]


def test_incomplete_placeholder_bundle_fails_with_missing_evidence(
    tmp_path, capsys
) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    bundle_path = tmp_path / "incomplete-f9-evidence.json"
    bundle = {
        "trading_dates": ["2026-06-22"],
        "restart_loop_ok": True,
        "backlog_ok": False,
        "dashboard_ok": "TODO",
        "direction_comparison_ok": "placeholder",
        "kill_switch_drill_ok": True,
        "signal_count": 0,
        "backtest_tracking_error_pct": "replace me",
        "max_drawdown_ok": True,
        "slippage_ok": True,
        "operator_approval_ref": "TBD",
    }
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    rc = module.main([str(bundle_path), "--json", "--strict"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert report["status"] == "fail"
    assert (
        "trading_dates: requires at least 3 trading dates" in report["missing_evidence"]
    )
    assert "backlog_ok: expected true" in report["missing_evidence"]
    assert "dashboard_ok: placeholder value" in report["missing_evidence"]
    assert "direction_comparison_ok: placeholder value" in report["missing_evidence"]
    assert "signal_count: expected positive integer" in report["missing_evidence"]
    assert (
        "backtest_tracking_error_pct: placeholder value" in report["missing_evidence"]
    )
    assert "operator_approval_ref: placeholder value" in report["missing_evidence"]
    assert report["f9_gate1"]["status"] == "fail"
    assert report["f9_gate2"]["status"] == "fail"
    assert report["phase5_small_live"]["status"] == "fail"


def test_phase5_requires_100_signals_and_tracking_error_within_20pct(
    tmp_path, capsys
) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    bundle_path = tmp_path / "phase5-low-signal-evidence.yaml"
    bundle = {
        "trading_dates": ["2026-06-22", "2026-06-23", "2026-06-24"],
        "restart_loop_ok": True,
        "backlog_ok": True,
        "dashboard_ok": True,
        "direction_comparison_ok": True,
        "kill_switch_drill_ok": True,
        "signal_count": 99,
        "backtest_tracking_error_pct": 21.0,
        "max_drawdown_ok": True,
        "slippage_ok": True,
        "operator_approval_ref": "ops-approval-2026-06-24.md",
    }
    bundle_path.write_text(yaml.safe_dump(bundle), encoding="utf-8")

    rc = module.main([str(bundle_path), "--json", "--strict"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert report["f9_gate1"]["status"] == "pass"
    assert report["phase5_small_live"]["status"] == "fail"
    assert (
        "phase5_signal_count: requires at least 100 signals"
        in report["missing_evidence"]
    )
    assert (
        "backtest_tracking_error_pct: expected absolute value <= 20"
        in report["missing_evidence"]
    )


def test_missing_signal_count_fails_phase5_section(tmp_path, capsys) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    bundle_path = tmp_path / "missing-signal-count.yaml"
    bundle = {
        "trading_dates": ["2026-06-22", "2026-06-23", "2026-06-24"],
        "restart_loop_ok": True,
        "backlog_ok": True,
        "dashboard_ok": True,
        "direction_comparison_ok": True,
        "kill_switch_drill_ok": True,
        "backtest_tracking_error_pct": 2.4,
        "max_drawdown_ok": True,
        "slippage_ok": True,
        "operator_approval_ref": "ops-approval-2026-06-24.md",
    }
    bundle_path.write_text(yaml.safe_dump(bundle), encoding="utf-8")

    rc = module.main([str(bundle_path), "--json", "--strict"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert "signal_count: missing" in report["missing_evidence"]
    assert report["f9_gate1"]["status"] == "fail"
    assert report["phase5_small_live"]["status"] == "fail"
    assert "signal_count: missing" in report["phase5_small_live"]["missing_evidence"]


def test_strict_bundle_requires_setup_d_observation_when_strategy_enabled(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    _enable_setup_d_with_tmp_root(module, tmp_path, monkeypatch)
    bundle_path = _write_bundle(tmp_path)

    rc = module.main([str(bundle_path), "--json", "--strict"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert report["status"] == "fail"
    assert report["setup_d_observation"] == {
        "required": True,
        "path": "reports/futures/setup_d/latest.json",
    }
    assert (
        "setup_d_observation: missing reports/futures/setup_d/latest.json"
        in report["missing_evidence"]
    )


def test_strict_bundle_accepts_valid_setup_d_observation_when_strategy_enabled(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    _enable_setup_d_with_tmp_root(module, tmp_path, monkeypatch)
    _write_setup_d_report(
        tmp_path,
        {
            "strategy": "setup_d_vwap_reversion",
            "signals": "3",
            "accepted": 2,
            "rejected": 1,
        },
    )
    bundle_path = _write_bundle(tmp_path)

    rc = module.main([str(bundle_path), "--json", "--strict"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert report["status"] == "pass"
    assert report["missing_evidence"] == []


@pytest.mark.parametrize(
    ("payload", "expected_missing"),
    [
        ("{not-json", "setup_d_observation: invalid JSON"),
        (
            ["not", "a", "mapping"],
            "setup_d_observation: expected JSON object",
        ),
        (
            {
                "strategy": "setup_a_gap_reversion",
                "signals": 3,
                "accepted": 2,
                "rejected": 1,
            },
            "setup_d_observation: expected strategy setup_d_vwap_reversion",
        ),
        (
            {
                "strategy": "setup_d_vwap_reversion",
                "signals": "many",
                "accepted": 2,
                "rejected": 1,
            },
            "setup_d_observation: signals expected numeric integer",
        ),
        (
            {
                "strategy": "setup_d_vwap_reversion",
                "signals": 3,
                "accepted": 2,
            },
            "setup_d_observation: rejected missing",
        ),
    ],
)
def test_strict_bundle_rejects_invalid_setup_d_observation(
    tmp_path,
    monkeypatch,
    capsys,
    payload,
    expected_missing: str,
) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    _enable_setup_d_with_tmp_root(module, tmp_path, monkeypatch)
    _write_setup_d_report(tmp_path, payload)
    bundle_path = _write_bundle(tmp_path)

    rc = module.main([str(bundle_path), "--json", "--strict"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert report["status"] == "fail"
    assert expected_missing in report["missing_evidence"]
