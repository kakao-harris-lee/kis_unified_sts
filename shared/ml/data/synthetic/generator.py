"""Synthetic KOSPI-like intraday OHLCV generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from shared.config import ConfigLoader


class SyntheticGenerator:
    def __init__(self, config_path: str = "ml/synthetic_data.yaml", *, config_data: dict[str, Any] | None = None):
        self.config_path = config_path
        self.config = config_data or self._load_config(config_path)
        self.generator_cfg = dict(self.config.get("generator", {}) or {})
        self.scenarios = dict(self.config.get("scenarios", {}) or {})
        self.dataset_cfg = dict(self.config.get("dataset", {}) or {})

    def _load_config(self, config_path: str) -> dict[str, Any]:
        path = Path(config_path)
        if path.is_absolute() and path.exists():
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        if path.exists():
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        return ConfigLoader.load(config_path)

    def generate_dataset(self) -> pd.DataFrame:
        cfg = self.generator_cfg
        seed = int(cfg.get("seed", 42))
        rng = np.random.default_rng(seed)
        bars_per_day = int(cfg.get("bars_per_day", 390))
        start_date = pd.Timestamp(cfg.get("start_date", "2025-01-02"))
        num_days = int(cfg.get("num_days", 20))
        start_price = float(cfg.get("start_price", 350.0))
        annual_vol = float(cfg.get("annual_vol", 0.20))
        student_t_df = float(cfg.get("student_t_df", 6))
        base_jump_probability = float(cfg.get("jump_probability", 0.0005))
        base_jump_sigma = float(cfg.get("jump_sigma", 0.003))
        base_volume_lambda = float(cfg.get("volume_lambda", 1200))

        schedule = list(self.dataset_cfg.get("scenario_schedule") or list(self.scenarios.keys()) or ["base"])
        if not self.scenarios:
            self.scenarios = {"base": {}}

        bar_vol = annual_vol / np.sqrt(252 * bars_per_day)
        rows: list[dict[str, Any]] = []
        price = start_price

        for day_idx in range(num_days):
            day = start_date + pd.Timedelta(days=day_idx)
            scenario_name = schedule[day_idx % len(schedule)]
            scenario = dict(self.scenarios.get(scenario_name, {}) or {})
            price *= 1 + rng.normal(0, bar_vol * 0.25)
            daily_volume_level = base_volume_lambda * float(scenario.get("volume_level_multiplier", 1.0)) * np.exp(
                rng.normal(0.0, float(cfg.get("volume_day_level_sigma", 0.35)))
            )

            for bar in range(bars_per_day):
                dt = day + pd.Timedelta(hours=9, minutes=bar)
                progress = bar / max(bars_per_day - 1, 1)
                intraday_boost = self._u_shape(progress, cfg)
                drift = float(scenario.get("drift_per_bar", cfg.get("drift_per_bar", 0.0)))
                sigma = bar_vol * float(scenario.get("annual_vol_multiplier", 1.0)) * intraday_boost
                ret = drift + rng.standard_t(student_t_df) * sigma
                jump_probability = base_jump_probability * float(scenario.get("jump_probability_multiplier", 1.0))
                if rng.random() < jump_probability:
                    jump = rng.normal(0.0, base_jump_sigma * float(scenario.get("jump_sigma_multiplier", 1.0)))
                    if rng.random() < float(cfg.get("negative_jump_bias", 0.6)):
                        jump = -abs(jump)
                    ret += jump

                open_price = max(price, 1e-6)
                close_price = max(open_price * (1 + ret), 1e-6)
                wick_sigma = max(abs(ret) * 0.5 + sigma, 1e-6)
                high = max(open_price, close_price) * (1 + abs(rng.normal(0.0, wick_sigma)))
                low = min(open_price, close_price) * max(1e-6, 1 - abs(rng.normal(0.0, wick_sigma)))

                volume_curve = self._volume_curve(progress, cfg)
                vol_noise = np.exp(rng.normal(0.0, float(cfg.get("volume_noise_sigma", 0.25))))
                ret_impact = 1 + abs(ret) * float(cfg.get("volume_return_sensitivity", 1.8))
                volume = max(int(daily_volume_level * volume_curve * vol_noise * ret_impact), 1)

                rows.append(
                    {
                        "datetime": dt,
                        "open": float(open_price),
                        "high": float(max(high, open_price, close_price)),
                        "low": float(min(low, open_price, close_price)),
                        "close": float(close_price),
                        "volume": int(volume),
                        "scenario": scenario_name,
                        "scenario_id": f"{scenario_name}_{day_idx:04d}",
                        "source_type": "synthetic",
                        "source_market": "synthetic",
                        "generator_version": "synthetic_generator_v1",
                        "calibration_version": self.config.get("calibration_version", "base"),
                    }
                )
                price = close_price

        return pd.DataFrame(rows)

    def summarize_dataset(self, df: pd.DataFrame) -> dict[str, Any]:
        frame = df.copy()
        frame["date"] = pd.to_datetime(frame["datetime"]).dt.date
        daily = frame.groupby(["date", "scenario"], as_index=False).agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            total_volume=("volume", "sum"),
        )
        daily["day_return"] = daily["close"] / daily["open"] - 1.0
        daily["intraday_range"] = daily["high"] / daily["low"] - 1.0
        return {
            "rows": int(len(frame)),
            "days": int(daily["date"].nunique()),
            "avg_day_return": float(daily["day_return"].mean()),
            "avg_intraday_range": float(daily["intraday_range"].mean()),
            "max_intraday_range": float(daily["intraday_range"].max()),
            "scenarios": frame["scenario"].value_counts().to_dict(),
        }

    @staticmethod
    def _u_shape(progress: float, cfg: dict[str, Any]) -> float:
        intraday = dict(cfg.get("intraday", {}) or {})
        floor = float(intraday.get("floor", 0.6))
        open_boost = float(intraday.get("open_boost", 1.5))
        close_boost = float(intraday.get("close_boost", 1.3))
        decay = float(intraday.get("decay", 0.08))
        open_term = open_boost * np.exp(-progress / max(decay, 1e-6))
        close_term = close_boost * np.exp(-(1 - progress) / max(decay, 1e-6))
        return max(floor, floor + open_term + close_term)

    @staticmethod
    def _volume_curve(progress: float, cfg: dict[str, Any]) -> float:
        intraday = dict(cfg.get("volume_intraday", {}) or {})
        floor = float(intraday.get("floor", 0.78))
        open_boost = float(intraday.get("open_boost", 1.35))
        close_boost = float(intraday.get("close_boost", 1.18))
        decay = float(intraday.get("decay", 0.05))
        base = floor + open_boost * np.exp(-progress / max(decay, 1e-6)) + close_boost * np.exp(-(1 - progress) / max(decay, 1e-6))

        lunch = dict(cfg.get("volume_lunch_dip", {}) or {})
        lunch_center = float(lunch.get("center", 0.52))
        lunch_width = float(lunch.get("width", 0.11))
        lunch_depth = float(lunch.get("depth", 0.16))
        lunch_penalty = lunch_depth * np.exp(-((progress - lunch_center) ** 2) / max(2 * lunch_width**2, 1e-6))
        return max(0.1, base - lunch_penalty)
