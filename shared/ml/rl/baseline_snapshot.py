"""Baseline snapshot helpers for the hybrid RL data pipeline.

Phase 0 captures the current `rl_mppo` configuration, data source settings,
and artifact naming rules so that later hybrid-data experiments can be
compared against a fixed reference point.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from shared.ml.rl.features import RL_FEATURE_COLUMNS


def resolve_repo_config_path(repo_root: Path, config_path: str) -> Path:
    """Resolve a repository-relative config path.

    Args:
        repo_root: Repository root directory.
        config_path: Config path such as ``ml/rl_mppo.yaml`` or
            ``config/ml/rl_mppo.yaml``.

    Returns:
        Absolute path to the config file.
    """
    candidate = Path(config_path)
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0] == "config":
        return repo_root / candidate
    return repo_root / "config" / candidate


def get_git_sha(repo_root: Path) -> str:
    """Get git SHA for the repository, returning ``unknown`` on failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return "unknown"
    return result.stdout.strip() or "unknown"


def build_baseline_snapshot(
    source_config: Mapping[str, Any],
    *,
    source_config_path: str,
    repo_root: Path,
    generated_at: datetime | None = None,
    git_sha: str | None = None,
    manifest_version: int = 1,
    experiment_name: str = "hybrid_learning_pipeline_baseline",
) -> dict[str, Any]:
    """Build a structured baseline snapshot payload.

    Args:
        source_config: Parsed RL configuration.
        source_config_path: Relative path of the source config.
        repo_root: Repository root.
        generated_at: Optional fixed timestamp for tests.
        git_sha: Optional fixed git SHA for tests.
        manifest_version: Baseline manifest version.
        experiment_name: Stable experiment name for Phase 0.

    Returns:
        Serializable baseline snapshot dictionary.
    """
    ts = generated_at or datetime.now(UTC)
    data_cfg = dict(source_config.get("data", {}) or {})

    return {
        "manifest_version": manifest_version,
        "snapshot_kind": "rl_baseline",
        "experiment_name": experiment_name,
        "generated_at": ts.isoformat(),
        "git_sha": git_sha or get_git_sha(repo_root),
        "source_config_path": source_config_path,
        "feature_count": len(RL_FEATURE_COLUMNS),
        "data_profile": {
            "source": data_cfg.get("source", "clickhouse"),
            "database": data_cfg.get("database"),
            "table": data_cfg.get("table"),
            "symbol": data_cfg.get("symbol"),
            "train_ratio": data_cfg.get("train_ratio"),
            "min_bars_per_day": data_cfg.get("min_bars_per_day"),
            "mirror_augmentation": data_cfg.get("mirror_augmentation"),
            "quality": dict(data_cfg.get("quality", {}) or {}),
        },
        "env": dict(source_config.get("env", {}) or {}),
        "reward": dict(source_config.get("reward", {}) or {}),
        "mppo": dict(source_config.get("mppo", {}) or {}),
        "training": dict(source_config.get("training", {}) or {}),
        "tft_aux": dict(source_config.get("tft_aux", {}) or {}),
        "drift_monitoring": dict(source_config.get("drift_monitoring", {}) or {}),
        "notes": [
            "Phase 0 baseline snapshot for hybrid learning data pipeline.",
            "Final model selection must continue to use real-only holdout evaluation.",
        ],
    }


def render_baseline_summary(snapshot: Mapping[str, Any]) -> str:
    """Render a concise markdown summary for the baseline snapshot."""
    data_profile = snapshot.get("data_profile", {}) or {}
    mppo = snapshot.get("mppo", {}) or {}
    training = snapshot.get("training", {}) or {}
    reward = snapshot.get("reward", {}) or {}

    lines = [
        "# RL Baseline Snapshot",
        "",
        f"- generated_at: {snapshot.get('generated_at')}",
        f"- git_sha: {snapshot.get('git_sha')}",
        f"- experiment_name: {snapshot.get('experiment_name')}",
        f"- source_config: {snapshot.get('source_config_path')}",
        f"- feature_count: {snapshot.get('feature_count')}",
        "",
        "## Data Profile",
        f"- source: {data_profile.get('source')}",
        f"- database: {data_profile.get('database')}",
        f"- table: {data_profile.get('table')}",
        f"- symbol: {data_profile.get('symbol')}",
        f"- train_ratio: {data_profile.get('train_ratio')}",
        f"- min_bars_per_day: {data_profile.get('min_bars_per_day')}",
        f"- mirror_augmentation: {data_profile.get('mirror_augmentation')}",
        "",
        "## MPPO Hyperparameters",
        f"- learning_rate: {mppo.get('learning_rate')}",
        f"- gamma: {mppo.get('gamma')}",
        f"- n_steps: {mppo.get('n_steps')}",
        f"- batch_size: {mppo.get('batch_size')}",
        f"- total_timesteps: {mppo.get('total_timesteps')}",
        "",
        "## Reward Weights",
        f"- w_profit: {reward.get('w_profit')}",
        f"- w_cost: {reward.get('w_cost')}",
        f"- w_risk: {reward.get('w_risk')}",
        f"- reward_scale: {reward.get('reward_scale')}",
        "",
        "## Training Paths",
        f"- tensorboard_log: {training.get('tensorboard_log')}",
        f"- save_dir: {training.get('save_dir')}",
        "",
        "## Notes",
    ]

    for note in snapshot.get("notes", []):
        lines.append(f"- {note}")

    lines.append("")
    return "\n".join(lines)


def write_baseline_snapshot(
    snapshot: Mapping[str, Any],
    *,
    output_dir: Path,
    source_config_text: str | None = None,
    source_config_filename: str = "rl_mppo_config_snapshot.yaml",
) -> dict[str, str]:
    """Persist snapshot artifacts to disk.

    Args:
        snapshot: Baseline snapshot payload.
        output_dir: Artifact directory.
        source_config_text: Raw config text to persist.
        source_config_filename: Output filename for config copy.

    Returns:
        Mapping of artifact label to file path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "baseline_snapshot.json"
    json_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary_path = output_dir / "baseline_summary.md"
    summary_path.write_text(
        render_baseline_summary(snapshot),
        encoding="utf-8",
    )

    artifact_paths = {
        "json": str(json_path),
        "summary": str(summary_path),
    }

    if source_config_text is not None:
        config_copy_path = output_dir / source_config_filename
        config_copy_path.write_text(source_config_text, encoding="utf-8")
        artifact_paths["config_copy"] = str(config_copy_path)

    return artifact_paths
