"""Tests for Phase 0 RL baseline snapshot helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from shared.ml.rl.baseline_snapshot import (
    build_baseline_snapshot,
    render_baseline_summary,
    resolve_repo_config_path,
    write_baseline_snapshot,
)


def test_resolve_repo_config_path_accepts_ml_shortcut(tmp_path: Path):
    repo_root = tmp_path
    resolved = resolve_repo_config_path(repo_root, "ml/rl_mppo.yaml")
    assert resolved == repo_root / "config" / "ml" / "rl_mppo.yaml"


def test_build_baseline_snapshot_includes_core_sections(tmp_path: Path):
    snapshot = build_baseline_snapshot(
        {
            "data": {
                "source": "clickhouse",
                "database": "kospi",
                "table": "kospi200f_1m",
                "symbol": "101S6000",
                "train_ratio": 0.8,
                "min_bars_per_day": 300,
                "mirror_augmentation": True,
                "quality": {"enabled": True},
            },
            "env": {"initial_balance": 100_000_000},
            "reward": {"w_profit": 10.0},
            "mppo": {"learning_rate": 0.0001, "gamma": 0.999},
            "training": {"save_dir": "./models/futures/rl/"},
        },
        source_config_path="ml/rl_mppo.yaml",
        repo_root=tmp_path,
        generated_at=datetime(2026, 3, 10, tzinfo=UTC),
        git_sha="abc123",
        experiment_name="phase0_test",
    )

    assert snapshot["snapshot_kind"] == "rl_baseline"
    assert snapshot["git_sha"] == "abc123"
    assert snapshot["source_config_path"] == "ml/rl_mppo.yaml"
    assert snapshot["data_profile"]["symbol"] == "101S6000"
    assert snapshot["mppo"]["gamma"] == 0.999
    assert snapshot["feature_count"] > 0


def test_render_and_write_baseline_snapshot(tmp_path: Path):
    snapshot = build_baseline_snapshot(
        {
            "data": {
                "source": "clickhouse",
                "database": "kospi",
                "table": "kospi200f_1m",
                "symbol": "101S6000",
                "train_ratio": 0.8,
                "min_bars_per_day": 300,
                "mirror_augmentation": True,
            },
            "reward": {"w_profit": 10.0, "w_cost": 0.3, "w_risk": 0.0, "reward_scale": 100.0},
            "mppo": {
                "learning_rate": 0.0001,
                "gamma": 0.999,
                "n_steps": 2048,
                "batch_size": 64,
                "total_timesteps": 5_000_000,
            },
            "training": {
                "tensorboard_log": "./results/rl/tensorboard/",
                "save_dir": "./models/futures/rl/",
            },
        },
        source_config_path="ml/rl_mppo.yaml",
        repo_root=tmp_path,
        generated_at=datetime(2026, 3, 10, tzinfo=UTC),
        git_sha="abc123",
    )

    summary = render_baseline_summary(snapshot)
    assert "# RL Baseline Snapshot" in summary
    assert "101S6000" in summary
    assert "abc123" in summary

    paths = write_baseline_snapshot(
        snapshot,
        output_dir=tmp_path / "artifacts",
        source_config_text="mppo:\n  learning_rate: 0.0001\n",
    )

    json_path = Path(paths["json"])
    summary_path = Path(paths["summary"])
    config_copy_path = Path(paths["config_copy"])

    assert json_path.exists()
    assert summary_path.exists()
    assert config_copy_path.exists()

    written = json.loads(json_path.read_text(encoding="utf-8"))
    assert written["git_sha"] == "abc123"
    assert "RL Baseline Snapshot" in summary_path.read_text(encoding="utf-8")
    assert "learning_rate" in config_copy_path.read_text(encoding="utf-8")
