"""Stream 메시지

Redis Stream 메시지 래퍼.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StreamMessage:
    """Stream 메시지 래퍼 with distributed tracing

    Attributes:
        id: Redis message ID
        data: Parsed message data
        stream: Stream name
        correlation_id: Trace ID for distributed tracing
        parent_id: Parent message's correlation ID (for lineage)
        timestamp: Message creation timestamp
    """

    id: str
    data: dict[str, Any]
    stream: str
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_id: str | None = None
    timestamp: float = field(default_factory=time.time)

    @classmethod
    def from_raw(
        cls, stream: str, msg_id: str, fields: dict[str, str]
    ) -> StreamMessage:
        """Raw Redis 메시지 파싱"""
        parsed = {}

        # Tracing 메타데이터 추출
        correlation_id = fields.pop("_corr_id", None) or str(uuid.uuid4())[:8]
        parent_id = fields.pop("_parent_id", None) or None
        timestamp = float(fields.pop("_ts", 0)) or time.time()

        # JSON 필드 자동 파싱
        for k, v in fields.items():
            if k.endswith("_json"):
                try:
                    parsed[k.replace("_json", "")] = json.loads(v)
                except json.JSONDecodeError:
                    parsed[k] = v
            else:
                parsed[k] = v

        return cls(
            id=msg_id,
            data=parsed,
            stream=stream,
            correlation_id=correlation_id,
            parent_id=parent_id if parent_id else None,
            timestamp=timestamp,
        )

    def create_child_id(self) -> str:
        """자식 메시지용 correlation ID 생성"""
        return f"{self.correlation_id}-{str(uuid.uuid4())[:4]}"

    def get_trace_dict(self) -> dict[str, str]:
        """Downstream 발행용 tracing 메타데이터"""
        return {
            "_corr_id": self.correlation_id,
            "_parent_id": self.parent_id or "",
            "_ts": str(self.timestamp),
        }

    def __repr__(self) -> str:
        return (
            f"StreamMessage(id={self.id}, corr={self.correlation_id}, "
            f"stream={self.stream})"
        )
