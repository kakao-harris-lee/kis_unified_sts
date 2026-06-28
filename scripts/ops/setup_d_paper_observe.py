#!/usr/bin/env python3
"""Build a paper evidence report for Setup D VWAP reversion."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


STRATEGY_ID = "setup_d_vwap_reversion"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def build_setup_d_report(path: Path) -> dict[str, Any]:
    rows = [row for row in _load_jsonl(path) if row.get("strategy") == STRATEGY_ID]
    accepted = [row for row in rows if row.get("status") == "accepted"]
    rejected = [row for row in rows if row.get("status") == "rejected"]
    reject_reasons = Counter(
        f"{row.get('reject_stage') or 'unknown'}:{row.get('reject_reason') or 'unknown'}"
        for row in rejected
    )
    return {
        "strategy": STRATEGY_ID,
        "signals": len(rows),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "long_signals": sum(1 for row in rows if str(row.get("side")).upper() == "BUY"),
        "short_signals": sum(
            1 for row in rows if str(row.get("side")).upper() == "SELL"
        ),
        "total_pnl": sum(float(row.get("pnl") or 0.0) for row in accepted),
        "top_reject_reasons": dict(reject_reasons.most_common(10)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = build_setup_d_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
