#!/usr/bin/env python3
"""Summarize theme target and fusion quality evidence."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

# This project is KST-native (Korea); all time math uses Asia/Seoul, not UTC.
KST = ZoneInfo("Asia/Seoul")

DEFAULT_MAX_AGE_SECONDS = 1800.0
DEFAULT_MAX_FUTURE_SKEW_SECONDS = 300.0


def _normalize_state(value: Any) -> str:
    state = str(value or "unknown")
    if state == "quarantine":
        return "quarantined"
    return state


def _extract_legacy_targets(data: dict[str, Any]) -> list[dict[str, Any]]:
    targets = data.get("targets") or []
    if not isinstance(targets, list):
        return []
    return [target for target in targets if isinstance(target, dict)]


def _extract_canonical_targets(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_codes = data.get("codes") or []
    scores = data.get("scores") or {}
    metadata = data.get("metadata") or {}
    raw_quarantined_codes = data.get("quarantined_codes") or []
    if not isinstance(raw_codes, list):
        return []
    if not isinstance(scores, dict):
        scores = {}
    if not isinstance(metadata, dict):
        metadata = {}
    if not isinstance(raw_quarantined_codes, list):
        raw_quarantined_codes = []

    codes: list[str] = []
    seen: set[str] = set()
    for raw_code in raw_codes:
        code = str(raw_code).strip()
        if code and code not in seen:
            codes.append(code)
            seen.add(code)

    quarantined_codes = {
        str(code).strip() for code in raw_quarantined_codes if str(code).strip()
    }
    metadata_quarantined_codes = {
        str(code).strip()
        for code, item_metadata in metadata.items()
        if str(code).strip()
        and isinstance(item_metadata, dict)
        and _normalize_state(
            item_metadata.get("state", item_metadata.get("theme_state"))
        )
        == "quarantined"
    }
    additional_codes = sorted((quarantined_codes | metadata_quarantined_codes) - seen)
    codes.extend(additional_codes)

    targets: list[dict[str, Any]] = []
    for code in codes:
        item_metadata = metadata.get(code) or {}
        if not isinstance(item_metadata, dict):
            item_metadata = {}
        state = item_metadata.get("state", item_metadata.get("theme_state"))
        if code in quarantined_codes:
            state = "quarantined"
        targets.append(
            {
                "code": code,
                "theme_id": item_metadata.get("theme_id"),
                "state": state,
                "leader_score": scores.get(
                    code,
                    item_metadata.get(
                        "leader_score",
                        item_metadata.get("theme_leader_score"),
                    ),
                ),
            }
        )
    return targets


def _parse_generated_at(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    # A tz-naive producer timestamp is interpreted as KST (this project is
    # KST-native) so cross-timezone comparisons stay correct.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    return parsed


def _comparison_now(timestamp: datetime, now: datetime | None) -> datetime:
    if now is None:
        # Always compare against an aware KST clock so freshness is timezone-safe.
        return datetime.now(KST)
    if now.tzinfo is None:
        # A naive injected now is treated as KST.
        now = now.replace(tzinfo=KST)
    # An aware injected now is converted to the snapshot's timezone (legacy path).
    return now.astimezone(timestamp.tzinfo)


def _coerce_non_negative_seconds(value: float) -> float:
    return max(0.0, float(value))


def _coerce_leader_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _freshness_report(
    raw_generated_at: Any,
    *,
    now: datetime | None,
    max_age_seconds: float,
    max_future_skew_seconds: float,
) -> dict[str, Any]:
    max_age = _coerce_non_negative_seconds(max_age_seconds)
    max_future_skew = _coerce_non_negative_seconds(max_future_skew_seconds)
    report: dict[str, Any] = {
        "ok": False,
        "status": "missing",
        "reasons": [],
        "age_seconds": None,
        "future_skew_seconds": None,
        "max_age_seconds": max_age,
        "max_future_skew_seconds": max_future_skew,
    }

    if not isinstance(raw_generated_at, str) or not raw_generated_at.strip():
        report["reasons"] = ["generated_at missing"]
        return report

    generated_at = _parse_generated_at(raw_generated_at)
    if generated_at is None:
        report["status"] = "invalid"
        report["reasons"] = ["generated_at invalid ISO datetime"]
        return report

    current = _comparison_now(generated_at, now)
    age_seconds = (current - generated_at).total_seconds()
    if age_seconds < 0:
        future_skew_seconds = abs(age_seconds)
        report["age_seconds"] = 0.0
        report["future_skew_seconds"] = future_skew_seconds
        if future_skew_seconds > max_future_skew:
            report["status"] = "future"
            report["reasons"] = ["generated_at is in the future"]
            return report
        report["ok"] = True
        report["status"] = "fresh"
        return report

    report["age_seconds"] = age_seconds
    report["future_skew_seconds"] = 0.0
    if age_seconds > max_age:
        report["status"] = "stale"
        report["reasons"] = ["generated_at stale"]
        return report

    report["ok"] = True
    report["status"] = "fresh"
    return report


def build_theme_fusion_quality_report(
    snapshot_path: Path,
    *,
    now: datetime | None = None,
    max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
    max_future_skew_seconds: float = DEFAULT_MAX_FUTURE_SKEW_SECONDS,
) -> dict[str, Any]:
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        # Degrade gracefully on unexpected top-level shapes (e.g. a JSON list)
        # instead of raising AttributeError on the .get() accessors below.
        data = {}
    targets = _extract_legacy_targets(data) or _extract_canonical_targets(data)
    state_counts = Counter(_normalize_state(target.get("state")) for target in targets)
    theme_counts = Counter(
        str(target.get("theme_id") or "unknown") for target in targets
    )
    scores = [
        score
        for score in (
            _coerce_leader_score(target.get("leader_score")) for target in targets
        )
        if score is not None
    ]

    source = data.get("source")
    if not isinstance(source, dict):
        source = {}
    source_status = source.get("status")

    freshness = _freshness_report(
        data.get("generated_at"),
        now=now,
        max_age_seconds=max_age_seconds,
        max_future_skew_seconds=max_future_skew_seconds,
    )
    target_count = len(targets)
    ok = bool(
        freshness["ok"]
        and target_count > 0
        and source_status not in {"stale_universe", "no_matches"}
    )
    if ok:
        status = "ok"
    elif not freshness["ok"]:
        status = str(freshness["status"])
    elif source_status in {"stale_universe", "no_matches"}:
        status = str(source_status)
    elif target_count == 0:
        status = "empty"
    else:
        status = "degraded"

    return {
        "generated_at": data.get("generated_at"),
        "freshness": freshness,
        "target_count": target_count,
        "state_counts": dict(state_counts),
        "theme_counts": dict(theme_counts),
        "min_leader_score": min(scores) if scores else None,
        "max_leader_score": max(scores) if scores else None,
        "false_positive_examples": data.get("false_positive_examples") or [],
        "source_status": source_status,
        "ok": ok,
        "status": status,
    }


def main(argv: Sequence[str] | None = None, *, now: datetime | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--max-age-seconds",
        default=DEFAULT_MAX_AGE_SECONDS,
        type=float,
        help="Maximum acceptable snapshot age in seconds.",
    )
    parser.add_argument(
        "--max-future-skew-seconds",
        default=DEFAULT_MAX_FUTURE_SKEW_SECONDS,
        type=float,
        help="Maximum tolerated clock skew when generated_at is in the future.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit code when the overall report is not ok.",
    )
    args = parser.parse_args(argv)
    report = build_theme_fusion_quality_report(
        args.snapshot,
        now=now,
        max_age_seconds=args.max_age_seconds,
        max_future_skew_seconds=args.max_future_skew_seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    if args.strict and not report["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
