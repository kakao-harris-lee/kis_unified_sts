"""Redis 클라이언트

Redis 연결 관리 싱글톤.
"""

from __future__ import annotations

import logging
import os
import ssl
import threading
from typing import Optional

import redis

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis 연결 관리 싱글톤

    Usage:
        client = RedisClient.get_client()
        client.ping()
    """

    _instance: Optional[redis.Redis] = None
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def _create_client(cls) -> redis.Redis:
        """Create a new Redis client from environment variables."""
        host = os.environ.get("REDIS_HOST", "localhost")
        port = int(os.environ.get("REDIS_PORT", "6379"))
        password = os.environ.get("REDIS_PASSWORD", None) or None
        db = int(os.environ.get("REDIS_DB", "1"))

        # TLS configuration
        tls_enabled = os.environ.get("REDIS_TLS_ENABLED", "false").lower() == "true"

        # Base connection parameters
        connection_params = {
            "host": host,
            "port": port,
            "password": password,
            "db": db,
            "decode_responses": True,
            "socket_connect_timeout": 5,
            "socket_timeout": 5,
        }

        # Add TLS parameters if enabled
        if tls_enabled:
            connection_params["ssl"] = True

            # Certificate requirements (default: required)
            cert_reqs = os.environ.get("REDIS_TLS_CERT_REQS", "required").lower()
            if cert_reqs == "none":
                connection_params["ssl_cert_reqs"] = ssl.CERT_NONE
            elif cert_reqs == "optional":
                connection_params["ssl_cert_reqs"] = ssl.CERT_OPTIONAL
            else:  # "required" or any other value
                connection_params["ssl_cert_reqs"] = ssl.CERT_REQUIRED

            # CA certificate bundle path
            ca_certs = os.environ.get("REDIS_TLS_CA_CERTS", None)
            if ca_certs:
                connection_params["ssl_ca_certs"] = ca_certs

            logger.debug(f"Redis TLS 활성화: {host}:{port} (cert_reqs={cert_reqs})")
        else:
            logger.debug(f"Redis TLS 비활성화: {host}:{port}")

        client = redis.Redis(**connection_params)
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
                try:
                    cls._instance.close()
                except Exception:
                    pass
                cls._instance = None

        with cls._lock:
            # Double-check after acquiring lock
            if cls._instance is not None:
                try:
                    cls._instance.ping()
                    return cls._instance
                except (redis.ConnectionError, redis.TimeoutError, OSError):
                    try:
                        cls._instance.close()
                    except Exception:
                        pass
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
