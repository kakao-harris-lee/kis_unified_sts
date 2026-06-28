#!/usr/bin/env python3
"""Summarize theme target and fusion quality evidence."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


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


def build_theme_fusion_quality_report(snapshot_path: Path) -> dict[str, Any]:
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    targets = _extract_legacy_targets(data) or _extract_canonical_targets(data)
    state_counts = Counter(_normalize_state(target.get("state")) for target in targets)
    theme_counts = Counter(str(target.get("theme_id") or "unknown") for target in targets)
    scores = [
        float(target.get("leader_score"))
        for target in targets
        if target.get("leader_score") is not None
    ]
    return {
        "generated_at": data.get("generated_at"),
        "target_count": len(targets),
        "state_counts": dict(state_counts),
        "theme_counts": dict(theme_counts),
        "min_leader_score": min(scores) if scores else None,
        "max_leader_score": max(scores) if scores else None,
        "false_positive_examples": data.get("false_positive_examples") or [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = build_theme_fusion_quality_report(args.snapshot)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
