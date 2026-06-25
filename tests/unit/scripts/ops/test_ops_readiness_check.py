"""Unit tests for the offline ops readiness checklist."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.ops.ops_readiness_check as m


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _minimal_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    _write(
        repo / "config" / "storage.yaml",
        "\n".join(
            [
                "runtime_storage:",
                "  backend: sqlite",
                "  sqlite:",
                "    path: data/runtime/dev/runtime.db",
                "market_data:",
                "  source: parquet",
            ]
        ),
    )
    _write(repo / ".env.example", "REDIS_URL=redis://localhost:6379/1\n")
    _write(repo / "shared" / "storage" / "runtime_ledger.py")
    _write(repo / "docs" / "testing" / "quant-ops-workbench-2026-06-25.md")
    _write(repo / "config" / "strategy_lab" / "defaults.yaml", "strategy_lab: {}\n")
    _write(repo / "shared" / "strategy_lab" / "evaluator.py")
    _write(repo / "shared" / "strategy_lab" / "order_bridge.py")
    _write(repo / "services" / "dashboard" / "routes" / "strategy_lab.py")
    _write(
        repo / "strategy-builder-ui" / "src" / "lib" / "dashboard" / "strategyLab.ts"
    )
    _write(repo / "tests" / "unit" / "trading" / "test_position_recovery.py")
    _write(repo / "scripts" / "trading" / "recover_positions.py")
    return repo


def test_offline_report_shape_and_no_live_http_by_default(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)

    report = m.build_report(repo_root=repo, require_live_http=False)

    assert set(report) == {
        "generated_at",
        "repo_root",
        "require_live_http",
        "overall_status",
        "sections",
        "remaining_external_operations",
    }
    assert report["require_live_http"] is False
    assert set(report["sections"]) == {
        "runtime_storage_smoke",
        "position_recovery_drill",
        "mlflow_tracking",
        "workbench_qa_artifacts",
        "strategy_lab_workflow",
    }
    assert report["sections"]["runtime_storage_smoke"]["status"] == "action_required"
    assert report["sections"]["workbench_qa_artifacts"]["status"] == "pass"
    assert report["sections"]["strategy_lab_workflow"]["status"] == "action_required"
    assert report["sections"]["mlflow_tracking"]["status"] == "action_required"
    assert (
        "Strategy Lab backtest/paper feedback and reactivation-gate depth"
        in report["remaining_external_operations"]
    )
    assert (
        "Redis+SQLite E2E smoke after cutovers"
        in report["remaining_external_operations"]
    )
    assert "MLflow restart/readiness" in report["remaining_external_operations"]


def test_missing_artifacts_are_action_required_not_pass(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    (repo / "docs" / "testing" / "quant-ops-workbench-2026-06-25.md").unlink()
    (repo / "tests" / "unit" / "trading" / "test_position_recovery.py").unlink()
    (repo / ".env.example").write_text(
        "REDIS_URL=redis://localhost:6379/0\n", encoding="utf-8"
    )

    report = m.build_report(repo_root=repo, require_live_http=False)

    assert report["overall_status"] == "action_required"
    assert report["sections"]["runtime_storage_smoke"]["status"] == "action_required"
    assert report["sections"]["position_recovery_drill"]["status"] == "action_required"
    assert report["sections"]["workbench_qa_artifacts"]["status"] == "action_required"
    assert report["sections"]["runtime_storage_smoke"]["checks"]["redis_db_1"] == {
        "status": "action_required",
        "detail": "No Redis URL using DB 1 found in env examples or compose config.",
    }


def test_ops_runbook_itself_does_not_count_as_workbench_qa_evidence(
    tmp_path: Path,
) -> None:
    repo = _minimal_repo(tmp_path)
    (repo / "docs" / "testing" / "quant-ops-workbench-2026-06-25.md").unlink()
    _write(repo / "docs" / "runbooks" / "ops-readiness-checks.md")

    report = m.build_report(repo_root=repo, require_live_http=False)

    assert report["sections"]["workbench_qa_artifacts"]["status"] == ("action_required")
    assert (
        report["sections"]["workbench_qa_artifacts"]["checks"]["qa_evidence_doc"][
            "detail"
        ]
        == "No Workbench QA evidence doc found."
    )


def test_cli_emits_json_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _minimal_repo(tmp_path)

    rc = m.main(["--repo-root", str(repo)])

    assert rc == 0
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["repo_root"] == str(repo)
    assert emitted["sections"]["runtime_storage_smoke"]["status"] == "action_required"
