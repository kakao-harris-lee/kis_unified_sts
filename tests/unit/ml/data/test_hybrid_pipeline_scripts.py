from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

from scripts.training.build_real_regime_catalog import _resolve_clickhouse_native_port
from scripts.training.build_synthetic_dataset import build_synthetic_dataset
from scripts.training.build_transfer_dataset import build_transfer_dataset


def test_resolve_clickhouse_native_port_ignores_http_port(monkeypatch):
    monkeypatch.delenv("CLICKHOUSE_NATIVE_PORT", raising=False)
    monkeypatch.setenv("CLICKHOUSE_PORT", "8123")
    assert _resolve_clickhouse_native_port() == 9000


def test_build_synthetic_dataset_smoke(tmp_path: Path):
    cfg = yaml.safe_load(Path("config/ml/synthetic_data.yaml").read_text(encoding="utf-8"))
    cfg["generator"]["num_days"] = 2
    cfg["generator"]["bars_per_day"] = 60

    cfg_path = tmp_path / "synthetic.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    result = build_synthetic_dataset(
        source_config_override=str(cfg_path),
        output_dir_override=str(tmp_path / "synthetic_output"),
        dataset_label="synthetic_test",
    )

    dataset = pd.read_parquet(result["artifacts"]["dataset"])
    assert not dataset.empty
    assert set(dataset["source_type"].unique()) == {"synthetic"}


def test_build_transfer_dataset_smoke(tmp_path: Path):
    cfg = yaml.safe_load(Path("config/ml/cross_market_transfer.yaml").read_text(encoding="utf-8"))
    cfg["output"]["output_dir"] = str(tmp_path / "transfer_output")
    cfg["output"]["charting"] = {"enabled": False}
    cfg_path = tmp_path / "transfer.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    result = build_transfer_dataset(str(cfg_path))
    dataset = pd.read_parquet(result["artifacts"]["dataset"])
    assert not dataset.empty
    assert "source_market_distribution" in result["summary"]
