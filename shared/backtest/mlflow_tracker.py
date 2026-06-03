"""MLflow 트래커

백테스트 결과를 MLflow로 추적.

Usage:
    tracker = MLflowTracker("experiment_name")

    with tracker.start_run(run_name="bb_reversion_v1"):
        result = engine.run(data)
        tracker.log_result(result, strategy_config)

    # 또는 간편 함수
    run_id = track_backtest(
        experiment_name="stock_strategies",
        result=result,
        strategy_config=config,
    )
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

import pandas as pd

from shared.backtest.mlflow_uri import resolve_tracking_uri
from shared.backtest.result import BacktestResult

logger = logging.getLogger(__name__)

# Optional imports
try:
    import mlflow

    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False
    mlflow = None

try:
    import matplotlib.pyplot as plt

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    plt = None

try:
    import seaborn as sns

    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False
    sns = None


class MLflowTracker:
    """MLflow 기반 실험 추적기

    백테스트를 ML 실험으로 취급하여 추적:
    - Parameters: 전략 하이퍼파라미터 + git SHA
    - Metrics: Sharpe ratio, MDD, win rate 등
    - Artifacts: equity curve, drawdown chart, trade log

    Usage:
        tracker = MLflowTracker("V35_Development")

        with tracker.start_run(run_name="RSI_14_MACD_12_26"):
            result = engine.run(data)
            tracker.log_result(result, strategy.get_config())
    """

    def __init__(
        self,
        experiment_name: str,
        tracking_uri: str | None = None,
    ):
        """
        Args:
            experiment_name: MLflow 실험 이름
            tracking_uri: MLflow tracking URI. Defaults to MLFLOW_TRACKING_URI
                (the docker mlflow server when set) or local sqlite.
        """
        if not HAS_MLFLOW:
            raise ImportError(
                "MLflow is required. Install with: pip install mlflow>=2.10.0"
            )

        self.experiment_name = experiment_name
        self.tracking_uri = resolve_tracking_uri(tracking_uri)

        mlflow.set_tracking_uri(self.tracking_uri)
        mlflow.set_experiment(experiment_name)

        logger.info(
            f"MLflowTracker initialized: {experiment_name} " f"(uri={self.tracking_uri})"
        )

    @contextmanager
    def start_run(
        self, run_name: str | None = None
    ) -> Generator[mlflow.ActiveRun, None, None]:
        """실험 run 시작

        Args:
            run_name: run 이름 (예: "RSI_14_baseline")

        Yields:
            MLflow ActiveRun
        """
        with mlflow.start_run(run_name=run_name) as run:
            yield run

    def log_params(self, params: dict[str, Any]) -> None:
        """파라미터 로깅

        자동 추가:
        - git_sha: 코드 버전
        - backtest_timestamp: 실행 시각
        """
        params = params.copy()
        params["git_sha"] = self._get_git_sha()
        params["backtest_timestamp"] = datetime.now().isoformat()

        # MLflow 파라미터 값 길이 제한 (500자)
        for key, value in params.items():
            if isinstance(value, str) and len(value) > 500:
                params[key] = value[:497] + "..."

        mlflow.log_params(params)
        logger.debug(f"Logged {len(params)} parameters")

    def log_metrics(self, result: BacktestResult) -> None:
        """메트릭 로깅"""
        metrics = result.to_metrics_dict()

        # None 값 및 비숫자 필터링
        metrics = {
            k: v
            for k, v in metrics.items()
            if v is not None and isinstance(v, (int, float))
        }

        mlflow.log_metrics(metrics)
        logger.debug(f"Logged {len(metrics)} metrics")

    def log_equity_curve(
        self,
        equity_curve: list[tuple[datetime, float]],
        benchmark_curve: list[tuple[datetime, float]] | None = None,
    ) -> None:
        """자산 곡선 시각화 로깅"""
        if not HAS_MATPLOTLIB:
            logger.warning("matplotlib not installed, skipping equity curve plot")
            return

        if not equity_curve:
            logger.warning("Empty equity curve, skipping plot")
            return

        dates = [point[0] for point in equity_curve]
        values = [point[1] for point in equity_curve]
        equity_series = pd.Series(values, index=pd.to_datetime(dates))

        fig, ax = plt.subplots(figsize=(12, 6))

        ax.plot(
            equity_series.index,
            equity_series.values,
            label="Strategy",
            linewidth=2,
            color="blue",
        )

        if benchmark_curve:
            bench_dates = [point[0] for point in benchmark_curve]
            bench_values = [point[1] for point in benchmark_curve]
            bench_series = pd.Series(bench_values, index=pd.to_datetime(bench_dates))
            ax.plot(
                bench_series.index,
                bench_series.values,
                label="Benchmark",
                linewidth=1.5,
                color="gray",
                alpha=0.7,
            )

        ax.set_title("Equity Curve")
        ax.set_xlabel("Date")
        ax.set_ylabel("Portfolio Value (KRW)")
        ax.legend()
        ax.grid(True, alpha=0.3)

        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, p: format(int(x), ","))
        )

        plt.tight_layout()
        mlflow.log_figure(fig, "equity_curve.png")
        plt.close(fig)
        logger.debug("Logged equity curve plot")

    def log_drawdown_chart(
        self, equity_curve: list[tuple[datetime, float]]
    ) -> None:
        """드로다운 시각화 로깅"""
        if not HAS_MATPLOTLIB:
            logger.warning("matplotlib not installed, skipping drawdown plot")
            return

        if not equity_curve:
            logger.warning("Empty equity curve, skipping drawdown plot")
            return

        dates = [point[0] for point in equity_curve]
        values = [point[1] for point in equity_curve]
        equity_series = pd.Series(values, index=pd.to_datetime(dates))

        running_max = equity_series.cummax()
        drawdown = (equity_series - running_max) / running_max * 100

        fig, ax = plt.subplots(figsize=(12, 4))

        ax.fill_between(
            drawdown.index,
            0,
            drawdown.values,
            color="red",
            alpha=0.3,
        )
        ax.plot(
            drawdown.index,
            drawdown.values,
            color="red",
            linewidth=1,
        )

        ax.set_title("Drawdown")
        ax.set_xlabel("Date")
        ax.set_ylabel("Drawdown (%)")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        mlflow.log_figure(fig, "drawdown.png")
        plt.close(fig)
        logger.debug("Logged drawdown chart")

    def log_monthly_returns_heatmap(
        self, equity_curve: list[tuple[datetime, float]]
    ) -> None:
        """월별 수익률 히트맵 로깅"""
        if not HAS_MATPLOTLIB or not HAS_SEABORN:
            logger.warning("matplotlib/seaborn not installed, skipping heatmap")
            return

        if not equity_curve or len(equity_curve) < 30:
            logger.warning("Insufficient data for monthly returns heatmap")
            return

        dates = [point[0] for point in equity_curve]
        values = [point[1] for point in equity_curve]
        equity_series = pd.Series(values, index=pd.to_datetime(dates))

        monthly = equity_series.resample("ME").last()
        monthly_returns = monthly.pct_change() * 100

        monthly_returns = monthly_returns.dropna()
        if len(monthly_returns) < 2:
            return

        df = pd.DataFrame(
            {
                "year": monthly_returns.index.year,
                "month": monthly_returns.index.month,
                "return": monthly_returns.values,
            }
        )
        pivot = df.pivot(index="year", columns="month", values="return")

        month_names = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]
        pivot.columns = [month_names[m - 1] for m in pivot.columns]

        fig, ax = plt.subplots(figsize=(12, max(4, len(pivot) * 0.8)))

        sns.heatmap(
            pivot,
            annot=True,
            fmt=".1f",
            cmap="RdYlGn",
            center=0,
            ax=ax,
            cbar_kws={"label": "Return (%)"},
        )
        ax.set_title("Monthly Returns (%)")

        plt.tight_layout()
        mlflow.log_figure(fig, "monthly_returns_heatmap.png")
        plt.close(fig)
        logger.debug("Logged monthly returns heatmap")

    def log_trades_csv(self, result: BacktestResult) -> None:
        """거래 내역 CSV 로깅"""
        if not result.trades:
            logger.warning("No trades to log")
            return

        trade_dicts = [trade.to_dict() for trade in result.trades]
        df = pd.DataFrame(trade_dicts)

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            delete=False,
        ) as f:
            df.to_csv(f, index=False)
            temp_path = f.name

        mlflow.log_artifact(temp_path, "trades.csv")

        Path(temp_path).unlink(missing_ok=True)
        logger.debug(f"Logged {len(result.trades)} trades to CSV")

    def log_result(
        self,
        result: BacktestResult,
        strategy_config: dict[str, Any],
        benchmark_curve: list[tuple[datetime, float]] | None = None,
    ) -> None:
        """전체 결과 로깅 (편의 메서드)

        Args:
            result: 백테스트 결과
            strategy_config: 전략 설정 딕셔너리
            benchmark_curve: 벤치마크 곡선 (선택)
        """
        self.log_params(strategy_config)
        self.log_metrics(result)

        if result.equity_curve:
            self.log_equity_curve(result.equity_curve, benchmark_curve)
            self.log_drawdown_chart(result.equity_curve)
            self.log_monthly_returns_heatmap(result.equity_curve)

        if result.trades:
            self.log_trades_csv(result)

        logger.info(
            f"Logged backtest result: "
            f"Sharpe={result.sharpe_ratio:.2f}, "
            f"MDD={result.max_drawdown_pct:.1f}%, "
            f"Trades={result.total_trades}"
        )

    def _get_git_sha(self) -> str:
        """현재 git commit SHA 조회"""
        try:
            sha = (
                subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
            return sha[:8]
        except Exception:
            return "unknown"

    @staticmethod
    def search_runs(
        experiment_name: str,
        filter_string: str | None = None,
        order_by: list[str] | None = None,
        max_results: int = 100,
    ) -> pd.DataFrame:
        """실험 run 검색

        Example:
            runs = MLflowTracker.search_runs(
                experiment_name="stock_strategies",
                filter_string="metrics.sharpe_ratio > 2.0",
                order_by=["metrics.sharpe_ratio DESC"],
            )
        """
        if not HAS_MLFLOW:
            raise ImportError("MLflow is required")

        return mlflow.search_runs(
            experiment_names=[experiment_name],
            filter_string=filter_string,
            order_by=order_by,
            max_results=max_results,
        )

    @staticmethod
    def get_best_run(
        experiment_name: str,
        metric: str = "sharpe_ratio",
        ascending: bool = False,
    ) -> dict[str, Any] | None:
        """최적 run 조회

        Args:
            experiment_name: 실험 이름
            metric: 최적화 메트릭 (기본: sharpe_ratio)
            ascending: True면 낮을수록 좋음

        Returns:
            최적 run 정보 딕셔너리 또는 None
        """
        order = "ASC" if ascending else "DESC"
        runs = MLflowTracker.search_runs(
            experiment_name=experiment_name,
            order_by=[f"metrics.{metric} {order}"],
            max_results=1,
        )

        if runs.empty:
            return None

        best = runs.iloc[0]
        return {
            "run_id": best["run_id"],
            "git_sha": best.get("params.git_sha"),
            "sharpe_ratio": best.get("metrics.sharpe_ratio"),
            "max_drawdown_pct": best.get("metrics.max_drawdown_pct"),
            "total_return_pct": best.get("metrics.total_return_pct"),
            "win_rate": best.get("metrics.win_rate"),
        }


def track_backtest(
    experiment_name: str,
    result: BacktestResult,
    strategy_config: dict[str, Any],
    run_name: str | None = None,
    tracking_uri: str | None = None,
) -> str:
    """단일 백테스트 추적 (편의 함수)

    Args:
        experiment_name: 실험 이름
        result: 백테스트 결과
        strategy_config: 전략 설정
        run_name: run 이름 (선택)
        tracking_uri: MLflow URI (선택)

    Returns:
        MLflow run ID
    """
    tracker = MLflowTracker(experiment_name, tracking_uri)

    with tracker.start_run(run_name=run_name) as run:
        tracker.log_result(result, strategy_config)
        return run.info.run_id
