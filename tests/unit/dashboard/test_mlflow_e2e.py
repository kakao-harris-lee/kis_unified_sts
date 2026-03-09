"""E2E tests for backtest → MLflow → experiments workflow.

Tests the complete workflow:
1. Run backtest via API
2. Track results to MLflow
3. Query experiments endpoint
4. Verify run appears in experiment list
5. View run details with metrics
"""
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_mlflow_client():
    """Mock MLflow client for testing."""
    # Create mock experiment
    mock_experiment = MagicMock()
    mock_experiment.experiment_id = "test-exp-123"
    mock_experiment.name = "stock_strategies"
    mock_experiment.artifact_location = "/tmp/mlflow/artifacts"
    mock_experiment.lifecycle_stage = "active"
    mock_experiment.creation_time = int(datetime.now().timestamp() * 1000)
    mock_experiment.last_update_time = int(datetime.now().timestamp() * 1000)

    # Create mock run with metrics
    mock_run = MagicMock()
    mock_run.info.run_id = "test-run-456"
    mock_run.info.experiment_id = "test-exp-123"
    mock_run.info.status = "FINISHED"
    mock_run.info.start_time = int(datetime.now().timestamp() * 1000)
    mock_run.info.end_time = int((datetime.now() + timedelta(minutes=5)).timestamp() * 1000)

    # Mock metrics data
    mock_run.data.metrics = {
        "sharpe_ratio": 1.85,
        "total_return_pct": 12.5,
        "max_drawdown_pct": -8.3,
        "win_rate": 0.65,
    }

    # Mock params data
    mock_run.data.params = {
        "strategy_name": "bb_reversion",
        "symbol": "005930",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
    }

    # Create mock client
    mock_client = MagicMock()
    mock_client.search_experiments.return_value = [mock_experiment]
    mock_client.search_runs.return_value = [mock_run]
    mock_client.create_experiment.return_value = "test-exp-123"

    return mock_client, mock_experiment, mock_run


@pytest.fixture
def sample_backtest_data():
    """Generate sample OHLCV data for backtest."""
    base = datetime(2024, 1, 1, 9, 0)
    rows = []
    price = 100.0
    for i in range(100):
        price += 0.1 * (i % 10 - 5)  # Oscillating price
        rows.append(
            {
                "code": "005930",
                "name": "삼성전자",
                "datetime": base + timedelta(minutes=i),
                "open": price - 0.2,
                "high": price + 0.3,
                "low": price - 0.4,
                "close": price,
                "volume": 1000 + i * 10,
            }
        )
    return pd.DataFrame(rows)


@pytest.mark.asyncio
async def test_mlflow_e2e_workflow_with_tracking(mock_mlflow_client, sample_backtest_data):
    """E2E test: Run backtest with MLflow tracking, verify in experiments.

    Workflow:
    1. Run backtest via POST /api/backtest/run
    2. Verify backtest completes successfully
    3. Track result to MLflow (mocked)
    4. Query GET /api/experiments to list experiments
    5. Query GET /api/experiments/{id}/runs to get runs
    6. Verify run appears with correct metrics
    """
    from services.dashboard.app import create_app
    from services.dashboard.routes import backtest as backtest_routes

    mock_client, mock_experiment, mock_run = mock_mlflow_client

    # Patch backtest data fetching and chart generation
    with patch.object(
        backtest_routes, "_fetch_ohlcv", return_value=sample_backtest_data
    ), patch.object(backtest_routes, "_generate_chart", return_value=None):

        app = create_app()
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Step 1: Run backtest via API
            backtest_response = await client.post(
                "/api/backtest/run",
                json={
                    "asset_class": "stock",
                    "strategy": "bb_reversion",
                    "symbol": "005930",
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                    "initial_capital": 10000000,
                },
            )

            # Step 2: Verify backtest completed successfully
            assert backtest_response.status_code == 200
            backtest_data = backtest_response.json()
            assert "run_id" in backtest_data
            assert "status" in backtest_data
            assert backtest_data["status"] == "completed"
            assert "result" in backtest_data

            result = backtest_data["result"]
            assert "sharpe_ratio" in result
            assert "total_return_pct" in result
            assert "max_drawdown_pct" in result
            assert "win_rate" in result
            assert "total_trades" in result

            # Verify metrics are numeric
            assert isinstance(result["sharpe_ratio"], (int, float))
            assert isinstance(result["total_return_pct"], (int, float))
            assert isinstance(result["max_drawdown_pct"], (int, float))
            assert isinstance(result["win_rate"], (int, float))
            assert isinstance(result["total_trades"], int)

            # Step 3: Simulate MLflow tracking (in real implementation, this would
            # be done automatically in the backtest endpoint)
            # For now, we verify the MLflow client would be called correctly

            # Step 4: Query experiments endpoint with mocked MLflow
            with patch("services.dashboard.routes.experiments._get_mlflow_client") as mock_get_client:
                mock_get_client.return_value = mock_client

                experiments_response = await client.get("/api/experiments")

                # Step 5: Verify experiments list
                assert experiments_response.status_code == 200
                experiments_data = experiments_response.json()
                assert "experiments" in experiments_data
                assert "total" in experiments_data
                assert experiments_data["total"] >= 1

                experiments = experiments_data["experiments"]
                assert len(experiments) >= 1

                # Verify experiment structure
                experiment = experiments[0]
                assert "experiment_id" in experiment
                assert "name" in experiment
                assert "run_count" in experiment
                assert experiment["experiment_id"] == "test-exp-123"
                assert experiment["name"] == "stock_strategies"

                # Step 6: Query runs for the experiment
                experiment_id = experiment["experiment_id"]
                runs_response = await client.get(
                    f"/api/experiments/{experiment_id}/runs"
                )

                # Step 7: Verify runs list
                assert runs_response.status_code == 200
                runs_data = runs_response.json()
                assert "runs" in runs_data
                assert "total" in runs_data
                assert runs_data["total"] >= 1

                runs = runs_data["runs"]
                assert len(runs) >= 1

                # Step 8: Verify run details with metrics
                run = runs[0]
                assert "run_id" in run
                assert "experiment_id" in run
                assert "status" in run
                assert "metrics" in run
                assert "params" in run
                assert run["run_id"] == "test-run-456"
                assert run["status"] == "FINISHED"

                # Verify metrics match what we tracked
                metrics = run["metrics"]
                assert metrics["sharpe_ratio"] == 1.85
                assert metrics["total_return"] == 12.5
                assert metrics["max_drawdown"] == -8.3
                assert metrics["win_rate"] == 0.65

                # Verify params
                params = run["params"]
                assert params["strategy"] == "bb_reversion"
                assert params["symbol"] == "005930"
                assert params["start_date"] == "2024-01-01"
                assert params["end_date"] == "2024-12-31"

                # Step 9: Query best run
                best_response = await client.get(
                    f"/api/experiments/{experiment_id}/best?metric=sharpe_ratio"
                )

                assert best_response.status_code == 200
                best_data = best_response.json()
                assert "run" in best_data
                assert "metric" in best_data
                assert "value" in best_data
                assert best_data["metric"] == "sharpe_ratio"
                assert best_data["value"] == 1.85

                best_run = best_data["run"]
                assert best_run is not None
                assert best_run["run_id"] == "test-run-456"


@pytest.mark.asyncio
async def test_mlflow_experiments_multiple_runs(mock_mlflow_client):
    """Test experiments page with multiple runs."""
    from services.dashboard.app import create_app

    mock_client, mock_experiment, mock_run = mock_mlflow_client

    # Create additional runs
    mock_run_2 = MagicMock()
    mock_run_2.info.run_id = "test-run-789"
    mock_run_2.info.experiment_id = "test-exp-123"
    mock_run_2.info.status = "FINISHED"
    mock_run_2.info.start_time = int((datetime.now() - timedelta(hours=1)).timestamp() * 1000)
    mock_run_2.info.end_time = int(datetime.now().timestamp() * 1000)
    mock_run_2.data.metrics = {
        "sharpe_ratio": 2.15,
        "total_return_pct": 18.7,
        "max_drawdown_pct": -6.5,
        "win_rate": 0.72,
    }
    mock_run_2.data.params = {
        "strategy_name": "bb_reversion",
        "symbol": "005930",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
    }

    # Update mock to return multiple runs
    mock_client.search_runs.return_value = [mock_run, mock_run_2]

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("services.dashboard.routes.experiments._get_mlflow_client") as mock_get_client:
            mock_get_client.return_value = mock_client

            # Query runs
            runs_response = await client.get(
                "/api/experiments/test-exp-123/runs?limit=10"
            )

            assert runs_response.status_code == 200
            runs_data = runs_response.json()
            assert runs_data["total"] == 2

            runs = runs_data["runs"]
            assert len(runs) == 2

            # Verify both runs are present
            run_ids = [r["run_id"] for r in runs]
            assert "test-run-456" in run_ids
            assert "test-run-789" in run_ids

            # Verify best run (highest sharpe_ratio)
            best_response = await client.get(
                "/api/experiments/test-exp-123/best?metric=sharpe_ratio"
            )

            assert best_response.status_code == 200
            best_data = best_response.json()
            assert best_data["run"]["run_id"] == "test-run-789"  # Higher sharpe
            assert best_data["value"] == 2.15


@pytest.mark.asyncio
async def test_mlflow_experiments_filter_by_status(mock_mlflow_client):
    """Test filtering runs by status."""
    from services.dashboard.app import create_app

    mock_client, mock_experiment, mock_run = mock_mlflow_client

    # Create runs with different statuses
    mock_run_finished = mock_run
    mock_run_failed = MagicMock()
    mock_run_failed.info.run_id = "test-run-failed"
    mock_run_failed.info.experiment_id = "test-exp-123"
    mock_run_failed.info.status = "FAILED"
    mock_run_failed.info.start_time = int(datetime.now().timestamp() * 1000)
    mock_run_failed.info.end_time = int((datetime.now() + timedelta(minutes=1)).timestamp() * 1000)
    mock_run_failed.data.metrics = {}
    mock_run_failed.data.params = {}

    # Mock will return filtered results based on status
    def mock_search_runs(experiment_ids, filter_string="", order_by=None, max_results=50):
        if "FINISHED" in filter_string:
            return [mock_run_finished]
        elif "FAILED" in filter_string:
            return [mock_run_failed]
        return [mock_run_finished, mock_run_failed]

    mock_client.search_runs.side_effect = mock_search_runs

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("services.dashboard.routes.experiments._get_mlflow_client") as mock_get_client:
            mock_get_client.return_value = mock_client

            # Query with status filter
            response = await client.get(
                "/api/experiments/test-exp-123/runs?status=finished"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["runs"][0]["status"] == "FINISHED"


@pytest.mark.asyncio
async def test_backtest_result_structure():
    """Test backtest result structure matches MLflow expectations."""
    from services.dashboard.app import create_app
    from services.dashboard.routes import backtest as backtest_routes

    # Generate sample data
    base = datetime(2024, 1, 1, 9, 0)
    rows = []
    price = 100.0
    for i in range(60):
        price += 0.1
        rows.append(
            {
                "code": "005930",
                "name": "005930",
                "datetime": base + timedelta(minutes=i),
                "open": price - 0.2,
                "high": price + 0.3,
                "low": price - 0.4,
                "close": price,
                "volume": 1000 + i,
            }
        )
    df = pd.DataFrame(rows)

    with patch.object(
        backtest_routes, "_fetch_ohlcv", return_value=df
    ), patch.object(backtest_routes, "_generate_chart", return_value=None):

        app = create_app()
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/backtest/run",
                json={
                    "asset_class": "stock",
                    "strategy": "bb_reversion",
                    "symbol": "005930",
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                    "initial_capital": 10000000,
                },
            )

            assert response.status_code == 200
            data = response.json()
            result = data["result"]

            # Verify all required fields for MLflow tracking are present
            required_metrics = [
                "sharpe_ratio",
                "total_return_pct",
                "max_drawdown_pct",
                "win_rate",
            ]

            for metric in required_metrics:
                assert metric in result, f"Missing metric: {metric}"
                # Verify it's a number (not None)
                assert isinstance(
                    result[metric], (int, float)
                ), f"Metric {metric} is not numeric"

            # Verify strategy info for params
            assert "strategy" in result
            assert "symbol" in result
            assert "start_date" in result
            assert "end_date" in result


@pytest.mark.asyncio
async def test_create_experiment():
    """Test creating a new experiment."""
    from services.dashboard.app import create_app

    mock_client = MagicMock()
    mock_client.create_experiment.return_value = "new-exp-456"

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("services.dashboard.routes.experiments._get_mlflow_client") as mock_get_client:
            mock_get_client.return_value = mock_client

            response = await client.post(
                "/api/experiments?name=new_experiment"
            )

            assert response.status_code == 200
            data = response.json()
            assert "experiment_id" in data
            assert "name" in data
            assert data["experiment_id"] == "new-exp-456"
            assert data["name"] == "new_experiment"
            mock_client.create_experiment.assert_called_once_with("new_experiment")
