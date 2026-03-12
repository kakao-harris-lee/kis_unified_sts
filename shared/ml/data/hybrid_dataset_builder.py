"""Hybrid dataset manifest builder for RL training/evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from shared.config import ConfigLoader
from shared.ml.data.charting import render_dataset_charts


class HybridDatasetBuilder:
    def __init__(self, config_path: str = "ml/hybrid_dataset.yaml"):
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.inputs = dict(self.config.get("inputs", {}) or {})
        self.split = dict(self.config.get("split", {}) or {})
        self.mixing = dict(self.config.get("mixing", {}) or {})
        self.output = dict(self.config.get("output", {}) or {})

    def _load_config(self, config_path: str) -> dict[str, Any]:
        path = Path(config_path)
        if path.is_absolute() and path.exists():
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        if path.exists():
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        return ConfigLoader.load(config_path)

    def build(self, repo_root: Path) -> dict[str, Any]:
        real_path = self._resolve_path(repo_root, self.inputs.get("real_catalog_path"))
        synthetic_path = self._resolve_path(repo_root, self.inputs.get("synthetic_dataset_path"))
        transfer_path = self._resolve_path(repo_root, self.inputs.get("transfer_dataset_path"))

        real_df = self._load_frame(real_path, source_type="real", source_market="kospi")
        synthetic_df = self._load_frame(synthetic_path, source_type="synthetic", source_market="synthetic")
        transfer_df = self._load_frame(transfer_path, source_type="transfer", source_market="transfer")

        bootstrap_mode = False
        real_catalog_source_mode, real_catalog_authentic = self._infer_real_catalog_provenance(real_path, real_df)

        real_train, real_validation, real_test = self._split_real(real_df)
        if real_df.empty and bool(self.split.get("bootstrap_when_real_missing", False)):
            bootstrap_mode = True
            bootstrap_source = str(self.split.get("bootstrap_test_source", "synthetic"))
            source_df = synthetic_df if bootstrap_source == "synthetic" else transfer_df
            real_train, real_validation, real_test = self._bootstrap_split(source_df)
            real_catalog_source_mode = bootstrap_source
            real_catalog_authentic = False

        if real_train.empty and synthetic_df.empty and transfer_df.empty:
            raise ValueError("No input data available for hybrid dataset build")

        train_df = self._build_train_mix(real_train, synthetic_df, transfer_df)
        validation_df = real_validation.copy()
        test_df = real_test.copy()

        if validation_df.empty:
            validation_df = self._sample_days(synthetic_df, max(1, int(self._unique_days_count(synthetic_df) * float(self.split.get("synthetic_validation_ratio", 0.1)))), self._seed() + 1)
        if test_df.empty:
            candidate = transfer_df if not transfer_df.empty else synthetic_df
            test_df = self._sample_days(candidate, max(1, min(2, self._unique_days_count(candidate))), self._seed() + 2)

        output_dir = repo_root / self.output.get("output_dir", "artifacts/datasets/hybrid")
        output_dir.mkdir(parents=True, exist_ok=True)
        train_path = self._write_frame(train_df, output_dir / "train")
        validation_path = self._write_frame(validation_df, output_dir / "validation")
        test_path = self._write_frame(test_df, output_dir / "test")

        test_is_real_only = not test_df.empty and bool((test_df.get("source_type") == "real").all())
        final_selection_allowed = bool(real_catalog_authentic and test_is_real_only and not bootstrap_mode)

        manifest = {
            "manifest_version": int(self.output.get("manifest_version", 1)),
            "train": {"path": train_path, "rows": int(len(train_df)), "days": self._unique_days_count(train_df)},
            "validation": {"path": validation_path, "rows": int(len(validation_df)), "days": self._unique_days_count(validation_df)},
            "test": {"path": test_path, "rows": int(len(test_df)), "days": self._unique_days_count(test_df)},
            "rules": {
                "bootstrap_mode": bootstrap_mode,
                "test_is_real_only": test_is_real_only,
                "real_catalog_authentic": real_catalog_authentic,
                "real_catalog_source_mode": real_catalog_source_mode,
                "final_selection_allowed": final_selection_allowed,
            },
            "mixing": dict(self.mixing),
        }
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        summary_path = output_dir / "summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "train_source_distribution": train_df.get("source_type", pd.Series(dtype=str)).value_counts().to_dict(),
                    "validation_source_distribution": validation_df.get("source_type", pd.Series(dtype=str)).value_counts().to_dict(),
                    "test_source_distribution": test_df.get("source_type", pd.Series(dtype=str)).value_counts().to_dict(),
                    "rules": manifest["rules"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        artifacts = {"manifest": str(manifest_path), "summary": str(summary_path)}
        chart_result = render_dataset_charts(train_df, output_dir=output_dir, dataset_label="hybrid_train", chart_cfg=self.output.get("charting", {}))
        if chart_result.get("manifest"):
            artifacts["chart_manifest"] = chart_result["manifest"]

        return {"output_dir": str(output_dir), "artifacts": artifacts, "manifest": manifest}

    def _resolve_path(self, repo_root: Path, path_str: str | None) -> Path | None:
        if not path_str:
            return None
        candidate = Path(path_str)
        if candidate.is_absolute():
            return candidate
        direct = repo_root / candidate
        if direct.exists():
            return direct
        config_relative = repo_root / "config" / candidate
        return config_relative

    def _load_frame(self, path: Path | None, *, source_type: str, source_market: str) -> pd.DataFrame:
        if path is None or not path.exists():
            return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume", "source_type", "source_market"])
        frame = pd.read_csv(path) if path.suffix == ".csv" else pd.read_parquet(path)
        frame = frame.copy()
        frame["datetime"] = pd.to_datetime(frame["datetime"])
        frame = self._normalize_ohlcv_columns(frame)
        frame = frame.sort_values("datetime").reset_index(drop=True)
        if "date" not in frame.columns:
            frame["date"] = frame["datetime"].dt.date
        if "source_type" not in frame.columns:
            frame["source_type"] = source_type
        if "source_market" not in frame.columns:
            frame["source_market"] = source_market
        return frame

    @staticmethod
    def _normalize_ohlcv_columns(frame: pd.DataFrame) -> pd.DataFrame:
        normalized = frame.copy()
        for base in ["open", "high", "low", "close", "volume"]:
            if base in normalized.columns:
                continue
            for candidate in [f"{base}_x", f"{base}_y", f"{base}_left", f"{base}_right"]:
                if candidate in normalized.columns:
                    normalized[base] = normalized[candidate]
                    break
        return normalized

    def _infer_real_catalog_provenance(self, real_path: Path | None, real_df: pd.DataFrame) -> tuple[str, bool]:
        if not real_df.empty:
            source_mode = str(real_df.get("real_data_source", pd.Series(["clickhouse"])).iloc[0]) if "real_data_source" in real_df.columns else "clickhouse"
            authentic = bool(real_df.get("real_data_authentic", pd.Series([True])).iloc[0]) if "real_data_authentic" in real_df.columns else True
            return source_mode, authentic
        if real_path is not None:
            summary_path = real_path.parent / "summary.json"
            if summary_path.exists():
                payload = json.loads(summary_path.read_text(encoding="utf-8"))
                provenance = payload.get("provenance", {}) or {}
                return str(provenance.get("source_mode", "unknown")), bool(provenance.get("is_authentic_real", False))
        return "missing", False

    def _split_real(self, real_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        if real_df.empty:
            return real_df.copy(), real_df.copy(), real_df.copy()
        dates = list(pd.Index(real_df["date"].drop_duplicates()).sort_values())
        n_dates = len(dates)
        train_n = max(1, int(n_dates * float(self.split.get("real_train_ratio", 0.7))))
        validation_n = max(1, int(n_dates * float(self.split.get("real_validation_ratio", 0.15))))
        remaining = max(n_dates - train_n - validation_n, 0)
        test_n = max(1, remaining) if n_dates >= 3 else max(n_dates - train_n - validation_n, 0)

        train_dates = set(dates[:train_n])
        validation_dates = set(dates[train_n:train_n + validation_n])
        test_dates = set(dates[train_n + validation_n:train_n + validation_n + test_n])
        return (
            real_df[real_df["date"].isin(train_dates)].copy(),
            real_df[real_df["date"].isin(validation_dates)].copy(),
            real_df[real_df["date"].isin(test_dates)].copy(),
        )

    def _bootstrap_split(self, source_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        if source_df.empty:
            return source_df.copy(), source_df.copy(), source_df.copy()
        dates = list(pd.Index(source_df["date"].drop_duplicates()).sort_values())
        n_dates = len(dates)
        train_n = max(1, int(n_dates * 0.7))
        validation_n = max(1, int(n_dates * 0.15))
        train_dates = set(dates[:train_n])
        validation_dates = set(dates[train_n:train_n + validation_n])
        test_dates = set(dates[train_n + validation_n:])
        if not test_dates:
            test_dates = validation_dates
        return (
            source_df[source_df["date"].isin(train_dates)].copy(),
            source_df[source_df["date"].isin(validation_dates)].copy(),
            source_df[source_df["date"].isin(test_dates)].copy(),
        )

    def _build_train_mix(self, real_train: pd.DataFrame, synthetic_df: pd.DataFrame, transfer_df: pd.DataFrame) -> pd.DataFrame:
        parts = []
        if not real_train.empty:
            parts.append(real_train.copy())
        real_days = max(self._unique_days_count(real_train), 1)
        real_weight = max(float(self.mixing.get("train_real_weight", 0.6)), 1e-9)
        synth_target = int(round(real_days * float(self.mixing.get("train_synthetic_weight", 0.4)) / real_weight))
        transfer_target = int(round(real_days * float(self.mixing.get("train_transfer_weight", 0.2)) / real_weight))
        if real_train.empty:
            synth_target = max(synth_target, self._unique_days_count(synthetic_df))
            transfer_target = max(transfer_target, self._unique_days_count(transfer_df))

        if not synthetic_df.empty and synth_target > 0:
            parts.append(self._sample_days(synthetic_df, synth_target, self._seed()))
        if not transfer_df.empty and transfer_target > 0:
            parts.append(self._sample_days(transfer_df, transfer_target, self._seed() + 7))
        if not parts:
            return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume", "source_type", "source_market", "date"])
        return pd.concat(parts, ignore_index=True).sort_values(["date", "datetime"]).reset_index(drop=True)

    def _sample_days(self, df: pd.DataFrame, n_days: int, seed: int) -> pd.DataFrame:
        if df.empty or n_days <= 0:
            return df.head(0).copy()
        unique_dates = pd.Index(df["date"].drop_duplicates()).sort_values()
        if n_days >= len(unique_dates):
            chosen = set(unique_dates)
        else:
            rng = np.random.default_rng(seed)
            chosen = set(rng.choice(unique_dates.to_numpy(), size=n_days, replace=False).tolist())
        return df[df["date"].isin(chosen)].copy()

    def _write_frame(self, df: pd.DataFrame, path_without_suffix: Path) -> str:
        path_without_suffix.parent.mkdir(parents=True, exist_ok=True)
        try:
            parquet_path = path_without_suffix.with_suffix(".parquet")
            df.to_parquet(parquet_path, index=False)
            return str(parquet_path)
        except Exception:
            csv_path = path_without_suffix.with_suffix(".csv")
            df.to_csv(csv_path, index=False)
            return str(csv_path)

    @staticmethod
    def _unique_days_count(df: pd.DataFrame) -> int:
        if df.empty or "date" not in df.columns:
            return 0
        return int(pd.Index(df["date"].drop_duplicates()).size)

    def _seed(self) -> int:
        return int(self.mixing.get("shuffle_seed", 42))
