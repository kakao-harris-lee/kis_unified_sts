"""Experiments (MLflow) endpoints."""
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Optional MLflow dependency
try:
    import mlflow
    from mlflow.entities import ViewType

    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False
    mlflow = None
    logger.warning("MLflow not installed. Install with: pip install mlflow>=2.10.0")

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


# MLflow client initialization
def _get_mlflow_client():
    """Get MLflow tracking client."""
    if not HAS_MLFLOW:
        raise HTTPException(
            status_code=503,
            detail="MLflow not installed. Install with: pip install mlflow>=2.10.0",
        )

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
    mlflow.set_tracking_uri(tracking_uri)
    return mlflow.tracking.MlflowClient()


class ExperimentResponse(BaseModel):
    """Experiment response model."""

    experiment_id: str
    name: str
    artifact_location: str
    lifecycle_stage: str
    creation_time: datetime
    last_update_time: datetime
    run_count: int


class ExperimentListResponse(BaseModel):
    """Experiment list response."""

    experiments: List[ExperimentResponse]
    total: int


class RunMetrics(BaseModel):
    """Run metrics."""

    sharpe_ratio: Optional[float] = None
    total_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None


class RunParams(BaseModel):
    """Run parameters."""

    strategy: Optional[str] = None
    symbol: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class RunResponse(BaseModel):
    """Run response model."""

    run_id: str
    experiment_id: str
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    metrics: RunMetrics
    params: RunParams


class RunListResponse(BaseModel):
    """Run list response."""

    runs: List[RunResponse]
    total: int


class BestRunResponse(BaseModel):
    """Best run response."""

    run: Optional[RunResponse]
    metric: str
    value: Optional[float]


@router.get("", response_model=ExperimentListResponse)
async def get_experiments():
    """Get list of experiments from MLflow."""
    try:
        client = _get_mlflow_client()
        mlflow_experiments = client.search_experiments(view_type=ViewType.ACTIVE_ONLY)

        experiments = []
        for exp in mlflow_experiments:
            # Count runs for this experiment
            runs = client.search_runs(
                experiment_ids=[exp.experiment_id],
                filter_string="",
            )

            experiments.append(
                ExperimentResponse(
                    experiment_id=exp.experiment_id,
                    name=exp.name,
                    artifact_location=exp.artifact_location,
                    lifecycle_stage=exp.lifecycle_stage,
                    creation_time=datetime.fromtimestamp(exp.creation_time / 1000.0),
                    last_update_time=datetime.fromtimestamp(
                        exp.last_update_time / 1000.0
                    ),
                    run_count=len(runs),
                )
            )

        return ExperimentListResponse(
            experiments=experiments,
            total=len(experiments),
        )

    except Exception as e:
        logger.error(f"Failed to fetch experiments: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch experiments: {str(e)}")


@router.get("/{experiment_id}/runs", response_model=RunListResponse)
async def get_experiment_runs(
    experiment_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Number of runs"),
):
    """Get runs for an experiment from MLflow."""
    try:
        client = _get_mlflow_client()

        # Build filter string
        filter_parts = []
        if status:
            filter_parts.append(f"attributes.status = '{status.upper()}'")

        filter_string = " and ".join(filter_parts) if filter_parts else ""

        # Search runs
        mlflow_runs = client.search_runs(
            experiment_ids=[experiment_id],
            filter_string=filter_string,
            order_by=["attributes.start_time DESC"],
            max_results=limit,
        )

        runs = []
        for run in mlflow_runs:
            # Extract metrics
            metrics_data = run.data.metrics
            metrics = RunMetrics(
                sharpe_ratio=metrics_data.get("sharpe_ratio"),
                total_return=metrics_data.get("total_return_pct"),
                max_drawdown=metrics_data.get("max_drawdown_pct"),
                win_rate=metrics_data.get("win_rate"),
            )

            # Extract params
            params_data = run.data.params
            params = RunParams(
                strategy=params_data.get("strategy_name"),
                symbol=params_data.get("symbol"),
                start_date=params_data.get("start_date"),
                end_date=params_data.get("end_date"),
            )

            # Convert timestamps
            start_time = datetime.fromtimestamp(run.info.start_time / 1000.0)
            end_time = (
                datetime.fromtimestamp(run.info.end_time / 1000.0)
                if run.info.end_time
                else None
            )

            runs.append(
                RunResponse(
                    run_id=run.info.run_id,
                    experiment_id=run.info.experiment_id,
                    status=run.info.status,
                    start_time=start_time,
                    end_time=end_time,
                    metrics=metrics,
                    params=params,
                )
            )

        return RunListResponse(
            runs=runs,
            total=len(runs),
        )

    except Exception as e:
        logger.error(f"Failed to fetch runs for experiment {experiment_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch runs: {str(e)}",
        )


@router.get("/{experiment_id}/best", response_model=BestRunResponse)
async def get_best_run(
    experiment_id: str,
    metric: str = Query("sharpe_ratio", description="Metric to optimize"),
    minimize: bool = Query(False, description="Whether to minimize metric"),
):
    """Get best run for an experiment based on metric from MLflow."""
    try:
        client = _get_mlflow_client()

        # Map frontend metric names to MLflow metric names
        metric_mapping = {
            "sharpe_ratio": "sharpe_ratio",
            "total_return": "total_return_pct",
            "max_drawdown": "max_drawdown_pct",
            "win_rate": "win_rate",
        }
        mlflow_metric = metric_mapping.get(metric, metric)

        # Search for best run
        order = "ASC" if minimize else "DESC"
        mlflow_runs = client.search_runs(
            experiment_ids=[experiment_id],
            filter_string=f"metrics.{mlflow_metric} != 'nan'",
            order_by=[f"metrics.{mlflow_metric} {order}"],
            max_results=1,
        )

        if not mlflow_runs:
            return BestRunResponse(run=None, metric=metric, value=None)

        best = mlflow_runs[0]

        # Extract metrics
        metrics_data = best.data.metrics
        metrics = RunMetrics(
            sharpe_ratio=metrics_data.get("sharpe_ratio"),
            total_return=metrics_data.get("total_return_pct"),
            max_drawdown=metrics_data.get("max_drawdown_pct"),
            win_rate=metrics_data.get("win_rate"),
        )

        # Extract params
        params_data = best.data.params
        params = RunParams(
            strategy=params_data.get("strategy_name"),
            symbol=params_data.get("symbol"),
            start_date=params_data.get("start_date"),
            end_date=params_data.get("end_date"),
        )

        # Convert timestamps
        start_time = datetime.fromtimestamp(best.info.start_time / 1000.0)
        end_time = (
            datetime.fromtimestamp(best.info.end_time / 1000.0)
            if best.info.end_time
            else None
        )

        run = RunResponse(
            run_id=best.info.run_id,
            experiment_id=best.info.experiment_id,
            status=best.info.status,
            start_time=start_time,
            end_time=end_time,
            metrics=metrics,
            params=params,
        )

        best_value = metrics_data.get(mlflow_metric)

        return BestRunResponse(
            run=run,
            metric=metric,
            value=best_value,
        )

    except Exception as e:
        logger.error(f"Failed to fetch best run for experiment {experiment_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch best run: {str(e)}",
        )


@router.post("")
async def create_experiment(name: str = Query(..., description="Experiment name")):
    """Create a new experiment in MLflow."""
    try:
        client = _get_mlflow_client()

        # Create experiment
        experiment_id = client.create_experiment(name)

        return {"experiment_id": experiment_id, "name": name}

    except Exception as e:
        logger.error(f"Failed to create experiment '{name}': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create experiment: {str(e)}",
        )
