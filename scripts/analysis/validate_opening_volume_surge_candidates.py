#!/usr/bin/env python3
"""Validate intraday volume-surge candidate generation from Parquet data.

This script builds a reproducible validation bundle for opening-volume-surge style
entry timing checks:
1) Applies distortion-reduction filters (auction/time-window/liquidity guards)
2) Replays historical minute bars to generate per-minute real-time candidates
3) Extracts entry points (code + timestamp) for manual review
4) Renders price/volume charts with entry markers

Outputs (under --output-dir):
- candidates_all.csv
- candidates_top_per_minute.csv
- entries_first_signal.csv
- charts/*.png
- summary.md
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd
from shared.storage.config import StorageConfig
from shared.storage.market_data_store import ParquetMarketDataStore

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _load_env_file(path: str = ".env") -> None:
    """Best-effort .env loader without external dependency."""
    p = Path(path)
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _create_store() -> ParquetMarketDataStore:
    storage_config = StorageConfig.load_or_default()
    return ParquetMarketDataStore(
        storage_config.market_data.parquet.root,
        asset_class="stock",
    )


def _parse_codes(raw: str) -> list[str]:
    if not raw.strip():
        return []
    out: list[str] = []
    for code in raw.split(","):
        c = code.strip()
        if not c:
            continue
        if not c.isalnum():
            raise ValueError(f"Invalid code value: {c}")
        out.append(c)
    return out


def _load_minute_data(
    store: ParquetMarketDataStore,
    start: str,
    end: str,
    codes: list[str],
) -> pd.DataFrame:
    if not codes:
        dataset_dir = store.root / "stock" / "minute"
        codes = sorted(
            path.name.removeprefix("code=")
            for path in dataset_dir.glob("code=*")
            if path.is_dir()
        )
    frames = [store.get_minute_bars(code, start=start, end=end) for code in codes]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        return df
    df["value"] = pd.to_numeric(df["close"], errors="coerce") * pd.to_numeric(
        df["volume"], errors="coerce"
    )

    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("volume", "value"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df = df.dropna(subset=["datetime", "open", "high", "low", "close"])
    df["code"] = df["code"].astype(str)
    return df.reset_index(drop=True)


@dataclass
class FilterConfig:
    market_open_minute: int
    market_close_minute: int
    min_intra_vol_ma20: float
    min_intra_value_ma20: float
    min_slot_vol_ma5: float
    min_slot_value_ma5: float
    min_vol_ratio_20: float
    min_vol_ratio_slot: float
    spike_hit_ratio: float
    min_spike_hits_5m: int
    min_ret_1m_pct: float
    min_range_pos: float
    max_upper_shadow_ratio: float
    min_body_ratio: float
    min_score: float
    require_close_above_open: bool


def _add_features(df: pd.DataFrame, cfg: FilterConfig) -> pd.DataFrame:
    work = df.copy()
    work = work.sort_values(["code", "datetime"]).reset_index(drop=True)

    work["date"] = work["datetime"].dt.date
    work["minute_of_day"] = work["datetime"].dt.hour * 60 + work["datetime"].dt.minute

    intraday = work.groupby(["code", "date"], sort=False)
    work["prev_close"] = intraday["close"].shift(1)
    work["ret_1m"] = (
        (work["close"] / work["prev_close"] - 1.0)
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )

    spread = (work["high"] - work["low"]).replace(0, np.nan)
    work["range_pos"] = (
        ((work["close"] - work["low"]) / spread).clip(0.0, 1.0).fillna(0.5)
    )
    work["upper_shadow_ratio"] = (
        ((work["high"] - work[["open", "close"]].max(axis=1)) / spread)
        .clip(lower=0.0)
        .fillna(0.0)
    )
    work["body_ratio"] = ((work["close"] - work["open"]).abs() / spread).fillna(0.0)

    work["vol_ma20"] = intraday["volume"].transform(
        lambda s: s.shift(1).rolling(20, min_periods=5).mean()
    )
    work["value_ma20"] = intraday["value"].transform(
        lambda s: s.shift(1).rolling(20, min_periods=5).mean()
    )

    # Same minute-slot baseline across previous trading days.
    slot_sorted = work.sort_values(["code", "minute_of_day", "datetime"]).reset_index()
    slot_group = slot_sorted.groupby(["code", "minute_of_day"], sort=False)
    slot_sorted["vol_slot_ma5"] = slot_group["volume"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=3).mean()
    )
    slot_sorted["value_slot_ma5"] = slot_group["value"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=3).mean()
    )
    work = (
        slot_sorted.set_index("index")
        .sort_index()
        .rename_axis(index=None)
        .reset_index(drop=True)
    )

    work["vol_ratio_20"] = (work["volume"] / work["vol_ma20"]).replace(
        [np.inf, -np.inf], np.nan
    )
    work["vol_ratio_slot"] = (work["volume"] / work["vol_slot_ma5"]).replace(
        [np.inf, -np.inf], np.nan
    )

    work = work.sort_values(["code", "datetime"]).reset_index(drop=True)
    intraday = work.groupby(["code", "date"], sort=False)
    work["spike_hit"] = (work["vol_ratio_20"] >= cfg.spike_hit_ratio).astype(int)
    work["spike_hits_5m"] = intraday["spike_hit"].transform(
        lambda s: s.rolling(5, min_periods=1).sum()
    )

    score = (
        np.log1p(work["vol_ratio_slot"].clip(lower=0).fillna(0)) * 0.45
        + np.log1p(work["vol_ratio_20"].clip(lower=0).fillna(0)) * 0.35
        + work["ret_1m"].clip(lower=0).fillna(0) * 100.0 * 0.15
        + work["range_pos"].clip(lower=0).fillna(0) * 0.05
    )
    work["score"] = score

    # Forward returns (for quality check, not for signal generation).
    for horizon in (5, 15, 30):
        future_close = intraday["close"].shift(-horizon)
        work[f"fwd_ret_{horizon}m_pct"] = (future_close / work["close"] - 1.0) * 100.0

    return work


def _candidate_mask(work: pd.DataFrame, cfg: FilterConfig) -> pd.Series:
    mask = pd.Series(True, index=work.index)
    mask &= work["minute_of_day"].between(
        cfg.market_open_minute, cfg.market_close_minute
    )
    mask &= work["vol_ma20"] >= cfg.min_intra_vol_ma20
    mask &= work["value_ma20"] >= cfg.min_intra_value_ma20
    mask &= work["vol_slot_ma5"] >= cfg.min_slot_vol_ma5
    mask &= work["value_slot_ma5"] >= cfg.min_slot_value_ma5
    mask &= work["vol_ratio_20"] >= cfg.min_vol_ratio_20
    mask &= work["vol_ratio_slot"] >= cfg.min_vol_ratio_slot
    mask &= work["spike_hits_5m"] >= cfg.min_spike_hits_5m
    mask &= (work["ret_1m"] * 100.0) >= cfg.min_ret_1m_pct
    mask &= work["range_pos"] >= cfg.min_range_pos
    mask &= work["upper_shadow_ratio"] <= cfg.max_upper_shadow_ratio
    mask &= work["body_ratio"] >= cfg.min_body_ratio
    mask &= work["score"] >= cfg.min_score
    if cfg.require_close_above_open:
        mask &= work["close"] >= work["open"]
    return mask


def _select_realtime_candidates(
    candidates: pd.DataFrame, top_per_minute: int
) -> pd.DataFrame:
    out = candidates.sort_values(["datetime", "score"], ascending=[True, False]).copy()
    out["rank_at_minute"] = (
        out.groupby("datetime")["score"]
        .rank(method="dense", ascending=False)
        .astype(int)
    )
    return out[out["rank_at_minute"] <= top_per_minute].copy()


def _select_first_entries(realtime: pd.DataFrame) -> pd.DataFrame:
    out = realtime.sort_values(["code", "datetime"]).copy()
    out["date"] = pd.to_datetime(out["datetime"]).dt.date
    return out.drop_duplicates(subset=["code", "date"], keep="first").reset_index(
        drop=True
    )


def _plot_entry_window(
    day_df: pd.DataFrame,
    entry_ts: pd.Timestamp,
    title: str,
    save_path: Path,
    before_minutes: int,
    after_minutes: int,
) -> None:
    day_df = day_df.sort_values("datetime").reset_index(drop=True)
    hit = np.where(day_df["datetime"].values == np.datetime64(entry_ts))[0]
    if len(hit) == 0:
        return
    center = int(hit[0])

    start_idx = max(0, center - before_minutes)
    end_idx = min(len(day_df) - 1, center + after_minutes)
    window = day_df.iloc[start_idx : end_idx + 1].reset_index(drop=True)
    entry_idx = center - start_idx
    x = np.arange(len(window))

    fig, (ax_price, ax_vol) = plt.subplots(
        2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [2, 1]}
    )

    ax_price.plot(x, window["close"], color="#1f2937", linewidth=1.8, label="Close")
    ax_price.scatter(
        [entry_idx],
        [window.loc[entry_idx, "close"]],
        color="#dc2626",
        marker="^",
        s=90,
        label="Entry",
        zorder=5,
    )
    ax_price.axvline(entry_idx, color="#dc2626", linestyle="--", linewidth=1.0)
    ax_price.grid(alpha=0.25, linestyle=":")
    ax_price.legend(loc="upper left")
    ax_price.set_ylabel("Price")
    ax_price.set_title(title)

    up = window["close"] >= window["open"]
    colors = np.where(up, "#16a34a", "#f97316")
    ax_vol.bar(x, window["volume"], color=colors, alpha=0.8, label="Volume")
    if "vol_ma20" in window:
        ax_vol.plot(
            x, window["vol_ma20"], color="#0284c7", linewidth=1.2, label="Vol MA20"
        )
    if "vol_slot_ma5" in window:
        ax_vol.plot(
            x, window["vol_slot_ma5"], color="#7c3aed", linewidth=1.2, label="Slot MA5"
        )
    ax_vol.axvline(entry_idx, color="#dc2626", linestyle="--", linewidth=1.0)
    ax_vol.grid(alpha=0.25, linestyle=":")
    ax_vol.legend(loc="upper left")
    ax_vol.set_ylabel("Volume")

    tick_step = max(1, len(window) // 10)
    tick_idx = list(range(0, len(window), tick_step))
    if tick_idx[-1] != len(window) - 1:
        tick_idx.append(len(window) - 1)
    tick_labels = [window.loc[i, "datetime"].strftime("%H:%M") for i in tick_idx]
    ax_vol.set_xticks(tick_idx)
    ax_vol.set_xticklabels(tick_labels, rotation=30, ha="right")
    ax_vol.set_xlabel("Time (KST)")

    fig.tight_layout()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=140)
    plt.close(fig)


def _write_summary(
    path: Path,
    cfg: FilterConfig,
    full_df: pd.DataFrame,
    candidates: pd.DataFrame,
    realtime: pd.DataFrame,
    entries: pd.DataFrame,
    chart_rows: pd.DataFrame,
) -> None:
    lines: list[str] = []
    lines.append("# Opening Volume Surge Candidate Validation")
    lines.append("")
    lines.append("## Dataset")
    lines.append(f"- Rows: {len(full_df):,}")
    lines.append(f"- Symbols: {full_df['code'].nunique():,}")
    lines.append(f"- Range: {full_df['datetime'].min()} ~ {full_df['datetime'].max()}")
    lines.append("")
    lines.append("## Distortion Filters")
    lines.append(
        f"- Time window: {cfg.market_open_minute}~{cfg.market_close_minute} (minute-of-day)"
    )
    lines.append(f"- min_vol_ma20: {cfg.min_intra_vol_ma20}")
    lines.append(f"- min_value_ma20: {cfg.min_intra_value_ma20}")
    lines.append(f"- min_slot_vol_ma5: {cfg.min_slot_vol_ma5}")
    lines.append(f"- min_slot_value_ma5: {cfg.min_slot_value_ma5}")
    lines.append(f"- min_vol_ratio_20: {cfg.min_vol_ratio_20}")
    lines.append(f"- min_vol_ratio_slot: {cfg.min_vol_ratio_slot}")
    lines.append(f"- spike_hit_ratio: {cfg.spike_hit_ratio}")
    lines.append(f"- min_spike_hits_5m: {cfg.min_spike_hits_5m}")
    lines.append(f"- min_ret_1m_pct: {cfg.min_ret_1m_pct}")
    lines.append(f"- min_range_pos: {cfg.min_range_pos}")
    lines.append(f"- max_upper_shadow_ratio: {cfg.max_upper_shadow_ratio}")
    lines.append(f"- min_body_ratio: {cfg.min_body_ratio}")
    lines.append(f"- min_score: {cfg.min_score}")
    lines.append("")
    lines.append("## Candidate Counts")
    lines.append(f"- All filtered candidates: {len(candidates):,}")
    lines.append(f"- Realtime top-per-minute candidates: {len(realtime):,}")
    lines.append(f"- First-entry points (code x day): {len(entries):,}")
    lines.append("")

    if not entries.empty:
        lines.append("## Entry Forward Return (First-entry)")
        for horizon in (5, 15, 30):
            col = f"fwd_ret_{horizon}m_pct"
            if col in entries.columns:
                s = pd.to_numeric(entries[col], errors="coerce").dropna()
                if len(s) > 0:
                    wr = float((s > 0).mean() * 100.0)
                    lines.append(
                        f"- {horizon}m: mean={s.mean():.3f}% median={s.median():.3f}% win_rate={wr:.1f}% n={len(s)}"
                    )
        lines.append("")

        by_hour = (
            entries.assign(hour=pd.to_datetime(entries["datetime"]).dt.hour)
            .groupby("hour")
            .size()
            .sort_index()
        )
        lines.append("## Entry Hour Distribution")
        for hour, count in by_hour.items():
            lines.append(f"- {int(hour):02d}:00 -> {int(count)}")
        lines.append("")

        top_symbols = (
            entries.groupby("code").size().sort_values(ascending=False).head(15)
        )
        lines.append("## Top Symbols by Entry Count")
        for code, count in top_symbols.items():
            lines.append(f"- {code}: {int(count)}")
        lines.append("")

    if not chart_rows.empty:
        lines.append("## Chart Samples")
        for _, row in chart_rows.iterrows():
            lines.append(
                f"- {row['code']} {row['datetime']} | "
                f"score={row['score']:.3f} | "
                f"vol20={row['vol_ratio_20']:.2f}x slot={row['vol_ratio_slot']:.2f}x | "
                f"chart={row['chart_path']}"
            )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Validate volume-surge realtime candidates")
    p.add_argument("--start", default="2026-01-20 09:00:00")
    p.add_argument("--end", default="2026-02-28 00:00:00")
    p.add_argument("--codes", default="", help="Comma-separated code list (optional)")
    p.add_argument("--output-dir", default="artifacts/ovs_validation")
    p.add_argument("--top-per-minute", type=int, default=3)
    p.add_argument("--max-charts", type=int, default=30)
    p.add_argument("--chart-before-minutes", type=int, default=30)
    p.add_argument("--chart-after-minutes", type=int, default=30)

    # Distortion filters
    p.add_argument("--market-open-minute", type=int, default=545)  # 09:05
    p.add_argument("--market-close-minute", type=int, default=920)  # 15:20
    p.add_argument("--min-intra-vol-ma20", type=float, default=1000.0)
    p.add_argument("--min-intra-value-ma20", type=float, default=100_000_000.0)
    p.add_argument("--min-slot-vol-ma5", type=float, default=1000.0)
    p.add_argument("--min-slot-value-ma5", type=float, default=100_000_000.0)
    p.add_argument("--min-vol-ratio-20", type=float, default=3.0)
    p.add_argument("--min-vol-ratio-slot", type=float, default=3.0)
    p.add_argument("--spike-hit-ratio", type=float, default=2.0)
    p.add_argument("--min-spike-hits-5m", type=int, default=3)
    p.add_argument("--min-ret-1m-pct", type=float, default=0.0)
    p.add_argument("--min-range-pos", type=float, default=0.6)
    p.add_argument("--max-upper-shadow-ratio", type=float, default=0.4)
    p.add_argument("--min-body-ratio", type=float, default=0.15)
    p.add_argument("--min-score", type=float, default=-999.0)
    p.add_argument("--no-require-close-above-open", action="store_true")
    return p


def main() -> int:
    _load_env_file(".env")
    args = build_arg_parser().parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = FilterConfig(
        market_open_minute=args.market_open_minute,
        market_close_minute=args.market_close_minute,
        min_intra_vol_ma20=args.min_intra_vol_ma20,
        min_intra_value_ma20=args.min_intra_value_ma20,
        min_slot_vol_ma5=args.min_slot_vol_ma5,
        min_slot_value_ma5=args.min_slot_value_ma5,
        min_vol_ratio_20=args.min_vol_ratio_20,
        min_vol_ratio_slot=args.min_vol_ratio_slot,
        spike_hit_ratio=args.spike_hit_ratio,
        min_spike_hits_5m=args.min_spike_hits_5m,
        min_ret_1m_pct=args.min_ret_1m_pct,
        min_range_pos=args.min_range_pos,
        max_upper_shadow_ratio=args.max_upper_shadow_ratio,
        min_body_ratio=args.min_body_ratio,
        min_score=args.min_score,
        require_close_above_open=not args.no_require_close_above_open,
    )

    codes = _parse_codes(args.codes)
    store = _create_store()
    df = _load_minute_data(
        store=store,
        start=args.start,
        end=args.end,
        codes=codes,
    )
    if df.empty:
        print("No data found for the requested range.")
        return 1

    print(
        f"Loaded {len(df):,} rows | symbols={df['code'].nunique()} | "
        f"range={df['datetime'].min()}~{df['datetime'].max()}"
    )

    full = _add_features(df, cfg)
    mask = _candidate_mask(full, cfg)
    candidates = full.loc[mask].copy()
    candidates = candidates.sort_values(["datetime", "score"], ascending=[True, False])
    candidates.to_csv(out_dir / "candidates_all.csv", index=False)

    realtime = _select_realtime_candidates(
        candidates, top_per_minute=max(1, args.top_per_minute)
    )
    realtime.to_csv(out_dir / "candidates_top_per_minute.csv", index=False)

    entries = _select_first_entries(realtime)
    entries.to_csv(out_dir / "entries_first_signal.csv", index=False)

    chart_rows: list[dict[str, Any]] = []
    if args.max_charts > 0 and not entries.empty:
        # Prioritize high-score entries for manual inspection
        chart_targets = entries.sort_values("score", ascending=False).head(
            args.max_charts
        )
        for _, row in chart_targets.iterrows():
            code = str(row["code"])
            ts = pd.to_datetime(row["datetime"])
            d = pd.to_datetime(row["datetime"]).date()
            day_df = full[(full["code"] == code) & (full["date"] == d)].copy()
            if day_df.empty:
                continue
            fname = f"{code}_{ts.strftime('%Y%m%d_%H%M')}.png"
            rel = Path("charts") / fname
            chart_path = out_dir / rel
            title = (
                f"{code} {ts.strftime('%Y-%m-%d %H:%M')} | "
                f"score={row['score']:.3f} "
                f"(v20={row['vol_ratio_20']:.2f}x slot={row['vol_ratio_slot']:.2f}x)"
            )
            _plot_entry_window(
                day_df=day_df,
                entry_ts=ts,
                title=title,
                save_path=chart_path,
                before_minutes=max(1, args.chart_before_minutes),
                after_minutes=max(1, args.chart_after_minutes),
            )
            chart_rows.append(
                {
                    "code": code,
                    "datetime": ts,
                    "score": float(row["score"]),
                    "vol_ratio_20": float(row["vol_ratio_20"]),
                    "vol_ratio_slot": float(row["vol_ratio_slot"]),
                    "chart_path": str(rel),
                }
            )

    chart_index = pd.DataFrame(chart_rows)
    chart_index.to_csv(out_dir / "chart_index.csv", index=False)

    _write_summary(
        path=out_dir / "summary.md",
        cfg=cfg,
        full_df=full,
        candidates=candidates,
        realtime=realtime,
        entries=entries,
        chart_rows=chart_index,
    )

    print(f"Candidates(all): {len(candidates):,}")
    print(f"Candidates(top/min): {len(realtime):,}")
    print(f"First entries(code x day): {len(entries):,}")
    print(f"Charts: {len(chart_rows):,}")
    print(f"Output: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
