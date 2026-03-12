#!/usr/bin/env python3
"""Apply calibration scorecard recommendations to a synthetic config candidate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.ml.data.calibration.kospi_calibrator import KOSPICalibrator  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply synthetic calibration recommendations")
    parser.add_argument("--scorecard", default="artifacts/datasets/calibration/scorecard.json")
    parser.add_argument("--source-config", default="config/ml/synthetic_data.yaml")
    parser.add_argument(
        "--output-config",
        default="artifacts/datasets/calibration/synthetic_data_calibrated.yaml",
    )
    parser.add_argument(
        "--output-report",
        default="artifacts/datasets/calibration/synthetic_data_calibrated_report.json",
    )
    args = parser.parse_args()

    scorecard = json.loads((project_root / args.scorecard).read_text(encoding="utf-8"))
    source_config = yaml.safe_load((project_root / args.source_config).read_text(encoding="utf-8"))

    calibrator = KOSPICalibrator()
    candidate_config, patch_report = calibrator.apply_recommended_adjustments(source_config, scorecard)

    output_config = calibrator.write_config_candidate(candidate_config, project_root / args.output_config)
    output_report_path = project_root / args.output_report
    output_report_path.parent.mkdir(parents=True, exist_ok=True)
    output_report = {
        "source_config": str(project_root / args.source_config),
        "scorecard": str(project_root / args.scorecard),
        "output_config": output_config,
        "patch_report": patch_report,
    }
    output_report_path.write_text(json.dumps(output_report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(output_report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()