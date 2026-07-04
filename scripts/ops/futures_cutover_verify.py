"""F-9 futures cutover verification - read-only repo-state audit.

This verifier does not start, stop, or mutate services. It inspects repo-local
compose/config/env/runbook state and reports whether the first cutover gates are
discoverable. Default mode is audit-only and exits 0 even when checks fail; use
``--strict`` to make failed checks return a nonzero exit code.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_EXPECTED_PROFILE_SERVICES: dict[str, tuple[str, ...]] = {
    "futures-ingest": ("futures-market-ingest",),
    "futures-pipeline": (
        "futures-decision-engine",
        "futures-risk-filter",
        "futures-order-router",
        "futures-monitor",
    ),
    "futures-killswitch": ("futures-kill-switch",),
}

_EXPECTED_DAEMON_ENV: tuple[tuple[str, str, str], ...] = (
    (
        "futures-decision-engine",
        "FUTURES_STRATEGY_DAEMON",
        "${FUTURES_PIPELINE_MODE:-shadow}",
    ),
    (
        "futures-risk-filter",
        "FUTURES_RISK_FILTER",
        "${FUTURES_PIPELINE_MODE:-shadow}",
    ),
    (
        "futures-monitor",
        "FUTURES_MONITOR_DAEMON",
        "${FUTURES_PIPELINE_MODE:-shadow}",
    ),
    (
        "futures-order-router",
        "FUTURES_ORDER_ROUTER",
        "${FUTURES_ORDER_ROUTER_MODE:-paper}",
    ),
    (
        "futures-order-router",
        "TRADING_MODE",
        "${FUTURES_EXECUTOR_TRADING_MODE:-PAPER}",
    ),
    (
        "futures-decision-engine",
        "FUTURES_STRATEGY_SYMBOL",
        "${FUTURES_STRATEGY_SYMBOL:-}",
    ),
)

_REDIS_DB_ENV_KEYS = (
    "REDIS_DB",
    "REDIS_STOCK_DB",
    "REDIS_FUTURES_DB",
    "REDIS_SYSTEM_DB",
)

_EVIDENCE_PLACEHOLDER_MARKERS = (
    "todo",
    "tbd",
    "placeholder",
    "replace me",
    "lorem ipsum",
    "record 3-5 trading days",
    "record 3\u20135 trading days",
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str
    source: str
    action: str | None = None

    def as_dict(self) -> dict[str, str]:
        result = {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "source": self.source,
        }
        if self.action:
            result["action"] = self.action
        return result


@dataclass(frozen=True)
class VerificationReport:
    repo_root: Path
    checks: tuple[CheckResult, ...]
    strict: bool = False

    @property
    def summary(self) -> dict[str, int | bool]:
        passed = sum(1 for check in self.checks if check.status == "pass")
        warned = sum(1 for check in self.checks if check.status == "warn")
        failed = sum(1 for check in self.checks if check.status == "fail")
        return {
            "pass": passed,
            "warn": warned,
            "fail": failed,
            "ok": failed == 0 and warned == 0,
            "strict": self.strict,
        }

    def exit_code(self) -> int:
        return 1 if self.strict and self.summary["fail"] else 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "repo_root": str(self.repo_root),
            "summary": self.summary,
            "checks": [check.as_dict() for check in self.checks],
        }


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not parse to a mapping")
    return data


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _as_profiles(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, Iterable):
        return {str(item) for item in value}
    return {str(value)}


def _service_env(service: dict[str, Any]) -> dict[str, str]:
    env = service.get("environment") or {}
    if isinstance(env, dict):
        return {str(key): str(value) for key, value in env.items()}
    if isinstance(env, list):
        parsed: dict[str, str] = {}
        for item in env:
            key, _, value = str(item).partition("=")
            parsed[key] = value
        return parsed
    return {}


def _check_compose_profiles(repo_root: Path, compose: dict[str, Any]) -> CheckResult:
    services = compose.get("services") or {}
    failures: list[str] = []
    present: list[str] = []
    for profile, expected_services in _EXPECTED_PROFILE_SERVICES.items():
        profile_present: list[str] = []
        for service_name in expected_services:
            service = services.get(service_name)
            if not isinstance(service, dict):
                failures.append(f"{service_name} missing")
                continue
            if profile not in _as_profiles(service.get("profiles")):
                failures.append(f"{service_name} missing profile {profile}")
                continue
            profile_present.append(service_name)
        present.append(f"{profile}=[{', '.join(profile_present)}]")

    status = "fail" if failures else "pass"
    detail = "; ".join(failures or present)
    return CheckResult(
        name="compose futures profiles/services",
        status=status,
        detail=detail,
        source=str(repo_root / "docker-compose.yml"),
        action=None if status == "pass" else "Restore the F-9 compose profile wiring.",
    )


def _check_daemon_defaults(repo_root: Path, compose: dict[str, Any]) -> CheckResult:
    services = compose.get("services") or {}
    failures: list[str] = []
    actuals: list[str] = []
    for service_name, env_key, expected_value in _EXPECTED_DAEMON_ENV:
        service = services.get(service_name)
        env = _service_env(service) if isinstance(service, dict) else {}
        actual = env.get(env_key)
        if actual != expected_value:
            failures.append(f"{service_name}.{env_key}={actual!r}")
        else:
            actuals.append(f"{service_name}.{env_key}={actual}")

    status = "fail" if failures else "pass"
    return CheckResult(
        name="futures daemon mode defaults",
        status=status,
        detail="; ".join(failures or actuals),
        source=str(repo_root / "docker-compose.yml"),
        action=(
            None
            if status == "pass"
            else "Keep shadow/paper/PAPER defaults until the gated live cutover."
        ),
    )


def _check_redis_db_one(repo_root: Path, compose: dict[str, Any]) -> CheckResult:
    redis_env = compose.get("x-redis-runtime-env") or {}
    failures: list[str] = []
    details: list[str] = []
    if not isinstance(redis_env, dict):
        failures.append("x-redis-runtime-env missing")
    else:
        for key in _REDIS_DB_ENV_KEYS:
            actual = str(redis_env.get(key))
            if actual != f"${{{key}:-1}}":
                failures.append(f"{key}={actual!r}")
            else:
                details.append(f"{key}=1")
        redis_url = str(redis_env.get("REDIS_URL"))
        if not redis_url.endswith("@redis:6379/1}"):
            failures.append(f"REDIS_URL={redis_url!r}")
        else:
            details.append("REDIS_URL db=1")

    status = "fail" if failures else "pass"
    return CheckResult(
        name="redis db 1 wiring",
        status=status,
        detail="; ".join(failures or details),
        source=str(repo_root / "docker-compose.yml"),
        action=None if status == "pass" else "Keep futures Redis wiring on DB 1.",
    )


def _check_live_guard(repo_root: Path) -> CheckResult:
    path = repo_root / "config" / "futures_live.yaml"
    try:
        cfg = _load_yaml(path).get("futures_live") or {}
    except Exception as exc:
        return CheckResult(
            name="futures live guard config",
            status="fail",
            detail=f"unreadable: {type(exc).__name__}",
            source=str(path),
            action="Restore config/futures_live.yaml.",
        )
    enabled = cfg.get("enabled")
    suspend_key = cfg.get("suspend_key")
    failures: list[str] = []
    if enabled is not False:
        failures.append(f"enabled={enabled!r}")
    if suspend_key != "futures:live:suspended":
        failures.append(f"suspend_key={suspend_key!r}")
    status = "fail" if failures else "pass"
    return CheckResult(
        name="futures live guard config",
        status=status,
        detail="; ".join(
            failures or ["enabled=false", "suspend_key=futures:live:suspended"]
        ),
        source=str(path),
        action=(
            None
            if status == "pass"
            else "Keep live orders blocked by config and Redis suspend key pre-cutover."
        ),
    )


def _check_kill_switch_sentinel(repo_root: Path) -> CheckResult:
    path = repo_root / "config" / "kill_switch.yaml"
    try:
        cfg = _load_yaml(path).get("kill_switch") or {}
    except Exception as exc:
        return CheckResult(
            name="kill-switch sentinel path",
            status="fail",
            detail=f"unreadable: {type(exc).__name__}",
            source=str(path),
            action="Restore config/kill_switch.yaml.",
        )
    sentinel_path = str(cfg.get("sentinel_path", ""))
    if not sentinel_path:
        return CheckResult(
            name="kill-switch sentinel path",
            status="fail",
            detail="kill_switch.sentinel_path missing",
            source=str(path),
            action="Set a kill_switch.sentinel_path before live cutover.",
        )
    if sentinel_path.startswith("/var/run/"):
        return CheckResult(
            name="kill-switch sentinel path",
            status="warn",
            detail=sentinel_path,
            source=str(path),
            action=(
                "Before live, move sentinel_path under the shared data/runtime mount "
                "so order_router and kill_switch see the same file."
            ),
        )
    status = "pass" if "data/runtime" in sentinel_path else "warn"
    return CheckResult(
        name="kill-switch sentinel path",
        status=status,
        detail=sentinel_path,
        source=str(path),
        action=(
            None
            if status == "pass"
            else "Confirm this path is shared by both containers."
        ),
    )


def _active_env_line(text: str, key: str) -> bool:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=", re.MULTILINE)
    return bool(pattern.search(text))


def _check_orchestrator_guard(repo_root: Path) -> CheckResult:
    # The F-8 guard originally lived in cli/main.py; the runtime-command
    # refactor (#59e18a72) moved it into cli/commands/trading_control.py, which
    # cli/main.py re-exports. Scan both so the audit follows the guard's real
    # location instead of false-negating after the split.
    cli_paths = (
        repo_root / "cli" / "main.py",
        repo_root / "cli" / "commands" / "trading_control.py",
    )
    env_paths = (
        repo_root / ".env.paper.example",
        repo_root / ".env.live.example",
    )
    guard_files = [
        path.name
        for path in cli_paths
        if path.exists() and "FUTURES_ORCHESTRATOR_ENABLED" in _read_text(path)
    ]
    cli_has_guard = bool(guard_files)
    cli_source = "; ".join(str(path) for path in cli_paths)
    env_with_knob = [
        path.name
        for path in env_paths
        if path.exists()
        and _active_env_line(_read_text(path), "FUTURES_ORCHESTRATOR_ENABLED")
    ]
    if cli_has_guard and env_with_knob:
        return CheckResult(
            name="futures orchestrator guard knob",
            status="pass",
            detail=(
                f"guard in {', '.join(guard_files)}; "
                f"env knob in {', '.join(env_with_knob)}"
            ),
            source=f"{cli_source}; {', '.join(str(path) for path in env_paths)}",
        )
    if cli_has_guard:
        return CheckResult(
            name="futures orchestrator guard knob",
            status="warn",
            detail=(
                f"guard exists in {', '.join(guard_files)}; "
                "no active env example knob found"
            ),
            source=f"{cli_source}; {', '.join(str(path) for path in env_paths)}",
            action=(
                "At cutover, set FUTURES_ORCHESTRATOR_ENABLED=false in the operator "
                "env file before keeping trader-futures stopped."
            ),
        )
    return CheckResult(
        name="futures orchestrator guard knob",
        status="fail",
        detail="FUTURES_ORCHESTRATOR_ENABLED guard not found",
        source=cli_source,
        action="Restore the F-8 double-trade guard before F-9 cutover.",
    )


def _nonempty_file(path: Path) -> bool:
    return path.exists() and path.is_file() and bool(_read_text(path).strip())


def _gate1_evidence_failure(path: Path) -> str | None:
    """Return why a Gate 1 evidence file is not acceptable.

    This is deliberately lightweight. The verifier cannot prove that operators
    actually completed multi-day shadow validation, but it can reject empty
    files and runbook templates that still contain obvious placeholder markers.
    """

    if not path.exists() or not path.is_file():
        return f"missing: {path}"
    text = _read_text(path).strip()
    if not text:
        return f"empty: {path}"
    lowered = text.lower()
    marker = next(
        (
            placeholder_marker
            for placeholder_marker in _EVIDENCE_PLACEHOLDER_MARKERS
            if placeholder_marker in lowered
        ),
        None,
    )
    if marker is not None:
        return f"placeholder marker {marker!r}: {path}"
    return None


def _check_gate1_evidence(
    repo_root: Path, evidence_paths: tuple[Path, ...]
) -> CheckResult:
    if not evidence_paths:
        return CheckResult(
            name="gate 1 shadow evidence",
            status="fail",
            detail="no --gate1-evidence file supplied",
            source=str(
                repo_root / "docs" / "runbooks" / "futures-pipeline-cutover-f9.md"
            ),
            action="Provide 3-5 trading days of shadow-validation evidence.",
        )
    failures = [
        failure
        for path in evidence_paths
        if (failure := _gate1_evidence_failure(path)) is not None
    ]
    status = "fail" if failures else "pass"
    return CheckResult(
        name="gate 1 shadow evidence",
        status=status,
        detail=(
            f"invalid evidence: {', '.join(failures)}"
            if failures
            else f"evidence files={len(evidence_paths)}"
        ),
        source=", ".join(str(path) for path in evidence_paths),
        action=(
            None
            if status == "pass"
            else "Supply real shadow evidence files without template placeholders."
        ),
    )


def _check_operator_approval(
    repo_root: Path, approval_file: Path | None
) -> CheckResult:
    if approval_file is None:
        return CheckResult(
            name="operator approval",
            status="fail",
            detail="no --operator-approval-file supplied",
            source=str(
                repo_root / "docs" / "runbooks" / "futures-pipeline-cutover-f9.md"
            ),
            action="Provide the written operator approval file before live cutover.",
        )
    status = "pass" if _nonempty_file(approval_file) else "fail"
    return CheckResult(
        name="operator approval",
        status=status,
        detail=(
            str(approval_file)
            if status == "pass"
            else f"missing/empty: {approval_file}"
        ),
        source=str(approval_file),
        action=None if status == "pass" else "Supply a non-empty approval file.",
    )


def run_checks(
    *,
    repo_root: Path,
    strict: bool = False,
    gate1_evidence: tuple[Path, ...] = (),
    operator_approval_file: Path | None = None,
) -> VerificationReport:
    repo_root = repo_root.resolve()
    compose = _load_yaml(repo_root / "docker-compose.yml")
    checks = (
        _check_compose_profiles(repo_root, compose),
        _check_daemon_defaults(repo_root, compose),
        _check_redis_db_one(repo_root, compose),
        _check_live_guard(repo_root),
        _check_kill_switch_sentinel(repo_root),
        _check_orchestrator_guard(repo_root),
        _check_gate1_evidence(repo_root, gate1_evidence),
        _check_operator_approval(repo_root, operator_approval_file),
    )
    return VerificationReport(repo_root=repo_root, checks=checks, strict=strict)


def render_human(report: VerificationReport) -> str:
    labels = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}
    lines = [
        "F-9 futures cutover verification (read-only)",
        f"repo: {report.repo_root}",
    ]
    for check in report.checks:
        lines.append(f"[{labels[check.status]}] {check.name}: {check.detail}")
        lines.append(f"       source: {check.source}")
        if check.action:
            lines.append(f"       action: {check.action}")
    summary = report.summary
    lines.append(
        "summary: "
        f"pass={summary['pass']} warn={summary['warn']} "
        f"fail={summary['fail']} strict={summary['strict']}"
    )
    if summary["fail"] and not report.strict:
        lines.append("default audit mode exits 0; use --strict to enforce failures")
    return "\n".join(lines)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only F-9 futures cutover verification audit"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root to inspect (default: current directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human text",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit nonzero when any failed checks are present",
    )
    parser.add_argument(
        "--gate1-evidence",
        action="append",
        type=Path,
        default=[],
        help=(
            "Gate 1 shadow-validation evidence file, repeatable; files must be "
            "non-empty and free of obvious TODO/TBD/placeholder markers"
        ),
    )
    parser.add_argument(
        "--operator-approval-file",
        "--operator-approval",
        dest="operator_approval_file",
        type=Path,
        help="Non-empty written operator approval file",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = run_checks(
        repo_root=args.repo_root,
        strict=args.strict,
        gate1_evidence=tuple(args.gate1_evidence),
        operator_approval_file=args.operator_approval_file,
    )
    if args.json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        print(render_human(report))
    return report.exit_code()


if __name__ == "__main__":
    import sys

    sys.exit(main())
