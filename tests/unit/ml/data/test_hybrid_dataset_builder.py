from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

from shared.ml.data.hybrid_dataset_builder import HybridDatasetBuilder


def _make_frame(start_date: str, days: int, *, source_type: str, source_market: str) -> pd.DataFrame:
    rows = []
    for day in range(days):
        date = pd.Timestamp(start_date) + pd.Timedelta(days=day)
        price = 100 + day
        for minute in range(220):
            dt = date + pd.Timedelta(hours=9, minutes=minute)
            rows.append(
                {
                    "datetime": dt,
                    "date": dt.date(),
                    "open": price,
                    "high": price * 1.001,
                    "low": price * 0.999,
                    "close": price * (1 + 0.0002 * minute),
                    "volume": 1000 + minute,
                    "source_type": source_type,
                    "source_market": source_market,
                    "real_data_source": "clickhouse" if source_type == "real" else source_type,
                    "real_data_authentic": True if source_type == "real" else False,
                }
            )
    return pd.DataFrame(rows)


def test_hybrid_dataset_builder_creates_real_only_holdout(tmp_path: Path):
    real_path = tmp_path / "real.parquet"
    synthetic_path = tmp_path / "synthetic.parquet"
    transfer_path = tmp_path / "transfer.parquet"

    _make_frame("2025-01-02", 8, source_type="real", source_market="kospi").to_parquet(real_path, index=False)
    _make_frame("2025-02-01", 4, source_type="synthetic", source_market="synthetic").to_parquet(synthetic_path, index=False)
    _make_frame("2025-03-01", 3, source_type="transfer", source_market="cme").to_parquet(transfer_path, index=False)

    config_path = tmp_path / "hybrid_dataset.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "inputs": {
                    "real_catalog_path": str(real_path),
                    "synthetic_dataset_path": str(synthetic_path),
                    "transfer_dataset_path": str(transfer_path),
                },
                "split": {
                    "real_train_ratio": 0.6,
                    "real_validation_ratio": 0.2,
                    "real_test_ratio": 0.2,
                    "synthetic_validation_ratio": 0.1,
                    "bootstrap_when_real_missing": False,
                },
                "mixing": {
                    "train_real_weight": 0.6,
                    "train_synthetic_weight": 0.4,
                    "train_transfer_weight": 0.2,
                    "shuffle_seed": 42,
                },
                "output": {
                    "output_dir": str(tmp_path / "output"),
                    "save_splits": True,
                    "manifest_version": 1,
                    "charting": {"enabled": False},
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = HybridDatasetBuilder(str(config_path)).build(tmp_path)

    manifest = json.loads(Path(result["artifacts"]["manifest"]).read_text(encoding="utf-8"))
    assert manifest["rules"]["real_catalog_authentic"] is True
    assert manifest["rules"]["test_is_real_only"] is True
    assert manifest["rules"]["final_selection_allowed"] is True

    test_df = pd.read_parquet(manifest["test"]["path"])
    assert set(test_df["source_type"].unique()) == {"real"}


def test_hybrid_dataset_builder_normalizes_suffixed_ohlc_columns(tmp_path: Path):
    real_path = tmp_path / "real.parquet"
    real_df = _make_frame("2025-01-02", 4, source_type="real", source_market="kospi").rename(
        columns={"open": "open_x", "high": "high_x", "low": "low_x", "close": "close_x"}
    )
    real_df.to_parquet(real_path, index=False)

    config_path = tmp_path / "hybrid_dataset.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "inputs": {"real_catalog_path": str(real_path)},
                "split": {
                    "real_train_ratio": 0.6,
                    "real_validation_ratio": 0.2,
                    "real_test_ratio": 0.2,
                    "bootstrap_when_real_missing": False,
                },
                "mixing": {
                    "train_real_weight": 1.0,
                    "train_synthetic_weight": 0.0,
                    "train_transfer_weight": 0.0,
                    "shuffle_seed": 42,
                },
                "output": {
                    "output_dir": str(tmp_path / "output"),
                    "save_splits": True,
                    "manifest_version": 1,
                    "charting": {"enabled": False},
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = HybridDatasetBuilder(str(config_path)).build(tmp_path)
    train_df = pd.read_parquet(result["manifest"]["train"]["path"])
    assert {"open", "high", "low", "close"}.issubset(train_df.columns)
