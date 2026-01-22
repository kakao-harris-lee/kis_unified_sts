"""Async HTTP session management utilities.

Provides reusable session management patterns for aiohttp clients.

Usage:
    from shared.http.session import AsyncSessionMixin

    class MyClient(AsyncSessionMixin):
        async def fetch_data(self):
            session = await self._get_session()
            async with session.get(url) as resp:
                return await resp.json()

        async def cleanup(self):
            await self._close_session()

SSL Configuration:
    class SecureClient(AsyncSessionMixin):
        _ssl_verify = True  # Enable SSL verification (default)
        _ssl_context = None  # Custom SSL context (optional)

Connection Pooling:
    class PooledClient(AsyncSessionMixin):
        _pool_limit = 100           # Total max connections (default: 100)
        _pool_limit_per_host = 10   # Max connections per host (default: 0 = unlimited)
        _pool_keepalive_timeout = 15.0  # Keep-alive timeout in seconds
"""

from __future__ import annotations

import logging
import ssl
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class ConnectionPoolConfig:
    """Configuration for HTTP connection pooling.

    Attributes:
        limit: Total number of simultaneous connections (default: 100)
        limit_per_host: Max connections per host (default: 0 = unlimited)
        keepalive_timeout: Seconds to keep idle connections alive (default: 15)
        enable_cleanup_closed: Close timed out connections (default: True)
        ttl_dns_cache: DNS cache TTL in seconds (default: 10)
    """

    limit: int = 100
    limit_per_host: int = 0  # 0 means unlimited per host
    keepalive_timeout: float = 15.0
    enable_cleanup_closed: bool = True
    ttl_dns_cache: int = 10


# Default connection pool configuration
DEFAULT_POOL_CONFIG = ConnectionPoolConfig()


class AsyncSessionMixin:
    """Mixin providing async HTTP session management.

    Provides lazy initialization and proper cleanup for aiohttp sessions.
    Supports connection pooling through session reuse.

    Attributes:
        _session: The aiohttp ClientSession (lazy initialized)
        _ssl_verify: Whether to verify SSL certificates (default: True)
        _ssl_context: Optional custom SSL context for certificate configuration
        _pool_config: Connection pool configuration

    Note:
        Classes using this mixin should NOT define _session at class level.
        The session is stored as an instance attribute on first access.

    SSL Configuration:
        - Set _ssl_verify = False to disable SSL verification (not recommended)
        - Set _ssl_context to a custom ssl.SSLContext for custom certificates

    Connection Pooling:
        - Set _pool_config to a ConnectionPoolConfig instance for custom limits
        - Or override individual attributes: _pool_limit, _pool_limit_per_host
    """

    # Note: _session is intentionally NOT defined here as a class attribute.
    # It will be created as an instance attribute on first _get_session() call.
    # This prevents shared state across instances.

    # SSL configuration (can be overridden in subclasses)
    _ssl_verify: bool = True
    _ssl_context: Optional[ssl.SSLContext] = None

    # Connection pool configuration (can be overridden in subclasses)
    _pool_config: Optional[ConnectionPoolConfig] = None
    _pool_limit: int = 100
    _pool_limit_per_host: int = 0
    _pool_keepalive_timeout: float = 15.0

    def _get_ssl_context(self) -> ssl.SSLContext | bool:
        """Get SSL context for session creation.

        Returns:
            ssl.SSLContext if custom context is set,
            True for default SSL verification,
            False to disable SSL verification (not recommended)
        """
        if self._ssl_context is not None:
            return self._ssl_context
        return self._ssl_verify

    def _get_pool_config(self) -> ConnectionPoolConfig:
        """Get connection pool configuration.

        Returns:
            ConnectionPoolConfig with pool settings
        """
        if self._pool_config is not None:
            return self._pool_config

        # Build from individual attributes
        return ConnectionPoolConfig(
            limit=self._pool_limit,
            limit_per_host=self._pool_limit_per_host,
            keepalive_timeout=self._pool_keepalive_timeout,
        )

    async def _get_session(self) -> "aiohttp.ClientSession":
        """Get or create aiohttp session.

        Returns:
            Active ClientSession instance

        Note:
            Session is created lazily on first access.
            Subsequent calls return the same session for connection pooling.
        """
        import aiohttp

        # Use getattr to safely check instance attribute (may not exist yet)
        session = getattr(self, "_session", None)
        if session is None or session.closed:
            # Get configurations
            ssl_context = self._get_ssl_context()
            pool_config = self._get_pool_config()

            # Create connector with SSL and pool configuration
            connector = aiohttp.TCPConnector(
                ssl=ssl_context,
                limit=pool_config.limit,
                limit_per_host=pool_config.limit_per_host,
                keepalive_timeout=pool_config.keepalive_timeout,
                enable_cleanup_closed=pool_config.enable_cleanup_closed,
                ttl_dns_cache=pool_config.ttl_dns_cache,
            )
            self._session = aiohttp.ClientSession(connector=connector)
            logger.debug(
                f"{self.__class__.__name__}: HTTP session created "
                f"(pool_limit={pool_config.limit}, "
                f"per_host={pool_config.limit_per_host})"
            )
        return self._session

    async def _close_session(self) -> None:
        """Close the HTTP session if open.

        Safe to call multiple times. Does nothing if session is already closed.
        """
        session = getattr(self, "_session", None)
        if session is not None and not session.closed:
            await session.close()
            logger.debug(f"{self.__class__.__name__}: HTTP session closed")
        self._session = None

    @property
    def _session_active(self) -> bool:
        """Check if session is currently active."""
        session = getattr(self, "_session", None)
        return session is not None and not session.closed


class AsyncSessionWithTimeoutMixin(AsyncSessionMixin):
    """Session mixin with configurable timeout.

    Attributes:
        _session_timeout: Timeout in seconds for requests
    """

    _session_timeout: float = 30.0

    async def _get_session(self) -> "aiohttp.ClientSession":
        """Get or create session with timeout configuration."""
        import aiohttp

        session = getattr(self, "_session", None)
        if session is None or session.closed:
            timeout = aiohttp.ClientTimeout(total=self._session_timeout)

            # Get configurations from parent
            ssl_context = self._get_ssl_context()
            pool_config = self._get_pool_config()

            # Create connector with SSL and pool configuration
            connector = aiohttp.TCPConnector(
                ssl=ssl_context,
                limit=pool_config.limit,
                limit_per_host=pool_config.limit_per_host,
                keepalive_timeout=pool_config.keepalive_timeout,
                enable_cleanup_closed=pool_config.enable_cleanup_closed,
                ttl_dns_cache=pool_config.ttl_dns_cache,
            )
            self._session = aiohttp.ClientSession(
                timeout=timeout, connector=connector
            )
            logger.debug(
                f"{self.__class__.__name__}: HTTP session created "
                f"(timeout={self._session_timeout}s, "
                f"pool_limit={pool_config.limit})"
            )
        return self._session
