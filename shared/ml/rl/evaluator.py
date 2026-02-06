"""RL 모델 평가 및 슬리피지 분석

논문 표1(모델 비교), 표2(테스트만 슬리피지), 표3(학습+테스트 슬리피지) 재현.
결과는 MLflow artifacts로 저장.

Usage:
    evaluator = RLEvaluator()
    results = evaluator.evaluate_model(model, test_days, test_prices)
    comparison = evaluator.compare_models(models, test_days, test_prices)
    slip_df = evaluator.slippage_analysis(model, test_days, test_prices)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from shared.config import ConfigLoader
from shared.ml.rl.env import FuturesTradingEnv, RLEnvConfig, mask_fn

logger = logging.getLogger(__name__)


class RLEvaluator:
    """RL 모델 평가기

    모든 평가 지표 및 슬리피지 설정은 config에서 로드.
    """

    def __init__(self, config_path: str = "ml/rl_mppo.yaml"):
        self.config = ConfigLoader.load(config_path)
        self.env_config = RLEnvConfig.from_yaml(config_path)
        self.slippage_values = self.config.get(
            "slippage_test_values", [0.00, 0.05, 0.10, 0.15, 0.20]
        )

    def evaluate_model(
        self,
        model: Any,
        test_days: list[np.ndarray],
        test_prices: list[np.ndarray],
        slippage: float = 0.0,
        deterministic: bool = True,
    ) -> dict[str, float]:
        """단일 모델 평가

        논문 식 6~8: 평균수익률, 손익비, 승률

        Args:
            model: 학습된 SB3 모델
            test_days: 테스트 일별 피처 배열 리스트
            test_prices: 테스트 일별 OHLC 배열 리스트
            slippage: 슬리피지 값
            deterministic: 결정적 행동 사용 여부

        Returns:
            평가 지표 딕셔너리
        """
        config = RLEnvConfig.from_yaml()
        config.slippage = slippage

        daily_returns = []
        total_trades = 0
        total_wins = 0
        total_losses = 0
        gross_profit = 0.0
        gross_loss = 0.0
        all_trade_pnls: list[float] = []

        for day_data, day_prices in zip(test_days, test_prices):
            env = FuturesTradingEnv(
                day_data=day_data, config=config, prices=day_prices
            )
            obs, info = env.reset()

            terminated = False
            while not terminated:
                # action masking 처리
                masks = env.action_masks()
                try:
                    action, _ = model.predict(
                        obs,
                        deterministic=deterministic,
                        action_masks=masks,
                    )
                except TypeError:
                    # DQN/A2C/PPO는 action_masks 미지원
                    action, _ = model.predict(obs, deterministic=deterministic)

                obs, reward, terminated, truncated, info = env.step(int(action))

            # 일일 수익률
            daily_return = (
                (info["balance"] - config.initial_balance) / config.initial_balance
            )
            daily_returns.append(daily_return)

            # 거래 통계
            total_trades += info["n_trades"]
            total_wins += env.wins
            total_losses += env.losses

            for trade in env.trade_history:
                pnl = trade["pnl"]
                all_trade_pnls.append(pnl)
                if pnl > 0:
                    gross_profit += pnl
                elif pnl < 0:
                    gross_loss += abs(pnl)

        # 평균 수익률 (식 6)
        avg_return = np.mean(daily_returns) * 100 if daily_returns else 0.0

        # 손익비 (식 7): 총이익 / 총손실
        rr_ratio = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # 승률 (식 8)
        win_rate = (total_wins / max(total_trades, 1)) * 100

        # 추가 지표
        total_return = sum(daily_returns) * 100
        max_drawdown = self._calc_max_drawdown(daily_returns)
        sharpe = self._calc_sharpe(daily_returns)

        return {
            "avg_return_pct": round(avg_return, 2),
            "total_return_pct": round(total_return, 2),
            "rr_ratio": round(rr_ratio, 2),
            "win_rate_pct": round(win_rate, 1),
            "total_trades": total_trades,
            "max_drawdown_pct": round(max_drawdown * 100, 2),
            "sharpe_ratio": round(sharpe, 2),
            "daily_returns": daily_returns,
            "slippage": slippage,
        }

    def compare_models(
        self,
        models: dict[str, Any],
        test_days: list[np.ndarray],
        test_prices: list[np.ndarray],
    ) -> pd.DataFrame:
        """표1: 모델 비교 (슬리피지 0)

        Args:
            models: algo_name → model 딕셔너리
            test_days: 테스트 데이터
            test_prices: 테스트 가격 데이터

        Returns:
            모델별 평가 지표 DataFrame
        """
        results = []
        for name, model in models.items():
            logger.info(f"Evaluating {name}...")
            metrics = self.evaluate_model(
                model, test_days, test_prices, slippage=0.0
            )
            results.append(
                {
                    "model": name.upper(),
                    "return_pct": metrics["avg_return_pct"],
                    "rr_ratio": metrics["rr_ratio"],
                    "win_rate_pct": metrics["win_rate_pct"],
                    "total_trades": metrics["total_trades"],
                    "sharpe_ratio": metrics["sharpe_ratio"],
                }
            )

        df = pd.DataFrame(results)
        logger.info(f"\n=== Model Comparison (Table 1) ===\n{df.to_string(index=False)}")

        self._log_mlflow_artifact("model_comparison.csv", df)
        return df

    def slippage_analysis(
        self,
        model: Any,
        test_days: list[np.ndarray],
        test_prices: list[np.ndarray],
        retrain: bool = False,
        trainer: Any = None,
        train_days: list[np.ndarray] | None = None,
        train_prices: list[np.ndarray] | None = None,
    ) -> pd.DataFrame:
        """슬리피지 분석

        retrain=False → 표2 (테스트만 슬리피지 적용)
        retrain=True  → 표3 (학습+테스트 동일 슬리피지로 재학습)

        Args:
            model: 기본 학습된 모델
            test_days: 테스트 데이터
            test_prices: 테스트 가격 데이터
            retrain: 슬리피지별 재학습 여부
            trainer: RLTrainer 인스턴스 (retrain=True시 필요)
            train_days: 학습 데이터 (retrain=True시 필요)
            train_prices: 학습 가격 데이터 (retrain=True시 필요)

        Returns:
            슬리피지별 평가 지표 DataFrame
        """
        results = []
        table_name = "Table 3 (retrain)" if retrain else "Table 2 (test-only)"

        for slip in self.slippage_values:
            logger.info(f"{table_name} | slippage={slip}")

            eval_model = model
            if retrain and trainer is not None and train_days is not None:
                logger.info(f"Retraining with slippage={slip}...")
                eval_model = trainer.train(
                    algo="mppo",
                    train_days=train_days,
                    train_prices=train_prices,
                    slippage=slip,
                )

            metrics = self.evaluate_model(
                eval_model, test_days, test_prices, slippage=slip
            )
            results.append(
                {
                    "slippage": slip,
                    "return_pct": metrics["avg_return_pct"],
                    "rr_ratio": metrics["rr_ratio"],
                    "win_rate_pct": metrics["win_rate_pct"],
                    "total_trades": metrics["total_trades"],
                }
            )

        df = pd.DataFrame(results)
        logger.info(f"\n=== {table_name} ===\n{df.to_string(index=False)}")

        artifact_name = "slippage_retrain.csv" if retrain else "slippage_test_only.csv"
        self._log_mlflow_artifact(artifact_name, df)
        return df

    def _calc_max_drawdown(self, daily_returns: list[float]) -> float:
        """최대 낙폭 계산"""
        if not daily_returns:
            return 0.0

        cumulative = np.cumprod(1 + np.array(daily_returns))
        peak = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - peak) / peak
        return float(np.min(drawdown))

    def _calc_sharpe(
        self, daily_returns: list[float], risk_free_rate: float = 0.035
    ) -> float:
        """샤프 비율 계산 (연율화)"""
        if not daily_returns or len(daily_returns) < 2:
            return 0.0

        returns = np.array(daily_returns)
        daily_rf = (1 + risk_free_rate) ** (1 / 252) - 1
        excess = returns - daily_rf
        if np.std(excess) == 0:
            return 0.0
        return float(np.mean(excess) / np.std(excess) * np.sqrt(252))

    def _log_mlflow_artifact(self, name: str, df: pd.DataFrame) -> None:
        """MLflow artifact로 저장"""
        try:
            import mlflow

            if mlflow.active_run():
                path = Path(f"/tmp/{name}")
                df.to_csv(path, index=False)
                mlflow.log_artifact(str(path))
                logger.info(f"MLflow artifact saved: {name}")
        except (ImportError, Exception) as e:
            logger.debug(f"MLflow artifact save skipped: {e}")
