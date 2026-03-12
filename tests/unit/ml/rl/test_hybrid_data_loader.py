"""Tests for hybrid RL dataset loading."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from shared.ml.rl.hybrid_data_loader import HybridRLDataLoader


def test_hybrid_loader_prepares_day_arrays(tmp_path: Path):
    train_path = tmp_path / "train.parquet"
    validation_path = tmp_path / "validation.parquet"
    test_path = tmp_path / "test.parquet"

    rows = []
    for day in range(3):
        date = pd.Timestamp("2025-01-02") + pd.Timedelta(days=day)
        price = 100 + day
        for minute in range(220):
            rows.append(
                {
                    "datetime": date + pd.Timedelta(hours=9, minutes=minute),
                    "date": (date + pd.Timedelta(hours=9, minutes=minute)).date(),
                    "open": price,
                    "high": price * 1.001,
                    "low": price * 0.999,
                    "close": price * (1 + 0.0005 * minute),
                    "volume": 1000 + minute,
                    "source_type": "real",
                    "regime_label": "bull|normal|normal",
                }
            )
    df = pd.DataFrame(rows)
    df.to_parquet(train_path, index=False)
    df[df["date"] == pd.Timestamp("2025-01-02").date()].to_parquet(train_path, index=False)
    df[df["date"] == pd.Timestamp("2025-01-03").date()].to_parquet(validation_path, index=False)
    df[df["date"] == pd.Timestamp("2025-01-04").date()].to_parquet(test_path, index=False)

    manifest = {
        "train": {"path": str(train_path)},
        "validation": {"path": str(validation_path)},
        "test": {"path": str(test_path)},
        "rules": {"test_is_real_only": True},
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    loader = HybridRLDataLoader("ml/rl_mppo.yaml")
    result = loader.load_from_manifest(manifest_path)

    assert len(result["train_days"]) >= 1
    assert len(result["validation_days"]) >= 1
    assert len(result["test_days"]) >= 1
    assert result["manifest"]["rules"]["test_is_real_only"] is True


def test_hybrid_loader_persists_runtime_scaler_name(tmp_path: Path):
    train_path = tmp_path / "train.parquet"
    validation_path = tmp_path / "validation.parquet"
    test_path = tmp_path / "test.parquet"

    rows = []
    for day in range(3):
        date = pd.Timestamp("2025-01-02") + pd.Timedelta(days=day)
        for minute in range(220):
            dt = date + pd.Timedelta(hours=9, minutes=minute)
            rows.append(
                {
                    "datetime": dt,
                    "date": dt.date(),
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.0 + minute * 0.01,
                    "volume": 1000 + minute,
                }
            )
    df = pd.DataFrame(rows)
    df[df["date"] == pd.Timestamp("2025-01-02").date()].to_parquet(train_path, index=False)
    df[df["date"] == pd.Timestamp("2025-01-03").date()].to_parquet(validation_path, index=False)
    df[df["date"] == pd.Timestamp("2025-01-04").date()].to_parquet(test_path, index=False)

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "train": {"path": str(train_path)},
                "validation": {"path": str(validation_path)},
                "test": {"path": str(test_path)},
                "rules": {"test_is_real_only": True},
            }
        ),
        encoding="utf-8",
    )

    loader = HybridRLDataLoader("ml/rl_mppo.yaml")
    loader.rl_config.setdefault("training", {})
    loader.rl_config["training"]["save_dir"] = str(tmp_path / "models")
    loader.load_from_manifest(manifest_path, persist_scaler=True)

    assert (tmp_path / "models" / "scaler.joblib").exists()
    assert (tmp_path / "models" / "hybrid_scaler.joblib").exists()
