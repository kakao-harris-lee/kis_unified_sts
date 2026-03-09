"""E2E tests for experiment run comparison workflow.

Tests the complete workflow:
1. Navigate to experiments page (/experiments)
2. Select an experiment
3. Fetch multiple runs for comparison
4. Sort runs by sharpe_ratio
5. Verify comparison data structure (for charts and table)
6. Test filtering and sorting of runs
"""
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_mlflow_client_with_multiple_runs():
    """Mock MLflow client with multiple runs for comparison testing."""
    # Create mock experiment
    mock_experiment = MagicMock()
    mock_experiment.experiment_id = "test-exp-comparison"
    mock_experiment.name = "stock_strategies_comparison"
    mock_experiment.artifact_location = "/tmp/mlflow/artifacts"
    mock_experiment.lifecycle_stage = "active"
    mock_experiment.creation_time = int(datetime.now().timestamp() * 1000)
    mock_experiment.last_update_time = int(datetime.now().timestamp() * 1000)

    # Create multiple mock runs with different metrics for comparison
    mock_runs = []

    # Run 1: Best sharpe_ratio
    run1 = MagicMock()
    run1.info.run_id = "run-best-sharpe"
    run1.info.experiment_id = "test-exp-comparison"
    run1.info.status = "FINISHED"
    run1.info.start_time = int((datetime.now() - timedelta(hours=3)).timestamp() * 1000)
    run1.info.end_time = int((datetime.now() - timedelta(hours=2)).timestamp() * 1000)
    run1.data.metrics = {
        "sharpe_ratio": 2.45,
        "total_return_pct": 15.8,
        "max_drawdown_pct": -7.2,
        "win_rate": 0.68,
    }
    run1.data.params = {
        "strategy_name": "bb_reversion",
        "symbol": "005930",
        "start_date": "2024-01-01",
        "end_date": "2024-06-30",
    }
    mock_runs.append(run1)

    # Run 2: Best return
    run2 = MagicMock()
    run2.info.run_id = "run-best-return"
    run2.info.experiment_id = "test-exp-comparison"
    run2.info.status = "FINISHED"
    run2.info.start_time = int((datetime.now() - timedelta(hours=2)).timestamp() * 1000)
    run2.info.end_time = int((datetime.now() - timedelta(hours=1)).timestamp() * 1000)
    run2.data.metrics = {
        "sharpe_ratio": 1.95,
        "total_return_pct": 22.4,
        "max_drawdown_pct": -12.5,
        "win_rate": 0.62,
    }
    run2.data.params = {
        "strategy_name": "bb_reversion",
        "symbol": "005930",
        "start_date": "2024-01-01",
        "end_date": "2024-06-30",
    }
    mock_runs.append(run2)

    # Run 3: Best win rate
    run3 = MagicMock()
    run3.info.run_id = "run-best-winrate"
    run3.info.experiment_id = "test-exp-comparison"
    run3.info.status = "FINISHED"
    run3.info.start_time = int((datetime.now() - timedelta(hours=1)).timestamp() * 1000)
    run3.info.end_time = int(datetime.now().timestamp() * 1000)
    run3.data.metrics = {
        "sharpe_ratio": 1.72,
        "total_return_pct": 11.3,
        "max_drawdown_pct": -5.8,
        "win_rate": 0.75,
    }
    run3.data.params = {
        "strategy_name": "bb_reversion",
        "symbol": "005930",
        "start_date": "2024-01-01",
        "end_date": "2024-06-30",
    }
    mock_runs.append(run3)

    # Run 4: Failed run
    run4 = MagicMock()
    run4.info.run_id = "run-failed"
    run4.info.experiment_id = "test-exp-comparison"
    run4.info.status = "FAILED"
    run4.info.start_time = int((datetime.now() - timedelta(hours=4)).timestamp() * 1000)
    run4.info.end_time = int((datetime.now() - timedelta(hours=4)).timestamp() * 1000)
    run4.data.metrics = {}
    run4.data.params = {
        "strategy_name": "bb_reversion",
        "symbol": "005930",
        "start_date": "2024-01-01",
        "end_date": "2024-06-30",
    }
    mock_runs.append(run4)

    # Run 5: Running (in progress)
    run5 = MagicMock()
    run5.info.run_id = "run-in-progress"
    run5.info.experiment_id = "test-exp-comparison"
    run5.info.status = "RUNNING"
    run5.info.start_time = int(datetime.now().timestamp() * 1000)
    run5.info.end_time = None
    run5.data.metrics = {}
    run5.data.params = {
        "strategy_name": "bb_reversion",
        "symbol": "005930",
        "start_date": "2024-01-01",
        "end_date": "2024-06-30",
    }
    mock_runs.append(run5)

    # Create mock client
    mock_client = MagicMock()
    mock_client.search_experiments.return_value = [mock_experiment]
    mock_client.search_runs.return_value = mock_runs

    return mock_client, mock_experiment, mock_runs


@pytest.mark.asyncio
async def test_experiment_comparison_fetch_multiple_runs(mock_mlflow_client_with_multiple_runs):
    """E2E test: Fetch multiple runs for comparison.

    Workflow:
    1. Navigate to /experiments
    2. Get experiment list
    3. Select an experiment
    4. Fetch all runs for that experiment (GET /api/experiments/{id}/runs)
    5. Verify all runs are returned with correct structure
    """
    from services.dashboard.app import create_app

    mock_client, mock_experiment, mock_runs = mock_mlflow_client_with_multiple_runs

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("services.dashboard.routes.experiments._get_mlflow_client") as mock_get_client:
            mock_get_client.return_value = mock_client

            # Step 1: Get experiments list
            experiments_response = await client.get("/api/experiments")
            assert experiments_response.status_code == 200
            experiments_data = experiments_response.json()
            assert experiments_data["total"] >= 1

            # Step 2: Select experiment (use first one)
            experiment_id = experiments_data["experiments"][0]["experiment_id"]
            assert experiment_id == "test-exp-comparison"

            # Step 3: Fetch all runs for comparison
            runs_response = await client.get(
                f"/api/experiments/{experiment_id}/runs?limit=100"
            )

            # Step 4: Verify response structure
            assert runs_response.status_code == 200
            runs_data = runs_response.json()
            assert "runs" in runs_data
            assert "total" in runs_data
            assert runs_data["total"] == 5

            # Step 5: Verify all runs are present
            runs = runs_data["runs"]
            assert len(runs) == 5

            run_ids = [r["run_id"] for r in runs]
            assert "run-best-sharpe" in run_ids
            assert "run-best-return" in run_ids
            assert "run-best-winrate" in run_ids
            assert "run-failed" in run_ids
            assert "run-in-progress" in run_ids

            # Step 6: Verify each run has required fields for comparison
            for run in runs:
                assert "run_id" in run
                assert "experiment_id" in run
                assert "status" in run
                assert "start_time" in run
                assert "metrics" in run
                assert "params" in run


@pytest.mark.asyncio
async def test_experiment_comparison_sort_by_sharpe_ratio(mock_mlflow_client_with_multiple_runs):
    """E2E test: Sort runs by sharpe_ratio (descending).

    Workflow:
    1. Fetch runs for an experiment
    2. Query best run by sharpe_ratio metric
    3. Verify best run is the one with highest sharpe_ratio
    4. Verify sorting order of metrics
    """
    from services.dashboard.app import create_app

    mock_client, mock_experiment, mock_runs = mock_mlflow_client_with_multiple_runs

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("services.dashboard.routes.experiments._get_mlflow_client") as mock_get_client:
            mock_get_client.return_value = mock_client

            experiment_id = "test-exp-comparison"

            # Step 1: Get best run by sharpe_ratio
            best_response = await client.get(
                f"/api/experiments/{experiment_id}/best?metric=sharpe_ratio"
            )

            assert best_response.status_code == 200
            best_data = best_response.json()
            assert "run" in best_data
            assert "metric" in best_data
            assert "value" in best_data

            # Step 2: Verify best run is the one with highest sharpe_ratio
            assert best_data["metric"] == "sharpe_ratio"
            assert best_data["run"]["run_id"] == "run-best-sharpe"
            assert best_data["value"] == 2.45

            # Step 3: Verify metrics structure
            best_run = best_data["run"]
            assert best_run["metrics"]["sharpe_ratio"] == 2.45
            assert best_run["metrics"]["total_return"] == 15.8
            assert best_run["metrics"]["max_drawdown"] == -7.2
            assert best_run["metrics"]["win_rate"] == 0.68


@pytest.mark.asyncio
async def test_experiment_comparison_metrics_table_data(mock_mlflow_client_with_multiple_runs):
    """E2E test: Verify metrics comparison table data structure.

    This test verifies that the data returned by the API is suitable
    for rendering a comparison table with all required metrics.
    """
    from services.dashboard.app import create_app

    mock_client, mock_experiment, mock_runs = mock_mlflow_client_with_multiple_runs

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("services.dashboard.routes.experiments._get_mlflow_client") as mock_get_client:
            mock_get_client.return_value = mock_client

            experiment_id = "test-exp-comparison"

            # Fetch all runs
            runs_response = await client.get(
                f"/api/experiments/{experiment_id}/runs?limit=100"
            )

            assert runs_response.status_code == 200
            runs_data = runs_response.json()
            runs = runs_data["runs"]

            # Verify comparison table can be built with this data
            # Each run should have all required fields
            for run in runs:
                # Required fields for table rows
                assert "run_id" in run
                assert "status" in run
                assert "start_time" in run
                assert "metrics" in run

                # For FINISHED runs, verify all metrics are present
                if run["status"] == "FINISHED":
                    metrics = run["metrics"]
                    assert "sharpe_ratio" in metrics
                    assert "total_return" in metrics
                    assert "max_drawdown" in metrics
                    assert "win_rate" in metrics

                    # Verify metrics are numeric
                    assert isinstance(metrics["sharpe_ratio"], (int, float))
                    assert isinstance(metrics["total_return"], (int, float))
                    assert isinstance(metrics["max_drawdown"], (int, float))
                    assert isinstance(metrics["win_rate"], (int, float))

            # Verify we can identify runs by status for summary stats
            finished_runs = [r for r in runs if r["status"] == "FINISHED"]
            running_runs = [r for r in runs if r["status"] == "RUNNING"]
            failed_runs = [r for r in runs if r["status"] == "FAILED"]

            assert len(finished_runs) == 3
            assert len(running_runs) == 1
            assert len(failed_runs) == 1


@pytest.mark.asyncio
async def test_experiment_comparison_charts_data(mock_mlflow_client_with_multiple_runs):
    """E2E test: Verify data structure for comparison charts.

    This test verifies that the data can be transformed into chart data
    for the 4 comparison charts (Sharpe, Return, Win Rate, Drawdown).
    """
    from services.dashboard.app import create_app

    mock_client, mock_experiment, mock_runs = mock_mlflow_client_with_multiple_runs

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("services.dashboard.routes.experiments._get_mlflow_client") as mock_get_client:
            mock_get_client.return_value = mock_client

            experiment_id = "test-exp-comparison"

            # Fetch all runs
            runs_response = await client.get(
                f"/api/experiments/{experiment_id}/runs?limit=100"
            )

            assert runs_response.status_code == 200
            runs_data = runs_response.json()
            runs = runs_data["runs"]

            # Simulate chart data transformation (as done in ExperimentComparison component)
            chart_data = []
            for run in runs:
                if run["status"] == "FINISHED":
                    chart_data.append({
                        "name": run["run_id"][:8],  # Shortened run ID for chart label
                        "sharpe": run["metrics"]["sharpe_ratio"],
                        "return": run["metrics"]["total_return"],
                        "winRate": run["metrics"]["win_rate"],
                        "drawdown": run["metrics"]["max_drawdown"],
                    })

            # Verify chart data is valid
            assert len(chart_data) == 3  # Only FINISHED runs

            # Verify each chart data point has all required fields
            for data_point in chart_data:
                assert "name" in data_point
                assert "sharpe" in data_point
                assert "return" in data_point
                assert "winRate" in data_point
                assert "drawdown" in data_point

                # Verify numeric values
                assert isinstance(data_point["sharpe"], (int, float))
                assert isinstance(data_point["return"], (int, float))
                assert isinstance(data_point["winRate"], (int, float))
                assert isinstance(data_point["drawdown"], (int, float))

            # Verify we can identify the best run for each metric
            best_sharpe = max(chart_data, key=lambda x: x["sharpe"])
            best_return = max(chart_data, key=lambda x: x["return"])
            best_winrate = max(chart_data, key=lambda x: x["winRate"])
            best_drawdown = max(chart_data, key=lambda x: x["drawdown"])  # Least negative

            assert best_sharpe["sharpe"] == 2.45
            assert best_return["return"] == 22.4
            assert best_winrate["winRate"] == 0.75
            assert best_drawdown["drawdown"] == -5.8  # Least negative is best


@pytest.mark.asyncio
async def test_experiment_comparison_filter_finished_runs(mock_mlflow_client_with_multiple_runs):
    """E2E test: Filter runs to show only FINISHED status for comparison.

    For meaningful comparison, users typically want to compare only
    completed runs, not failed or in-progress runs.
    """
    from services.dashboard.app import create_app

    mock_client, mock_experiment, mock_runs = mock_mlflow_client_with_multiple_runs

    # Configure mock to return only FINISHED runs when filtered
    def mock_search_runs(experiment_ids, filter_string="", order_by=None, max_results=50):
        if "FINISHED" in filter_string:
            return [r for r in mock_runs if r.info.status == "FINISHED"]
        return mock_runs

    mock_client.search_runs.side_effect = mock_search_runs

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("services.dashboard.routes.experiments._get_mlflow_client") as mock_get_client:
            mock_get_client.return_value = mock_client

            experiment_id = "test-exp-comparison"

            # Fetch only FINISHED runs for comparison
            runs_response = await client.get(
                f"/api/experiments/{experiment_id}/runs?status=finished&limit=100"
            )

            assert runs_response.status_code == 200
            runs_data = runs_response.json()
            runs = runs_data["runs"]

            # Verify only FINISHED runs are returned
            assert len(runs) == 3
            for run in runs:
                assert run["status"] == "FINISHED"

            # Verify all FINISHED runs have complete metrics
            for run in runs:
                assert run["metrics"]["sharpe_ratio"] is not None
                assert run["metrics"]["total_return"] is not None
                assert run["metrics"]["max_drawdown"] is not None
                assert run["metrics"]["win_rate"] is not None


@pytest.mark.asyncio
async def test_experiment_comparison_sort_order_verification(mock_mlflow_client_with_multiple_runs):
    """E2E test: Verify different sort orders for comparison table.

    The comparison table should support sorting by different metrics,
    both ascending and descending.
    """
    from services.dashboard.app import create_app

    mock_client, mock_experiment, mock_runs = mock_mlflow_client_with_multiple_runs

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("services.dashboard.routes.experiments._get_mlflow_client") as mock_get_client:
            mock_get_client.return_value = mock_client

            experiment_id = "test-exp-comparison"

            # Fetch runs
            runs_response = await client.get(
                f"/api/experiments/{experiment_id}/runs?limit=100"
            )

            assert runs_response.status_code == 200
            runs_data = runs_response.json()
            runs = runs_data["runs"]

            # Filter only FINISHED runs for sorting tests
            finished_runs = [r for r in runs if r["status"] == "FINISHED"]
            assert len(finished_runs) == 3

            # Test sorting by sharpe_ratio (descending)
            sorted_by_sharpe_desc = sorted(
                finished_runs,
                key=lambda x: x["metrics"]["sharpe_ratio"],
                reverse=True
            )
            assert sorted_by_sharpe_desc[0]["run_id"] == "run-best-sharpe"
            assert sorted_by_sharpe_desc[0]["metrics"]["sharpe_ratio"] == 2.45

            # Test sorting by total_return (descending)
            sorted_by_return_desc = sorted(
                finished_runs,
                key=lambda x: x["metrics"]["total_return"],
                reverse=True
            )
            assert sorted_by_return_desc[0]["run_id"] == "run-best-return"
            assert sorted_by_return_desc[0]["metrics"]["total_return"] == 22.4

            # Test sorting by win_rate (descending)
            sorted_by_winrate_desc = sorted(
                finished_runs,
                key=lambda x: x["metrics"]["win_rate"],
                reverse=True
            )
            assert sorted_by_winrate_desc[0]["run_id"] == "run-best-winrate"
            assert sorted_by_winrate_desc[0]["metrics"]["win_rate"] == 0.75

            # Test sorting by max_drawdown (ascending - less negative is better)
            sorted_by_drawdown_asc = sorted(
                finished_runs,
                key=lambda x: x["metrics"]["max_drawdown"],
                reverse=True
            )
            assert sorted_by_drawdown_asc[0]["run_id"] == "run-best-winrate"
            assert sorted_by_drawdown_asc[0]["metrics"]["max_drawdown"] == -5.8


@pytest.mark.asyncio
async def test_complete_comparison_workflow(mock_mlflow_client_with_multiple_runs):
    """E2E test: Complete experiment comparison workflow.

    End-to-end simulation of user workflow:
    1. Navigate to /experiments
    2. Select an experiment
    3. Fetch all runs for that experiment
    4. Filter to FINISHED runs only
    5. Sort by sharpe_ratio (descending)
    6. View metrics comparison table
    7. Verify charts can be rendered with the data
    """
    from services.dashboard.app import create_app

    mock_client, mock_experiment, mock_runs = mock_mlflow_client_with_multiple_runs

    # Configure mock to support filtering
    def mock_search_runs(experiment_ids, filter_string="", order_by=None, max_results=50):
        if "FINISHED" in filter_string:
            return [r for r in mock_runs if r.info.status == "FINISHED"]
        return mock_runs

    mock_client.search_runs.side_effect = mock_search_runs

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("services.dashboard.routes.experiments._get_mlflow_client") as mock_get_client:
            mock_get_client.return_value = mock_client

            # Step 1: Navigate to /experiments - Get experiments list
            experiments_response = await client.get("/api/experiments")
            assert experiments_response.status_code == 200
            experiments_data = experiments_response.json()
            assert experiments_data["total"] >= 1

            # Step 2: Select an experiment
            experiment_id = experiments_data["experiments"][0]["experiment_id"]

            # Step 3: Fetch all runs for comparison
            runs_response = await client.get(
                f"/api/experiments/{experiment_id}/runs?status=finished&limit=100"
            )
            assert runs_response.status_code == 200
            runs_data = runs_response.json()

            # Step 4: Verify FINISHED runs only
            runs = runs_data["runs"]
            assert len(runs) == 3
            for run in runs:
                assert run["status"] == "FINISHED"

            # Step 5: Sort by sharpe_ratio (client-side simulation)
            sorted_runs = sorted(
                runs,
                key=lambda x: x["metrics"]["sharpe_ratio"],
                reverse=True
            )

            # Step 6: Verify metrics comparison table data
            assert sorted_runs[0]["run_id"] == "run-best-sharpe"
            assert sorted_runs[0]["metrics"]["sharpe_ratio"] == 2.45

            # Verify all required columns are present
            for run in sorted_runs:
                assert "run_id" in run
                assert "status" in run
                assert "start_time" in run
                assert run["metrics"]["sharpe_ratio"] is not None
                assert run["metrics"]["total_return"] is not None
                assert run["metrics"]["win_rate"] is not None
                assert run["metrics"]["max_drawdown"] is not None

            # Step 7: Verify charts data can be generated
            chart_data = []
            for run in sorted_runs:
                chart_data.append({
                    "name": run["run_id"][:8],
                    "sharpe": run["metrics"]["sharpe_ratio"],
                    "return": run["metrics"]["total_return"],
                    "winRate": run["metrics"]["win_rate"],
                    "drawdown": run["metrics"]["max_drawdown"],
                })

            assert len(chart_data) == 3

            # Verify charts render correctly (all data points valid)
            for data_point in chart_data:
                assert isinstance(data_point["sharpe"], (int, float))
                assert isinstance(data_point["return"], (int, float))
                assert isinstance(data_point["winRate"], (int, float))
                assert isinstance(data_point["drawdown"], (int, float))
                assert data_point["sharpe"] > 0  # Sharpe should be positive
                assert data_point["winRate"] > 0 and data_point["winRate"] <= 1  # Win rate 0-1
                assert data_point["drawdown"] < 0  # Drawdown should be negative
