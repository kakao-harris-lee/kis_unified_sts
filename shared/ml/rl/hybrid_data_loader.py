"""Hybrid dataset loader for RL training/evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

from shared.config import ConfigLoader
from shared.ml.rl.features import RLFeatureCalculator, RL_FEATURE_COLUMNS


def _read_frame(path: Path) -> pd.DataFrame:
    if path.suffix == ".csv":
        return pd.read_csv(path)
    return pd.read_parquet(path)


def _frame_to_days(df: pd.DataFrame, scaler: MinMaxScaler) -> tuple[list[np.ndarray], list[np.ndarray]]:
    days: list[np.ndarray] = []
    prices: list[np.ndarray] = []
    for _, day_df in df.groupby("date", sort=True):
        if day_df.empty:
            continue
        features = scaler.transform(day_df[RL_FEATURE_COLUMNS].values)
        ohlc = day_df[["open", "high", "low", "close"]].values
        days.append(features.astype(np.float32))
        prices.append(ohlc.astype(np.float32))
    return days, prices


class HybridRLDataLoader:
    """Prepare hybrid dataset manifest splits for the existing RL trainer."""

    def __init__(self, rl_config_path: str = "ml/rl_mppo.yaml"):
        self.rl_config = ConfigLoader.load(rl_config_path)
        self.rl_config_path = rl_config_path
        self.feature_calculator = RLFeatureCalculator()

    def load_from_manifest(
        self,
        manifest_path: str | Path,
        *,
        persist_scaler: bool = False,
    ) -> dict[str, Any]:
        manifest_file = Path(manifest_path)
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

        train_df = self._prepare_split(manifest["train"]["path"])
        validation_df = self._prepare_split(manifest["validation"]["path"])
        test_df = self._prepare_split(manifest["test"]["path"])

        scaler = MinMaxScaler()
        scaler.fit(train_df[RL_FEATURE_COLUMNS].values)

        if persist_scaler:
            save_dir = Path(self.rl_config.get("training", {}).get("save_dir", "./models/futures/rl/"))
            save_dir.mkdir(parents=True, exist_ok=True)
            joblib.dump(scaler, save_dir / "scaler.joblib")
            joblib.dump(scaler, save_dir / "hybrid_scaler.joblib")

        train_days, train_prices = _frame_to_days(train_df, scaler)
        validation_days, validation_prices = _frame_to_days(validation_df, scaler)
        test_days, test_prices = _frame_to_days(test_df, scaler)

        return {
            "manifest": manifest,
            "train_days": train_days,
            "train_prices": train_prices,
            "validation_days": validation_days,
            "validation_prices": validation_prices,
            "test_days": test_days,
            "test_prices": test_prices,
        }

    def _prepare_split(self, split_path: str) -> pd.DataFrame:
        df = _read_frame(Path(split_path)).copy()
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values(["date", "datetime"]).reset_index(drop=True)
        calc_df = self.feature_calculator.calculate(df[["datetime", "open", "high", "low", "close", "volume"]].copy())
        calc_df["date"] = pd.to_datetime(calc_df["datetime"]).dt.date

        metadata_cols = [
            col for col in [
                "source_type",
                "source_market",
                "scenario_id",
                "generator_version",
                "calibration_version",
                "regime_label",
                "scenario",
            ]
            if col in df.columns
        ]
        if metadata_cols:
            merged = calc_df.merge(
                df[["datetime", *metadata_cols]].drop_duplicates(subset=["datetime"]),
                on="datetime",
                how="left",
            )
        else:
            merged = calc_df

        return merged.dropna(subset=RL_FEATURE_COLUMNS).reset_index(drop=True)
