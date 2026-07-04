"""Synchronous trading session calendar utilities."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from datetime import time as dt_time
from enum import Enum
from pathlib import Path
from typing import Protocol

import yaml

logger = logging.getLogger(__name__)

MAX_YAML_FILE_SIZE = 1_024 * 1_024  # 1MB max for YAML config files


class HolidayLoader(Protocol):
    """Protocol for holiday data loading (allows injection for testing)."""

    def __call__(self, config_path: str) -> set[date]:
        """Load holidays from config file."""
        ...


def default_holiday_loader(
    config_path: str = "config/market_schedule.yaml",
) -> set[date]:
    """Default implementation for loading holidays from config file.

    Args:
        config_path: Path to market schedule YAML config

    Returns:
        Set of holiday dates
    """
    holidays: set[date] = set()
    path = Path(config_path)

    if not path.exists():
        logger.warning(f"Holiday config not found: {config_path}, using empty set")
        return holidays

    try:
        # Security: Check file size before parsing to prevent DoS via large files
        file_size = path.stat().st_size
        if file_size > MAX_YAML_FILE_SIZE:
            logger.error(
                f"Holiday config file too large: {file_size} bytes > {MAX_YAML_FILE_SIZE} bytes"
            )
            return holidays

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            logger.warning(f"Invalid holiday config format in {config_path}")
            return holidays

        for holiday_str in data.get("holidays", []):
            try:
                if isinstance(holiday_str, str):
                    holidays.add(date.fromisoformat(holiday_str))
                elif isinstance(holiday_str, date):
                    holidays.add(holiday_str)
            except (ValueError, TypeError) as e:
                logger.debug(f"Skipping invalid holiday entry: {holiday_str} - {e}")
    except (OSError, yaml.YAMLError) as e:
        logger.error(f"Failed to load holidays from config file: {e}", exc_info=True)
    except (KeyError, TypeError, AttributeError) as e:
        logger.error(f"Invalid holiday config format: {e}", exc_info=True)

    return holidays


class HolidayCache:
    """Thread-safe holiday cache with injectable loader.

    NOTE: This is a legacy sync version. For async contexts, use
    AsyncHolidayCache from services.trading.holiday_cache instead.

    Usage:
        # Default usage
        cache = HolidayCache()
        holidays = cache.get()

        # With custom loader (for testing)
        cache = HolidayCache(loader=lambda path: {date(2024, 1, 1)})
    """

    def __init__(
        self,
        loader: Callable[[str], set[date]] | None = None,
        config_path: str = "config/market_schedule.yaml",
    ):
        self._loader = loader or default_holiday_loader
        self._config_path = config_path
        self._cache: set[date] | None = None
        self._lock = asyncio.Lock()

    def get(self) -> set[date]:
        """Get holidays (loads on first access)."""
        if self._cache is None:
            self._cache = self._loader(self._config_path)
        return self._cache

    def reload(self):
        """Force reload of holidays (sync version, not thread-safe for concurrent use)."""
        self._cache = None

    async def reload_async(self):
        """Force reload of holidays with async lock for thread-safety."""
        async with self._lock:
            self._cache = None

    async def get_async(self) -> set[date]:
        """Get holidays with async lock for concurrent access."""
        async with self._lock:
            return self.get()


# Global holiday cache (can be replaced for testing)
_holiday_cache = HolidayCache()


def _get_holidays() -> set[date]:
    """공휴일 가져오기 (캐시 사용)"""
    return _holiday_cache.get()


def reload_holidays():
    """공휴일 다시 로드 (설정 변경 시)"""
    _holiday_cache.reload()


def set_holiday_cache(cache: HolidayCache):
    """Replace global holiday cache (for testing)."""
    global _holiday_cache
    _holiday_cache = cache


class TradingState(Enum):
    """트레이딩 상태"""

    IDLE = "idle"  # 대기 중
    WAITING = "waiting"  # 장 시작 대기
    RUNNING = "running"  # 거래 중
    PAUSED = "paused"  # 일시 정지
    STOPPED = "stopped"  # 종료됨
    ERROR = "error"  # 오류 발생


@dataclass
class MarketSchedule:
    """장 시간 설정"""

    # 주식
    stock_open: dt_time = field(default_factory=lambda: dt_time(9, 0))
    stock_close: dt_time = field(default_factory=lambda: dt_time(15, 30))

    # 선물 - default 08:45 matches market_schedule.yaml::futures.regular.open.
    # NOT hardcoded to 09:00; populated by load_from_yaml() below.
    futures_open: dt_time = field(default_factory=lambda: dt_time(8, 45))
    futures_close: dt_time = field(default_factory=lambda: dt_time(15, 45))

    # 서비스 시작/종료 (장 시작 전/후 여유)
    service_start_offset_minutes: int = 5
    service_end_offset_minutes: int = 5

    @classmethod
    def load_from_yaml(
        cls, config_path: str = "config/market_schedule.yaml"
    ) -> MarketSchedule:
        """Load a MarketSchedule from *config_path*.

        Reads ``market_schedule.{stock,futures}.regular.{open,close}`` and
        constructs a schedule.  Falls back to the dataclass defaults when the
        file is absent or a key is missing.
        """
        import yaml as _yaml

        schedule = cls()
        path = Path(config_path)
        if not path.exists():
            logger.warning(
                "market_schedule config not found: %s; using defaults", config_path
            )
            return schedule
        try:
            data = _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            ms = data.get("market_schedule", {})

            def _parse_time(section: dict, key: str, default: dt_time) -> dt_time:
                raw = section.get(key)
                if not raw:
                    return default
                parts = str(raw).strip().split(":")
                if len(parts) < 2:
                    return default
                return dt_time(int(parts[0]), int(parts[1]))

            stock_reg = ms.get("stock", {}).get("regular", {})
            futures_reg = ms.get("futures", {}).get("regular", {})

            schedule = cls(
                stock_open=_parse_time(stock_reg, "open", dt_time(9, 0)),
                stock_close=_parse_time(stock_reg, "close", dt_time(15, 30)),
                futures_open=_parse_time(futures_reg, "open", dt_time(8, 45)),
                futures_close=_parse_time(futures_reg, "close", dt_time(15, 45)),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to load market_schedule from %s: %s; using defaults",
                config_path,
                exc,
            )
        return schedule

    def get_open_time(self, asset_class: str) -> dt_time:
        return self.stock_open if asset_class == "stock" else self.futures_open

    def get_close_time(self, asset_class: str) -> dt_time:
        return self.stock_close if asset_class == "stock" else self.futures_close


def is_trading_day(d: date | None = None, holidays: set[date] | None = None) -> bool:
    """거래일 여부 확인

    Args:
        d: 확인할 날짜 (None이면 오늘)
        holidays: 공휴일 set (None이면 설정 파일에서 로드)

    Returns:
        거래일이면 True
    """
    if d is None:
        d = date.today()

    # 주말
    if d.weekday() >= 5:
        return False

    # 공휴일
    if holidays is None:
        holidays = _get_holidays()

    return d not in holidays
