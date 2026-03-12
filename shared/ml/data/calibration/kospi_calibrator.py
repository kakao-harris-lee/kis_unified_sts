"""Calibration utilities for matching synthetic data to KOSPI-like behavior."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


class KOSPICalibrator:
    def build_scorecard(
        self,
        real_summary: dict[str, Any],
        synthetic_summary: dict[str, Any],
        *,
        real_frame: pd.DataFrame | None = None,
        synthetic_frame: pd.DataFrame | None = None,
    ) -> dict[str, Any]:
        real_range = float(real_summary.get("avg_intraday_range", real_summary.get("max_intraday_range", 0.0)) or 0.0)
        synth_range = float(synthetic_summary.get("avg_intraday_range", synthetic_summary.get("max_intraday_range", 0.0)) or 0.0)
        volume_shape = self._compare_volume_shape(real_frame, synthetic_frame)
        metrics = {
            "return_gap": abs(float(real_summary.get("avg_day_return", 0.0)) - float(synthetic_summary.get("avg_day_return", 0.0))),
            "range_ratio": float(synth_range / (real_range + 1e-10)) if real_range > 0 else 1.0,
            "range_ratio_gap": abs((float(synth_range / (real_range + 1e-10)) if real_range > 0 else 1.0) - 1.0),
            "days_gap": abs(int(real_summary.get("days", real_summary.get("rows", 0)) or 0) - int(synthetic_summary.get("days", synthetic_summary.get("rows", 0)) or 0)),
            "volume_shape": volume_shape,
        }
        recommendations = self._build_recommendations(metrics)
        return {
            "metrics": metrics,
            "recommendations": recommendations,
            "summary": {
                "objective": self.score_scorecard({"metrics": metrics})["objective"],
                "recommendation_count": len(recommendations),
            },
        }

    def write_scorecard(self, scorecard: dict[str, Any], output_path: Path) -> str:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(output_path)

    def apply_recommended_adjustments(
        self,
        source_config: dict[str, Any],
        scorecard: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        candidate = deepcopy(source_config)
        generator = candidate.setdefault("generator", {})
        patch_report: list[dict[str, Any]] = []
        metrics = dict(scorecard.get("metrics", {}) or {})

        range_gap = float(metrics.get("range_ratio_gap", 0.0))
        range_ratio = float(metrics.get("range_ratio", 1.0))
        if range_gap > 0.05:
            direction = -1 if range_ratio > 1.0 else 1
            for key in ["annual_vol", "jump_sigma"]:
                old = float(generator.get(key, 0.20 if key == "annual_vol" else 0.003))
                new = max(old * (1 + 0.08 * direction), 1e-6)
                generator[key] = round(new, 8)
                patch_report.append({"path": f"generator.{key}", "old": old, "new": generator[key]})

        return_gap = float(metrics.get("return_gap", 0.0))
        if return_gap > 0.001:
            old = float(generator.get("drift_per_bar", 0.0))
            direction = -1 if old > 0 else 1
            new = old + direction * min(return_gap / 20, 0.00005)
            generator["drift_per_bar"] = round(new, 8)
            patch_report.append({"path": "generator.drift_per_bar", "old": old, "new": generator["drift_per_bar"]})

        volume_shape = dict(metrics.get("volume_shape", {}) or {})
        if float(volume_shape.get("profile_correlation", 1.0)) < 0.85:
            volume_intraday = generator.setdefault("volume_intraday", {})
            for key, factor in [("open_boost", 1.05), ("close_boost", 1.03)]:
                old = float(volume_intraday.get(key, 1.0))
                volume_intraday[key] = round(old * factor, 6)
                patch_report.append({"path": f"generator.volume_intraday.{key}", "old": old, "new": volume_intraday[key]})

        return candidate, patch_report

    def write_config_candidate(self, candidate_config: dict[str, Any], output_path: Path) -> str:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(yaml.safe_dump(candidate_config, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return str(output_path)

    def compare_scorecards(self, previous_scorecard: dict[str, Any], next_scorecard: dict[str, Any]) -> dict[str, Any]:
        prev_metrics = dict(previous_scorecard.get("metrics", {}) or {})
        next_metrics = dict(next_scorecard.get("metrics", {}) or {})
        improved: list[str] = []
        worsened: list[str] = []
        neutral: list[str] = []

        keys = sorted(set(prev_metrics) | set(next_metrics))
        for key in keys:
            prev_val = prev_metrics.get(key)
            next_val = next_metrics.get(key)
            if isinstance(prev_val, dict) or isinstance(next_val, dict):
                continue
            prev_num = float(prev_val or 0.0)
            next_num = float(next_val or 0.0)
            if next_num < prev_num - 1e-9:
                improved.append(key)
            elif next_num > prev_num + 1e-9:
                worsened.append(key)
            else:
                neutral.append(key)

        prev_score = self.score_scorecard(previous_scorecard)
        next_score = self.score_scorecard(next_scorecard)
        return {
            "previous": prev_score,
            "next": next_score,
            "summary": {
                "improved_metrics": improved,
                "worsened_metrics": worsened,
                "unchanged_metrics": neutral,
                "objective_delta": next_score["objective"] - prev_score["objective"],
            },
        }

    def score_scorecard(self, scorecard: dict[str, Any]) -> dict[str, Any]:
        metrics = dict(scorecard.get("metrics", {}) or {})
        volume_shape = dict(metrics.get("volume_shape", {}) or {})
        components = {
            "return_gap": float(metrics.get("return_gap", 0.0)) * 100.0,
            "range_ratio_gap": float(metrics.get("range_ratio_gap", 0.0)) * 20.0,
            "days_gap": float(metrics.get("days_gap", 0.0)) * 0.01,
            "volume_profile_mae": float(volume_shape.get("profile_mae", 0.0)) * 10.0,
            "volume_profile_correlation_penalty": max(0.0, 1.0 - float(volume_shape.get("profile_correlation", 1.0))) * 5.0,
        }
        objective = float(sum(components.values()))
        return {"objective": objective, "components": components}

    def _build_recommendations(self, metrics: dict[str, Any]) -> list[str]:
        recommendations: list[str] = []
        if float(metrics.get("range_ratio", 1.0)) > 1.1:
            recommendations.append("reduce_volatility")
        elif float(metrics.get("range_ratio", 1.0)) < 0.9:
            recommendations.append("increase_volatility")
        if float(metrics.get("return_gap", 0.0)) > 0.001:
            recommendations.append("tune_drift")
        if float((metrics.get("volume_shape") or {}).get("profile_correlation", 1.0)) < 0.85:
            recommendations.append("reshape_intraday_volume")
        return recommendations

    def _compare_volume_shape(
        self,
        real_frame: pd.DataFrame | None,
        synthetic_frame: pd.DataFrame | None,
    ) -> dict[str, float]:
        if real_frame is None or synthetic_frame is None or real_frame.empty or synthetic_frame.empty:
            return {
                "profile_mae": 0.0,
                "profile_correlation": 1.0,
                "morning_lunch_ratio_gap": 0.0,
                "close_lunch_ratio_gap": 0.0,
            }

        real_profile = self._intraday_volume_profile(real_frame)
        synth_profile = self._intraday_volume_profile(synthetic_frame)
        aligned = pd.concat([real_profile, synth_profile], axis=1).fillna(0.0)
        aligned.columns = ["real", "synthetic"]
        if aligned.empty:
            return {
                "profile_mae": 0.0,
                "profile_correlation": 1.0,
                "morning_lunch_ratio_gap": 0.0,
                "close_lunch_ratio_gap": 0.0,
            }

        mae = float((aligned["real"] - aligned["synthetic"]).abs().mean())
        corr = float(aligned["real"].corr(aligned["synthetic"])) if len(aligned) > 1 else 1.0
        corr = 1.0 if np.isnan(corr) else corr

        def _segment_ratio(series: pd.Series, start: float, end: float, base_start: float, base_end: float) -> float:
            n = len(series)
            if n == 0:
                return 1.0
            idx = np.arange(n)
            seg = series[(idx >= int(n * start)) & (idx < int(n * end))].mean()
            base = series[(idx >= int(n * base_start)) & (idx < int(n * base_end))].mean()
            return float(seg / (base + 1e-10))

        real_morning = _segment_ratio(aligned["real"], 0.0, 0.2, 0.4, 0.6)
        synth_morning = _segment_ratio(aligned["synthetic"], 0.0, 0.2, 0.4, 0.6)
        real_close = _segment_ratio(aligned["real"], 0.8, 1.0, 0.4, 0.6)
        synth_close = _segment_ratio(aligned["synthetic"], 0.8, 1.0, 0.4, 0.6)
        return {
            "profile_mae": mae,
            "profile_correlation": corr,
            "morning_lunch_ratio_gap": abs(real_morning - synth_morning),
            "close_lunch_ratio_gap": abs(real_close - synth_close),
        }

    def _intraday_volume_profile(self, frame: pd.DataFrame) -> pd.Series:
        df = frame.copy()
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime")
        df["bar_index"] = df.groupby(df["datetime"].dt.date).cumcount()
        grouped = df.groupby("bar_index")["volume"].mean()
        total = float(grouped.sum())
        return grouped / total if total > 0 else grouped
