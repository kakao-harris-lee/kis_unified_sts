"""Lightweight dataset chart rendering helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def _pick_series(frame: pd.DataFrame, *candidates: str) -> pd.Series:
    for name in candidates:
        if name in frame.columns:
            return frame[name]
    raise KeyError(candidates[0])


def _plot_close_volume(df: pd.DataFrame, title: str, output_path: Path, *, include_volume: bool) -> str | None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None

    frame = df.copy()
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    frame = frame.sort_values("datetime")

    if frame.empty:
        return None

    close_series = _pick_series(frame, "close", "close_x", "close_y")
    volume_series = _pick_series(frame, "volume", "volume_x", "volume_y") if include_volume else None

    if include_volume:
        fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, height_ratios=[3, 1])
        price_ax, volume_ax = axes
    else:
        fig, price_ax = plt.subplots(1, 1, figsize=(12, 4))
        volume_ax = None

    price_ax.plot(frame["datetime"], close_series, linewidth=1.1, color="#0b6e4f")
    price_ax.set_title(title)
    price_ax.set_ylabel("Close")
    price_ax.grid(alpha=0.25)

    if include_volume and volume_ax is not None:
        volume_ax.bar(frame["datetime"], volume_series, width=0.01, color="#6c8ebf")
        volume_ax.set_ylabel("Volume")
        volume_ax.grid(alpha=0.2)

    fig.autofmt_xdate()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=144)
    plt.close(fig)
    return str(output_path)


def render_dataset_charts(
    df: pd.DataFrame,
    *,
    output_dir: str | Path,
    dataset_label: str,
    chart_cfg: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Render a minimal chart manifest without failing the build pipeline."""
    cfg = chart_cfg or {}
    if not bool(cfg.get("enabled", False)):
        return {}

    output_root = Path(output_dir) / cfg.get("output_dirname", "charts")
    output_root.mkdir(parents=True, exist_ok=True)

    if df.empty:
        manifest_path = output_root / "manifest.json"
        manifest_path.write_text(
            json.dumps({"dataset_label": dataset_label, "charts": [], "skipped": "empty_dataset"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {"manifest": str(manifest_path)}

    frame = df.copy()
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    frame = frame.sort_values("datetime")

    charts: list[dict[str, str]] = []
    if bool(cfg.get("create_overview", True)):
        chart_path = _plot_close_volume(
            frame,
            f"{dataset_label} overview",
            output_root / f"{dataset_label}_overview.{cfg.get('file_format', 'png')}",
            include_volume=bool(cfg.get("include_volume", True)),
        )
        if chart_path:
            charts.append({"kind": "overview", "path": chart_path})

    if bool(cfg.get("create_monthly_charts", False)):
        monthly = frame.assign(month=frame["datetime"].dt.to_period("M"))
        for month, month_df in monthly.groupby("month", sort=True):
            chart_path = _plot_close_volume(
                month_df,
                f"{dataset_label} {month}",
                output_root / f"{dataset_label}_{month}.{cfg.get('file_format', 'png')}",
                include_volume=bool(cfg.get("include_volume", True)),
            )
            if chart_path:
                charts.append({"kind": "monthly", "label": str(month), "path": chart_path})

    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(
        json.dumps({"dataset_label": dataset_label, "charts": charts}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"manifest": str(manifest_path)}
