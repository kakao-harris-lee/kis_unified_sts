"""Test API pagination."""
import pytest
from datetime import datetime
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient


def _make_trades(count: int = 25):
    """Create mock trade dicts for testing."""
    trades = []
    for i in range(count):
        trades.append({
            "id": f"trade_{i}",
            "symbol": "005930" if i % 2 == 0 else "000660",
            "side": "BUY",
            "quantity": 10,
            "entry_price": 50000.0,
            "exit_price": 51000.0 if i % 3 != 0 else 49000.0,
            "pnl": 10000.0 if i % 3 != 0 else -10000.0,
            "pnl_pct": 2.0 if i % 3 != 0 else -2.0,
            "strategy": "v35" if i % 2 == 0 else "breakout",
            "entry_time": datetime.now().isoformat(),
            "exit_time": datetime.now().isoformat(),
        })
    return trades


@pytest.fixture
def mock_trades():
    """Patch _load_trades to return test data."""
    with patch("services.dashboard.routes.trades._load_trades", return_value=_make_trades(25)):
        yield


@pytest.mark.asyncio
async def test_trades_pagination_first_page(mock_trades):
    """Test trades endpoint returns first page correctly."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trades", params={"page": 1, "limit": 10})

        assert response.status_code == 200
        data = response.json()

        assert "trades" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data

        assert len(data["trades"]) == 10
        assert data["total"] == 25
        assert data["page"] == 1
        assert data["limit"] == 10


@pytest.mark.asyncio
async def test_trades_pagination_second_page(mock_trades):
    """Test trades endpoint returns second page correctly."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trades", params={"page": 2, "limit": 10})

        assert response.status_code == 200
        data = response.json()

        assert len(data["trades"]) == 10
        assert data["page"] == 2


@pytest.mark.asyncio
async def test_trades_pagination_last_page(mock_trades):
    """Test trades endpoint returns partial last page correctly."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trades", params={"page": 3, "limit": 10})

        assert response.status_code == 200
        data = response.json()

        # 25 trades, page 3 with limit 10 = 5 remaining
        assert len(data["trades"]) == 5
        assert data["page"] == 3


@pytest.mark.asyncio
async def test_trades_pagination_beyond_last_page(mock_trades):
    """Test trades endpoint returns empty for page beyond data."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trades", params={"page": 10, "limit": 10})

        assert response.status_code == 200
        data = response.json()

        assert len(data["trades"]) == 0
        assert data["total"] == 25


@pytest.mark.asyncio
async def test_trades_pagination_with_filter(mock_trades):
    """Test trades pagination with strategy filter."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/trades", params={"strategy": "v35", "page": 1, "limit": 10}
        )

        assert response.status_code == 200
        data = response.json()

        # All returned trades should be v35 strategy
        for trade in data["trades"]:
            assert trade["strategy"] == "v35"

        # Total should be filtered count
        assert data["total"] == 13  # Every other trade (0,2,4,...,24)


@pytest.mark.asyncio
async def test_trades_pagination_limit_validation():
    """Test trades endpoint validates limit parameter."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Limit above max (100)
        response = await client.get("/api/trades", params={"limit": 200})
        assert response.status_code == 422  # Validation error

        # Limit below min (1)
        response = await client.get("/api/trades", params={"limit": 0})
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_trades_pagination_page_validation():
    """Test trades endpoint validates page parameter."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Page below min (1)
        response = await client.get("/api/trades", params={"page": 0})
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_trades_default_pagination():
    """Test trades endpoint uses default pagination values."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/trades")

        assert response.status_code == 200
        data = response.json()

        # Default values: page=1, limit=50
        assert data["page"] == 1
        assert data["limit"] == 50
