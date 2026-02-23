"""Stream Publisher

Redis Stream에 데이터 발행.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any

from shared.streaming.client import RedisClient
from shared.streaming.message import StreamMessage

logger = logging.getLogger(__name__)


def _get_correlation_id() -> str:
    """현재 correlation ID 반환 (없으면 새로 생성)"""
    return str(uuid.uuid4())[:8]


class StreamPublisher:
    """Stream에 데이터 발행

    Usage:
        publisher = StreamPublisher("FEATURE_STREAM")

        # Simple publish (auto-generates correlation ID)
        publisher.publish({"symbol": "101V3000", ...})

        # Publish with parent tracing (for pipeline)
        publisher.publish(data, parent_message=input_msg)
    """

    def __init__(self, stream_name: str, maxlen: int | None = None):
        """
        Args:
            stream_name: 발행할 Stream 이름
            maxlen: Stream 최대 길이 (기본: 10000)
        """
        self.stream = stream_name
        self.maxlen = maxlen or int(os.environ.get("REDIS_STREAM_MAXLEN", "10000"))
        self.client = RedisClient.get_client()
        self._publish_count = 0

    def publish(
        self,
        data: dict[str, Any],
        correlation_id: str | None = None,
        parent_message: StreamMessage | None = None,
    ) -> str:
        """데이터를 Stream에 추가

        Args:
            data: 메시지 데이터
            correlation_id: Correlation ID (없으면 자동 생성)
            parent_message: 부모 메시지 (lineage tracking용)

        Returns:
            Redis message ID
        """
        processed = {}

        # Tracing 메타데이터 추가
        if parent_message:
            processed["_corr_id"] = parent_message.correlation_id
            processed["_parent_id"] = parent_message.id
        else:
            processed["_corr_id"] = correlation_id or _get_correlation_id()
            processed["_parent_id"] = ""

        processed["_ts"] = str(time.time())

        # 딕셔너리/리스트는 JSON으로 변환
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                processed[f"{k}_json"] = json.dumps(v)
            else:
                processed[k] = str(v) if v is not None else ""

        msg_id = self.client.xadd(self.stream, processed, maxlen=self.maxlen)
        self.client.expire(self.stream, 86400)  # 24h TTL, renewed on each publish

        self._publish_count += 1
        logger.debug(
            f"Published to {self.stream}: {msg_id} [corr={processed['_corr_id']}]"
        )
        return msg_id

    def get_stats(self) -> dict[str, Any]:
        """Publisher 통계"""
        return {
            "stream": self.stream,
            "publish_count": self._publish_count,
            "maxlen": self.maxlen,
        }
