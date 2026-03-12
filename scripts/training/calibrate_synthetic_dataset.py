#!/usr/bin/env python3
"""Build a Phase 3 calibration scorecard from real and synthetic summaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.ml.data.calibration.kospi_calibrator import KOSPICalibrator  # noqa: E402


def _read_frame(path: Path) -> pd.DataFrame:
    if path.suffix == ".csv":
        return pd.read_csv(path)
    return pd.read_parquet(path)


def build_calibration_scorecard(
    *,
    real_summary_path: Path,
    synthetic_summary_path: Path,
    real_bars_path: Path | None = None,
    synthetic_bars_path: Path | None = None,
    output_path: Path | None = None,
) -> tuple[dict[str, Any], str | None]:
    real_summary = json.loads(real_summary_path.read_text(encoding="utf-8"))
    synthetic_summary = json.loads(synthetic_summary_path.read_text(encoding="utf-8"))
    real_frame = _read_frame(real_bars_path) if real_bars_path and real_bars_path.exists() else None
    synthetic_frame = _read_frame(synthetic_bars_path) if synthetic_bars_path and synthetic_bars_path.exists() else None

    calibrator = KOSPICalibrator()
    scorecard = calibrator.build_scorecard(
        real_summary,
        synthetic_summary,
        real_frame=real_frame,
        synthetic_frame=synthetic_frame,
    )
    written_path = calibrator.write_scorecard(scorecard, output_path) if output_path is not None else None
    return scorecard, written_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate synthetic dataset against real summary")
    parser.add_argument("--real-summary", default="artifacts/datasets/regime_catalog/summary.json")
    parser.add_argument("--synthetic-summary", default="artifacts/datasets/synthetic/summary.json")
    parser.add_argument("--real-bars", default="artifacts/datasets/regime_catalog/labeled_bars.parquet")
    parser.add_argument("--synthetic-bars", default="artifacts/datasets/synthetic/synthetic_dataset.parquet")
    parser.add_argument("--output", default="artifacts/datasets/calibration/scorecard.json")
    args = parser.parse_args()

    real_bars_path = project_root / args.real_bars
    synthetic_bars_path = project_root / args.synthetic_bars
    scorecard, output_path = build_calibration_scorecard(
        real_summary_path=project_root / args.real_summary,
        synthetic_summary_path=project_root / args.synthetic_summary,
        real_bars_path=real_bars_path,
        synthetic_bars_path=synthetic_bars_path,
        output_path=project_root / args.output,
    )
    print(json.dumps({"output": output_path, "scorecard": scorecard}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
