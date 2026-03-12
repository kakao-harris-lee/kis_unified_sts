"""Regime labeling for real KOSPI OHLCV catalogs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(slots=True)
class RegimeLabelerConfig:
    trend_window: int = 30
    short_vol_window: int = 20
    long_vol_window: int = 120
    morning_window: int = 30
    bull_return_threshold: float = 0.0025
    bear_return_threshold: float = -0.0025
    high_vol_ratio_threshold: float = 1.35
    shock_vol_ratio_threshold: float = 2.0
    low_vol_ratio_threshold: float = 0.75
    crash_return_threshold: float = -0.015
    rebound_return_threshold: float = 0.012
    melt_up_return_threshold: float = 0.015
    gap_down_threshold: float = -0.006
    gap_up_threshold: float = 0.006
    squeeze_range_threshold: float = 0.004
    opening_drive_return_threshold: float = 0.004
    opening_drive_volume_ratio_threshold: float = 1.2


class RegimeLabeler:
    def __init__(self, config: RegimeLabelerConfig | None = None):
        self.config = config or RegimeLabelerConfig()

    def label(self, df: pd.DataFrame) -> pd.DataFrame:
        frame = df.copy()
        frame["datetime"] = pd.to_datetime(frame["datetime"])
        frame = frame.sort_values("datetime").reset_index(drop=True)
        frame["date"] = frame["datetime"].dt.date
        frame["bar_return"] = frame["close"].pct_change().fillna(0.0)

        daily = self._build_daily_summary(frame)
        labeled = frame.merge(daily, on="date", how="left")
        labeled["source_type"] = labeled.get("source_type", "real")
        labeled["source_market"] = labeled.get("source_market", "kospi")
        return labeled

    def summarize_days(self, labeled_df: pd.DataFrame) -> pd.DataFrame:
        if labeled_df.empty:
            return pd.DataFrame()
        summary_cols = [
            "date",
            "open",
            "high",
            "low",
            "close",
            "total_volume",
            "bars",
            "day_return",
            "realized_vol",
            "intraday_range",
            "gap_return",
            "morning_return",
            "morning_volume_ratio",
            "trend_label",
            "volatility_label",
            "event_label",
            "regime_label",
        ]
        available = [col for col in summary_cols if col in labeled_df.columns]
        return labeled_df[available].drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)

    def summary_report(self, daily_summary_df: pd.DataFrame) -> dict[str, Any]:
        if daily_summary_df.empty:
            return {
                "rows": 0,
                "days": 0,
                "avg_day_return": 0.0,
                "avg_realized_vol": 0.0,
                "max_intraday_range": 0.0,
                "trend_distribution": {},
                "volatility_distribution": {},
                "event_distribution": {},
            }
        return {
            "rows": int(len(daily_summary_df)),
            "days": int(len(daily_summary_df)),
            "avg_day_return": float(daily_summary_df["day_return"].mean()),
            "avg_realized_vol": float(daily_summary_df["realized_vol"].mean()),
            "max_intraday_range": float(daily_summary_df["intraday_range"].max()),
            "trend_distribution": daily_summary_df["trend_label"].value_counts().to_dict(),
            "volatility_distribution": daily_summary_df["volatility_label"].value_counts().to_dict(),
            "event_distribution": daily_summary_df["event_label"].value_counts().to_dict(),
        }

    def _build_daily_summary(self, frame: pd.DataFrame) -> pd.DataFrame:
        cfg = self.config
        grouped = frame.groupby("date", sort=True)
        daily = grouped.agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            total_volume=("volume", "sum"),
            bars=("close", "size"),
        ).reset_index()
        daily["day_return"] = daily["close"] / daily["open"] - 1.0
        daily["intraday_range"] = daily["high"] / daily["low"] - 1.0
        daily["prev_close"] = daily["close"].shift(1)
        daily["gap_return"] = np.where(daily["prev_close"] > 0, daily["open"] / daily["prev_close"] - 1.0, 0.0)

        realized = grouped["bar_return"].std().reset_index(name="realized_vol")
        daily = daily.merge(realized, on="date", how="left")
        daily["realized_vol"] = daily["realized_vol"].fillna(0.0)

        morning = frame.groupby("date", sort=True).head(max(1, cfg.morning_window)).groupby("date", sort=True).agg(
            morning_open=("open", "first"),
            morning_close=("close", "last"),
            morning_volume=("volume", "sum"),
        ).reset_index()
        morning["morning_return"] = morning["morning_close"] / morning["morning_open"] - 1.0
        daily = daily.merge(morning[["date", "morning_return", "morning_volume"]], on="date", how="left")
        daily["morning_return"] = daily["morning_return"].fillna(0.0)
        daily["morning_volume_ratio"] = np.where(daily["total_volume"] > 0, daily["morning_volume"] / daily["total_volume"], 0.0)

        long_vol_ma = daily["realized_vol"].rolling(cfg.long_vol_window, min_periods=5).mean()
        vol_ratio = daily["realized_vol"] / (long_vol_ma + 1e-10)

        daily["trend_label"] = np.select(
            [daily["day_return"] >= cfg.bull_return_threshold, daily["day_return"] <= cfg.bear_return_threshold],
            ["bull", "bear"],
            default="sideways",
        )
        daily["volatility_label"] = np.select(
            [vol_ratio >= cfg.shock_vol_ratio_threshold, vol_ratio >= cfg.high_vol_ratio_threshold, vol_ratio <= cfg.low_vol_ratio_threshold],
            ["shock", "high", "low"],
            default="normal",
        )

        event = np.full(len(daily), "normal", dtype=object)
        event[daily["day_return"] <= cfg.crash_return_threshold] = "crash"
        event[daily["day_return"] >= cfg.rebound_return_threshold] = "rebound"
        event[daily["day_return"] >= cfg.melt_up_return_threshold] = "melt_up"
        event[daily["gap_return"] <= cfg.gap_down_threshold] = "gap_down"
        event[daily["gap_return"] >= cfg.gap_up_threshold] = "gap_up"
        squeeze_mask = (daily["intraday_range"] <= cfg.squeeze_range_threshold) & (daily["volatility_label"] == "low")
        event[squeeze_mask] = "squeeze"
        open_drive_mask = (
            (daily["morning_return"] >= cfg.opening_drive_return_threshold)
            & (daily["morning_volume_ratio"] >= cfg.opening_drive_volume_ratio_threshold / max(cfg.morning_window, 1))
        )
        event[open_drive_mask] = "opening_drive"
        daily["event_label"] = event
        daily["regime_label"] = (
            daily["trend_label"].astype(str)
            + "|"
            + daily["volatility_label"].astype(str)
            + "|"
            + daily["event_label"].astype(str)
        )

        daily = daily.drop(columns=["prev_close", "morning_volume"])
        return daily
