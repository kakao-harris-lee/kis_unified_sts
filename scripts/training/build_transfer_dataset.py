#!/usr/bin/env python3
"""Build a transfer dataset by adapting external-market patterns to KOSPI-like samples."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.ml.data.charting import render_dataset_charts  # noqa: E402
from shared.ml.data.dataset_quality import validate_ohlcv_quality  # noqa: E402
from shared.ml.data.transfer.cross_market_adapter import CrossMarketAdapter  # noqa: E402


def _write_frame(df: pd.DataFrame, path_without_suffix: Path) -> str:
    path_without_suffix.parent.mkdir(parents=True, exist_ok=True)
    try:
        parquet_path = path_without_suffix.with_suffix(".parquet")
        df.to_parquet(parquet_path, index=False)
        return str(parquet_path)
    except Exception:
        csv_path = path_without_suffix.with_suffix(".csv")
        df.to_csv(csv_path, index=False)
        return str(csv_path)


def build_transfer_dataset(config_path: str = "ml/cross_market_transfer.yaml") -> dict[str, Any]:
    adapter = CrossMarketAdapter(config_path)
    frames = adapter.load_source_frames(project_root)
    transformed = []
    for market, frame in frames:
        adapted = adapter.adapt_frame(frame, source_market=market)
        validate_ohlcv_quality(
            adapted,
            symbol=f"TRANSFER_{market.upper()}",
            table="transfer.external_futures",
        )
        transformed.append(adapted)
    merged = pd.concat(transformed, ignore_index=True)

    output_dir = project_root / adapter.output.get("output_dir", "artifacts/datasets/transfer")
    dataset_path = _write_frame(merged, output_dir / "transfer_dataset")
    summary = {
        "rows": int(len(merged)),
        "source_market_distribution": merged["source_market"].value_counts().to_dict(),
        "scenario_distribution": merged["scenario"].value_counts().to_dict(),
    }
    chart_result = render_dataset_charts(
        merged,
        output_dir=output_dir,
        dataset_label="transfer_dataset",
        chart_cfg=adapter.output.get("charting", {}),
    )
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts = {"dataset": dataset_path, "summary": str(summary_path)}
    if chart_result.get("manifest"):
        artifacts["chart_manifest"] = chart_result["manifest"]
    return {"artifacts": artifacts, "summary": summary}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build cross-market transfer dataset")
    parser.add_argument("--config", default="ml/cross_market_transfer.yaml")
    args = parser.parse_args()
    result = build_transfer_dataset(args.config)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
