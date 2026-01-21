"""Experiments (MLflow) endpoints."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


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


# Simulated experiment data (in production, would query MLflow)
_experiments_store: Dict[str, ExperimentResponse] = {}
_runs_store: Dict[str, List[RunResponse]] = {}


@router.get("", response_model=ExperimentListResponse)
async def get_experiments():
    """Get list of experiments."""
    experiments = list(_experiments_store.values())
    return ExperimentListResponse(
        experiments=experiments,
        total=len(experiments),
    )


@router.get("/{experiment_id}/runs", response_model=RunListResponse)
async def get_experiment_runs(
    experiment_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Number of runs"),
):
    """Get runs for an experiment."""
    runs = _runs_store.get(experiment_id, [])

    # Apply filters
    if status:
        runs = [r for r in runs if r.status == status]

    # Sort by start_time desc
    runs.sort(key=lambda r: r.start_time, reverse=True)

    return RunListResponse(
        runs=runs[:limit],
        total=len(runs),
    )


@router.get("/{experiment_id}/best", response_model=BestRunResponse)
async def get_best_run(
    experiment_id: str,
    metric: str = Query("sharpe_ratio", description="Metric to optimize"),
    minimize: bool = Query(False, description="Whether to minimize metric"),
):
    """Get best run for an experiment based on metric."""
    runs = _runs_store.get(experiment_id, [])

    if not runs:
        return BestRunResponse(run=None, metric=metric, value=None)

    # Find best run
    def get_metric_value(run: RunResponse) -> float:
        metrics_dict = run.metrics.model_dump()
        return metrics_dict.get(metric, float("-inf") if not minimize else float("inf"))

    best_run = min(runs, key=get_metric_value) if minimize else max(runs, key=get_metric_value)
    best_value = get_metric_value(best_run)

    return BestRunResponse(
        run=best_run,
        metric=metric,
        value=best_value if best_value not in [float("inf"), float("-inf")] else None,
    )


@router.post("")
async def create_experiment(name: str = Query(..., description="Experiment name")):
    """Create a new experiment."""
    import uuid

    exp_id = str(uuid.uuid4())[:8]
    now = datetime.now()

    experiment = ExperimentResponse(
        experiment_id=exp_id,
        name=name,
        artifact_location=f"mlruns/{exp_id}",
        lifecycle_stage="active",
        creation_time=now,
        last_update_time=now,
        run_count=0,
    )

    _experiments_store[exp_id] = experiment
    _runs_store[exp_id] = []

    return {"experiment_id": exp_id, "name": name}
