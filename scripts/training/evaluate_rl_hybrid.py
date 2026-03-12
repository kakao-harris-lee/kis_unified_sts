#!/usr/bin/env python3
"""Evaluate an RL model against the real-only holdout of the hybrid dataset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.ml.rl.evaluator import RLEvaluator  # noqa: E402
from shared.ml.rl.hybrid_manifest_warnings import build_hybrid_manifest_warning  # noqa: E402
from shared.ml.rl.hybrid_data_loader import HybridRLDataLoader  # noqa: E402


def _load_model(algo: str, model_path: Path):
    if algo == "mppo":
        from sb3_contrib import MaskablePPO

        return MaskablePPO.load(str(model_path))
    if algo == "ppo":
        from stable_baselines3 import PPO

        return PPO.load(str(model_path))
    if algo == "a2c":
        from stable_baselines3 import A2C

        return A2C.load(str(model_path))
    if algo == "dqn":
        from stable_baselines3 import DQN

        return DQN.load(str(model_path))
    if algo == "sac":
        from stable_baselines3 import SAC

        return SAC.load(str(model_path))
    raise ValueError(f"Unsupported algo: {algo}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate RL model on hybrid holdout")
    parser.add_argument("--rl-config", default="ml/rl_mppo.yaml", help="RL config path")
    parser.add_argument("--manifest", default="artifacts/datasets/hybrid/manifest.json", help="Hybrid dataset manifest path")
    parser.add_argument("--algo", default="mppo", help="Algorithm name")
    parser.add_argument("--model-path", help="Trained model path")
    parser.add_argument("--summary-only", action="store_true", help="Only print dataset summary")
    args = parser.parse_args()

    loader = HybridRLDataLoader(args.rl_config)
    data = loader.load_from_manifest(project_root / args.manifest)
    summary = {
        "test_days": len(data["test_days"]),
        "manifest_rules": data["manifest"].get("rules", {}),
    }

    warning_payload = build_hybrid_manifest_warning(summary["manifest_rules"], mode="evaluate")
    if warning_payload:
        summary.update(warning_payload)
        summary["selection_status"] = "non_final"
        print(f"[WARNING] {warning_payload['warning']}", file=sys.stderr)
        print(f"[WARNING] {warning_payload['recommendation']}", file=sys.stderr)
    else:
        summary["selection_status"] = "final_selection_eligible"

    if args.summary_only:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    if not args.model_path:
        raise ValueError("--model-path is required unless --summary-only is used")

    model = _load_model(args.algo, project_root / args.model_path)
    evaluator = RLEvaluator(config_path=args.rl_config)
    metrics = evaluator.evaluate_model(model, data["test_days"], data["test_prices"])
    print(json.dumps({"summary": summary, "metrics": metrics}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
