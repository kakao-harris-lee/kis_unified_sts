#!/usr/bin/env python3
"""Hybrid RL training entrypoint using the existing RL trainer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.ml.rl.hybrid_manifest_warnings import build_hybrid_manifest_warning  # noqa: E402
from shared.ml.rl.hybrid_data_loader import HybridRLDataLoader  # noqa: E402
from shared.ml.rl.trainer import RLTrainer  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Train RL model on hybrid dataset")
    parser.add_argument("--rl-config", default="ml/rl_mppo.yaml", help="RL config path")
    parser.add_argument(
        "--manifest",
        default="artifacts/datasets/hybrid/manifest.json",
        help="Hybrid dataset manifest path",
    )
    parser.add_argument("--algo", default="mppo", help="Algorithm to train")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run a tiny bootstrap smoke training by overriding trainer settings at runtime",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Only prepare arrays and print counts without starting training",
    )
    args = parser.parse_args()

    loader = HybridRLDataLoader(args.rl_config)
    data = loader.load_from_manifest(project_root / args.manifest, persist_scaler=not args.prepare_only)

    summary = {
        "train_days": len(data["train_days"]),
        "validation_days": len(data["validation_days"]),
        "test_days": len(data["test_days"]),
        "manifest_rules": data["manifest"].get("rules", {}),
    }

    warning_payload = build_hybrid_manifest_warning(summary["manifest_rules"], mode="train")
    if warning_payload:
        summary.update(warning_payload)
        summary["selection_status"] = "non_final"
        print(f"[WARNING] {warning_payload['warning']}", file=sys.stderr)
        print(f"[WARNING] {warning_payload['recommendation']}", file=sys.stderr)
    else:
        summary["selection_status"] = "final_selection_eligible"

    if args.prepare_only:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    trainer = RLTrainer(config_path=args.rl_config)
    if args.smoke:
        trainer.config.setdefault(args.algo, {})
        trainer.config[args.algo]["total_timesteps"] = 256
        trainer.config[args.algo]["n_steps"] = 128
        trainer.config[args.algo]["batch_size"] = 32
        trainer.config[args.algo]["n_epochs"] = 2
        trainer.config.setdefault("training", {})
        trainer.config["training"]["eval_freq"] = 128
        trainer.config["training"]["checkpoint_freq"] = 256
        trainer.save_dir = project_root / "models/futures/rl/bootstrap_smoke"
        trainer.save_dir.mkdir(parents=True, exist_ok=True)
        trainer.tb_log = "./results/rl/bootstrap_smoke/tensorboard/"
        summary["smoke_overrides"] = {
            "total_timesteps": 256,
            "n_steps": 128,
            "batch_size": 32,
            "n_epochs": 2,
        }

    trainer.train(
        algo=args.algo,
        train_days=data["train_days"],
        train_prices=data["train_prices"],
        eval_days=data["validation_days"],
        eval_prices=data["validation_prices"],
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
