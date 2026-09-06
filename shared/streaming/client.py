"""Redis 클라이언트

Redis 연결 관리 싱글톤.
"""

from __future__ import annotations

import contextlib
import logging
import os
import threading
from typing import Any

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from shared.config.tls import build_redis_tls_params

logger = logging.getLogger(__name__)

# Fail-fast connect defaults (operator decision 2026-09-06): redis-py 7.x's
# built-in `redis.Redis(...)` default is `Retry(ExponentialWithJitterBackoff(base=1,
# cap=10), retries=3)`, applied to connection errors (not just command errors).
# Against an unreachable Redis, that makes a single failed acquisition take
# ~9.6s — and `shared/strategy/gates/adapter_helper.py::acquire_infra_clients()`
# calls this on the strategy hot path claiming "hot-path safe". These env vars
# make the connect-time behavior config-driven; defaults keep the previously
# hardcoded socket_timeout unchanged but cut connect_timeout and disable
# connection retries so a down Redis fails fast instead of stalling.
_DEFAULT_CONNECT_TIMEOUT_SECONDS = 1.0
_DEFAULT_SOCKET_TIMEOUT_SECONDS = 5.0
_DEFAULT_CONNECT_RETRIES = 0


def _env_float(name: str, default: float) -> float:
    """Read a float env var, raising ValueError with a clear message if set but invalid."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(
            f"Invalid {name}={raw!r}: expected a number of seconds"
        ) from exc


def _env_int(name: str, default: int) -> int:
    """Read an int env var, raising ValueError with a clear message if set but invalid."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid {name}={raw!r}: expected an integer") from exc


class RedisClient:
    """Redis 연결 관리 싱글톤

    Usage:
        client = RedisClient.get_client()
        client.ping()
    """

    _instance: redis.Redis | None = None
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def _create_client(cls) -> redis.Redis:
        """Create a new Redis client from environment variables."""
        host = os.environ.get("REDIS_HOST", "localhost")
        port = int(os.environ.get("REDIS_PORT", "6379"))
        password = os.environ.get("REDIS_PASSWORD", None) or None
        db = int(os.environ.get("REDIS_DB", "1"))

        connect_timeout = _env_float(
            "REDIS_CONNECT_TIMEOUT_SECONDS", _DEFAULT_CONNECT_TIMEOUT_SECONDS
        )
        socket_timeout = _env_float(
            "REDIS_SOCKET_TIMEOUT_SECONDS", _DEFAULT_SOCKET_TIMEOUT_SECONDS
        )
        connect_retries = _env_int("REDIS_CONNECT_RETRIES", _DEFAULT_CONNECT_RETRIES)

        # Base connection parameters. `retry` overrides redis-py's own default
        # (3 retries with exponential-jitter backoff) so a down Redis fails
        # fast; NoBackoff + 0 retries by default means exactly one connect
        # attempt bounded by socket_connect_timeout.
        connection_params: dict[str, Any] = {
            "host": host,
            "port": port,
            "password": password,
            "db": db,
            "decode_responses": True,
            "socket_connect_timeout": connect_timeout,
            "socket_timeout": socket_timeout,
            "retry": Retry(NoBackoff(), connect_retries),
        }

        # Add TLS parameters if enabled
        tls_params = build_redis_tls_params()
        connection_params.update(tls_params)

        if tls_params:
            logger.debug(f"Redis TLS enabled: {host}:{port}")
        else:
            logger.debug(f"Redis TLS disabled: {host}:{port}")

        client: redis.Redis = redis.Redis(**connection_params)
        client.ping()
        logger.debug(f"Redis 연결 성공: {host}:{port}")
        return client

    @classmethod
    def get_client(cls) -> redis.Redis:
        """Redis 클라이언트 인스턴스 반환 (자동 재연결)"""
        if cls._instance is not None:
            try:
                cls._instance.ping()
                return cls._instance
            except (redis.ConnectionError, redis.TimeoutError, OSError):
                logger.warning("Redis 연결 끊김, 재연결 시도...")
                with contextlib.suppress(Exception):
                    cls._instance.close()
                cls._instance = None

        with cls._lock:
            # Double-check after acquiring lock
            if cls._instance is not None:
                try:
                    cls._instance.ping()
                    return cls._instance
                except (redis.ConnectionError, redis.TimeoutError, OSError):
                    with contextlib.suppress(Exception):
                        cls._instance.close()
                    cls._instance = None

            cls._instance = cls._create_client()
            return cls._instance

    @classmethod
    def close(cls) -> None:
        """연결 종료"""
        with cls._lock:
            if cls._instance:
                cls._instance.close()
                cls._instance = None
                logger.info("Redis 연결 종료")

    @classmethod
    def reset(cls) -> None:
        """인스턴스 리셋 (테스트용)"""
        cls._instance = None
