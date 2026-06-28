"""F-9 evidence bundle validator/compiler tests."""

from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime, timedelta

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
    bundle_path.write_text(
        yaml.safe_dump(bundle or _complete_bundle()), encoding="utf-8"
    )
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


def _disable_setup_d_with_tmp_root(module, tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config/strategies/futures/setup_d_vwap_reversion.yaml"
    monkeypatch.setattr(module, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "_SETUP_D_CONFIG_PATH", config_path)


def _write_setup_d_report(tmp_path, payload: object | str) -> None:
    report_path = tmp_path / "reports/futures/setup_d/latest.json"
    report_path.parent.mkdir(parents=True)
    if isinstance(payload, str):
        report_path.write_text(payload, encoding="utf-8")
        return
    report_path.write_text(json.dumps(payload), encoding="utf-8")


def _valid_setup_d_payload(generated_at: datetime) -> dict[str, object]:
    return {
        "strategy": "setup_d_vwap_reversion",
        "signals": "3",
        "accepted": 2,
        "rejected": 1,
        "generated_at": generated_at.isoformat(),
        "source_path": "/tmp/signals.jsonl",
    }


def test_complete_bundle_passes_and_reports_per_gate_sections(
    tmp_path, monkeypatch, capsys
) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    _disable_setup_d_with_tmp_root(module, tmp_path, monkeypatch)
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
        "required": False,
        "path": "reports/futures/setup_d/latest.json",
        "status": "disabled",
        "missing_evidence": [],
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


def test_setup_d_missing_is_decoupled_from_f9_strict_gate(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    _enable_setup_d_with_tmp_root(module, tmp_path, monkeypatch)
    bundle_path = _write_bundle(tmp_path)

    rc = module.main([str(bundle_path), "--json", "--strict"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert report["status"] == "pass"
    assert report["setup_d_observation"] == {
        "required": True,
        "path": "reports/futures/setup_d/latest.json",
        "status": "fail",
        "missing_evidence": ["missing reports/futures/setup_d/latest.json"],
    }
    # Top-level missing_evidence no longer carries Setup-D reasons.
    assert (
        "setup_d_observation: missing reports/futures/setup_d/latest.json"
        not in report["missing_evidence"]
    )

    rc = module.main([str(bundle_path), "--json", "--strict", "--strict-setup-d"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 1
    # Top-level status stays F-9-only even when --strict-setup-d trips the exit.
    assert report["status"] == "pass"


def test_non_strict_bundle_reports_missing_required_setup_d_observation(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    _enable_setup_d_with_tmp_root(module, tmp_path, monkeypatch)
    bundle_path = _write_bundle(tmp_path)

    rc = module.main([str(bundle_path), "--json"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert report["status"] == "pass"
    assert report["setup_d_observation"]["status"] == "fail"
    assert report["setup_d_observation"]["missing_evidence"] == [
        "missing reports/futures/setup_d/latest.json"
    ]


def test_non_strict_bundle_reports_invalid_required_setup_d_observation(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    _enable_setup_d_with_tmp_root(module, tmp_path, monkeypatch)
    _write_setup_d_report(tmp_path, "{not-json")
    bundle_path = _write_bundle(tmp_path)

    rc = module.main([str(bundle_path), "--json"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert report["status"] == "pass"
    assert report["setup_d_observation"]["status"] == "fail"
    assert report["setup_d_observation"]["missing_evidence"] == ["invalid JSON"]


def test_strict_bundle_accepts_valid_setup_d_observation_when_strategy_enabled(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    _enable_setup_d_with_tmp_root(module, tmp_path, monkeypatch)
    monkeypatch.setattr(module, "_now_kst", lambda: now, raising=False)
    _write_setup_d_report(tmp_path, _valid_setup_d_payload(now))
    bundle_path = _write_bundle(tmp_path)

    rc = module.main([str(bundle_path), "--json", "--strict", "--strict-setup-d"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert report["status"] == "pass"
    assert report["missing_evidence"] == []
    assert report["setup_d_observation"]["status"] == "pass"
    assert report["setup_d_observation"]["missing_evidence"] == []


@pytest.mark.parametrize(
    ("payload", "expected_missing"),
    [
        ("{not-json", "invalid JSON"),
        (
            ["not", "a", "mapping"],
            "expected JSON object",
        ),
        (
            {
                "strategy": "setup_a_gap_reversion",
                "signals": 3,
                "accepted": 2,
                "rejected": 1,
                "generated_at": "2026-06-28T12:00:00+00:00",
            },
            "expected strategy setup_d_vwap_reversion",
        ),
        (
            {
                "strategy": "setup_d_vwap_reversion",
                "signals": "many",
                "accepted": 2,
                "rejected": 1,
                "generated_at": "2026-06-28T12:00:00+00:00",
            },
            "signals expected non-negative integer",
        ),
        (
            {
                "strategy": "setup_d_vwap_reversion",
                "signals": 3,
                "accepted": 2,
                "generated_at": "2026-06-28T12:00:00+00:00",
            },
            "rejected missing",
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
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    _enable_setup_d_with_tmp_root(module, tmp_path, monkeypatch)
    monkeypatch.setattr(module, "_now_kst", lambda: now, raising=False)
    _write_setup_d_report(tmp_path, payload)
    bundle_path = _write_bundle(tmp_path)

    rc = module.main([str(bundle_path), "--json", "--strict", "--strict-setup-d"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert report["setup_d_observation"]["status"] == "fail"
    assert expected_missing in report["setup_d_observation"]["missing_evidence"]


@pytest.mark.parametrize(
    ("payload_update", "expected_missing"),
    [
        (
            {"accepted": -1, "rejected": 4},
            "accepted expected non-negative integer",
        ),
        (
            {"signals": 4},
            "signals count mismatch accepted+rejected",
        ),
        (
            {"generated_at": "not-a-date"},
            "generated_at invalid ISO datetime",
        ),
    ],
)
def test_strict_bundle_rejects_malformed_setup_d_counts_or_timestamp(
    tmp_path,
    monkeypatch,
    capsys,
    payload_update: dict[str, object],
    expected_missing: str,
) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    _enable_setup_d_with_tmp_root(module, tmp_path, monkeypatch)
    monkeypatch.setattr(module, "_now_kst", lambda: now, raising=False)
    payload = _valid_setup_d_payload(now)
    payload.update(payload_update)
    _write_setup_d_report(tmp_path, payload)
    bundle_path = _write_bundle(tmp_path)

    rc = module.main([str(bundle_path), "--json", "--strict", "--strict-setup-d"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert expected_missing in report["setup_d_observation"]["missing_evidence"]


def test_strict_bundle_rejects_stale_setup_d_observation(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    _enable_setup_d_with_tmp_root(module, tmp_path, monkeypatch)
    monkeypatch.setattr(module, "_now_kst", lambda: now, raising=False)
    _write_setup_d_report(
        tmp_path,
        _valid_setup_d_payload(now - timedelta(seconds=345601)),
    )
    bundle_path = _write_bundle(tmp_path)

    rc = module.main([str(bundle_path), "--json", "--strict", "--strict-setup-d"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert "generated_at stale" in report["setup_d_observation"]["missing_evidence"]


def test_strict_bundle_rejects_future_setup_d_observation(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    _enable_setup_d_with_tmp_root(module, tmp_path, monkeypatch)
    monkeypatch.setattr(module, "_now_kst", lambda: now, raising=False)
    _write_setup_d_report(
        tmp_path,
        _valid_setup_d_payload(now + timedelta(seconds=301)),
    )
    bundle_path = _write_bundle(tmp_path)

    rc = module.main([str(bundle_path), "--json", "--strict", "--strict-setup-d"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert (
        "generated_at is in the future"
        in report["setup_d_observation"]["missing_evidence"]
    )


def test_strict_bundle_rejects_zero_observation_setup_d_payload(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    _enable_setup_d_with_tmp_root(module, tmp_path, monkeypatch)
    monkeypatch.setattr(module, "_now_kst", lambda: now, raising=False)
    payload = _valid_setup_d_payload(now)
    payload.update({"signals": 0, "accepted": 0, "rejected": 0})
    _write_setup_d_report(tmp_path, payload)
    bundle_path = _write_bundle(tmp_path)

    rc = module.main([str(bundle_path), "--json", "--strict", "--strict-setup-d"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert (
        "expected at least one observed signal"
        in report["setup_d_observation"]["missing_evidence"]
    )


def test_strict_bundle_requires_evidence_when_setup_d_config_is_reshaped(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    config_path = tmp_path / "config/strategies/futures/setup_d_vwap_reversion.yaml"
    config_path.parent.mkdir(parents=True)
    # Present but reshaped/non-dict config must fail closed (require evidence).
    config_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(module, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "_SETUP_D_CONFIG_PATH", config_path)
    bundle_path = _write_bundle(tmp_path)

    rc = module.main([str(bundle_path), "--json", "--strict", "--strict-setup-d"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert (
        "missing reports/futures/setup_d/latest.json"
        in report["setup_d_observation"]["missing_evidence"]
    )


def test_strict_alone_does_not_gate_on_setup_d(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    module = importlib.import_module("scripts.ops.futures_evidence_bundle")
    _enable_setup_d_with_tmp_root(module, tmp_path, monkeypatch)
    bundle_path = _write_bundle(tmp_path)

    # Setup D is required and missing, but --strict alone never blocks on it.
    rc = module.main([str(bundle_path), "--json", "--strict"])
    report = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert report["status"] == "pass"
    assert report["setup_d_observation"]["status"] == "fail"
