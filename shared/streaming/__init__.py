"""Streaming 모듈

Redis Streams 클라이언트.

Usage:
    from shared.streaming import StreamPublisher, StreamConsumer, StreamMessage

    publisher = StreamPublisher("PREDICTION_STREAM")
    publisher.publish({"symbol": "101V3000", "up_prob": 0.85})
"""

from shared.streaming.client import RedisClient
from shared.streaming.consumer import MultiStreamConsumer, StreamConsumer
from shared.streaming.message import StreamMessage
from shared.streaming.publisher import StreamPublisher

__all__ = [
    "RedisClient",
    "StreamConsumer",
    "MultiStreamConsumer",
    "StreamPublisher",
    "StreamMessage",
]
