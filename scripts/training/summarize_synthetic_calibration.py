#!/usr/bin/env python3
"""Render a concise markdown summary from a synthetic calibration optimizer manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_summary_markdown(manifest: dict) -> str:
    summary = manifest.get("summary", manifest)
    lines = [
        "# Synthetic Calibration Optimizer Summary",
        "",
        f"- best_iteration: {summary.get('best_iteration')}",
        f"- best_objective: {summary.get('best_objective')}",
        f"- stopped_after: {summary.get('stopped_after')}",
        f"- best_config: {summary.get('best_config')}",
        "",
        "## Objective Components",
    ]
    for key, value in (summary.get("best_score_components") or {}).items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Iteration History"])
    for item in summary.get("history", []):
        comp = item.get("comparison_summary", {})
        lines.append(
            f"- iteration {item.get('iteration')}: objective={item.get('objective')}, "
            f"improvement_vs_best={item.get('improvement_vs_best')}, "
            f"improved={comp.get('improved_metrics')}, worsened={comp.get('worsened_metrics')}"
        )

    final_volume = (summary.get("final_scorecard_summary") or {}).get("volume_shape") or {}
    if final_volume:
        lines.extend(["", "## Final Volume Shape"])
        for key in [
            "profile_mae",
            "profile_correlation",
            "morning_lunch_ratio_gap",
            "close_lunch_ratio_gap",
        ]:
            lines.append(f"- {key}: {final_volume.get(key)}")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize synthetic calibration optimizer output")
    parser.add_argument(
        "--manifest",
        default="artifacts/datasets/calibration/optimizer_run/optimizer_manifest.json",
    )
    parser.add_argument(
        "--output",
        default="artifacts/datasets/calibration/optimizer_run/optimizer_summary.md",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    markdown = build_summary_markdown(manifest)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "output": str(output_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()