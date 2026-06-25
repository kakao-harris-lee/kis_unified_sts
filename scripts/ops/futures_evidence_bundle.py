"""Compile and validate F-9 futures evidence bundles.

The bundle is operator-supplied evidence metadata. This script does not prove
that shadow trading or Phase 5 checks happened; it rejects incomplete,
placeholder, or structurally invalid evidence before the cutover verifier and
runbook consume the bundle.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
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
    bundle: Mapping[str, Any], *, source: str | None = None
) -> dict[str, Any]:
    missing, failures_by_field = _validate_bundle(bundle)
    report: dict[str, Any] = {
        "status": "fail" if missing else "pass",
        "missing_evidence": missing,
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
    report = compile_report(bundle, source=str(args.bundle))
    output = json.dumps(report, indent=2, sort_keys=True)
    print(output)
    return 1 if args.strict and report["status"] == "fail" else 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
