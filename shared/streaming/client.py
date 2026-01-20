"""Redis 클라이언트

Redis 연결 관리 싱글톤.
"""

from __future__ import annotations

import logging
import os
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

    @classmethod
    def get_client(cls) -> redis.Redis:
        """Redis 클라이언트 인스턴스 반환"""
        if cls._instance is None:
            host = os.environ.get("REDIS_HOST", "localhost")
            port = int(os.environ.get("REDIS_PORT", "6379"))
            password = os.environ.get("REDIS_PASSWORD", None)
            db = int(os.environ.get("REDIS_DB", "0"))

            cls._instance = redis.Redis(
                host=host,
                port=port,
                password=password,
                db=db,
                decode_responses=True,
            )

            # 연결 테스트
            cls._instance.ping()
            logger.info(f"Redis 연결 성공: {host}:{port}")

        return cls._instance

    @classmethod
    def close(cls) -> None:
        """연결 종료"""
        if cls._instance:
            cls._instance.close()
            cls._instance = None
            logger.info("Redis 연결 종료")

    @classmethod
    def reset(cls) -> None:
        """인스턴스 리셋 (테스트용)"""
        cls._instance = None
