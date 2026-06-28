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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

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
_SETUP_D_CONFIG_PATH = _REPO_ROOT / "config/strategies/futures/setup_d_vwap_reversion.yaml"
_SETUP_D_OBSERVATION = {
    "required": True,
    "path": "reports/futures/setup_d/latest.json",
}
_SETUP_D_MAX_AGE_ENV = "FUTURES_SETUP_D_EVIDENCE_MAX_AGE_SECONDS"
_DEFAULT_SETUP_D_MAX_AGE_SECONDS = 129600.0
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


def _setup_d_enabled(config_path: Path | None = None) -> bool:
    config_path = config_path or _SETUP_D_CONFIG_PATH
    if not config_path.exists():
        return False
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return False
    strategy = data.get("strategy")
    if not isinstance(strategy, dict):
        return False
    return strategy.get("name") == "setup_d_vwap_reversion" and strategy.get(
        "enabled"
    ) is True


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
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)


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
    if (
        {"signals", "accepted", "rejected"}.issubset(counts)
        and counts["signals"] != counts["accepted"] + counts["rejected"]
    ):
        failures.append("signals count mismatch accepted+rejected")

    generated_at = _parse_datetime(payload.get("generated_at"))
    if "generated_at" not in payload:
        failures.append("generated_at missing")
    elif generated_at is None:
        failures.append("generated_at invalid ISO datetime")
    else:
        now = _utc_now()
        if (generated_at - now).total_seconds() > _setup_d_max_future_skew_seconds():
            failures.append("generated_at is in the future")
        elif (now - generated_at).total_seconds() > _setup_d_max_age_seconds():
            failures.append("generated_at stale")
    return failures


def _validate_setup_d_observation(
    failures_by_field: dict[str, list[str]],
) -> list[str]:
    if not _setup_d_enabled():
        return []
    observation_path = _REPO_ROOT / _SETUP_D_OBSERVATION["path"]
    if not observation_path.exists():
        reason = f"missing {_SETUP_D_OBSERVATION['path']}"
        failures_by_field.setdefault("setup_d_observation", []).append(reason)
        return [f"setup_d_observation: {reason}"]
    reasons = _validate_setup_d_payload(observation_path)
    if not reasons:
        return []
    failures_by_field.setdefault("setup_d_observation", []).extend(reasons)
    return [f"setup_d_observation: {reason}" for reason in reasons]


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
    missing, failures_by_field = _validate_bundle(bundle)
    if strict_setup_d:
        missing.extend(_validate_setup_d_observation(failures_by_field))
    report: dict[str, Any] = {
        "status": "fail" if missing else "pass",
        "missing_evidence": missing,
        "setup_d_observation": dict(_SETUP_D_OBSERVATION),
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
        help="Exit nonzero when the evidence bundle fails validation",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    bundle = _load_bundle(args.bundle)
    report = compile_report(
        bundle,
        source=str(args.bundle),
        strict_setup_d=args.strict,
    )
    output = json.dumps(report, indent=2, sort_keys=True)
    print(output)
    return 1 if args.strict and report["status"] == "fail" else 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
