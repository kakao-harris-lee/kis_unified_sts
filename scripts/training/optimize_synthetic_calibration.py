#!/usr/bin/env python3
"""Run multi-iteration synthetic calibration until convergence or max iterations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.training.build_synthetic_dataset import build_synthetic_dataset  # noqa: E402
from scripts.training.calibrate_synthetic_dataset import build_calibration_scorecard  # noqa: E402
from shared.ml.data.calibration.kospi_calibrator import KOSPICalibrator  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize synthetic calibration over multiple iterations")
    parser.add_argument("--scorecard", default="artifacts/datasets/calibration/scorecard.json")
    parser.add_argument("--source-config", default="config/ml/synthetic_data.yaml")
    parser.add_argument("--real-summary", default="artifacts/datasets/regime_catalog/summary.json")
    parser.add_argument("--real-bars", default="artifacts/datasets/regime_catalog/labeled_bars.parquet")
    parser.add_argument("--output-root", default="artifacts/datasets/calibration/optimizer_run")
    parser.add_argument("--max-iterations", type=int, default=3)
    parser.add_argument("--patience", type=int, default=1)
    parser.add_argument("--min-improvement", type=float, default=1e-6)
    args = parser.parse_args()

    output_root = project_root / args.output_root
    output_root.mkdir(parents=True, exist_ok=True)

    calibrator = KOSPICalibrator()
    current_scorecard = json.loads((project_root / args.scorecard).read_text(encoding="utf-8"))
    current_config = yaml.safe_load((project_root / args.source_config).read_text(encoding="utf-8"))

    best_score = calibrator.score_scorecard(current_scorecard)
    best_scorecard = current_scorecard
    best_iteration = 0
    best_config_path = str(project_root / args.source_config)
    no_improve_count = 0
    history: list[dict[str, object]] = []

    for iteration in range(1, args.max_iterations + 1):
        iteration_dir = output_root / f"iteration_{iteration:02d}"
        iteration_dir.mkdir(parents=True, exist_ok=True)

        candidate_config, patch_report = calibrator.apply_recommended_adjustments(current_config, current_scorecard)
        candidate_config_path = Path(
            calibrator.write_config_candidate(candidate_config, iteration_dir / "synthetic_data_candidate.yaml")
        )
        (iteration_dir / "candidate_patch_report.json").write_text(
            json.dumps(patch_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        synthetic_result = build_synthetic_dataset(
            source_config_override=str(candidate_config_path),
            output_dir_override=str((iteration_dir / "synthetic_dataset").relative_to(project_root)),
            dataset_label=f"synthetic_dataset_iteration_{iteration:02d}",
        )

        next_scorecard, scorecard_path = build_calibration_scorecard(
            real_summary_path=project_root / args.real_summary,
            synthetic_summary_path=Path(synthetic_result["artifacts"]["summary_json"]),
            real_bars_path=project_root / args.real_bars,
            synthetic_bars_path=Path(synthetic_result["artifacts"]["dataset"]),
            output_path=iteration_dir / f"scorecard_iteration_{iteration:02d}.json",
        )
        comparison = calibrator.compare_scorecards(current_scorecard, next_scorecard)
        comparison_path = iteration_dir / "scorecard_comparison.json"
        comparison_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")

        score = calibrator.score_scorecard(next_scorecard)
        improvement = best_score["objective"] - score["objective"]
        improved = improvement > args.min_improvement

        history.append(
            {
                "iteration": iteration,
                "candidate_config": str(candidate_config_path),
                "scorecard": scorecard_path,
                "comparison": str(comparison_path),
                "objective": score["objective"],
                "improvement_vs_best": improvement,
                "comparison_summary": comparison["summary"],
            }
        )

        current_config = candidate_config
        current_scorecard = next_scorecard

        if improved:
            best_score = score
            best_scorecard = next_scorecard
            best_iteration = iteration
            best_config_path = str(candidate_config_path)
            no_improve_count = 0
        else:
            no_improve_count += 1

        if no_improve_count > args.patience:
            break

    manifest = {
        "best_iteration": best_iteration,
        "best_config": best_config_path,
        "best_objective": best_score["objective"],
        "best_score_components": best_score["components"],
        "stopped_after": len(history),
        "history": history,
        "final_scorecard_summary": {
            "range_ratio": best_scorecard.get("metrics", {}).get("range_ratio"),
            "return_gap": best_scorecard.get("metrics", {}).get("return_gap"),
            "volume_shape": best_scorecard.get("metrics", {}).get("volume_shape"),
        },
    }
    manifest_path = output_root / "optimizer_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"output_root": str(output_root), "manifest": str(manifest_path), "summary": manifest}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()