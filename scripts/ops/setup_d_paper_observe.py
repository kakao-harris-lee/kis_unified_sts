#!/usr/bin/env python3
"""Build a paper evidence report for Setup D VWAP reversion."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STRATEGY_ID = "setup_d_vwap_reversion"

# Statuses that mean the signal was resolved as accepted (passed risk/order).
ACCEPTED_STATUSES = {
    "accepted",
    "paper_filled",
    "filled",
    "passed",
    "orderable",
    "paper_orderable",
}
# Statuses that mean the signal was resolved as rejected (blocked downstream).
REJECTED_STATUSES = {
    "rejected",
    "blocked",
    "paper_rejected",
}

# Direction synonyms mapped onto the repo vocabulary (PositionSide long/short).
_LONG_TOKENS = {"long", "buy", "b"}
_SHORT_TOKENS = {"short", "sell", "s"}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _normalize_direction(row: dict[str, Any]) -> str | None:
    raw = row.get("direction")
    if raw is None:
        raw = row.get("side")
    if raw is None:
        return None
    token = str(raw).casefold()
    if token in _LONG_TOKENS:
        return "long"
    if token in _SHORT_TOKENS:
        return "short"
    return None


def _normalize_status(row: dict[str, Any]) -> str | None:
    raw = row.get("status")
    if raw is None:
        return None
    return str(raw).casefold()


def _safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _utc_iso(value: datetime | None = None) -> str:
    dt = value or datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def build_setup_d_report(
    path: Path,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    rows = [row for row in _load_jsonl(path) if row.get("strategy") == STRATEGY_ID]
    accepted = [row for row in rows if _normalize_status(row) in ACCEPTED_STATUSES]
    rejected = [row for row in rows if _normalize_status(row) in REJECTED_STATUSES]
    reject_reasons = Counter(
        f"{row.get('reject_stage') or 'unknown'}:{row.get('reject_reason') or 'unknown'}"
        for row in rejected
    )
    directions = [_normalize_direction(row) for row in rows]
    pnl_values = [_safe_float(row.get("pnl")) for row in accepted]
    contributing_pnl = [value for value in pnl_values if value is not None]
    return {
        "strategy": STRATEGY_ID,
        "generated_at": _utc_iso(generated_at),
        "source_path": str(path),
        # Validator invariant: signals == accepted + rejected (resolved signals).
        "signals": len(accepted) + len(rejected),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "unresolved": len(rows) - len(accepted) - len(rejected),
        "total_rows": len(rows),
        "long_signals": sum(1 for direction in directions if direction == "long"),
        "short_signals": sum(1 for direction in directions if direction == "short"),
        "total_pnl": sum(contributing_pnl),
        "pnl_rows": len(contributing_pnl),
        "top_reject_reasons": dict(reject_reasons.most_common(10)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.input.exists():
        print(f"missing input: {args.input}", file=sys.stderr)
        return 1
    report = build_setup_d_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
