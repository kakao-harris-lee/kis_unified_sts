"""Holiday cache with async file I/O support.

This module provides non-blocking holiday loading to prevent event loop blocking
in async contexts.
"""

import asyncio
import logging
from datetime import date
from pathlib import Path
from typing import Awaitable, Callable, Protocol

import yaml

try:
    import aiofiles

    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False

logger = logging.getLogger(__name__)

MAX_YAML_FILE_SIZE = 1_024 * 1_024  # 1MB


class AsyncHolidayLoader(Protocol):
    """Protocol for async holiday loading."""

    async def __call__(self, config_path: str) -> set[date]: ...


async def async_holiday_loader(
    config_path: str = "config/market_schedule.yaml",
) -> set[date]:
    """Async holiday loader (non-blocking).

    Uses aiofiles if available, otherwise performs a small synchronous read.

    Args:
        config_path: Path to YAML config file containing holidays.

    Returns:
        Set of holiday dates.
    """
    holidays: set[date] = set()
    path = Path(config_path)

    if not path.exists():
        logger.warning(f"Holiday config not found: {config_path}")
        return holidays

    try:
        # Security: Check file size
        file_size = path.stat().st_size
        if file_size > MAX_YAML_FILE_SIZE:
            logger.error(
                f"Holiday config too large: {file_size} > {MAX_YAML_FILE_SIZE}"
            )
            return holidays

        # Load content asynchronously
        if HAS_AIOFILES:
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                content = await f.read()
        else:
            # NOTE: In some constrained environments, asyncio's default executor can
            # intermittently hang when used for file I/O. This loader only allows
            # up to 1MB, and it is called infrequently, so a direct synchronous read
            # is a safer fallback.
            content = path.read_text(encoding="utf-8")

        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            logger.warning("Invalid holiday config format")
            return holidays

        for h in data.get("holidays", []):
            try:
                if isinstance(h, str):
                    holidays.add(date.fromisoformat(h))
                elif isinstance(h, date):
                    holidays.add(h)
            except (ValueError, TypeError) as e:
                logger.debug(f"Skipping invalid holiday: {h} - {e}")
    except (OSError, IOError, yaml.YAMLError, ValueError, TypeError) as e:
        logger.error(f"Failed to load holidays: {e}", exc_info=True)

    return holidays


class AsyncHolidayCache:
    """Async-friendly holiday cache with proper locking.

    Features:
    - Async file I/O (non-blocking)
    - Double-checked locking for thread-safety
    - Concurrent access protection
    - Sync is_holiday() check for pre-loaded data

    Example:
        >>> cache = AsyncHolidayCache()
        >>> holidays = await cache.get()
        >>> if cache.is_holiday(date.today()):
        ...     print("Market closed")
    """

    def __init__(
        self,
        loader: Callable[[str], Awaitable[set[date]]] | None = None,
        config_path: str = "config/market_schedule.yaml",
    ):
        """Initialize cache.

        Args:
            loader: Custom async loader function. Defaults to async_holiday_loader.
            config_path: Path to config file.
        """
        self._loader = loader or async_holiday_loader
        self._config_path = config_path
        self._cache: set[date] | None = None
        self._lock = asyncio.Lock()

    async def get(self) -> set[date]:
        """Get holidays asynchronously (cached, thread-safe).

        Uses double-checked locking to prevent redundant loads.

        Returns:
            Set of holiday dates.
        """
        if self._cache is not None:
            return self._cache

        async with self._lock:
            if self._cache is None:
                self._cache = await self._loader(self._config_path)
            return self._cache

    async def reload(self) -> None:
        """Force reload holidays asynchronously.

        Useful when config file has been updated.
        """
        async with self._lock:
            self._cache = await self._loader(self._config_path)

    def is_holiday(self, d: date, holidays: set[date] | None = None) -> bool:
        """Check if date is holiday (sync, use pre-loaded data).

        Args:
            d: Date to check.
            holidays: Optional explicit holidays set. If None, uses cache.

        Returns:
            True if date is a holiday.

        Raises:
            RuntimeError: If cache not loaded and holidays not provided.
        """
        if holidays is None:
            if self._cache is None:
                raise RuntimeError("Cache not loaded. Call await get() first.")
            holidays = self._cache
        return d in holidays
