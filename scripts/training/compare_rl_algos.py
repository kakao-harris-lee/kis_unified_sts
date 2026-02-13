"""RL 알고리즘 성능 비교 리포트

MPPO baseline과 새 알고리즘(SAC, Multi-Agent, Hierarchical)을 비교.
WF-style 평가: Sharpe, 승률, 손익비, 거래 빈도, Max Drawdown.

Usage:
    python scripts/training/compare_rl_algos.py
    python scripts/training/compare_rl_algos.py --algos mppo sac
    python scripts/training/compare_rl_algos.py --output results/rl/comparison.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 프로젝트 루트
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.ml.rl.evaluator import RLEvaluator
from shared.ml.rl.trainer import ALGO_REGISTRY, CONTINUOUS_ACTION_ALGOS

logger = logging.getLogger(__name__)


def load_or_train_model(
    algo: str,
    config_path: str,
    train_days: list[np.ndarray],
    train_prices: list[np.ndarray],
    eval_days: list[np.ndarray],
    eval_prices: list[np.ndarray],
    force_train: bool = False,
):
    """모델 로드 (있으면) 또는 학습

    Returns:
        학습된 모델
    """
    from shared.config import ConfigLoader

    config = ConfigLoader.load(config_path)
    save_dir = Path(config.get("training", {}).get("save_dir", "./models/futures/rl/"))
    model_path = save_dir / f"{algo}_final.zip"

    if model_path.exists() and not force_train:
        logger.info(f"Loading existing model: {model_path}")
        if algo == "mppo":
            from sb3_contrib import MaskablePPO
            return MaskablePPO.load(str(model_path))
        elif algo == "sac":
            from stable_baselines3 import SAC
            return SAC.load(str(model_path))
        elif algo == "dqn":
            from stable_baselines3 import DQN
            return DQN.load(str(model_path))
        elif algo == "a2c":
            from stable_baselines3 import A2C
            return A2C.load(str(model_path))
        elif algo == "ppo":
            from stable_baselines3 import PPO
            return PPO.load(str(model_path))

    # 학습
    logger.info(f"Training {algo}...")
    from shared.ml.rl.trainer import RLTrainer

    trainer = RLTrainer(config_path=config_path)
    return trainer.train(
        algo=algo,
        train_days=train_days,
        train_prices=train_prices,
        eval_days=eval_days,
        eval_prices=eval_prices,
    )


def compare_algorithms(
    algos: list[str],
    config_path: str = "ml/rl_mppo.yaml",
    force_train: bool = False,
    output_path: str | None = None,
) -> pd.DataFrame:
    """알고리즘 비교 리포트 생성

    Returns:
        비교 결과 DataFrame
    """
    from scripts.training.train_rl import load_data_from_clickhouse

    # 데이터 로드
    logger.info("Loading data...")
    train_days, train_prices, test_days, test_prices = load_data_from_clickhouse(
        config_path
    )

    evaluator = RLEvaluator(config_path=config_path)

    results = []
    for algo in algos:
        if algo not in ALGO_REGISTRY:
            logger.warning(f"Unknown algo: {algo}, skipping")
            continue

        # SAC는 별도 config
        algo_config = "ml/rl_sac.yaml" if algo == "sac" else config_path

        try:
            model = load_or_train_model(
                algo, algo_config,
                train_days, train_prices,
                test_days, test_prices,
                force_train=force_train,
            )

            is_continuous = algo in CONTINUOUS_ACTION_ALGOS
            metrics = evaluator.evaluate_model(
                model, test_days, test_prices,
                slippage=0.0,
                continuous=is_continuous,
            )

            results.append({
                "Algorithm": algo.upper(),
                "Avg Return (%)": metrics["avg_return_pct"],
                "Total Return (%)": metrics["total_return_pct"],
                "Sharpe Ratio": metrics["sharpe_ratio"],
                "Win Rate (%)": metrics["win_rate_pct"],
                "RR Ratio": metrics["rr_ratio"],
                "Total Trades": metrics["total_trades"],
                "Max Drawdown (%)": metrics["max_drawdown_pct"],
            })

            logger.info(
                f"{algo.upper()}: Sharpe={metrics['sharpe_ratio']}, "
                f"WR={metrics['win_rate_pct']}%, "
                f"Trades={metrics['total_trades']}"
            )

        except Exception as e:
            logger.error(f"Failed to evaluate {algo}: {e}")
            results.append({
                "Algorithm": algo.upper(),
                "Avg Return (%)": "ERROR",
                "Total Return (%)": str(e)[:50],
            })

    # MA-CROSS baseline
    try:
        from shared.ml.rl.baselines import MACrossBaseline

        baseline = MACrossBaseline(config_path=config_path)
        bl_metrics = baseline.evaluate(test_days, test_prices)
        results.append({
            "Algorithm": "MA-CROSS (baseline)",
            "Avg Return (%)": bl_metrics["avg_return_pct"],
            "Total Return (%)": "-",
            "Sharpe Ratio": "-",
            "Win Rate (%)": bl_metrics["win_rate_pct"],
            "RR Ratio": bl_metrics["rr_ratio"],
            "Total Trades": bl_metrics["total_trades"],
            "Max Drawdown (%)": "-",
        })
    except Exception as e:
        logger.warning(f"MA-CROSS baseline failed: {e}")

    df = pd.DataFrame(results)

    # 출력
    print("\n" + "=" * 80)
    print("RL Algorithm Comparison Report")
    print("=" * 80)
    print(df.to_string(index=False))
    print("=" * 80)

    if output_path:
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        logger.info(f"Report saved: {output_path}")

    return df


def main():
    parser = argparse.ArgumentParser(description="RL 알고리즘 성능 비교")
    parser.add_argument(
        "--algos", nargs="+",
        default=["mppo", "sac"],
        help="비교할 알고리즘 (default: mppo sac)",
    )
    parser.add_argument(
        "--config", default="ml/rl_mppo.yaml",
        help="기본 config 경로",
    )
    parser.add_argument(
        "--output", default="results/rl/comparison.csv",
        help="결과 CSV 경로",
    )
    parser.add_argument(
        "--force-train", action="store_true",
        help="기존 모델 무시하고 재학습",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    compare_algorithms(
        algos=args.algos,
        config_path=args.config,
        force_train=args.force_train,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
