"""계층적 RL 모델 평가 및 비교

Hierarchical RL (High-level + Low-level) 모델 평가 및 flat rl_mppo와 비교.
결과는 MLflow artifacts로 저장.

Usage:
    evaluator = HierarchicalEvaluator()
    results = evaluator.evaluate_hierarchical(
        high_model, low_model, test_days_1m, test_prices_1m, mode="directional"
    )
    comparison = evaluator.compare_with_baseline(
        high_model, low_model, baseline_model, test_days_1m, test_prices_1m
    )
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from shared.config import ConfigLoader
from shared.ml.rl.env import RLEnvConfig
from shared.ml.rl.hierarchical.high_level_env import (
    DirectionalHighLevelConfig,
    DirectionalHighLevelEnv,
    HighLevelAction,
    HighLevelConfig,
    HighLevelDirectionalAction,
    HighLevelEnv,
)
from shared.ml.rl.hierarchical.low_level_env import LowLevelEnv

logger = logging.getLogger(__name__)


class HierarchicalEvaluator:
    """계층적 RL 모델 평가기

    High-level (15분봉) + Low-level (1분봉) 모델 평가 및 비교.
    모든 평가 지표는 config에서 로드.
    """

    def __init__(self, config_path: str = "ml/rl_mppo.yaml"):
        self.config = ConfigLoader.load(config_path)
        self.env_config = RLEnvConfig.from_yaml(config_path)

        hl_cfg = self.config.get("hierarchical", {})
        self.bars_per_step = hl_cfg.get("bars_per_step", 15)  # 15분 = 15개 1분봉

        # High-level 환경 설정
        self.high_level_config = HighLevelConfig(
            n_bar_features=hl_cfg.get("n_bar_features", 25),
            n_summary_features=hl_cfg.get("n_summary_features", 5),
            bars_per_step=self.bars_per_step,
            max_steps=hl_cfg.get("max_steps", 27),
        )

        self.directional_high_level_config = DirectionalHighLevelConfig(
            n_bar_features=hl_cfg.get("n_bar_features", 25),
            n_summary_features=hl_cfg.get("n_summary_features", 5),
            bars_per_step=self.bars_per_step,
            max_steps=hl_cfg.get("max_steps", 27),
        )

    def evaluate_hierarchical(
        self,
        high_model: Any,
        low_model: Any,
        test_days_1m: list[np.ndarray],
        test_prices_1m: list[np.ndarray],
        test_days_15m: list[np.ndarray] | None = None,
        mode: str = "risk_budget",
        slippage: float = 0.0,
        deterministic: bool = True,
    ) -> dict[str, float]:
        """계층적 모델 평가

        Args:
            high_model: High-level 학습된 모델 (PPO)
            low_model: Low-level 학습된 모델 (MaskablePPO)
            test_days_1m: 테스트 일별 1분봉 피처 배열 리스트
            test_prices_1m: 테스트 일별 1분봉 OHLC 배열 리스트
            test_days_15m: 테스트 일별 15분봉 피처 배열 리스트 (None이면 1분봉에서 생성)
            mode: "risk_budget" 또는 "directional"
            slippage: 슬리피지 값
            deterministic: 결정적 행동 사용 여부

        Returns:
            평가 지표 딕셔너리
        """
        if mode not in ("risk_budget", "directional"):
            raise ValueError(f"Invalid mode '{mode}'. Must be 'risk_budget' or 'directional'.")

        config = copy.copy(self.env_config)
        config.slippage = slippage

        daily_returns = []
        total_trades = 0
        total_wins = 0
        total_losses = 0
        gross_profit = 0.0
        gross_loss = 0.0

        # 15분봉 데이터가 없으면 1분봉에서 생성
        if test_days_15m is None:
            test_days_15m = self._create_15m_data(test_days_1m)

        for day_idx, (day_data_1m, day_prices_1m, day_data_15m) in enumerate(
            zip(test_days_1m, test_prices_1m, test_days_15m)
        ):
            logger.debug(f"Evaluating hierarchical model on day {day_idx + 1}/{len(test_days_1m)}")

            # Low-level 환경 생성
            low_env = LowLevelEnv(day_data=day_data_1m, config=config, prices=day_prices_1m)
            low_obs, _ = low_env.reset()

            # High-level 환경 생성
            if mode == "directional":
                high_env = DirectionalHighLevelEnv(
                    day_data_15m=day_data_15m,
                    config=self.directional_high_level_config,
                )
            else:
                high_env = HighLevelEnv(
                    day_data_15m=day_data_15m,
                    config=self.high_level_config,
                )
            high_obs, _ = high_env.reset()

            # 에피소드 실행
            step = 0
            high_step = 0
            terminated = False
            current_risk_budget = 1.0
            current_directional_bias = "flat"

            while not terminated:
                # 15분 간격으로 high-level 행동 결정
                if step % self.bars_per_step == 0:
                    high_action, _ = high_model.predict(high_obs, deterministic=deterministic)
                    high_action = int(high_action)

                    if mode == "directional":
                        # Directional bias 설정
                        current_directional_bias = HighLevelDirectionalAction.BIAS_NAMES.get(
                            high_action, "flat"
                        )
                        low_env.set_directional_bias(current_directional_bias)
                    else:
                        # Risk budget 설정
                        current_risk_budget = self.high_level_config.risk_budgets.get(
                            high_action, 0.5
                        )
                        low_env.set_risk_budget(current_risk_budget)

                # Low-level 행동 (action masking 적용)
                masks = low_env.action_masks()
                low_action, _ = low_model.predict(
                    low_obs, deterministic=deterministic, action_masks=masks
                )
                low_obs, reward, terminated, truncated, info = low_env.step(int(low_action))

                step += 1

            # 일일 수익률
            daily_return = (info["balance"] - config.initial_balance) / config.initial_balance
            daily_returns.append(daily_return)

            # 거래 통계
            total_trades += info["n_trades"]
            total_wins += low_env.wins
            total_losses += low_env.losses

            for trade in low_env.trade_history:
                pnl = trade["pnl"]
                if pnl > 0:
                    gross_profit += pnl
                elif pnl < 0:
                    gross_loss += abs(pnl)

        # 평균 수익률
        avg_return = np.mean(daily_returns) * 100 if daily_returns else 0.0

        # 손익비: 총이익 / 총손실
        rr_ratio = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # 승률
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
            "mode": mode,
        }

    def compare_with_baseline(
        self,
        high_model: Any,
        low_model: Any,
        baseline_model: Any,
        test_days_1m: list[np.ndarray],
        test_prices_1m: list[np.ndarray],
        test_days_15m: list[np.ndarray] | None = None,
        mode: str = "directional",
    ) -> pd.DataFrame:
        """계층적 모델과 baseline flat rl_mppo 비교

        Args:
            high_model: High-level 학습된 모델
            low_model: Low-level 학습된 모델
            baseline_model: Flat rl_mppo 모델 (baseline)
            test_days_1m: 테스트 1분봉 데이터
            test_prices_1m: 테스트 1분봉 가격 데이터
            test_days_15m: 테스트 15분봉 데이터 (선택)
            mode: "risk_budget" 또는 "directional"

        Returns:
            비교 결과 DataFrame
        """
        logger.info("Evaluating hierarchical model...")
        hierarchical_metrics = self.evaluate_hierarchical(
            high_model,
            low_model,
            test_days_1m,
            test_prices_1m,
            test_days_15m,
            mode=mode,
            slippage=0.0,
        )

        logger.info("Evaluating baseline flat rl_mppo...")
        baseline_metrics = self._evaluate_baseline(
            baseline_model, test_days_1m, test_prices_1m, slippage=0.0
        )

        # 비교 결과 생성
        results = [
            {
                "model": f"Hierarchical ({mode})",
                "return_pct": hierarchical_metrics["avg_return_pct"],
                "total_return_pct": hierarchical_metrics["total_return_pct"],
                "rr_ratio": hierarchical_metrics["rr_ratio"],
                "win_rate_pct": hierarchical_metrics["win_rate_pct"],
                "total_trades": hierarchical_metrics["total_trades"],
                "sharpe_ratio": hierarchical_metrics["sharpe_ratio"],
                "max_drawdown_pct": hierarchical_metrics["max_drawdown_pct"],
            },
            {
                "model": "Baseline (flat rl_mppo)",
                "return_pct": baseline_metrics["avg_return_pct"],
                "total_return_pct": baseline_metrics["total_return_pct"],
                "rr_ratio": baseline_metrics["rr_ratio"],
                "win_rate_pct": baseline_metrics["win_rate_pct"],
                "total_trades": baseline_metrics["total_trades"],
                "sharpe_ratio": baseline_metrics["sharpe_ratio"],
                "max_drawdown_pct": baseline_metrics["max_drawdown_pct"],
            },
        ]

        # 개선율 계산
        improvement = {
            "model": "Improvement (%)",
            "return_pct": self._calc_improvement(
                baseline_metrics["avg_return_pct"], hierarchical_metrics["avg_return_pct"]
            ),
            "total_return_pct": self._calc_improvement(
                baseline_metrics["total_return_pct"], hierarchical_metrics["total_return_pct"]
            ),
            "rr_ratio": self._calc_improvement(
                baseline_metrics["rr_ratio"], hierarchical_metrics["rr_ratio"]
            ),
            "win_rate_pct": self._calc_improvement(
                baseline_metrics["win_rate_pct"], hierarchical_metrics["win_rate_pct"]
            ),
            "total_trades": hierarchical_metrics["total_trades"] - baseline_metrics["total_trades"],
            "sharpe_ratio": self._calc_improvement(
                baseline_metrics["sharpe_ratio"], hierarchical_metrics["sharpe_ratio"]
            ),
            "max_drawdown_pct": self._calc_improvement(
                baseline_metrics["max_drawdown_pct"],
                hierarchical_metrics["max_drawdown_pct"],
                lower_is_better=True,
            ),
        }
        results.append(improvement)

        df = pd.DataFrame(results)
        logger.info(f"\n=== Hierarchical vs Baseline Comparison ===\n{df.to_string(index=False)}")

        self._log_mlflow_artifact("hierarchical_comparison.csv", df)
        return df

    def _evaluate_baseline(
        self,
        model: Any,
        test_days: list[np.ndarray],
        test_prices: list[np.ndarray],
        slippage: float = 0.0,
        deterministic: bool = True,
    ) -> dict[str, float]:
        """Baseline flat rl_mppo 모델 평가 (RLEvaluator.evaluate_model과 유사)"""
        config = copy.copy(self.env_config)
        config.slippage = slippage

        daily_returns = []
        total_trades = 0
        total_wins = 0
        total_losses = 0
        gross_profit = 0.0
        gross_loss = 0.0

        for day_data, day_prices in zip(test_days, test_prices):
            from shared.ml.rl.env import FuturesTradingEnv

            env = FuturesTradingEnv(day_data=day_data, config=config, prices=day_prices)
            obs, info = env.reset()

            terminated = False
            while not terminated:
                # action masking 처리
                masks = env.action_masks()
                try:
                    action, _ = model.predict(
                        obs, deterministic=deterministic, action_masks=masks
                    )
                except TypeError:
                    # action_masks 미지원 모델
                    action, _ = model.predict(obs, deterministic=deterministic)
                obs, reward, terminated, truncated, info = env.step(int(action))

            # 일일 수익률
            daily_return = (info["balance"] - config.initial_balance) / config.initial_balance
            daily_returns.append(daily_return)

            # 거래 통계
            total_trades += info["n_trades"]
            total_wins += env.wins
            total_losses += env.losses

            for trade in env.trade_history:
                pnl = trade["pnl"]
                if pnl > 0:
                    gross_profit += pnl
                elif pnl < 0:
                    gross_loss += abs(pnl)

        # 평균 수익률
        avg_return = np.mean(daily_returns) * 100 if daily_returns else 0.0

        # 손익비
        rr_ratio = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # 승률
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
        }

    def _create_15m_data(self, days_1m: list[np.ndarray]) -> list[np.ndarray]:
        """1분봉 데이터에서 15분봉 데이터 생성 (간단한 리샘플링)

        Args:
            days_1m: 1분봉 피처 배열 리스트

        Returns:
            15분봉 피처 배열 리스트
        """
        days_15m = []
        for day_1m in days_1m:
            n_bars = len(day_1m)
            n_15m_bars = n_bars // self.bars_per_step

            # 15분 간격으로 리샘플링 (평균)
            bars_15m = []
            for i in range(n_15m_bars):
                start_idx = i * self.bars_per_step
                end_idx = start_idx + self.bars_per_step
                segment = day_1m[start_idx:end_idx]
                # 평균값으로 15분봉 생성
                bar_15m = np.mean(segment, axis=0)
                bars_15m.append(bar_15m)

            days_15m.append(np.array(bars_15m, dtype=np.float32))

        return days_15m

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

    def _calc_improvement(
        self, baseline: float, new: float, lower_is_better: bool = False
    ) -> float:
        """개선율 계산 (%)

        Args:
            baseline: 기준값
            new: 새로운 값
            lower_is_better: True면 낮을수록 좋은 지표 (예: max_drawdown)

        Returns:
            개선율 (%)
        """
        if baseline == 0:
            return 0.0

        improvement = ((new - baseline) / abs(baseline)) * 100
        if lower_is_better:
            improvement = -improvement  # 낮을수록 좋은 지표는 부호 반전

        return round(improvement, 2)

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
