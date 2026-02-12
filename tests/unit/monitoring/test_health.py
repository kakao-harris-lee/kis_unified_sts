"""Test HealthChecker."""
import pytest


@pytest.mark.asyncio
async def test_health_check_component():
    """Test component health check."""
    from shared.monitoring.health import HealthChecker

    checker = HealthChecker()

    # Register a healthy component
    async def healthy_check():
        return True

    checker.register("database", healthy_check)

    result = await checker.check("database")

    assert result.name == "database"
    assert result.healthy is True


@pytest.mark.asyncio
async def test_health_check_all():
    """Test checking all components."""
    from shared.monitoring.health import HealthChecker

    checker = HealthChecker()

    checker.register("db", lambda: True)
    checker.register("cache", lambda: True)

    results = await checker.check_all()

    assert len(results) == 2
    assert all(r.healthy for r in results)
