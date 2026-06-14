"""Stock strategy experiment API — on-demand runs + listing (Phase 3).

Wraps ``shared.backtest.experiment_runner``. Backtests are CPU-heavy, so an
on-demand run executes in a worker thread (``asyncio.to_thread``) behind a single
concurrency lock: the dashboard event loop stays responsive and concurrent
launches queue rather than pile up.

On-demand results are held IN MEMORY on the job (the dashboard mounts
``./reports`` read-only, so it cannot persist there). The authoritative on-disk
reports under ``reports/stock_experiment/`` come from the nightly scheduler job
(Phase 2); ``GET /latest`` and the listing read those.

Routes (under the existing kis-builder namespace so the Next.js proxy reaches
them via ``/api/experiments/*``):
- ``GET  /api/kis-builder/experiments``            → recent disk reports + jobs
- ``GET  /api/kis-builder/experiments/latest``     → newest disk report (full)
- ``GET  /api/kis-builder/experiments/strategies`` → registry stock strategy catalog
- ``POST /api/kis-builder/experiments/run``        → launch on-demand → job
- ``GET  /api/kis-builder/experiments/jobs/{id}``  → job status (+ report when done)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kis-builder/experiments", tags=["experiments"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_OUTPUT_DIR = os.environ.get("STOCK_EXPERIMENT_OUTPUT_DIR", "reports/stock_experiment")
_DEFAULT_SPEC = os.environ.get(
    "STOCK_EXPERIMENT_SPEC", "config/experiments/stock_default.yaml"
)
_STOCK_STRATEGY_DIR = os.environ.get(
    "STOCK_EXPERIMENT_STRATEGY_DIR", "config/strategies/stock"
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _resolve(raw: str | Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else _REPO_ROOT / path


# --------------------------------------------------------------------------- #
# Job manager — serialized background backtests, in-memory results
# --------------------------------------------------------------------------- #


class ExperimentJob(BaseModel):
    """On-demand experiment job metadata (the report is held separately)."""

    job_id: str
    status: str = "queued"  # queued | running | done | failed
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    experiment_id: str | None = None


class ExperimentJobManager:
    """Runs experiments off the event loop, one at a time, keeping results in RAM."""

    def __init__(self, runner: Any | None = None, max_jobs: int = 50) -> None:
        self._jobs: OrderedDict[str, ExperimentJob] = OrderedDict()
        self._reports: dict[str, dict[str, Any]] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._runner = runner  # injectable for tests; default resolved lazily
        self._max_jobs = max_jobs

    def _runner_fn(self) -> Any:
        if self._runner is not None:
            return self._runner
        from shared.backtest.experiment_runner import run_stock_experiment

        return run_stock_experiment

    async def submit(self, spec_dict: dict[str, Any]) -> ExperimentJob:
        from shared.backtest.experiment_runner import ExperimentSpec

        spec = ExperimentSpec.from_dict(spec_dict)  # raises on invalid spec
        job_id = uuid.uuid4().hex[:12]
        job = ExperimentJob(job_id=job_id, status="queued", created_at=_now_iso())
        self._jobs[job_id] = job
        while len(self._jobs) > self._max_jobs:
            old_id, _ = self._jobs.popitem(last=False)
            self._reports.pop(old_id, None)
            self._tasks.pop(old_id, None)
        self._tasks[job_id] = asyncio.create_task(self._run(job, spec))
        return job

    async def _run(self, job: ExperimentJob, spec: Any) -> None:
        async with self._lock:  # serialize CPU-heavy backtests
            job.status = "running"
            job.started_at = _now_iso()
            try:
                report = await asyncio.to_thread(self._runner_fn(), spec)
                job.experiment_id = report.get("experiment", {}).get("id")
                # Only retain the (heavy) report if the job is still tracked — a
                # job evicted while queued must not re-leak its report into
                # _reports, which would then never be evicted again.
                if job.job_id in self._jobs:
                    self._reports[job.job_id] = report
                job.status = "done"
            except Exception as exc:  # noqa: BLE001 - surface as job failure
                logger.exception("experiment job %s failed", job.job_id)
                job.status = "failed"
                job.error = f"{type(exc).__name__}: {exc}"
            finally:
                job.finished_at = _now_iso()
                self._prune()

    def _prune(self) -> None:
        """Keep _reports/_tasks bounded to the tracked jobs (defends against an
        eviction that raced with an in-flight run)."""
        live = set(self._jobs)
        for jid in [k for k in self._reports if k not in live]:
            self._reports.pop(jid, None)
        for jid in [k for k, t in self._tasks.items() if k not in live and t.done()]:
            self._tasks.pop(jid, None)

    def get(self, job_id: str) -> ExperimentJob | None:
        return self._jobs.get(job_id)

    def report(self, job_id: str) -> dict[str, Any] | None:
        return self._reports.get(job_id)

    def list_jobs(self, limit: int = 20) -> list[ExperimentJob]:
        return list(self._jobs.values())[-limit:][::-1]


_manager = ExperimentJobManager()


# --------------------------------------------------------------------------- #
# Disk report helpers (scheduler-written reports)
# --------------------------------------------------------------------------- #


def _report_paths() -> list[Path]:
    out = _resolve(_OUTPUT_DIR)
    if not out.exists():
        return []
    return sorted(out.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def _read_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _report_summary_row(path: Path) -> dict[str, Any]:
    """Lightweight listing row (no equity_curves/trades payload)."""
    try:
        data = _read_report(path)
    except (OSError, ValueError):
        return {"filename": path.name, "error": "unreadable"}
    exp = data.get("experiment", {})
    return {
        "filename": path.name,
        "experiment_id": exp.get("id"),
        "start_date": exp.get("start_date"),
        "end_date": exp.get("end_date"),
        "generated_at": exp.get("generated_at"),
        "strategy_count": len(data.get("summaries", [])),
        "status_by_strategy": data.get("status_by_strategy", []),
    }


def _strategy_catalog() -> list[dict[str, Any]]:
    """Registry stock strategies the user can experiment (name/enabled/timeframe)."""
    out: list[dict[str, Any]] = []
    sdir = _resolve(_STOCK_STRATEGY_DIR)
    if not sdir.exists():
        return out
    for path in sorted(sdir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        strat = data.get("strategy", {})
        if not isinstance(strat, dict):
            continue
        out.append(
            {
                "name": strat.get("name", path.stem),
                "enabled": bool(strat.get("enabled", False)),
                "timeframe": strat.get("timeframe", "minute"),
                "description": strat.get("description", ""),
            }
        )
    return out


def _load_default_spec() -> dict[str, Any]:
    path = _resolve(_DEFAULT_SPEC)
    if not path.exists():
        return {"id": "stock_experiment", "strategies": [], "symbols": []}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


class RunExperimentRequest(BaseModel):
    """On-demand run overrides; any omitted field falls back to the default spec."""

    id: str | None = None
    description: str | None = None
    strategies: list[dict[str, Any]] | None = None
    symbols: list[str] | None = None
    start: str | None = None
    end: str | None = None
    lookback_days: int | None = Field(default=None, ge=1)


@router.get("")
async def list_experiments() -> dict[str, Any]:
    return {
        "reports": [_report_summary_row(p) for p in _report_paths()[:10]],
        "jobs": [j.model_dump(mode="json") for j in _manager.list_jobs()],
    }


@router.get("/latest")
async def latest_report() -> dict[str, Any]:
    paths = _report_paths()
    return {"report": _read_report(paths[0]) if paths else None}


@router.get("/strategies")
async def strategy_catalog() -> dict[str, Any]:
    return {"strategies": _strategy_catalog()}


@router.post("/run")
async def run_experiment(req: RunExperimentRequest) -> dict[str, Any]:
    try:
        spec_dict = _load_default_spec()
        spec_dict.update(req.model_dump(exclude_none=True))
        job = await _manager.submit(spec_dict)
    except Exception as exc:  # noqa: BLE001 - bad spec/config → 400
        raise HTTPException(
            status_code=400, detail=f"Invalid experiment spec: {exc}"
        ) from exc
    return job.model_dump(mode="json")


@router.get("/jobs/{job_id}")
async def job_status(job_id: str) -> dict[str, Any]:
    job = _manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
    out = job.model_dump(mode="json")
    if job.status == "done":
        out["report"] = _manager.report(job_id)
    return out
