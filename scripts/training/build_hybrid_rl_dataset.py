#!/usr/bin/env python3
"""Build the Phase 5 hybrid RL dataset manifest and split artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.ml.data.hybrid_dataset_builder import HybridDatasetBuilder  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Build hybrid RL dataset")
    parser.add_argument(
        "--config",
        default="ml/hybrid_dataset.yaml",
        help="Hybrid dataset config path",
    )
    args = parser.parse_args()

    builder = HybridDatasetBuilder(args.config)
    result = builder.build(project_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
