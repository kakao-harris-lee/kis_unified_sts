#!/usr/bin/env python3
"""Build a synthetic KOSPI-like dataset for the hybrid learning pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.config import ConfigLoader  # noqa: E402
from shared.ml.data.charting import render_dataset_charts  # noqa: E402
from shared.ml.data.dataset_quality import validate_ohlcv_quality  # noqa: E402
from shared.ml.data.synthetic.generator import SyntheticGenerator  # noqa: E402


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


def _daily_summary(df: pd.DataFrame) -> pd.DataFrame:
    out = (
        df.assign(date=pd.to_datetime(df["datetime"]).dt.date)
        .groupby(["date", "scenario"], as_index=False)
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            total_volume=("volume", "sum"),
            bars=("close", "size"),
        )
    )
    out["day_return"] = out["close"] / out["open"] - 1.0
    out["intraday_range"] = out["high"] / out["low"] - 1.0
    return out


def _render_summary_markdown(summary: dict[str, Any], artifacts: dict[str, str]) -> str:
    lines = [
        "# Synthetic Dataset Summary",
        "",
        f"- rows: {summary.get('rows')}",
        f"- days: {summary.get('days')}",
        f"- avg_day_return: {summary.get('avg_day_return')}",
        f"- avg_intraday_range: {summary.get('avg_intraday_range')}",
        f"- max_intraday_range: {summary.get('max_intraday_range')}",
        "",
        "## Scenario Distribution",
    ]
    for key, value in (summary.get("scenarios") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Artifacts"])
    for key, value in artifacts.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    return "\n".join(lines)


def _resolve_repo_file(path_str: str) -> Path:
    candidate = Path(path_str)
    if candidate.is_absolute():
        return candidate
    direct = project_root / candidate
    if direct.exists():
        return direct
    config_relative = project_root / "config" / candidate
    return config_relative


def build_synthetic_dataset(
    config_path: str = "ml/hybrid_learning_pipeline.yaml",
    *,
    source_config_override: str | None = None,
    output_dir_override: str | None = None,
    dataset_label: str = "synthetic_dataset",
    source_config_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pipeline_cfg = ConfigLoader.load(config_path)
    phase2 = pipeline_cfg.get("phase2", {}).get("synthetic_dataset", {})
    source_config = source_config_override or phase2.get("source_config", "ml/synthetic_data.yaml")
    output_dir = project_root / (output_dir_override or phase2.get("output_dir", "artifacts/datasets/synthetic"))

    config_data = source_config_data
    if config_data is None and source_config_override is not None:
        config_data = yaml.safe_load(_resolve_repo_file(source_config_override).read_text(encoding="utf-8"))

    generator = SyntheticGenerator(source_config, config_data=config_data)
    df = generator.generate_dataset()
    validate_ohlcv_quality(df, symbol="SYNTHETIC_KOSPI200", table="synthetic.kospi200f_1m")
    daily_summary_df = _daily_summary(df)
    summary = generator.summarize_dataset(df)

    artifacts: dict[str, str] = {}
    if bool(phase2.get("save_dataset", True)):
        artifacts["dataset"] = _write_frame(df, output_dir / "synthetic_dataset")
    if bool(phase2.get("save_daily_summary", True)):
        artifacts["daily_summary"] = _write_frame(daily_summary_df, output_dir / "daily_summary")

    chart_result = render_dataset_charts(
        df,
        output_dir=output_dir,
        dataset_label=dataset_label,
        chart_cfg=generator.dataset_cfg.get("charting", {}),
    )
    if chart_result.get("manifest"):
        artifacts["chart_manifest"] = chart_result["manifest"]

    summary_json_path = output_dir / "summary.json"
    summary_json_path.parent.mkdir(parents=True, exist_ok=True)
    summary_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts["summary_json"] = str(summary_json_path)

    summary_md_path = output_dir / "summary.md"
    summary_md_path.write_text(_render_summary_markdown(summary, artifacts), encoding="utf-8")
    artifacts["summary_md"] = str(summary_md_path)

    return {
        "output_dir": str(output_dir),
        "artifacts": artifacts,
        "summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build synthetic KOSPI-like dataset")
    parser.add_argument(
        "--config",
        default="ml/hybrid_learning_pipeline.yaml",
        help="Hybrid pipeline config path",
    )
    parser.add_argument("--source-config", help="Override synthetic source config path")
    parser.add_argument("--output-dir", help="Override synthetic output directory")
    parser.add_argument("--dataset-label", default="synthetic_dataset", help="Dataset label for chart outputs")
    args = parser.parse_args()
    result = build_synthetic_dataset(
        args.config,
        source_config_override=args.source_config,
        output_dir_override=args.output_dir,
        dataset_label=args.dataset_label,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
