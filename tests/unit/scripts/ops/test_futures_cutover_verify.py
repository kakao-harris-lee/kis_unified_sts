"""F-9 futures cutover verifier: read-only repo-state audit."""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path


def test_json_audit_reports_futures_cutover_readiness(capsys) -> None:
    module = importlib.import_module("scripts.ops.futures_cutover_verify")
    repo_root = Path.cwd()

    rc = module.main(["--repo-root", str(repo_root), "--json"])
    output = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert output["summary"]["ok"] is False
    checks = {check["name"]: check for check in output["checks"]}
    assert checks["compose futures profiles/services"]["status"] == "pass"
    assert "futures-pipeline" in checks["compose futures profiles/services"]["detail"]
    assert checks["futures daemon mode defaults"]["status"] == "pass"
    assert checks["kill-switch sentinel path"]["status"] == "warn"
    assert (
        "/var/run/kis_kill_switch.tripped"
        in checks["kill-switch sentinel path"]["detail"]
    )
    assert checks["gate 1 shadow evidence"]["status"] == "fail"
    assert checks["operator approval"]["status"] == "fail"

    strict_rc = module.main(["--repo-root", str(repo_root), "--json", "--strict"])
    strict_output = json.loads(capsys.readouterr().out)

    assert strict_rc == 1
    assert strict_output["summary"]["fail"] >= 2


def test_rollback_helper_defaults_to_dry_run() -> None:
    script = Path("scripts/ops/futures_cutover_rollback.sh")

    result = subprocess.run(
        ["bash", str(script)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "dry_run=1" in result.stdout
    assert "DRY-RUN: docker compose" in result.stdout
    assert "futures-decision-engine" in result.stdout
    assert "FUTURES_ORCHESTRATOR_ENABLED=true" in result.stdout
    assert not any(line.startswith("RUN:") for line in result.stdout.splitlines())
