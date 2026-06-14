"""Unit tests for the on-demand experiment API (Phase 3).

The job manager is tested directly (async) with an injected fast runner so no
real backtest runs; the HTTP routes are tested via a bare FastAPI app (no auth
middleware), mirroring the other dashboard route tests.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_MINIMAL_SPEC = {
    "id": "t",
    "strategies": [{"type": "registry", "name": "pattern_pullback"}],
    "symbols": ["005930"],
    "start": "2025-01-01",
    "end": "2026-01-01",
}


def _fake_report(spec):
    return {
        "experiment": {"id": spec.id, "generated_at": "2026-06-01T00:00:00+00:00"},
        "summaries": [{"strategy_id": "pattern_pullback", "total_return_pct": 1.0}],
        "equity_curves": {},
        "trades": [],
        "status_by_strategy": [{"strategy_id": "pattern_pullback", "status": "ok"}],
    }


@pytest.mark.asyncio
async def test_job_manager_runs_and_holds_report_in_memory():
    from services.dashboard.routes.experiments import ExperimentJobManager

    mgr = ExperimentJobManager(runner=_fake_report)
    job = await mgr.submit(_MINIMAL_SPEC)
    assert job.status in ("queued", "running")
    await mgr._tasks[job.job_id]  # let the background task finish

    done = mgr.get(job.job_id)
    assert done.status == "done"
    assert done.experiment_id == "t"
    report = mgr.report(job.job_id)
    assert report["summaries"][0]["strategy_id"] == "pattern_pullback"


@pytest.mark.asyncio
async def test_job_manager_captures_failure():
    from services.dashboard.routes.experiments import ExperimentJobManager

    def boom(spec):
        raise RuntimeError("kaboom")

    mgr = ExperimentJobManager(runner=boom)
    job = await mgr.submit(_MINIMAL_SPEC)
    await mgr._tasks[job.job_id]
    failed = mgr.get(job.job_id)
    assert failed.status == "failed"
    assert "kaboom" in (failed.error or "")


@pytest.mark.asyncio
async def test_job_manager_serializes_runs():
    """The lock means only one backtest runs at a time; both still complete."""
    from services.dashboard.routes.experiments import ExperimentJobManager

    mgr = ExperimentJobManager(runner=_fake_report)
    j1 = await mgr.submit(_MINIMAL_SPEC)
    j2 = await mgr.submit(_MINIMAL_SPEC)
    await mgr._tasks[j1.job_id]
    await mgr._tasks[j2.job_id]
    assert mgr.get(j1.job_id).status == "done"
    assert mgr.get(j2.job_id).status == "done"


def _client(monkeypatch, tmp_path: Path) -> tuple[TestClient, object]:
    monkeypatch.setenv("STOCK_EXPERIMENT_OUTPUT_DIR", str(tmp_path / "reports"))
    from services.dashboard.routes import experiments

    importlib.reload(experiments)
    app = FastAPI()
    app.include_router(experiments.router)
    return TestClient(app), experiments


def test_strategies_catalog_lists_registry_stock_strategies(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    resp = client.get("/api/kis-builder/experiments/strategies")
    assert resp.status_code == 200
    names = {s["name"] for s in resp.json()["strategies"]}
    # real config/strategies/stock has these; each row carries name/enabled/timeframe
    assert "pattern_pullback" in names
    row = next(s for s in resp.json()["strategies"] if s["name"] == "pattern_pullback")
    assert row["timeframe"] == "daily"
    assert "enabled" in row


def test_latest_report_reads_disk(monkeypatch, tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "stock_experiment_20260601_000000.json").write_text(
        json.dumps({"experiment": {"id": "disk_exp"}, "summaries": []}),
        encoding="utf-8",
    )
    client, _ = _client(monkeypatch, tmp_path)
    resp = client.get("/api/kis-builder/experiments/latest")
    assert resp.status_code == 200
    assert resp.json()["report"]["experiment"]["id"] == "disk_exp"


def test_latest_report_none_when_empty(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    resp = client.get("/api/kis-builder/experiments/latest")
    assert resp.status_code == 200
    assert resp.json()["report"] is None


def test_run_endpoint_launches_job(monkeypatch, tmp_path):
    client, experiments = _client(monkeypatch, tmp_path)
    experiments._manager._runner = _fake_report  # avoid a real backtest
    resp = client.post(
        "/api/kis-builder/experiments/run",
        json={
            "strategies": [{"type": "registry", "name": "pattern_pullback"}],
            "symbols": ["005930"],
            "start": "2025-01-01",
            "end": "2026-01-01",
        },
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    assert resp.json()["status"] in ("queued", "running", "done")
    # job is retrievable
    assert client.get(f"/api/kis-builder/experiments/jobs/{job_id}").status_code == 200


def test_run_endpoint_invalid_spec_returns_400(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    # strategy entry missing required 'name' → ExperimentSpec validation fails
    resp = client.post(
        "/api/kis-builder/experiments/run",
        json={"strategies": [{"type": "registry"}]},
    )
    assert resp.status_code == 400
    assert "Invalid experiment spec" in resp.json()["detail"]


def test_jobs_unknown_returns_404(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    assert client.get("/api/kis-builder/experiments/jobs/nope").status_code == 404
