"""Tests for async holiday cache module."""

import asyncio
from datetime import date
from unittest.mock import patch

import pytest
import yaml


@pytest.mark.asyncio
async def test_async_holiday_loader_is_coroutine():
    """async_holiday_loader should be a coroutine function."""
    from services.trading.holiday_cache import async_holiday_loader

    assert asyncio.iscoroutinefunction(async_holiday_loader)


@pytest.mark.asyncio
async def test_async_holiday_loader_with_aiofiles(tmp_path):
    """Test loading with aiofiles."""
    from services.trading.holiday_cache import HAS_AIOFILES, async_holiday_loader

    if not HAS_AIOFILES:
        pytest.skip("aiofiles not installed")

    # Create test config
    config_file = tmp_path / "market_schedule.yaml"
    holidays_data = {
        "holidays": [
            "2024-01-01",
            "2024-05-01",
            "2024-12-25",
        ]
    }
    config_file.write_text(yaml.dump(holidays_data), encoding="utf-8")

    # Load holidays
    holidays = await async_holiday_loader(str(config_file))

    # Verify
    assert len(holidays) == 3
    assert date(2024, 1, 1) in holidays
    assert date(2024, 5, 1) in holidays
    assert date(2024, 12, 25) in holidays


@pytest.mark.asyncio
async def test_async_holiday_loader_fallback_without_aiofiles(tmp_path):
    """Test fallback to run_in_executor when aiofiles not available."""
    from services.trading import holiday_cache

    # Create test config
    config_file = tmp_path / "market_schedule.yaml"
    holidays_data = {"holidays": ["2024-01-01"]}
    config_file.write_text(yaml.dump(holidays_data), encoding="utf-8")

    # Mock aiofiles as unavailable
    with patch.object(holiday_cache, "HAS_AIOFILES", False):
        holidays = await holiday_cache.async_holiday_loader(str(config_file))

    # Verify fallback worked
    assert len(holidays) == 1
    assert date(2024, 1, 1) in holidays


@pytest.mark.asyncio
async def test_async_holiday_loader_missing_file():
    """Test handling of missing config file."""
    from services.trading.holiday_cache import async_holiday_loader

    holidays = await async_holiday_loader("nonexistent.yaml")

    assert holidays == set()


@pytest.mark.asyncio
async def test_async_holiday_loader_file_too_large(tmp_path):
    """Test security check for file size limit."""
    from services.trading.holiday_cache import async_holiday_loader

    # Create large file
    config_file = tmp_path / "large.yaml"
    large_content = "x" * (1_024 * 1_024 + 1)  # > 1MB
    config_file.write_text(large_content, encoding="utf-8")

    holidays = await async_holiday_loader(str(config_file))

    assert holidays == set()


@pytest.mark.asyncio
async def test_async_holiday_loader_invalid_yaml(tmp_path):
    """Test handling of invalid YAML content."""
    from services.trading.holiday_cache import async_holiday_loader

    config_file = tmp_path / "invalid.yaml"
    config_file.write_text("[invalid yaml content", encoding="utf-8")

    holidays = await async_holiday_loader(str(config_file))

    assert holidays == set()


@pytest.mark.asyncio
async def test_async_holiday_loader_invalid_dates(tmp_path):
    """Test handling of invalid date formats."""
    from services.trading.holiday_cache import async_holiday_loader

    config_file = tmp_path / "invalid_dates.yaml"
    holidays_data = {
        "holidays": [
            "2024-01-01",  # Valid
            "invalid-date",  # Invalid
            "2024-13-32",  # Invalid
            12345,  # Invalid type
        ]
    }
    config_file.write_text(yaml.dump(holidays_data), encoding="utf-8")

    holidays = await async_holiday_loader(str(config_file))

    # Only valid date should be loaded
    assert len(holidays) == 1
    assert date(2024, 1, 1) in holidays


@pytest.mark.asyncio
async def test_async_holiday_cache_double_checked_locking():
    """Cache should use double-checked locking."""
    from services.trading.holiday_cache import AsyncHolidayCache

    call_count = 0

    async def mock_loader(_path: str) -> set[date]:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)  # Simulate I/O
        return {date(2024, 1, 1)}

    cache = AsyncHolidayCache(loader=mock_loader)

    # First get should load
    holidays1 = await cache.get()
    assert call_count == 1

    # Second get should use cache
    holidays2 = await cache.get()
    assert call_count == 1
    assert holidays1 is holidays2


@pytest.mark.asyncio
async def test_async_holiday_cache_concurrent_access():
    """Concurrent get() calls should not cause multiple loads."""
    from services.trading.holiday_cache import AsyncHolidayCache

    call_count = 0

    async def mock_loader(_path: str) -> set[date]:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)  # Simulate slow I/O
        return {date(2024, 1, 1)}

    cache = AsyncHolidayCache(loader=mock_loader)

    # Launch 10 concurrent get() calls
    results = await asyncio.gather(*[cache.get() for _ in range(10)])

    # Loader should only be called once
    assert call_count == 1

    # All results should be identical
    for result in results:
        assert result == {date(2024, 1, 1)}


@pytest.mark.asyncio
async def test_async_holiday_cache_reload():
    """Test force reload functionality."""
    from services.trading.holiday_cache import AsyncHolidayCache

    call_count = 0

    async def mock_loader(_path: str) -> set[date]:
        nonlocal call_count
        call_count += 1
        return {date(2024, 1, call_count)}

    cache = AsyncHolidayCache(loader=mock_loader)

    # First load
    holidays1 = await cache.get()
    assert date(2024, 1, 1) in holidays1

    # Reload
    await cache.reload()
    holidays2 = await cache.get()
    assert date(2024, 1, 2) in holidays2

    assert call_count == 2


def test_is_holiday_sync():
    """is_holiday should work synchronously with pre-loaded data."""
    from services.trading.holiday_cache import AsyncHolidayCache

    cache = AsyncHolidayCache()

    # With explicit holidays set
    holidays = {date(2024, 1, 1), date(2024, 12, 25)}
    assert cache.is_holiday(date(2024, 1, 1), holidays) is True
    assert cache.is_holiday(date(2024, 6, 15), holidays) is False


def test_is_holiday_without_preload_raises():
    """is_holiday should raise if cache not loaded."""
    from services.trading.holiday_cache import AsyncHolidayCache

    cache = AsyncHolidayCache()

    with pytest.raises(RuntimeError, match="Cache not loaded"):
        cache.is_holiday(date(2024, 1, 1))


@pytest.mark.asyncio
async def test_is_holiday_uses_cache():
    """is_holiday should use cached data if available."""
    from services.trading.holiday_cache import AsyncHolidayCache

    async def mock_loader(_path: str) -> set[date]:
        return {date(2024, 1, 1)}

    cache = AsyncHolidayCache(loader=mock_loader)

    # Load cache
    await cache.get()

    # Now is_holiday should work without explicit holidays
    assert cache.is_holiday(date(2024, 1, 1)) is True
    assert cache.is_holiday(date(2024, 6, 15)) is False


@pytest.mark.asyncio
async def test_async_holiday_loader_date_objects(tmp_path):
    """Test loading with date objects in YAML."""
    from services.trading.holiday_cache import async_holiday_loader

    config_file = tmp_path / "dates.yaml"
    # YAML can represent dates as objects
    holidays_data = {
        "holidays": [
            date(2024, 1, 1),
            date(2024, 12, 25),
        ]
    }
    config_file.write_text(yaml.dump(holidays_data), encoding="utf-8")

    holidays = await async_holiday_loader(str(config_file))

    assert len(holidays) == 2
    assert date(2024, 1, 1) in holidays
    assert date(2024, 12, 25) in holidays
