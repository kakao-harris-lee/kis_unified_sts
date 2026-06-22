"""Unit tests for the on-demand experiment API (Phase 3).

The job manager is tested directly (async) with an injected fast runner so no
real backtest runs; the HTTP routes are tested via a bare FastAPI app (no auth
middleware), mirroring the other dashboard route tests.
"""

from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime
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


@pytest.mark.asyncio
async def test_eviction_does_not_leak_reports():
    """A job evicted while queued must not re-leak its (heavy) report into
    _reports — _reports/_tasks stay bounded to the tracked jobs."""
    import asyncio

    from services.dashboard.routes.experiments import ExperimentJobManager

    mgr = ExperimentJobManager(runner=_fake_report, max_jobs=2)
    tasks = []
    for _ in range(6):
        job = await mgr.submit(_MINIMAL_SPEC)
        tasks.append(mgr._tasks[job.job_id])  # capture before a later submit evicts it
    await asyncio.gather(*tasks)  # all 6 serialized runs finish

    # tracking + retained results never exceed the cap, even though 6 ran
    assert len(mgr._jobs) <= 2
    assert len(mgr._reports) <= 2
    assert set(mgr._reports).issubset(set(mgr._jobs))


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


def test_latest_paper_comparison_reports_missing_latest(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    resp = client.get("/api/kis-builder/experiments/latest/compare-paper")
    assert resp.status_code == 200
    body = resp.json()
    assert body["comparisons"] == []
    assert body["missing_evidence"] == ["latest_experiment_report"]


def test_latest_paper_comparison_aligned(monkeypatch, tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "stock_experiment_20260601_000000.json").write_text(
        json.dumps(
            {
                "experiment": {
                    "id": "disk_exp",
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-30",
                    "generated_at": "2026-06-01T00:00:00+00:00",
                },
                "summaries": [
                    {
                        "strategy_id": "pattern_pullback",
                        "strategy_name": "Pattern Pullback",
                        "closed_trades": 4,
                        "win_rate_pct": 50.0,
                        "total_return_pct": 3.0,
                        "realized_pnl": 1000.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    client, experiments = _client(monkeypatch, tmp_path)

    def fake_paper_trades(strategy_id, strategy_name, *, start=None, end=None):
        assert strategy_id == "pattern_pullback"
        assert strategy_name == "Pattern Pullback"
        assert start is not None
        assert end is not None
        return [
            {"symbol": "005930", "pnl": 200.0, "pnl_pct": 1.0},
            {"symbol": "005930", "pnl": -50.0, "pnl_pct": -0.2},
            {"symbol": "000660", "pnl": 150.0, "pnl_pct": 0.8},
        ], True

    monkeypatch.setattr(experiments, "_load_stock_paper_trades", fake_paper_trades)
    resp = client.get("/api/kis-builder/experiments/latest/compare-paper")
    assert resp.status_code == 200
    row = resp.json()["comparisons"][0]
    assert row["status"] == "aligned"
    assert row["missing_evidence"] == []
    assert row["paper"]["trade_count"] == 3
    assert row["paper"]["total_pnl"] == 300.0


def test_latest_paper_comparison_insufficient_without_ledger(monkeypatch, tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "stock_experiment_20260601_000000.json").write_text(
        json.dumps(
            {
                "experiment": {
                    "id": "disk_exp",
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-30",
                },
                "summaries": [
                    {
                        "strategy_id": "pattern_pullback",
                        "closed_trades": 2,
                        "win_rate_pct": 50.0,
                        "total_return_pct": 2.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    client, experiments = _client(monkeypatch, tmp_path)
    monkeypatch.setattr(
        experiments,
        "_load_stock_paper_trades",
        lambda _strategy_id, _strategy_name, **_kwargs: ([], False),
    )

    resp = client.get("/api/kis-builder/experiments/latest/compare-paper")
    assert resp.status_code == 200
    row = resp.json()["comparisons"][0]
    assert row["status"] == "insufficient_data"
    assert row["paper"]["trade_count"] == 0
    assert "runtime_ledger" in row["missing_evidence"]
    assert "paper_trade_count" in row["missing_evidence"]


def test_load_stock_paper_trades_filters_to_experiment_window(monkeypatch, tmp_path):
    _client(monkeypatch, tmp_path)
    from services.dashboard.routes import experiments
    from services.dashboard.routes import trades as trades_route

    def fake_runtime_trades(_asset_class, *, strategy, limit, **_kwargs):
        assert strategy == "pattern_pullback"
        assert limit == 0
        return [
            {
                "id": "before",
                "symbol": "005930",
                "exit_time": "2026-05-31T15:00:00+09:00",
                "pnl": 10.0,
            },
            {
                "id": "inside",
                "symbol": "005930",
                "exit_time": "2026-06-15T15:00:00+09:00",
                "pnl": 20.0,
            },
            {
                "id": "after",
                "symbol": "005930",
                "exit_time": "2026-07-01T15:00:00+09:00",
                "pnl": 30.0,
            },
        ], True

    monkeypatch.setattr(
        trades_route, "_load_runtime_ledger_trades", fake_runtime_trades
    )
    start = datetime(2026, 6, 1, tzinfo=UTC)
    end = datetime(2026, 6, 30, 23, 59, 59, tzinfo=UTC)

    rows, available = experiments._load_stock_paper_trades(
        "pattern_pullback",
        None,
        start=start,
        end=end,
    )

    assert available is True
    assert [row["id"] for row in rows] == ["inside"]


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
