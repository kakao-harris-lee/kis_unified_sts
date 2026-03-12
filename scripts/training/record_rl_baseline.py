#!/usr/bin/env python3
"""Record the current RL baseline snapshot for the hybrid data pipeline.

This Phase 0 utility captures the current `rl_mppo` configuration and writes a
stable artifact bundle that later hybrid-data experiments can compare against.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.config import ConfigLoader
from shared.ml.rl.baseline_snapshot import (  # noqa: E402
    build_baseline_snapshot,
    resolve_repo_config_path,
    write_baseline_snapshot,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Record RL baseline snapshot")
    parser.add_argument(
        "--config",
        default="ml/hybrid_learning_pipeline.yaml",
        help="Hybrid pipeline config path",
    )
    args = parser.parse_args()

    pipeline_config = ConfigLoader.load(args.config)
    baseline_cfg = (
        pipeline_config.get("phase0", {})
        .get("baseline", {})
    )

    source_config_path = baseline_cfg.get("source_config", "ml/rl_mppo.yaml")
    output_dir = project_root / baseline_cfg.get(
        "output_dir",
        "artifacts/rl/hybrid/baseline",
    )
    experiment_name = baseline_cfg.get(
        "experiment_name",
        "hybrid_learning_pipeline_baseline",
    )
    manifest_version = int(baseline_cfg.get("manifest_version", 1))
    save_source_config_copy = bool(baseline_cfg.get("save_source_config_copy", True))

    source_config = ConfigLoader.load(source_config_path)
    source_config_abs = resolve_repo_config_path(project_root, source_config_path)
    source_config_text = None
    if save_source_config_copy and source_config_abs.exists():
        source_config_text = source_config_abs.read_text(encoding="utf-8")

    snapshot = build_baseline_snapshot(
        source_config,
        source_config_path=source_config_path,
        repo_root=project_root,
        manifest_version=manifest_version,
        experiment_name=experiment_name,
    )
    artifact_paths = write_baseline_snapshot(
        snapshot,
        output_dir=output_dir,
        source_config_text=source_config_text,
    )

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "artifacts": artifact_paths,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
