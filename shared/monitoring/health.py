"""Health checking service."""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Union, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class ComponentHealth:
    """Health status of a component."""
    name: str
    healthy: bool
    timestamp: datetime
    latency_ms: float = 0.0
    message: Optional[str] = None


class HealthChecker:
    """Check health of system components.

    Features:
    - Register health check functions
    - Async/sync check support
    - Latency measurement
    - Aggregate health status
    """

    def __init__(self, timeout_seconds: float = 5.0):
        self.timeout = timeout_seconds
        self._checks: Dict[str, Callable] = {}

    def register(
        self,
        name: str,
        check_fn: Union[Callable[[], bool], Callable[[], Awaitable[bool]]],
    ) -> None:
        """Register health check function."""
        self._checks[name] = check_fn
        logger.debug(f"Registered health check: {name}")

    async def check(self, name: str) -> ComponentHealth:
        """Check health of single component.

        Args:
            name: Component name

        Returns:
            ComponentHealth with status
        """
        if name not in self._checks:
            return ComponentHealth(
                name=name,
                healthy=False,
                timestamp=datetime.now(),
                message="Component not registered",
            )

        check_fn = self._checks[name]
        start_time = datetime.now()

        try:
            result = check_fn()
            if asyncio.iscoroutine(result):
                result = await asyncio.wait_for(result, timeout=self.timeout)

            latency = (datetime.now() - start_time).total_seconds() * 1000

            return ComponentHealth(
                name=name,
                healthy=bool(result),
                timestamp=datetime.now(),
                latency_ms=latency,
            )

        except asyncio.TimeoutError:
            return ComponentHealth(
                name=name,
                healthy=False,
                timestamp=datetime.now(),
                message="Health check timed out",
            )
        except Exception as e:
            logger.error(f"Health check failed for {name}: {e}")
            return ComponentHealth(
                name=name,
                healthy=False,
                timestamp=datetime.now(),
                message=str(e),
            )

    async def check_all(self) -> List[ComponentHealth]:
        """Check health of all components.

        Returns:
            List of ComponentHealth for all registered components
        """
        tasks = [self.check(name) for name in self._checks]
        return await asyncio.gather(*tasks)

    def is_healthy(self, results: List[ComponentHealth]) -> bool:
        """Check if all components are healthy."""
        return all(r.healthy for r in results)

    def get_summary(self, results: List[ComponentHealth]) -> Dict:
        """Get health summary."""
        return {
            "healthy": self.is_healthy(results),
            "components": {
                r.name: {
                    "healthy": r.healthy,
                    "latency_ms": r.latency_ms,
                    "message": r.message,
                }
                for r in results
            },
            "timestamp": datetime.now().isoformat(),
        }
