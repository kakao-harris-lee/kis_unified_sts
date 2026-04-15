#!/usr/bin/env python3
"""Audit scaler.joblib vs current RLFeatureCalculator output.

Checks:
1. Dimensions align between scaler and feature columns
2. Scaler internal values (min_/scale_) are finite and valid
3. End-to-end: sample training data -> RLFeatureCalculator -> scaler -> reasonable range
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit RL scaler consistency")
    parser.add_argument(
        "--scaler",
        type=Path,
        default=Path("models/futures/rl/scaler.joblib"),
    )
    parser.add_argument(
        "--sample",
        type=Path,
        default=Path("data/kospi200f_1m_clean.csv"),
    )
    args = parser.parse_args()

    if not args.scaler.exists():
        print(f"FAIL: scaler not found at {args.scaler}")
        return 1

    scaler = joblib.load(args.scaler)
    print(f"Scaler type: {type(scaler).__name__}")

    from shared.ml.rl.features import RL_FEATURE_COLUMNS, RLFeatureCalculator

    n_scaler = int(getattr(scaler, "n_features_in_", 0))
    n_expected = len(RL_FEATURE_COLUMNS)
    print(f"Scaler n_features_in_ = {n_scaler}")
    print(f"RL_FEATURE_COLUMNS    = {n_expected}")
    if n_scaler != n_expected:
        print("FAIL: dimension mismatch")
        return 2
    print("OK: dimensions match")

    # For MinMaxScaler, check min_ and scale_
    scaler_min = getattr(scaler, "min_", None)
    scaler_scale = getattr(scaler, "scale_", None)

    if scaler_min is None or scaler_scale is None:
        print("FAIL: scaler missing min_/scale_ attributes")
        return 3
    if not np.isfinite(scaler_min).all():
        print(f"FAIL: non-finite min_: {scaler_min}")
        return 4
    if not np.isfinite(scaler_scale).all() or (scaler_scale <= 0).any():
        print(f"FAIL: invalid scale_ (non-positive or NaN): {scaler_scale}")
        return 5
    print("OK: scaler values finite, scale_ > 0")

    if not args.sample.exists():
        print(
            f"WARN: sample CSV not found at {args.sample} — skipping end-to-end check"
        )
        return 0

    df = pd.read_csv(args.sample)
    calc = RLFeatureCalculator()
    feats = calc.calculate(df)
    feats = feats[RL_FEATURE_COLUMNS].dropna()
    if len(feats) == 0:
        print("WARN: no complete feature rows in sample — skipping end-to-end check")
        return 0

    row = feats.iloc[-1].to_numpy().reshape(1, -1)
    scaled = scaler.transform(row)
    z_min = float(scaled.min())
    z_max = float(scaled.max())
    z_abs_max = float(np.abs(scaled).max())
    print(
        f"Sample scaled obs: min={z_min:.3f} max={z_max:.3f} |z|_max={z_abs_max:.3f}"
    )
    if z_abs_max > 1.5:
        print(
            f"WARN: scaled values outside [0,1] range ({z_min:.3f}, {z_max:.3f})"
        )
    else:
        print("OK: sample scaled obs within [0,1] range")

    return 0


if __name__ == "__main__":
    sys.exit(main())
