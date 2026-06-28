#!/usr/bin/env python3
"""Summarize theme target and fusion quality evidence."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def build_theme_fusion_quality_report(snapshot_path: Path) -> dict[str, Any]:
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    targets = data.get("targets") or []
    state_counts = Counter(str(target.get("state") or "unknown") for target in targets)
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
