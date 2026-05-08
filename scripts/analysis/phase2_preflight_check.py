#!/usr/bin/env python3
"""Phase 2 Pre-flight Check — operator-run Friday EOD verification.

Automates the runbook's pre-flight check section
(``docs/runbooks/phase2-startup.md`` § "Pre-flight check") plus three
extra integration checks that the runbook describes verbally:

  1. ClickHouse migrations applied (V1–V5)
  2. shadow_mode flag set to true in rl_mppo.yaml
  3. Setup A/C strategy.enabled true (paper-only)
  4. futures_live.enabled remains false (paper mode)
  5. Crontab has both Phase 2 entries (daily verification + weekly counterfactual)
  6. Prometheus shadow_loggers alerts loaded
  7. Telegram briefing channel credentials present

Each check returns PASS / FAIL / WARN with the actual observed value.
Exit code 0 = all critical checks PASS, 1 = at least one FAIL,
2 = script-level error.

Idempotent and read-only — safe to run any time.

Usage::

    python -m scripts.analysis.phase2_preflight_check
    python -m scripts.analysis.phase2_preflight_check --json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

_REPO_ROOT = Path(__file__).resolve().parents[2]

CheckStatus = Literal["PASS", "FAIL", "WARN"]


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    observed: str
    expected: str
    detail: str = ""


@dataclass
class PreflightReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def all_critical_pass(self) -> bool:
        return not any(c.status == "FAIL" for c in self.checks)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_ch_migrations(report: PreflightReport) -> None:
    """ClickHouse schema_migrations contains V1–V5."""
    expected = {"V1", "V2", "V3", "V4", "V5"}
    user = os.environ.get("CLICKHOUSE_USER", "default")
    password = os.environ.get("CLICKHOUSE_PASSWORD", "")
    try:
        result = subprocess.run(
            [
                "clickhouse-client",
                "--user", user,
                "--password", password,
                "-q",
                "SELECT version FROM kospi.schema_migrations ORDER BY version FORMAT TabSeparated",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            report.checks.append(CheckResult(
                name="clickhouse_migrations_v1_v5",
                status="FAIL",
                observed=f"clickhouse-client failed: {result.stderr.strip()[:200]}",
                expected="V1, V2, V3, V4, V5 (one per line)",
            ))
            return
        applied = set(result.stdout.strip().splitlines())
        missing = expected - applied
        if missing:
            report.checks.append(CheckResult(
                name="clickhouse_migrations_v1_v5",
                status="FAIL",
                observed=f"applied={sorted(applied)}, missing={sorted(missing)}",
                expected="V1, V2, V3, V4, V5 all applied",
                detail=(
                    "Run `python3 -m scripts.migrations.apply_clickhouse_migrations` "
                    "to apply pending migrations."
                ),
            ))
        else:
            report.checks.append(CheckResult(
                name="clickhouse_migrations_v1_v5",
                status="PASS",
                observed=f"applied={sorted(applied)}",
                expected="V1–V5",
            ))
    except FileNotFoundError:
        report.checks.append(CheckResult(
            name="clickhouse_migrations_v1_v5",
            status="WARN",
            observed="clickhouse-client binary not found in PATH",
            expected="V1–V5",
            detail="Install clickhouse-client or run from a host that has it.",
        ))
    except subprocess.TimeoutExpired:
        report.checks.append(CheckResult(
            name="clickhouse_migrations_v1_v5",
            status="FAIL",
            observed="timeout (10s)",
            expected="ClickHouse reachable on configured host:port",
        ))


def _check_shadow_mode(report: PreflightReport) -> None:
    """rl_mppo.yaml shadow_mode == true."""
    path = _REPO_ROOT / "config" / "strategies" / "futures" / "rl_mppo.yaml"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        report.checks.append(CheckResult(
            name="rl_mppo_shadow_mode_true",
            status="FAIL",
            observed=f"cannot read {path.name}: {e}",
            expected="shadow_mode: true",
        ))
        return
    has_true = any(
        line.strip().startswith("shadow_mode: true")
        for line in text.splitlines()
    )
    has_false = any(
        line.strip().startswith("shadow_mode: false")
        for line in text.splitlines()
    )
    if has_true and not has_false:
        report.checks.append(CheckResult(
            name="rl_mppo_shadow_mode_true",
            status="PASS",
            observed="shadow_mode: true",
            expected="shadow_mode: true",
        ))
    else:
        report.checks.append(CheckResult(
            name="rl_mppo_shadow_mode_true",
            status="FAIL",
            observed=f"true={has_true}, false={has_false}",
            expected="exactly one `shadow_mode: true` line",
            detail=(
                "Edit config/strategies/futures/rl_mppo.yaml and set "
                "entry.params.shadow_mode: true."
            ),
        ))


def _check_setup_strategies_enabled(report: PreflightReport) -> None:
    """Setup A and Setup C strategy.enabled true."""
    for setup_name, path_suffix in (
        ("setup_a_gap_reversion", "setup_a_gap_reversion.yaml"),
        ("setup_c_event_reaction", "setup_c_event_reaction.yaml"),
    ):
        path = _REPO_ROOT / "config" / "strategies" / "futures" / path_suffix
        try:
            import yaml

            with path.open(encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            enabled = cfg.get("strategy", {}).get("enabled")
        except Exception as e:
            report.checks.append(CheckResult(
                name=f"strategy_enabled_{setup_name}",
                status="FAIL",
                observed=f"yaml load failed: {e}",
                expected="strategy.enabled: true",
            ))
            continue
        if enabled is True:
            report.checks.append(CheckResult(
                name=f"strategy_enabled_{setup_name}",
                status="PASS",
                observed="true",
                expected="true",
            ))
        else:
            report.checks.append(CheckResult(
                name=f"strategy_enabled_{setup_name}",
                status="FAIL",
                observed=str(enabled),
                expected="true",
                detail=f"Set strategy.enabled: true in {path.name}.",
            ))


def _check_futures_live_disabled(report: PreflightReport) -> None:
    """futures_live.enabled must remain false (paper-only)."""
    path = _REPO_ROOT / "config" / "futures_live.yaml"
    try:
        import yaml

        with path.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        # YAML structure: `futures_live: { enabled: false, ... }`
        enabled = cfg.get("futures_live", {}).get("enabled")
    except Exception as e:
        report.checks.append(CheckResult(
            name="futures_live_disabled",
            status="FAIL",
            observed=f"yaml load failed: {e}",
            expected="enabled: false",
        ))
        return
    if enabled is False:
        report.checks.append(CheckResult(
            name="futures_live_disabled",
            status="PASS",
            observed="false (paper-only)",
            expected="false",
        ))
    else:
        report.checks.append(CheckResult(
            name="futures_live_disabled",
            status="FAIL",
            observed=str(enabled),
            expected="false",
            detail=(
                "Phase 2 is paper-only.  Live activation requires Gate 1-3 "
                "in docs/runbooks/phase5-verification.md."
            ),
        ))


def _check_crontab_entries(report: PreflightReport) -> None:
    """crontab has daily verification + weekly counterfactual entries."""
    expected_entries = [
        ("daily_verification", "phase2_daily_verification.sh"),
        ("weekly_counterfactual", "counterfactual_weekly.sh"),
    ]
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            report.checks.append(CheckResult(
                name="crontab_phase2_entries",
                status="FAIL",
                observed=f"crontab -l failed: {result.stderr.strip()[:100]}",
                expected="2 Phase 2 cron entries registered",
            ))
            return
        crontab = result.stdout
        missing: list[str] = []
        for label, fragment in expected_entries:
            if fragment not in crontab:
                missing.append(label)
        if missing:
            report.checks.append(CheckResult(
                name="crontab_phase2_entries",
                status="FAIL",
                observed=f"missing={missing}",
                expected="both phase2_daily_verification.sh AND counterfactual_weekly.sh",
                detail=(
                    "Re-run the operator commands documented in PR #184 / #188 "
                    "to install the missing crontab entries."
                ),
            ))
        else:
            report.checks.append(CheckResult(
                name="crontab_phase2_entries",
                status="PASS",
                observed="both registered",
                expected="both",
            ))
    except FileNotFoundError:
        report.checks.append(CheckResult(
            name="crontab_phase2_entries",
            status="WARN",
            observed="crontab binary not found",
            expected="cron daemon installed",
        ))


def _check_prometheus_alerts(report: PreflightReport) -> None:
    """Prometheus has shadow_loggers alert group loaded."""
    base_url = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
    expected_alerts = {
        "ShadowLoggerBatchesDropped",
        "ShadowLoggerFlushStale",
        "ShadowLoggerBufferFillingUp",
        "ShadowLoggerBufferNearOverflow",
    }
    try:
        url = f"{base_url.rstrip('/')}/api/v1/rules"
        with urllib.request.urlopen(url, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        loaded: set[str] = set()
        for grp in payload.get("data", {}).get("groups", []):
            if grp.get("name") == "shadow_loggers":
                for rule in grp.get("rules", []):
                    name = rule.get("name")
                    if name:
                        loaded.add(name)
        missing = expected_alerts - loaded
        if missing:
            report.checks.append(CheckResult(
                name="prometheus_shadow_logger_alerts",
                status="FAIL",
                observed=f"loaded={sorted(loaded)}, missing={sorted(missing)}",
                expected="all 4 ShadowLogger* alerts",
                detail=(
                    "If alert_rules.yml file was edited, restart "
                    "the Prometheus container so the bind mount picks up "
                    "the new inode."
                ),
            ))
        else:
            report.checks.append(CheckResult(
                name="prometheus_shadow_logger_alerts",
                status="PASS",
                observed="all 4 alerts loaded",
                expected="all 4",
            ))
    except urllib.error.URLError as e:
        report.checks.append(CheckResult(
            name="prometheus_shadow_logger_alerts",
            status="WARN",
            observed=f"prometheus unreachable: {e}",
            expected="Prometheus reachable",
            detail=(
                "Optional check — alerts won't fire if Prometheus is "
                "actually down, but the daily-verification script handles "
                "that case (gate omitted, not failed)."
            ),
        ))
    except Exception as e:
        report.checks.append(CheckResult(
            name="prometheus_shadow_logger_alerts",
            status="WARN",
            observed=f"unexpected error: {e}",
            expected="Prometheus reachable",
        ))


def _check_telegram_credentials(report: PreflightReport) -> None:
    """TELEGRAM_BRIEFING_* (or fallback TELEGRAM_FUTURES_*) creds present."""
    bot_token = os.environ.get("TELEGRAM_BRIEFING_BOT_TOKEN") or os.environ.get(
        "TELEGRAM_FUTURES_BOT_TOKEN"
    )
    chat_id = os.environ.get("TELEGRAM_BRIEFING_CHAT_ID") or os.environ.get(
        "TELEGRAM_FUTURES_CHAT_ID"
    )
    if bot_token and chat_id:
        report.checks.append(CheckResult(
            name="telegram_briefing_credentials",
            status="PASS",
            observed="bot_token + chat_id set",
            expected="both env vars present",
        ))
    else:
        report.checks.append(CheckResult(
            name="telegram_briefing_credentials",
            status="FAIL",
            observed=f"bot_token={'set' if bot_token else 'MISSING'}, chat_id={'set' if chat_id else 'MISSING'}",
            expected="both TELEGRAM_BRIEFING_* (or TELEGRAM_FUTURES_*) env vars set",
            detail=(
                "Without these, the daily-verification and weekly-counterfactual "
                "Telegram notifications will silently no-op."
            ),
        ))


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------


def _render_human(report: PreflightReport) -> str:
    icons = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}
    lines: list[str] = []
    lines.append("=" * 72)
    overall = "ALL PASS" if report.all_critical_pass else "FAIL"
    lines.append(f"Phase 2 Pre-flight Check — {overall}")
    lines.append("=" * 72)
    for c in report.checks:
        lines.append(f"{icons[c.status]} {c.name}")
        lines.append(f"   observed:  {c.observed}")
        lines.append(f"   expected:  {c.expected}")
        if c.detail and c.status != "PASS":
            lines.append(f"   action:    {c.detail}")
        lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines)


def _render_json(report: PreflightReport) -> str:
    return json.dumps(
        {
            "all_critical_pass": report.all_critical_pass,
            "checks": [asdict(c) for c in report.checks],
        },
        indent=2,
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run() -> PreflightReport:
    """Run all checks and return the report."""
    report = PreflightReport()
    _check_ch_migrations(report)
    _check_shadow_mode(report)
    _check_setup_strategies_enabled(report)
    _check_futures_live_disabled(report)
    _check_crontab_entries(report)
    _check_prometheus_alerts(report)
    _check_telegram_credentials(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 2 pre-flight check — automates the runbook's "
            "Friday-EOD verification (docs/runbooks/phase2-startup.md)."
        )
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON instead of human-readable text.",
    )
    args = parser.parse_args()

    try:
        report = run()
    except Exception as e:
        print(f"ERROR: pre-flight check crashed: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(_render_json(report))
    else:
        print(_render_human(report))

    return 0 if report.all_critical_pass else 1


if __name__ == "__main__":
    sys.exit(main())
