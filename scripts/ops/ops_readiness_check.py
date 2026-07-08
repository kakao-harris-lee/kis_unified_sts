"""Offline ops readiness checklist for common runtime follow-ups.

The default mode is intentionally offline: it reads repository files,
configuration, and locally installed packages only. Live HTTP probes run
only when explicitly requested.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import yaml

STATUS_PASS = "pass"
STATUS_ACTION_REQUIRED = "action_required"

SECTION_NAMES = (
    "runtime_storage_smoke",
    "position_recovery_drill",
    "mlflow_tracking",
    "workbench_qa_artifacts",
    "strategy_lab_workflow",
    "indicator_engine_deps",
)

WORKBENCH_QA_DOCS = ("docs/testing/quant-ops-workbench-2026-06-25.md",)

POSITION_RECOVERY_FILES = (
    "tests/unit/trading/test_position_recovery.py",
    "scripts/trading/recover_positions.py",
)

STRATEGY_LAB_FILES = (
    "config/strategy_lab/defaults.yaml",
    "shared/strategy_lab/evaluator.py",
    "shared/strategy_lab/order_bridge.py",
    "services/dashboard/routes/strategy_lab.py",
    "strategy-builder-ui/src/lib/dashboard/strategyLab.ts",
)


def _check(status: str, detail: str) -> dict[str, str]:
    return {"status": status, "detail": detail}


def _section(checks: dict[str, dict[str, str]]) -> dict[str, Any]:
    status = (
        STATUS_ACTION_REQUIRED
        if any(item["status"] != STATUS_PASS for item in checks.values())
        else STATUS_PASS
    )
    return {"status": status, "checks": checks}


def _exists(repo_root: Path, relative_path: str) -> bool:
    return (repo_root / relative_path).exists()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _load_yaml(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    if not text:
        return {}
    parsed = yaml.safe_load(text)
    return parsed if isinstance(parsed, dict) else {}


def _redis_db_one_present(repo_root: Path) -> bool:
    redis_url_re = re.compile(r"redis://[^\s\"']+/1(?:[^\d]|$)")
    candidates = [
        *repo_root.glob(".env*.example"),
        repo_root / "docker-compose.yml",
        repo_root / "config" / "monitoring.yaml",
    ]
    return any(redis_url_re.search(_read_text(path)) for path in candidates)


def _env_or_example_contains(repo_root: Path, name: str) -> tuple[bool, str]:
    if os.environ.get(name):
        return True, f"{name} is set in the current environment."
    for path in sorted(repo_root.glob(".env*.example")):
        text = _read_text(path)
        if re.search(rf"^{re.escape(name)}\s*=", text, flags=re.MULTILINE):
            return True, f"{name} is documented in {path.relative_to(repo_root)}."
    return False, f"{name} is not set and no env example documents it."


def check_runtime_storage(repo_root: Path) -> dict[str, Any]:
    storage_path = repo_root / "config" / "storage.yaml"
    storage = _load_yaml(storage_path)
    runtime_storage = storage.get("runtime_storage", {})
    sqlite_config = runtime_storage.get("sqlite", {})
    checks = {
        "storage_config": _check(
            STATUS_PASS if storage_path.exists() else STATUS_ACTION_REQUIRED,
            (
                "config/storage.yaml exists."
                if storage_path.exists()
                else "config/storage.yaml is missing."
            ),
        ),
        "runtime_backend": _check(
            (
                STATUS_PASS
                if runtime_storage.get("backend") == "sqlite"
                else STATUS_ACTION_REQUIRED
            ),
            f"runtime_storage.backend={runtime_storage.get('backend')!r}.",
        ),
        "sqlite_path": _check(
            STATUS_PASS if sqlite_config.get("path") else STATUS_ACTION_REQUIRED,
            (
                f"runtime SQLite path={sqlite_config.get('path')!r}."
                if sqlite_config.get("path")
                else "runtime_storage.sqlite.path is missing."
            ),
        ),
        "runtime_ledger_file": _check(
            (
                STATUS_PASS
                if _exists(repo_root, "shared/storage/runtime_ledger.py")
                else STATUS_ACTION_REQUIRED
            ),
            (
                "shared/storage/runtime_ledger.py exists."
                if _exists(repo_root, "shared/storage/runtime_ledger.py")
                else "shared/storage/runtime_ledger.py is missing."
            ),
        ),
        "redis_db_1": _check(
            STATUS_PASS if _redis_db_one_present(repo_root) else STATUS_ACTION_REQUIRED,
            (
                "Redis URL using DB 1 found in env examples or compose config."
                if _redis_db_one_present(repo_root)
                else "No Redis URL using DB 1 found in env examples or compose config."
            ),
        ),
        "e2e_smoke_execution": _check(
            STATUS_ACTION_REQUIRED,
            "Run Redis+SQLite E2E smoke after runtime cutovers.",
        ),
    }
    return _section(checks)


def check_position_recovery(repo_root: Path) -> dict[str, Any]:
    checks = {
        relative_path: _check(
            (
                STATUS_PASS
                if _exists(repo_root, relative_path)
                else STATUS_ACTION_REQUIRED
            ),
            (
                f"{relative_path} exists."
                if _exists(repo_root, relative_path)
                else f"{relative_path} is missing."
            ),
        )
        for relative_path in POSITION_RECOVERY_FILES
    }
    checks["drill_execution"] = _check(
        STATUS_ACTION_REQUIRED,
        "Run an operator position-recovery drill after runtime cutovers.",
    )
    return _section(checks)


def check_mlflow_tracking(repo_root: Path) -> dict[str, Any]:
    configured, detail = _env_or_example_contains(repo_root, "MLFLOW_TRACKING_URI")
    checks = {
        "tracking_uri": _check(
            STATUS_PASS if configured else STATUS_ACTION_REQUIRED,
            detail,
        ),
        "restart_readiness": _check(
            STATUS_ACTION_REQUIRED,
            "Confirm MLflow restart/readiness externally when needed.",
        ),
    }
    return _section(checks)


def check_workbench_qa_artifacts(repo_root: Path) -> dict[str, Any]:
    found = [path for path in WORKBENCH_QA_DOCS if _exists(repo_root, path)]
    checks = {
        "qa_evidence_doc": _check(
            STATUS_PASS if found else STATUS_ACTION_REQUIRED,
            (
                f"QA evidence found: {', '.join(found)}."
                if found
                else "No Workbench QA evidence doc found."
            ),
        ),
        "route_refresh": _check(
            STATUS_ACTION_REQUIRED,
            "Refresh Workbench QA artifacts when operator routes change.",
        ),
    }
    if found:
        checks["route_refresh"] = _check(
            STATUS_PASS,
            "Current route-change policy is documented by the QA evidence artifact.",
        )
    return _section(checks)


def check_strategy_lab_workflow(repo_root: Path) -> dict[str, Any]:
    checks = {
        relative_path: _check(
            (
                STATUS_PASS
                if _exists(repo_root, relative_path)
                else STATUS_ACTION_REQUIRED
            ),
            (
                f"{relative_path} exists."
                if _exists(repo_root, relative_path)
                else f"{relative_path} is missing."
            ),
        )
        for relative_path in STRATEGY_LAB_FILES
    }
    checks["non_workbench_feedback"] = _check(
        STATUS_ACTION_REQUIRED,
        "Backtest/paper feedback and reactivation-gate workflow depth remain external follow-ups.",
    )
    return _section(checks)


def _http_probe(url: str, timeout_seconds: float) -> dict[str, str]:
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 0)
    except URLError as exc:
        return _check(STATUS_ACTION_REQUIRED, f"{url} unreachable: {exc}.")
    except TimeoutError:
        return _check(STATUS_ACTION_REQUIRED, f"{url} timed out.")
    if 200 <= status < 500:
        return _check(STATUS_PASS, f"{url} returned HTTP {status}.")
    return _check(STATUS_ACTION_REQUIRED, f"{url} returned HTTP {status}.")


def check_live_http(
    *,
    require_live_http: bool,
    http_urls: list[str],
    timeout_seconds: float,
) -> dict[str, dict[str, str]]:
    if not require_live_http:
        return {}
    if not http_urls:
        return {
            "live_http_urls": _check(
                STATUS_ACTION_REQUIRED,
                "--require-live-http was set but no --http-url values were provided.",
            )
        }
    return {
        f"live_http_{index}": _http_probe(url, timeout_seconds)
        for index, url in enumerate(http_urls, start=1)
    }


def check_indicator_engine_deps() -> dict[str, Any]:
    """Verify the indicator-engine native dependencies in THIS environment.

    A missing TA-Lib wheel makes the engine's TA-Lib backend degrade
    gracefully, which lets indicator shadow-parity gates silently skip on
    the deploy host instead of failing — so surface it as an operator
    action item. vectorbt is an optional ``.[backtest]`` extra (WS-A4/P3)
    and is reported as informational only.
    """
    try:
        import talib  # noqa: F401

        talib_check = _check(STATUS_PASS, "talib imports in this environment.")
    except Exception as exc:  # pragma: no cover - depends on host env
        talib_check = _check(
            STATUS_ACTION_REQUIRED,
            f"talib import failed ({exc}); run: pip install -e '.[dev]'",
        )
    try:
        import vectorbt  # noqa: F401

        vectorbt_check = _check(
            STATUS_PASS, "vectorbt (optional backtest extra) is importable."
        )
    except Exception:
        vectorbt_check = _check(
            STATUS_PASS,
            "vectorbt not installed — optional .[backtest] extra, only needed "
            "for vectorbt backtest (WS-A4/P3) work.",
        )
    return _section({"talib": talib_check, "vectorbt_optional": vectorbt_check})


def _external_operations(sections: dict[str, dict[str, Any]]) -> list[str]:
    operations: list[str] = []
    if sections["runtime_storage_smoke"]["status"] != STATUS_PASS:
        operations.append("Redis+SQLite E2E smoke after cutovers")
    if sections["position_recovery_drill"]["status"] != STATUS_PASS:
        operations.append("position-recovery drill")
    if sections["mlflow_tracking"]["status"] != STATUS_PASS:
        operations.append("MLflow restart/readiness")
    if sections["workbench_qa_artifacts"]["status"] != STATUS_PASS:
        operations.append("Workbench QA artifact refresh when routes change")
    if sections["strategy_lab_workflow"]["status"] != STATUS_PASS:
        operations.append(
            "Strategy Lab backtest/paper feedback and reactivation-gate depth"
        )
    if sections["indicator_engine_deps"]["status"] != STATUS_PASS:
        operations.append(
            "install TA-Lib in the runtime venv (pip install -e '.[dev]')"
        )
    return operations


def build_report(
    *,
    repo_root: Path,
    require_live_http: bool = False,
    http_urls: list[str] | None = None,
    http_timeout_seconds: float = 3.0,
) -> dict[str, Any]:
    """Build a JSON-serializable readiness report."""
    repo_root = repo_root.resolve()
    sections = {
        "runtime_storage_smoke": check_runtime_storage(repo_root),
        "position_recovery_drill": check_position_recovery(repo_root),
        "mlflow_tracking": check_mlflow_tracking(repo_root),
        "workbench_qa_artifacts": check_workbench_qa_artifacts(repo_root),
        "strategy_lab_workflow": check_strategy_lab_workflow(repo_root),
        "indicator_engine_deps": check_indicator_engine_deps(),
    }
    live_http_checks = check_live_http(
        require_live_http=require_live_http,
        http_urls=http_urls or [],
        timeout_seconds=http_timeout_seconds,
    )
    if live_http_checks:
        sections["runtime_storage_smoke"]["checks"].update(live_http_checks)
        sections["runtime_storage_smoke"] = _section(
            sections["runtime_storage_smoke"]["checks"]
        )

    remaining = _external_operations(sections)
    overall_status = STATUS_ACTION_REQUIRED if remaining else STATUS_PASS
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "repo_root": str(repo_root),
        "require_live_http": require_live_http,
        "overall_status": overall_status,
        "sections": {name: sections[name] for name in SECTION_NAMES},
        "remaining_external_operations": remaining,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Emit a JSON ops readiness checklist report."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root to inspect. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--require-live-http",
        action="store_true",
        help="Enable explicit HTTP readiness probes. No network calls run by default.",
    )
    parser.add_argument(
        "--http-url",
        action="append",
        default=[],
        help="HTTP URL to probe when --require-live-http is set. May be repeated.",
    )
    parser.add_argument(
        "--http-timeout-seconds",
        type=float,
        default=3.0,
        help="Timeout for each explicit HTTP probe.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        repo_root=args.repo_root,
        require_live_http=args.require_live_http,
        http_urls=args.http_url,
        http_timeout_seconds=args.http_timeout_seconds,
    )
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
