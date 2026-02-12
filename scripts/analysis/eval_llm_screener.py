#!/usr/bin/env python3
"""Evaluate LLM screener outputs.

Reads `output/llm/unified_data_*.json` files and prints:
  - coverage / exclusion metrics
  - average screening scores of selected plans
  - optional realized-return metrics if CSV is provided

Optional realized CSV format:
  date,code,next_day_return
  2026-02-10,005930,1.25
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
from dataclasses import dataclass
from typing import Any


@dataclass
class EvalStats:
    files: int = 0
    total_selected: int = 0
    total_screened: int = 0
    total_excluded: int = 0
    score_sum: float = 0.0
    score_count: int = 0
    selected_with_risk: int = 0


def _load_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _build_realized_map(csv_path: str | None) -> dict[tuple[str, str], float]:
    if not csv_path:
        return {}
    out: dict[tuple[str, str], float] = {}
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt = str(row.get("date", "")).strip()
            code = str(row.get("code", "")).strip()
            ret_raw = row.get("next_day_return", "")
            if not dt or not code:
                continue
            try:
                out[(dt, code)] = float(ret_raw)
            except Exception:
                continue
    return out


def evaluate(pattern: str, realized_csv: str | None = None) -> dict[str, Any]:
    files = sorted(glob.glob(pattern))
    stats = EvalStats(files=len(files))
    realized = _build_realized_map(realized_csv)
    realized_hits = 0
    realized_count = 0
    realized_sum = 0.0

    for path in files:
        data = _load_json(path)
        analysis = data.get("analysis", {})
        stock = analysis.get("stock", {}) if isinstance(analysis, dict) else {}
        plans = data.get("stock_plans", []) if isinstance(data.get("stock_plans"), list) else []
        date_key = str(data.get("date", ""))

        excluded = stock.get("_excluded", {})
        excluded_count = len(excluded) if isinstance(excluded, dict) else 0
        stats.total_excluded += excluded_count

        symbol_keys = [k for k, v in stock.items() if not str(k).startswith("_") and isinstance(v, dict)]
        stats.total_screened += len(symbol_keys)

        for p in plans:
            if not isinstance(p, dict):
                continue
            code = str(p.get("code", "")).strip()
            if not code:
                continue
            stats.total_selected += 1

            screening = stock.get(code, {}).get("screening", {})
            score = screening.get("score")
            if isinstance(score, (int, float)):
                stats.score_sum += float(score)
                stats.score_count += 1

            risk_keywords = screening.get("metrics", {}).get("risk_keywords", [])
            if isinstance(risk_keywords, list) and risk_keywords:
                stats.selected_with_risk += 1

            if realized:
                r = realized.get((date_key, code))
                if r is not None:
                    realized_count += 1
                    realized_sum += r
                    if r > 0:
                        realized_hits += 1

    avg_selected = (stats.total_selected / stats.files) if stats.files else 0.0
    avg_score = (stats.score_sum / stats.score_count) if stats.score_count else 0.0
    exclusion_rate = (
        stats.total_excluded / max(1, (stats.total_excluded + stats.total_screened))
    )
    selected_risk_rate = stats.selected_with_risk / max(1, stats.total_selected)

    result: dict[str, Any] = {
        "files": stats.files,
        "total_selected": stats.total_selected,
        "avg_selected_per_file": round(avg_selected, 3),
        "total_screened": stats.total_screened,
        "total_excluded": stats.total_excluded,
        "exclusion_rate": round(exclusion_rate, 4),
        "avg_selected_screening_score": round(avg_score, 4),
        "selected_with_risk_rate": round(selected_risk_rate, 4),
    }

    if realized:
        result.update(
            {
                "realized_samples": realized_count,
                "realized_hit_rate": round(realized_hits / max(1, realized_count), 4),
                "realized_avg_return": round(realized_sum / max(1, realized_count), 4),
            }
        )

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate LLM screener output quality.")
    parser.add_argument(
        "--pattern",
        default="output/llm/unified_data_*.json",
        help="Glob pattern for unified screener output files",
    )
    parser.add_argument(
        "--realized-csv",
        default=None,
        help="Optional CSV with columns: date,code,next_day_return",
    )
    args = parser.parse_args()

    result = evaluate(args.pattern, args.realized_csv)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
