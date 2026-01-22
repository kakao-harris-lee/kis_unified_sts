"""HTTP utilities module.

Provides reusable patterns for async HTTP operations.
"""

from .session import (
    AsyncSessionMixin,
    AsyncSessionWithTimeoutMixin,
    ConnectionPoolConfig,
)

__all__ = [
    "AsyncSessionMixin",
    "AsyncSessionWithTimeoutMixin",
    "ConnectionPoolConfig",
]
