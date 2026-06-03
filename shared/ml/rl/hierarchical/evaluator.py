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
    latency = evaluator.benchmark_inference_latency(
        high_model, low_model, test_days_1m, test_prices_1m, mode="directional"
    )
"""

from __future__ import annotations

import copy
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from shared.config import ConfigLoader
from shared.ml.rl.env import RLEnvConfig
from shared.ml.rl.evaluator import RLEvaluator
from shared.ml.rl.hierarchical.high_level_env import (
    DirectionalHighLevelConfig,
    DirectionalHighLevelEnv,
    HighLevelConfig,
    HighLevelDirectionalAction,
    HighLevelEnv,
)
from shared.ml.rl.hierarchical.low_level_env import LowLevelEnv
from shared.ml.rl.hierarchical.utils import downsample_1m_to_15m

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

                    # High-level 환경 전진 (관측값 업데이트)
                    if high_step < len(day_data_15m) - 1:
                        high_obs, _, _, _, _ = high_env.step(high_action)
                    high_step += 1

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
        slippage = self.env_config.slippage

        logger.info("Evaluating hierarchical model...")
        hierarchical_metrics = self.evaluate_hierarchical(
            high_model,
            low_model,
            test_days_1m,
            test_prices_1m,
            test_days_15m,
            mode=mode,
            slippage=slippage,
        )

        logger.info("Evaluating baseline flat rl_mppo...")
        baseline_metrics = self._evaluate_baseline(
            baseline_model, test_days_1m, test_prices_1m, slippage=slippage
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

    def benchmark_inference_latency(
        self,
        high_model: Any,
        low_model: Any,
        test_days_1m: list[np.ndarray],
        test_prices_1m: list[np.ndarray],
        test_days_15m: list[np.ndarray] | None = None,
        mode: str = "directional",
        n_warmup: int = 10,
        deterministic: bool = True,
    ) -> dict[str, Any]:
        """추론 지연 시간 벤치마크

        High-level 및 Low-level 모델의 추론 시간을 측정하여
        1분봉 캔들 제약(< 60초) 충족 여부를 확인한다.

        Args:
            high_model: High-level 학습된 모델
            low_model: Low-level 학습된 모델
            test_days_1m: 테스트 1분봉 데이터
            test_prices_1m: 테스트 1분봉 가격 데이터
            test_days_15m: 테스트 15분봉 데이터 (선택)
            mode: "risk_budget" 또는 "directional"
            n_warmup: 워밍업 추론 횟수 (타이밍 제외)
            deterministic: 결정적 행동 사용 여부

        Returns:
            벤치마크 결과 딕셔너리 (mean, median, p95, p99, max 등)
        """
        if mode not in ("risk_budget", "directional"):
            raise ValueError(f"Invalid mode '{mode}'. Must be 'risk_budget' or 'directional'.")

        logger.info("=== Inference Latency Benchmark ===")
        logger.info(f"Mode: {mode}, Warmup iterations: {n_warmup}")

        # 15분봉 데이터가 없으면 1분봉에서 생성
        if test_days_15m is None:
            test_days_15m = self._create_15m_data(test_days_1m)

        # 첫 번째 날 데이터로 환경 생성
        if not test_days_1m or not test_days_15m:
            raise ValueError("Test data is empty")

        day_data_1m = test_days_1m[0]
        day_prices_1m = test_prices_1m[0]
        day_data_15m = test_days_15m[0]

        config = copy.copy(self.env_config)
        config.slippage = 0.0

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

        # === Warmup Phase ===
        logger.info(f"Warming up models ({n_warmup} iterations)...")
        for _ in range(n_warmup):
            # High-level warmup
            high_model.predict(high_obs, deterministic=deterministic)
            # Low-level warmup
            masks = low_env.action_masks()
            low_model.predict(low_obs, deterministic=deterministic, action_masks=masks)

        # === High-level Model Benchmark ===
        logger.info("Benchmarking high-level model...")
        high_times = []
        n_high_inferences = min(100, len(day_data_15m))  # 최대 100회 또는 데이터 길이

        for i in range(n_high_inferences):
            start = time.perf_counter()
            high_model.predict(high_obs, deterministic=deterministic)
            elapsed = time.perf_counter() - start
            high_times.append(elapsed * 1000)  # ms 단위로 저장

        # === Low-level Model Benchmark ===
        logger.info("Benchmarking low-level model...")
        low_times = []
        n_low_inferences = min(400, len(day_data_1m))  # 최대 400회 또는 데이터 길이

        for i in range(n_low_inferences):
            masks = low_env.action_masks()
            start = time.perf_counter()
            low_model.predict(low_obs, deterministic=deterministic, action_masks=masks)
            elapsed = time.perf_counter() - start
            low_times.append(elapsed * 1000)  # ms 단위로 저장

        # === Combined Hierarchical System Benchmark ===
        logger.info("Benchmarking combined hierarchical system...")
        combined_times = []
        n_combined = min(50, len(test_days_1m))  # 최대 50일 테스트

        for day_idx in range(n_combined):
            day_data_1m = test_days_1m[day_idx]
            day_prices_1m = test_prices_1m[day_idx]
            day_data_15m = test_days_15m[day_idx]

            # Low-level 환경 재생성
            low_env = LowLevelEnv(day_data=day_data_1m, config=config, prices=day_prices_1m)
            low_obs, _ = low_env.reset()

            # High-level 환경 재생성
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

            step = 0
            high_step = 0
            terminated = False
            day_start = time.perf_counter()

            while not terminated:
                # 15분 간격으로 high-level 행동 결정
                if step % self.bars_per_step == 0:
                    high_action, _ = high_model.predict(high_obs, deterministic=deterministic)
                    high_action = int(high_action)

                    if mode == "directional":
                        current_directional_bias = HighLevelDirectionalAction.BIAS_NAMES.get(
                            high_action, "flat"
                        )
                        low_env.set_directional_bias(current_directional_bias)
                    else:
                        current_risk_budget = self.high_level_config.risk_budgets.get(
                            high_action, 0.5
                        )
                        low_env.set_risk_budget(current_risk_budget)

                    # High-level 환경 전진 (관측값 업데이트)
                    if high_step < len(day_data_15m) - 1:
                        high_obs, _, _, _, _ = high_env.step(high_action)
                    high_step += 1

                # Low-level 행동
                masks = low_env.action_masks()
                low_action, _ = low_model.predict(
                    low_obs, deterministic=deterministic, action_masks=masks
                )
                low_obs, reward, terminated, truncated, info = low_env.step(int(low_action))
                step += 1

            day_elapsed = time.perf_counter() - day_start
            combined_times.append(day_elapsed * 1000)  # ms 단위

        # === 통계 계산 ===
        high_stats = self._compute_latency_stats(high_times, "High-level")
        low_stats = self._compute_latency_stats(low_times, "Low-level")
        combined_stats = self._compute_latency_stats(combined_times, "Combined (per day)")

        # === 1분봉 제약 검증 ===
        # Combined time을 1분봉 개수로 나눈 평균 시간
        avg_combined_ms = combined_stats["mean_ms"]
        avg_bars_per_day = np.mean([len(d) for d in test_days_1m])
        avg_time_per_bar_ms = avg_combined_ms / avg_bars_per_day if avg_bars_per_day > 0 else 0
        avg_time_per_bar_s = avg_time_per_bar_ms / 1000

        constraint_60s = 60.0  # 1분봉 제약
        passes_constraint = avg_time_per_bar_s < constraint_60s

        logger.info(f"\n=== Latency Constraint Check ===")
        logger.info(f"Average inference time per 1-minute bar: {avg_time_per_bar_ms:.2f} ms ({avg_time_per_bar_s:.3f} s)")
        logger.info(f"Constraint (< 60s per bar): {'✓ PASS' if passes_constraint else '✗ FAIL'}")

        if not passes_constraint:
            logger.warning(
                f"⚠️  Average inference time ({avg_time_per_bar_s:.3f}s) exceeds "
                f"1-minute candle constraint ({constraint_60s}s)!"
            )

        # === MLflow 로깅 ===
        results_df = pd.DataFrame([high_stats, low_stats, combined_stats])
        self._log_mlflow_artifact("inference_latency_benchmark.csv", results_df)

        # 결과 요약
        results = {
            "high_level_stats": high_stats,
            "low_level_stats": low_stats,
            "combined_stats": combined_stats,
            "avg_time_per_bar_ms": round(avg_time_per_bar_ms, 2),
            "avg_time_per_bar_s": round(avg_time_per_bar_s, 3),
            "passes_60s_constraint": passes_constraint,
            "n_high_inferences": n_high_inferences,
            "n_low_inferences": n_low_inferences,
            "n_combined_days": n_combined,
        }

        logger.info("\n=== Benchmark Complete ===")
        return results

    def _compute_latency_stats(self, times_ms: list[float], label: str) -> dict[str, Any]:
        """지연 시간 통계 계산

        Args:
            times_ms: 지연 시간 목록 (ms)
            label: 레이블 (예: "High-level")

        Returns:
            통계 딕셔너리
        """
        if not times_ms:
            return {
                "model": label,
                "mean_ms": 0.0,
                "median_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "max_ms": 0.0,
                "min_ms": 0.0,
                "std_ms": 0.0,
                "n_samples": 0,
            }

        times_arr = np.array(times_ms)
        stats = {
            "model": label,
            "mean_ms": round(float(np.mean(times_arr)), 2),
            "median_ms": round(float(np.median(times_arr)), 2),
            "p95_ms": round(float(np.percentile(times_arr, 95)), 2),
            "p99_ms": round(float(np.percentile(times_arr, 99)), 2),
            "max_ms": round(float(np.max(times_arr)), 2),
            "min_ms": round(float(np.min(times_arr)), 2),
            "std_ms": round(float(np.std(times_arr)), 2),
            "n_samples": len(times_ms),
        }

        logger.info(
            f"{label}: mean={stats['mean_ms']:.2f}ms, "
            f"median={stats['median_ms']:.2f}ms, "
            f"p95={stats['p95_ms']:.2f}ms, "
            f"p99={stats['p99_ms']:.2f}ms, "
            f"max={stats['max_ms']:.2f}ms "
            f"(n={stats['n_samples']})"
        )

        return stats

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
        return [downsample_1m_to_15m(day, self.bars_per_step) for day in days_1m]

    # _calc_max_drawdown / _calc_sharpe: RLEvaluator의 static 메서드 재사용
    _calc_max_drawdown = staticmethod(RLEvaluator._calc_max_drawdown)
    _calc_sharpe = staticmethod(RLEvaluator._calc_sharpe)

    def _calc_improvement(
        self, baseline: float, new: float, lower_is_better: bool = False
    ) -> float:
        """개선율 계산 (%)

        Args:
            baseline: 기준값
            new: 새로운 값
            lower_is_better: True면 낮을수록 좋은 지표 (예: max_drawdown)

        Returns:
            개선율 (%). 양수 = 개선, 음수 = 악화.
        """
        if lower_is_better:
            # max_drawdown 등 음수 지표: 절대값 기준으로 감소하면 개선
            abs_baseline = abs(baseline)
            abs_new = abs(new)
            if abs_baseline == 0:
                return 0.0
            # 절대값이 줄었으면 개선 (양수), 늘었으면 악화 (음수)
            improvement = ((abs_baseline - abs_new) / abs_baseline) * 100
        else:
            if baseline == 0:
                return 0.0
            improvement = ((new - baseline) / abs(baseline)) * 100

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
