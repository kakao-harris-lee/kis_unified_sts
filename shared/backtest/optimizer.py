"""파라미터 최적화

Optuna 기반 백테스트 파라미터 최적화.

Usage:
    from shared.backtest import BacktestEngine, BacktestConfig
    from shared.backtest.optimizer import StrategyOptimizer

    optimizer = StrategyOptimizer(
        strategy_class=BBReversionEntry,
        data=historical_data,
        config=BacktestConfig.stock(),
    )

    best_params = optimizer.optimize(
        n_trials=100,
        metric="sharpe_ratio",
    )
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd

from shared.backtest.config import BacktestConfig
from shared.backtest.result import BacktestResult

logger = logging.getLogger(__name__)

# Optional imports
try:
    import optuna
    from optuna import Trial
    from optuna.samplers import TPESampler

    HAS_OPTUNA = True
except ImportError:
    HAS_OPTUNA = False
    optuna = None
    Trial = None

try:
    import mlflow

    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False
    mlflow = None


@dataclass
class ParamSpec:
    """파라미터 스펙

    Attributes:
        name: 파라미터 이름
        param_type: 타입 ("int", "float", "categorical")
        low: 최소값 (int/float)
        high: 최대값 (int/float)
        step: 단계 (선택)
        choices: 선택지 (categorical)
        log: 로그 스케일 여부
    """

    name: str
    param_type: str  # "int", "float", "categorical"
    low: float | None = None
    high: float | None = None
    step: float | None = None
    choices: list[Any] | None = None
    log: bool = False

    @classmethod
    def int(
        cls,
        name: str,
        low: int,
        high: int,
        step: int = 1,
    ) -> ParamSpec:
        """정수 파라미터"""
        return cls(name=name, param_type="int", low=low, high=high, step=step)

    @classmethod
    def float(
        cls,
        name: str,
        low: float,
        high: float,
        step: float | None = None,
        log: bool = False,
    ) -> ParamSpec:
        """실수 파라미터"""
        return cls(name=name, param_type="float", low=low, high=high, step=step, log=log)

    @classmethod
    def categorical(cls, name: str, choices: list[Any]) -> ParamSpec:
        """범주형 파라미터"""
        return cls(name=name, param_type="categorical", choices=choices)


class StrategyOptimizer:
    """전략 파라미터 최적화기

    Optuna를 사용하여 백테스트 성능 기반 최적화.

    Usage:
        optimizer = StrategyOptimizer(
            strategy_factory=lambda params: BBReversionEntry(BBEntryConfig(**params)),
            data=data,
            backtest_config=BacktestConfig.stock(),
        )

        # 파라미터 공간 정의
        optimizer.add_param(ParamSpec.int("bb_period", 10, 30))
        optimizer.add_param(ParamSpec.float("bb_std", 1.5, 3.0, step=0.1))

        # 최적화 실행
        best_params = optimizer.optimize(n_trials=100, metric="sharpe_ratio")
    """

    def __init__(
        self,
        strategy_factory: Callable[[dict[str, Any]], Any],
        data: pd.DataFrame,
        backtest_config: BacktestConfig | None = None,
        mlflow_experiment: str | None = None,
    ):
        """
        Args:
            strategy_factory: 파라미터 딕셔너리로 전략 생성하는 함수
            data: 백테스트 데이터
            backtest_config: 백테스트 설정
            mlflow_experiment: MLflow 실험 이름 (선택)
        """
        if not HAS_OPTUNA:
            raise ImportError(
                "Optuna is required. Install with: pip install optuna>=3.0.0"
            )

        self.strategy_factory = strategy_factory
        self.data = data
        self.backtest_config = backtest_config or BacktestConfig()
        self.mlflow_experiment = mlflow_experiment

        self.param_specs: list[ParamSpec] = []
        self.study: optuna.Study | None = None
        self.best_result: BacktestResult | None = None

    def add_param(self, spec: ParamSpec) -> StrategyOptimizer:
        """파라미터 추가

        Args:
            spec: 파라미터 스펙

        Returns:
            self (체이닝용)
        """
        self.param_specs.append(spec)
        return self

    def add_params(self, specs: list[ParamSpec]) -> StrategyOptimizer:
        """여러 파라미터 추가"""
        self.param_specs.extend(specs)
        return self

    def optimize(
        self,
        n_trials: int = 100,
        metric: str = "sharpe_ratio",
        direction: str = "maximize",
        timeout: int | None = None,
        n_jobs: int = 1,
        show_progress_bar: bool = True,
    ) -> dict[str, Any]:
        """최적화 실행

        Args:
            n_trials: 시행 횟수
            metric: 최적화 메트릭 (sharpe_ratio, total_return_pct, profit_factor 등)
            direction: "maximize" 또는 "minimize"
            timeout: 타임아웃 (초)
            n_jobs: 병렬 처리 수 (-1이면 모든 CPU)
            show_progress_bar: 진행률 표시

        Returns:
            최적 파라미터 딕셔너리
        """
        if not self.param_specs:
            raise ValueError("No parameters defined. Use add_param() first.")

        logger.info(
            f"Starting optimization: {n_trials} trials, "
            f"metric={metric}, direction={direction}"
        )

        # MLflow 설정
        if self.mlflow_experiment and HAS_MLFLOW:
            mlflow.set_experiment(self.mlflow_experiment)

        # Optuna study 생성
        sampler = TPESampler(seed=42)
        self.study = optuna.create_study(
            direction=direction,
            sampler=sampler,
            study_name=f"optimize_{metric}",
        )

        # 최적화 실행
        self.study.optimize(
            lambda trial: self._objective(trial, metric),
            n_trials=n_trials,
            timeout=timeout,
            n_jobs=n_jobs,
            show_progress_bar=show_progress_bar,
        )

        best_params = self.study.best_params
        best_value = self.study.best_value

        logger.info("Optimization complete!")
        logger.info(f"Best {metric}: {best_value:.4f}")
        logger.info(f"Best params: {best_params}")

        return best_params

    def _objective(self, trial: Trial, metric: str) -> float:
        """Optuna 목적 함수"""
        from shared.backtest.engine import BacktestEngine

        # 파라미터 샘플링
        params = self._sample_params(trial)

        try:
            # 전략 생성
            strategy = self.strategy_factory(params)

            # 백테스트 실행
            engine = BacktestEngine(strategy, self.backtest_config)
            result = engine.run(self.data.copy())

            # 메트릭 추출
            value = self._get_metric_value(result, metric)

            # MLflow 로깅 (선택)
            if self.mlflow_experiment and HAS_MLFLOW:
                with mlflow.start_run(nested=True):
                    mlflow.log_params(params)
                    mlflow.log_metrics(result.to_metrics_dict())

            # 최고 결과 저장
            if self.best_result is None or value > self._get_metric_value(
                self.best_result, metric
            ):
                self.best_result = result

            return value

        except Exception as e:
            logger.warning(f"Trial failed: {e}")
            # 실패한 trial은 최악의 값 반환
            return float("-inf") if self.study.direction.name == "MAXIMIZE" else float("inf")

    def _sample_params(self, trial: Trial) -> dict[str, Any]:
        """파라미터 샘플링"""
        params = {}

        for spec in self.param_specs:
            if spec.param_type == "int":
                params[spec.name] = trial.suggest_int(
                    spec.name,
                    int(spec.low),
                    int(spec.high),
                    step=int(spec.step) if spec.step else 1,
                )
            elif spec.param_type == "float":
                if spec.step:
                    params[spec.name] = trial.suggest_float(
                        spec.name,
                        spec.low,
                        spec.high,
                        step=spec.step,
                    )
                else:
                    params[spec.name] = trial.suggest_float(
                        spec.name,
                        spec.low,
                        spec.high,
                        log=spec.log,
                    )
            elif spec.param_type == "categorical":
                params[spec.name] = trial.suggest_categorical(
                    spec.name,
                    spec.choices,
                )

        return params

    def _get_metric_value(self, result: BacktestResult, metric: str) -> float:
        """결과에서 메트릭 값 추출"""
        metrics = result.to_metrics_dict()
        if metric not in metrics:
            raise ValueError(f"Unknown metric: {metric}. Available: {list(metrics.keys())}")
        return metrics[metric]

    def get_optimization_history(self) -> pd.DataFrame:
        """최적화 히스토리 반환"""
        if self.study is None:
            raise ValueError("No optimization has been run yet.")

        return self.study.trials_dataframe()

    def get_param_importances(self) -> dict[str, float]:
        """파라미터 중요도 반환"""
        if self.study is None:
            raise ValueError("No optimization has been run yet.")

        try:
            return optuna.importance.get_param_importances(self.study)
        except Exception as e:
            logger.warning(f"Could not calculate importances: {e}")
            return {}

    def plot_optimization_history(self) -> None:
        """최적화 히스토리 시각화"""
        if self.study is None:
            raise ValueError("No optimization has been run yet.")

        try:
            fig = optuna.visualization.plot_optimization_history(self.study)
            fig.show()
        except Exception as e:
            logger.warning(f"Could not plot history: {e}")

    def plot_param_importances(self) -> None:
        """파라미터 중요도 시각화"""
        if self.study is None:
            raise ValueError("No optimization has been run yet.")

        try:
            fig = optuna.visualization.plot_param_importances(self.study)
            fig.show()
        except Exception as e:
            logger.warning(f"Could not plot importances: {e}")


def quick_optimize(
    strategy_factory: Callable[[dict[str, Any]], Any],
    param_specs: list[ParamSpec],
    data: pd.DataFrame,
    n_trials: int = 50,
    metric: str = "sharpe_ratio",
    backtest_config: BacktestConfig | None = None,
) -> dict[str, Any]:
    """빠른 최적화 (편의 함수)

    Args:
        strategy_factory: 전략 팩토리 함수
        param_specs: 파라미터 스펙 리스트
        data: 백테스트 데이터
        n_trials: 시행 횟수
        metric: 최적화 메트릭
        backtest_config: 백테스트 설정

    Returns:
        최적 파라미터 딕셔너리

    Example:
        best = quick_optimize(
            strategy_factory=lambda p: BBReversionEntry(BBEntryConfig(**p)),
            param_specs=[
                ParamSpec.int("bb_period", 10, 30),
                ParamSpec.float("bb_std", 1.5, 3.0),
            ],
            data=data,
            n_trials=100,
        )
    """
    optimizer = StrategyOptimizer(
        strategy_factory=strategy_factory,
        data=data,
        backtest_config=backtest_config,
    )

    optimizer.add_params(param_specs)

    return optimizer.optimize(
        n_trials=n_trials,
        metric=metric,
        show_progress_bar=True,
    )
