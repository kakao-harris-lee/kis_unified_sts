#!/usr/bin/env python3
"""Run one synthetic calibration iteration: apply -> rebuild -> recalibrate -> compare."""

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
    parser = argparse.ArgumentParser(description="Run one synthetic calibration iteration")
    parser.add_argument("--scorecard", default="artifacts/datasets/calibration/scorecard.json")
    parser.add_argument("--source-config", default="config/ml/synthetic_data.yaml")
    parser.add_argument("--real-summary", default="artifacts/datasets/regime_catalog/summary.json")
    parser.add_argument("--real-bars", default="artifacts/datasets/regime_catalog/labeled_bars.parquet")
    parser.add_argument("--iteration-dir", default="artifacts/datasets/calibration/iteration_01")
    args = parser.parse_args()

    iteration_dir = project_root / args.iteration_dir
    iteration_dir.mkdir(parents=True, exist_ok=True)

    calibrator = KOSPICalibrator()
    previous_scorecard = json.loads((project_root / args.scorecard).read_text(encoding="utf-8"))
    source_config = yaml.safe_load((project_root / args.source_config).read_text(encoding="utf-8"))

    candidate_config, patch_report = calibrator.apply_recommended_adjustments(source_config, previous_scorecard)
    candidate_config_path = Path(calibrator.write_config_candidate(candidate_config, iteration_dir / "synthetic_data_candidate.yaml"))

    patch_report_path = iteration_dir / "candidate_patch_report.json"
    patch_report_path.write_text(json.dumps(patch_report, ensure_ascii=False, indent=2), encoding="utf-8")

    synthetic_result = build_synthetic_dataset(
        source_config_override=str(candidate_config_path),
        output_dir_override=str((iteration_dir / "synthetic_dataset").relative_to(project_root)),
        dataset_label="synthetic_dataset_iteration_01",
    )

    new_scorecard, scorecard_path = build_calibration_scorecard(
        real_summary_path=project_root / args.real_summary,
        synthetic_summary_path=Path(synthetic_result["artifacts"]["summary_json"]),
        real_bars_path=project_root / args.real_bars,
        synthetic_bars_path=Path(synthetic_result["artifacts"]["dataset"]),
        output_path=iteration_dir / "scorecard_iteration_01.json",
    )

    comparison = calibrator.compare_scorecards(previous_scorecard, new_scorecard)
    comparison_path = iteration_dir / "scorecard_comparison.json"
    comparison_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")

    result = {
        "candidate_config": str(candidate_config_path),
        "patch_report": str(patch_report_path),
        "synthetic_output_dir": synthetic_result["output_dir"],
        "scorecard": scorecard_path,
        "comparison": str(comparison_path),
        "comparison_summary": comparison["summary"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()