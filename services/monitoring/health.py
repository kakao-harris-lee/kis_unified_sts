"""헬스 체크

시스템 컴포넌트 헬스 체크.

Usage:
    from services.monitoring import HealthChecker

    checker = HealthChecker()

    # 컴포넌트 등록
    checker.register("redis", redis_health_check)
    checker.register("database", db_health_check)

    # 전체 헬스 체크
    status = await checker.check_all()

    if status.is_healthy:
        print("All systems operational")
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class ComponentStatus(Enum):
    """컴포넌트 상태"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """컴포넌트 헬스 결과"""

    name: str
    status: ComponentStatus
    message: str = ""
    latency_ms: float = 0.0
    checked_at: datetime = field(default_factory=datetime.now)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": round(self.latency_ms, 2),
            "checked_at": self.checked_at.isoformat(),
            "details": self.details,
        }


@dataclass
class HealthStatus:
    """전체 헬스 상태"""

    status: ComponentStatus
    components: list[ComponentHealth]
    checked_at: datetime = field(default_factory=datetime.now)

    @property
    def is_healthy(self) -> bool:
        return self.status == ComponentStatus.HEALTHY

    @property
    def unhealthy_components(self) -> list[str]:
        return [
            c.name
            for c in self.components
            if c.status in (ComponentStatus.UNHEALTHY, ComponentStatus.UNKNOWN)
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "is_healthy": self.is_healthy,
            "components": [c.to_dict() for c in self.components],
            "unhealthy": self.unhealthy_components,
            "checked_at": self.checked_at.isoformat(),
        }


# 헬스 체크 함수 타입
HealthCheckFunc = Callable[[], Coroutine[Any, Any, ComponentHealth]]


class HealthChecker:
    """헬스 체크 관리자

    각 컴포넌트의 헬스 상태를 확인하고 집계.

    Usage:
        checker = HealthChecker()

        # 커스텀 체크 등록
        checker.register("redis", check_redis)

        # 전체 체크
        status = await checker.check_all()
    """

    def __init__(self, timeout: float = 5.0):
        """
        Args:
            timeout: 각 체크의 타임아웃 (초)
        """
        self.timeout = timeout
        self._checks: dict[str, HealthCheckFunc] = {}

        # 기본 체크 등록
        self._setup_default_checks()

    def _setup_default_checks(self):
        """기본 헬스 체크 등록"""
        self.register("system", self._check_system)

    def register(self, name: str, check_func: HealthCheckFunc):
        """헬스 체크 함수 등록

        Args:
            name: 컴포넌트 이름
            check_func: 헬스 체크 비동기 함수
        """
        self._checks[name] = check_func
        logger.debug(f"Health check registered: {name}")

    def unregister(self, name: str):
        """헬스 체크 함수 제거"""
        self._checks.pop(name, None)

    async def check(self, name: str) -> ComponentHealth:
        """단일 컴포넌트 체크

        Args:
            name: 컴포넌트 이름

        Returns:
            ComponentHealth 결과
        """
        if name not in self._checks:
            return ComponentHealth(
                name=name,
                status=ComponentStatus.UNKNOWN,
                message=f"No health check registered for {name}",
            )

        check_func = self._checks[name]
        start_time = datetime.now()

        try:
            result = await asyncio.wait_for(check_func(), timeout=self.timeout)
            result.latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            return result

        except asyncio.TimeoutError:
            return ComponentHealth(
                name=name,
                status=ComponentStatus.UNHEALTHY,
                message=f"Health check timed out after {self.timeout}s",
                latency_ms=self.timeout * 1000,
            )
        except Exception as e:
            return ComponentHealth(
                name=name,
                status=ComponentStatus.UNHEALTHY,
                message=str(e),
                latency_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

    async def check_all(self) -> HealthStatus:
        """모든 컴포넌트 체크

        Returns:
            HealthStatus 전체 상태
        """
        # 병렬 실행
        results = await asyncio.gather(
            *[self.check(name) for name in self._checks],
            return_exceptions=True,
        )

        components = []
        for name, result in zip(self._checks.keys(), results):
            if isinstance(result, Exception):
                components.append(
                    ComponentHealth(
                        name=name,
                        status=ComponentStatus.UNHEALTHY,
                        message=str(result),
                    )
                )
            else:
                components.append(result)

        # 전체 상태 결정
        statuses = [c.status for c in components]

        if all(s == ComponentStatus.HEALTHY for s in statuses):
            overall = ComponentStatus.HEALTHY
        elif any(s == ComponentStatus.UNHEALTHY for s in statuses):
            overall = ComponentStatus.UNHEALTHY
        elif any(s == ComponentStatus.DEGRADED for s in statuses):
            overall = ComponentStatus.DEGRADED
        else:
            overall = ComponentStatus.UNKNOWN

        return HealthStatus(
            status=overall,
            components=components,
        )

    # =========================================================================
    # 기본 체크 함수들
    # =========================================================================

    async def _check_system(self) -> ComponentHealth:
        """시스템 기본 체크"""
        import platform
        import sys

        return ComponentHealth(
            name="system",
            status=ComponentStatus.HEALTHY,
            message="System is running",
            details={
                "python_version": sys.version,
                "platform": platform.platform(),
            },
        )


# Redis 헬스 체크 팩토리
def create_redis_check(redis_url: str) -> HealthCheckFunc:
    """Redis 헬스 체크 함수 생성"""

    async def check_redis() -> ComponentHealth:
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(redis_url)
            await client.ping()
            await client.close()

            return ComponentHealth(
                name="redis",
                status=ComponentStatus.HEALTHY,
                message="Redis is connected",
            )
        except ImportError:
            return ComponentHealth(
                name="redis",
                status=ComponentStatus.UNKNOWN,
                message="redis package not installed",
            )
        except Exception as e:
            return ComponentHealth(
                name="redis",
                status=ComponentStatus.UNHEALTHY,
                message=str(e),
            )

    return check_redis


# Database 헬스 체크 팩토리
def create_database_check(connection_string: str) -> HealthCheckFunc:
    """데이터베이스 헬스 체크 함수 생성"""

    async def check_database() -> ComponentHealth:
        try:
            # ClickHouse 예시
            from clickhouse_driver import Client

            client = Client.from_url(connection_string)
            result = client.execute("SELECT 1")

            return ComponentHealth(
                name="database",
                status=ComponentStatus.HEALTHY,
                message="Database is connected",
            )
        except ImportError:
            return ComponentHealth(
                name="database",
                status=ComponentStatus.UNKNOWN,
                message="database driver not installed",
            )
        except Exception as e:
            return ComponentHealth(
                name="database",
                status=ComponentStatus.UNHEALTHY,
                message=str(e),
            )

    return check_database


# 전역 헬스 체커
_health_checker: HealthChecker | None = None


def get_health_checker() -> HealthChecker:
    """전역 헬스 체커 반환"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker
