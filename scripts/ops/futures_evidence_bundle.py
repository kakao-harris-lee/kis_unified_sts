"""Compile and validate F-9 futures evidence bundles.

The bundle is operator-supplied evidence metadata. This script does not prove
that shadow trading or Phase 5 checks happened; it rejects incomplete,
placeholder, or structurally invalid evidence before the cutover verifier and
runbook consume the bundle.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

# This project is KST-native (Korea); all time math uses Asia/Seoul, not UTC.
KST = ZoneInfo("Asia/Seoul")

_PLACEHOLDER_MARKERS = (
    "todo",
    "tbd",
    "placeholder",
    "replace me",
)

_REQUIRED_FIELDS = (
    "trading_dates",
    "restart_loop_ok",
    "backlog_ok",
    "dashboard_ok",
    "direction_comparison_ok",
    "kill_switch_drill_ok",
    "signal_count",
    "backtest_tracking_error_pct",
    "max_drawdown_ok",
    "slippage_ok",
    "operator_approval_ref",
)

_GATE_FIELDS: dict[str, tuple[str, ...]] = {
    "f9_gate1": (
        "trading_dates",
        "restart_loop_ok",
        "backlog_ok",
        "dashboard_ok",
        "direction_comparison_ok",
        "signal_count",
    ),
    "f9_gate2": (
        "operator_approval_ref",
        "kill_switch_drill_ok",
    ),
    "phase5_small_live": (
        "signal_count",
        "phase5_signal_count",
        "backtest_tracking_error_pct",
        "max_drawdown_ok",
        "slippage_ok",
    ),
}

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SETUP_D_CONFIG_PATH = (
    _REPO_ROOT / "config/strategies/futures/setup_d_vwap_reversion.yaml"
)
_SETUP_D_OBSERVATION = {
    "required": True,
    "path": "reports/futures/setup_d/latest.json",
}
_SETUP_D_MAX_AGE_ENV = "FUTURES_SETUP_D_EVIDENCE_MAX_AGE_SECONDS"
# 4 days so a Friday-EOD report still verifies after a normal weekend (and a
# single Monday holiday). Multi-day holiday clusters can widen via the env var.
_DEFAULT_SETUP_D_MAX_AGE_SECONDS = 345600.0
_SETUP_D_MAX_FUTURE_SKEW_ENV = "FUTURES_SETUP_D_EVIDENCE_MAX_FUTURE_SKEW_SECONDS"
_DEFAULT_SETUP_D_MAX_FUTURE_SKEW_SECONDS = 300.0


def _load_bundle(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON/YAML mapping")
    return data


def _is_placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.strip().lower()
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def _append_missing(
    missing: list[str], field: str, reason: str, failures_by_field: dict[str, list[str]]
) -> None:
    message = f"{field}: {reason}"
    missing.append(message)
    failures_by_field.setdefault(field, []).append(reason)


def _validate_bundle(
    bundle: Mapping[str, Any],
) -> tuple[list[str], dict[str, list[str]]]:
    missing: list[str] = []
    failures_by_field: dict[str, list[str]] = {}

    for field in _REQUIRED_FIELDS:
        if field not in bundle:
            _append_missing(missing, field, "missing", failures_by_field)
            continue
        if _is_placeholder(bundle[field]):
            _append_missing(missing, field, "placeholder value", failures_by_field)

    trading_dates = bundle.get("trading_dates")
    if "trading_dates" in bundle and not _is_placeholder(trading_dates):
        if not isinstance(trading_dates, list) or not all(
            isinstance(item, str) and item.strip() for item in trading_dates
        ):
            _append_missing(
                missing,
                "trading_dates",
                "expected non-empty date strings",
                failures_by_field,
            )
        elif len(trading_dates) < 3:
            _append_missing(
                missing,
                "trading_dates",
                "requires at least 3 trading dates",
                failures_by_field,
            )

    for field in (
        "restart_loop_ok",
        "backlog_ok",
        "dashboard_ok",
        "direction_comparison_ok",
        "kill_switch_drill_ok",
        "max_drawdown_ok",
        "slippage_ok",
    ):
        if (
            field in bundle
            and not _is_placeholder(bundle[field])
            and bundle[field] is not True
        ):
            _append_missing(missing, field, "expected true", failures_by_field)

    signal_count = bundle.get("signal_count")
    parsed_signal_count: int | None = None
    if (
        "signal_count" in bundle
        and not _is_placeholder(signal_count)
        and (
            not isinstance(signal_count, int)
            or isinstance(signal_count, bool)
            or signal_count <= 0
        )
    ):
        _append_missing(
            missing,
            "signal_count",
            "expected positive integer",
            failures_by_field,
        )
    elif isinstance(signal_count, int) and not isinstance(signal_count, bool):
        parsed_signal_count = signal_count
        if 0 < parsed_signal_count < 100:
            _append_missing(
                missing,
                "phase5_signal_count",
                "requires at least 100 signals",
                failures_by_field,
            )

    tracking_error = bundle.get("backtest_tracking_error_pct")
    if (
        "backtest_tracking_error_pct" in bundle
        and not _is_placeholder(tracking_error)
        and (
            not isinstance(tracking_error, int | float)
            or isinstance(tracking_error, bool)
        )
    ):
        _append_missing(
            missing,
            "backtest_tracking_error_pct",
            "expected numeric percentage",
            failures_by_field,
        )
    elif (
        isinstance(tracking_error, int | float)
        and not isinstance(tracking_error, bool)
        and abs(float(tracking_error)) > 20.0
    ):
        _append_missing(
            missing,
            "backtest_tracking_error_pct",
            "expected absolute value <= 20",
            failures_by_field,
        )

    approval_ref = bundle.get("operator_approval_ref")
    if (
        "operator_approval_ref" in bundle
        and not _is_placeholder(approval_ref)
        and (not isinstance(approval_ref, str) or not approval_ref.strip())
    ):
        _append_missing(
            missing,
            "operator_approval_ref",
            "expected non-empty reference",
            failures_by_field,
        )

    return missing, failures_by_field


def _setup_d_required(config_path: Path | None = None) -> bool:
    config_path = config_path or _SETUP_D_CONFIG_PATH
    if not config_path.exists():
        # Strategy config is absent (not deployed): evidence is not required.
        return False
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        # Present but unparseable -> fail closed (require evidence).
        return True
    if not isinstance(data, dict) or not isinstance(data.get("strategy"), dict):
        # Present but reshaped/non-dict -> fail closed (require evidence).
        return True
    strategy = data["strategy"]
    # Explicitly disabled -> evidence not required. Otherwise (enabled, or
    # present but cannot confirm it is disabled: name mismatch / enabled not
    # strictly True) -> fail closed and require evidence.
    return strategy.get("enabled") is not False


def _coerce_non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float):
        if not value.is_integer():
            return None
        parsed = int(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            number = float(stripped)
        except ValueError:
            return None
        if not number.is_integer():
            return None
        parsed = int(number)
    else:
        return None
    return parsed if parsed >= 0 else None


def _parse_datetime(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        dt = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    # A tz-naive timestamp is interpreted as KST (this project is KST-native).
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KST)
    return dt.astimezone(KST)


def _now_kst() -> datetime:
    return datetime.now(KST)


def _setup_d_max_age_seconds() -> float:
    raw = os.environ.get(_SETUP_D_MAX_AGE_ENV)
    if raw is None:
        return _DEFAULT_SETUP_D_MAX_AGE_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_SETUP_D_MAX_AGE_SECONDS
    return value if value > 0 else _DEFAULT_SETUP_D_MAX_AGE_SECONDS


def _setup_d_max_future_skew_seconds() -> float:
    raw = os.environ.get(_SETUP_D_MAX_FUTURE_SKEW_ENV)
    if raw is None:
        return _DEFAULT_SETUP_D_MAX_FUTURE_SKEW_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_SETUP_D_MAX_FUTURE_SKEW_SECONDS
    return value if value >= 0 else _DEFAULT_SETUP_D_MAX_FUTURE_SKEW_SECONDS


def _validate_setup_d_payload(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ["invalid JSON"]
    if not isinstance(payload, dict):
        return ["expected JSON object"]

    failures: list[str] = []
    if payload.get("strategy") != "setup_d_vwap_reversion":
        failures.append("expected strategy setup_d_vwap_reversion")

    counts: dict[str, int] = {}
    for field in ("signals", "accepted", "rejected"):
        if field not in payload:
            failures.append(f"{field} missing")
            continue
        parsed = _coerce_non_negative_int(payload.get(field))
        if parsed is None:
            failures.append(f"{field} expected non-negative integer")
            continue
        counts[field] = parsed
    has_all_counts = {"signals", "accepted", "rejected"}.issubset(counts)
    if has_all_counts and counts["signals"] != counts["accepted"] + counts["rejected"]:
        failures.append("signals count mismatch accepted+rejected")
    if has_all_counts and counts["signals"] <= 0:
        failures.append("expected at least one observed signal")

    generated_at = _parse_datetime(payload.get("generated_at"))
    if "generated_at" not in payload:
        failures.append("generated_at missing")
    elif generated_at is None:
        failures.append("generated_at invalid ISO datetime")
    else:
        now = _now_kst()
        if (generated_at - now).total_seconds() > _setup_d_max_future_skew_seconds():
            failures.append("generated_at is in the future")
        elif (now - generated_at).total_seconds() > _setup_d_max_age_seconds():
            failures.append("generated_at stale")
    return failures


def _validate_setup_d_observation(
    failures_by_field: dict[str, list[str]],
) -> list[str]:
    if not _setup_d_required():
        return []
    observation_path = _REPO_ROOT / _SETUP_D_OBSERVATION["path"]
    if not observation_path.exists():
        reason = f"missing {_SETUP_D_OBSERVATION['path']}"
        failures_by_field.setdefault("setup_d_observation", []).append(reason)
        return [reason]
    reasons = _validate_setup_d_payload(observation_path)
    if not reasons:
        return []
    failures_by_field.setdefault("setup_d_observation", []).extend(reasons)
    return reasons


def _gate_section(
    bundle: Mapping[str, Any],
    failures_by_field: Mapping[str, list[str]],
    fields: tuple[str, ...],
) -> dict[str, Any]:
    failures = [
        f"{field}: {reason}"
        for field in fields
        for reason in failures_by_field.get(field, ())
    ]
    section = {
        "status": "fail" if failures else "pass",
        "missing_evidence": failures,
    }
    for field in fields:
        if field == "phase5_signal_count":
            continue
        if field in bundle:
            section[field] = bundle[field]
    return section


def compile_report(
    bundle: Mapping[str, Any],
    *,
    source: str | None = None,
    strict_setup_d: bool = False,
) -> dict[str, Any]:
    # ``strict_setup_d`` is retained for a backwards-compatible signature but no
    # longer affects the report: Setup D gating is decoupled from the F-9/Phase-5
    # bundle (gated separately via --strict-setup-d in main()).
    _ = strict_setup_d
    missing, failures_by_field = _validate_bundle(bundle)

    required = _setup_d_required()
    setup_d_failures = (
        _validate_setup_d_observation(failures_by_field) if required else []
    )
    if not required:
        setup_d_status = "disabled"
    elif setup_d_failures:
        setup_d_status = "fail"
    else:
        setup_d_status = "pass"

    # Top-level status reflects ONLY the F-9/Phase-5 evidence bundle. Setup D
    # paper evidence is reported independently (setup_d_observation.status) so an
    # absent or failing Setup D report never blocks the futures cutover gate.
    status = "fail" if missing else "pass"

    setup_d_observation: dict[str, Any] = {
        "required": required,
        "path": _SETUP_D_OBSERVATION["path"],
        "status": setup_d_status,
        "missing_evidence": setup_d_failures,
    }
    report: dict[str, Any] = {
        "status": status,
        "missing_evidence": missing,
        "setup_d_observation": setup_d_observation,
    }
    if source is not None:
        report["source"] = source
    for gate_name, fields in _GATE_FIELDS.items():
        report[gate_name] = _gate_section(bundle, failures_by_field, fields)
    return report


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and compile an F-9 futures evidence bundle"
    )
    parser.add_argument("bundle", type=Path, help="JSON/YAML evidence bundle path")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the compiled JSON report",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit nonzero when the F-9/Phase-5 evidence bundle fails validation",
    )
    parser.add_argument(
        "--strict-setup-d",
        action="store_true",
        help="Also exit nonzero when the Setup D paper observation fails",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    bundle = _load_bundle(args.bundle)
    report = compile_report(bundle, source=str(args.bundle))
    output = json.dumps(report, indent=2, sort_keys=True)
    print(output)
    bundle_failed = args.strict and report["status"] == "fail"
    setup_d_failed = (
        args.strict_setup_d and report["setup_d_observation"].get("status") == "fail"
    )
    return 1 if bundle_failed or setup_d_failed else 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
