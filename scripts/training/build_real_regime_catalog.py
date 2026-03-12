#!/usr/bin/env python3
"""Build a real-data regime catalog for the hybrid learning pipeline."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.config import ConfigLoader  # noqa: E402
from shared.ml.data.charting import render_dataset_charts  # noqa: E402
from shared.ml.data.dataset_quality import validate_ohlcv_quality  # noqa: E402
from shared.ml.data.regime_labeler import RegimeLabeler, RegimeLabelerConfig  # noqa: E402


def _generate_sample_data(n_days: int = 20, bars_per_day: int = 390) -> pd.DataFrame:
    import numpy as np

    rng = np.random.default_rng(42)
    rows: list[dict[str, Any]] = []
    base_price = 350.0

    for day in range(n_days):
        price = base_price + day * 0.1
        date = pd.Timestamp("2025-01-02") + pd.Timedelta(days=day)
        for bar in range(bars_per_day):
            dt = date + pd.Timedelta(hours=9) + pd.Timedelta(minutes=bar)
            shock = rng.normal(0, 0.002)
            if day % 9 == 0 and 60 <= bar <= 100:
                shock -= 0.003
            if day % 7 == 0 and 180 <= bar <= 220:
                shock += 0.0025
            price *= 1 + shock
            open_price = price / (1 + shock) if shock != -1 else price
            close_price = price
            wick = abs(rng.normal(0, 0.0015))
            high = max(open_price, close_price) * (1 + wick)
            low = min(open_price, close_price) * (1 - wick)
            volume = max(int(rng.lognormal(mean=6.0, sigma=0.4)), 1)
            rows.append(
                {
                    "datetime": dt,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close_price,
                    "volume": volume,
                }
            )
    return pd.DataFrame(rows)


def _load_ohlcv_from_clickhouse(config_path: str, allow_sample_fallback: bool) -> tuple[pd.DataFrame, dict[str, Any]]:
    rl_config = ConfigLoader.load(config_path)
    data_cfg = rl_config.get("data", {})
    symbol = data_cfg.get("symbol", "101S6000")
    database = data_cfg.get("database", "kospi")
    table = data_cfg.get("table", "kospi200f_1m")
    start_date = data_cfg.get("start_date")
    end_date = data_cfg.get("end_date")
    provenance: dict[str, Any] = {
        "source_mode": "clickhouse",
        "is_authentic_real": True,
        "symbol": symbol,
        "database": database,
        "table": table,
        "start_date": start_date,
        "end_date": end_date,
        "fallback_reason": None,
    }

    try:
        from clickhouse_driver import Client as CHSyncClient

        client = CHSyncClient(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            port=int(os.getenv("CLICKHOUSE_NATIVE_PORT", os.getenv("CLICKHOUSE_PORT", "9000"))),
            user=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        )

        where = ["code = %(symbol)s"]
        params: dict[str, object] = {"symbol": symbol}
        if start_date:
            where.append("datetime >= %(start_dt)s")
            params["start_dt"] = pd.to_datetime(start_date).to_pydatetime()
        if end_date:
            where.append("datetime <= %(end_dt)s")
            params["end_dt"] = pd.to_datetime(end_date).to_pydatetime()

        query = f"""
            SELECT datetime, open, high, low, close, volume
            FROM {database}.{table}
            WHERE {' AND '.join(where)}
            ORDER BY datetime
        """
        rows = client.execute(query, params)
        df = pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"])
    except Exception as exc:
        if not allow_sample_fallback:
            raise
        df = _generate_sample_data()
        provenance.update(
            {
                "source_mode": "sample_fallback",
                "is_authentic_real": False,
                "fallback_reason": f"{type(exc).__name__}: {exc}",
            }
        )

    if df.empty:
        if not allow_sample_fallback:
            raise ValueError(f"No rows loaded for {database}.{table} ({symbol})")
        df = _generate_sample_data()
        provenance.update(
            {
                "source_mode": "sample_fallback",
                "is_authentic_real": False,
                "fallback_reason": provenance.get("fallback_reason") or "empty_clickhouse_result",
            }
        )

    validate_ohlcv_quality(df, symbol=symbol, table=f"{database}.{table}")
    return df, provenance


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


def _render_summary_markdown(summary: dict[str, Any], artifacts: dict[str, str]) -> str:
    lines = [
        "# Real Regime Catalog Summary",
        "",
        f"- rows: {summary.get('rows')}",
        f"- avg_day_return: {summary.get('avg_day_return')}",
        f"- avg_realized_vol: {summary.get('avg_realized_vol')}",
        f"- max_intraday_range: {summary.get('max_intraday_range')}",
        "",
        "## Provenance",
    ]
    for key, value in (summary.get("provenance") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend([
        "",
        "## Trend Distribution",
    ])
    for key, value in (summary.get("trend_distribution") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Volatility Distribution"])
    for key, value in (summary.get("volatility_distribution") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Event Distribution"])
    for key, value in (summary.get("event_distribution") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Artifacts"])
    for key, value in artifacts.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    return "\n".join(lines)


def build_regime_catalog(config_path: str = "ml/hybrid_learning_pipeline.yaml") -> dict[str, Any]:
    pipeline_cfg = ConfigLoader.load(config_path)
    phase1 = pipeline_cfg.get("phase1", {}).get("regime_catalog", {})

    output_dir = project_root / phase1.get("output_dir", "artifacts/datasets/regime_catalog")
    source_config = phase1.get("source_config", "ml/rl_mppo.yaml")
    allow_sample_fallback = bool(phase1.get("allow_sample_fallback", True))

    labeler = RegimeLabeler(
        RegimeLabelerConfig(
            trend_window=int(phase1.get("trend_window", 30)),
            short_vol_window=int(phase1.get("short_vol_window", 20)),
            long_vol_window=int(phase1.get("long_vol_window", 120)),
            morning_window=int(phase1.get("morning_window", 30)),
            bull_return_threshold=float(phase1.get("bull_return_threshold", 0.0025)),
            bear_return_threshold=float(phase1.get("bear_return_threshold", -0.0025)),
            high_vol_ratio_threshold=float(phase1.get("high_vol_ratio_threshold", 1.35)),
            shock_vol_ratio_threshold=float(phase1.get("shock_vol_ratio_threshold", 2.0)),
            low_vol_ratio_threshold=float(phase1.get("low_vol_ratio_threshold", 0.75)),
            crash_return_threshold=float(phase1.get("crash_return_threshold", -0.015)),
            rebound_return_threshold=float(phase1.get("rebound_return_threshold", 0.012)),
            melt_up_return_threshold=float(phase1.get("melt_up_return_threshold", 0.015)),
            gap_down_threshold=float(phase1.get("gap_down_threshold", -0.006)),
            gap_up_threshold=float(phase1.get("gap_up_threshold", 0.006)),
            squeeze_range_threshold=float(phase1.get("squeeze_range_threshold", 0.004)),
            opening_drive_return_threshold=float(phase1.get("opening_drive_return_threshold", 0.004)),
            opening_drive_volume_ratio_threshold=float(phase1.get("opening_drive_volume_ratio_threshold", 1.2)),
        )
    )

    raw_df, provenance = _load_ohlcv_from_clickhouse(source_config, allow_sample_fallback)
    labeled_df = labeler.label(raw_df)
    daily_summary_df = labeler.summarize_days(labeled_df)
    summary = labeler.summary_report(daily_summary_df)

    labeled_df["real_data_source"] = provenance["source_mode"]
    labeled_df["real_data_authentic"] = bool(provenance["is_authentic_real"])
    daily_summary_df["real_data_source"] = provenance["source_mode"]
    daily_summary_df["real_data_authentic"] = bool(provenance["is_authentic_real"])
    summary["provenance"] = provenance

    artifacts: dict[str, str] = {}
    if bool(phase1.get("save_labeled_bars", True)):
        artifacts["labeled_bars"] = _write_frame(labeled_df, output_dir / "labeled_bars")
    if bool(phase1.get("save_daily_summary", True)):
        artifacts["daily_summary"] = _write_frame(daily_summary_df, output_dir / "daily_summary")

    chart_result = render_dataset_charts(
        labeled_df,
        output_dir=output_dir,
        dataset_label="real_regime_catalog",
        chart_cfg=phase1.get("charting", {}),
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
    parser = argparse.ArgumentParser(description="Build real-data regime catalog")
    parser.add_argument(
        "--config",
        default="ml/hybrid_learning_pipeline.yaml",
        help="Hybrid pipeline config path",
    )
    args = parser.parse_args()
    result = build_regime_catalog(args.config)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
