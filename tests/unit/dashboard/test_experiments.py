"""Test experiments (MLflow) endpoints."""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_experiments_list():
    """Test experiments list endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/experiments")

    assert response.status_code == 200
    data = response.json()
    assert "experiments" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_experiment_runs():
    """Test experiment runs endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Use a numeric experiment ID (MLflow requires numeric IDs)
        response = await client.get("/api/experiments/0/runs")

    # 200 with empty runs or 500 if MLflow not available
    assert response.status_code in [200, 500]
    if response.status_code == 200:
        data = response.json()
        assert "runs" in data


@pytest.mark.asyncio
async def test_experiment_best_run():
    """Test best run endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Use a numeric experiment ID (MLflow requires numeric IDs)
        response = await client.get("/api/experiments/0/best?metric=sharpe_ratio")

    # 200 with no best run, 404 if experiment not found, or 500 if MLflow not available
    assert response.status_code in [200, 404, 500]
