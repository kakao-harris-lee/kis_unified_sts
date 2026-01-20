"""Stream Consumer

Redis Stream Consumer Group 기반 메시지 처리.
"""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any

import redis

from shared.streaming.client import RedisClient
from shared.streaming.message import StreamMessage

logger = logging.getLogger(__name__)


class StreamConsumer(ABC):
    """Stream Consumer 베이스 클래스

    Consumer Group을 사용하여 안정적인 메시지 처리 보장.

    Usage:
        class MyConsumer(StreamConsumer):
            def process_message(self, message: StreamMessage) -> bool:
                # 메시지 처리
                return True

        consumer = MyConsumer("FEATURE_STREAM", "my_group")
        consumer.run()
    """

    HEARTBEAT_INTERVAL = 30.0

    def __init__(
        self,
        stream_name: str,
        group_name: str,
        consumer_name: str | None = None,
        component_name: str | None = None,
    ):
        """
        Args:
            stream_name: 소비할 Stream 이름
            group_name: Consumer Group 이름
            consumer_name: Consumer 이름 (기본: {group}_worker_1)
            component_name: 헬스체크용 컴포넌트 이름
        """
        self.stream = stream_name
        self.group = group_name
        self.consumer = consumer_name or f"{group_name}_worker_1"
        self.client = RedisClient.get_client()
        self.running = False

        self._component_name = component_name
        self._last_heartbeat_time = 0.0

        # 설정
        self._read_count = int(os.environ.get("REDIS_CONSUMER_READ_COUNT", "10"))
        self._block_ms = int(os.environ.get("REDIS_CONSUMER_BLOCK_MS", "1000"))

        self._ensure_group_exists()

    def _ensure_group_exists(self) -> None:
        """Consumer Group이 없으면 생성"""
        try:
            self.client.xgroup_create(
                self.stream,
                self.group,
                id="0",  # 처음부터 읽기
                mkstream=True,  # Stream이 없으면 생성
            )
            logger.info(f"Consumer Group 생성: {self.group} on {self.stream}")
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.debug(f"Consumer Group 이미 존재: {self.group}")
            else:
                raise

    def set_component_name(self, name: str) -> None:
        """헬스체크용 컴포넌트 이름 설정"""
        self._component_name = name

    def _publish_heartbeat(self) -> None:
        """헬스 모니터링용 heartbeat 발행"""
        if not self._component_name:
            return

        now = time.time()
        if now - self._last_heartbeat_time < self.HEARTBEAT_INTERVAL:
            return

        try:
            heartbeat_key = f"heartbeat:{self._component_name}"
            self.client.set(heartbeat_key, str(now), ex=120)
            self._last_heartbeat_time = now
            logger.debug(f"Heartbeat published: {heartbeat_key}")
        except Exception as e:
            logger.warning(f"Failed to publish heartbeat: {e}")

    @abstractmethod
    def process_message(self, message: StreamMessage) -> bool:
        """메시지 처리 로직 (서브클래스에서 구현)

        Returns:
            처리 성공 여부
        """
        pass

    def _read_pending(self) -> list[StreamMessage]:
        """미처리(Pending) 메시지 읽기"""
        messages = []
        pending = self.client.xreadgroup(
            self.group,
            self.consumer,
            {self.stream: "0"},  # 0 = pending 메시지
            count=self._read_count,
            block=None,
        )

        if pending:
            for stream_name, stream_msgs in pending:
                for msg_id, fields in stream_msgs:
                    if fields:  # 빈 필드는 이미 ACK된 메시지
                        messages.append(
                            StreamMessage.from_raw(stream_name, msg_id, fields)
                        )
        return messages

    def _read_new(self) -> list[StreamMessage]:
        """새 메시지 읽기"""
        messages = []
        result = self.client.xreadgroup(
            self.group,
            self.consumer,
            {self.stream: ">"},  # > = 새 메시지만
            count=self._read_count,
            block=self._block_ms,
        )

        if result:
            for stream_name, stream_msgs in result:
                for msg_id, fields in stream_msgs:
                    messages.append(
                        StreamMessage.from_raw(stream_name, msg_id, fields)
                    )
        return messages

    def _ack(self, message: StreamMessage) -> None:
        """메시지 처리 완료 확인"""
        self.client.xack(self.stream, self.group, message.id)
        logger.debug(f"ACK: {message.id}")

    def run(self) -> None:
        """메인 처리 루프"""
        self.running = True
        logger.info(f"Consumer 시작: {self.consumer} [{self.stream}]")

        # 초기 heartbeat
        self._publish_heartbeat()

        # 1. 미처리 메시지 먼저 처리
        pending = self._read_pending()
        if pending:
            logger.info(f"미처리 메시지 {len(pending)}개 발견, 처리 시작")
            for msg in pending:
                try:
                    if self.process_message(msg):
                        self._ack(msg)
                except Exception as e:
                    logger.error(f"메시지 처리 실패 (pending): {msg.id}, {e}")

        # 2. 새 메시지 계속 처리
        while self.running:
            try:
                self._publish_heartbeat()

                messages = self._read_new()
                for msg in messages:
                    try:
                        if self.process_message(msg):
                            self._ack(msg)
                    except Exception as e:
                        logger.error(f"메시지 처리 실패: {msg.id}, {e}")

            except KeyboardInterrupt:
                logger.info("Consumer 종료 요청")
                self.stop()
            except Exception as e:
                logger.error(f"Consumer 오류: {e}")

    def stop(self) -> None:
        """Consumer 종료"""
        self.running = False
        logger.info(f"Consumer 종료: {self.consumer}")


class MultiStreamConsumer(ABC):
    """여러 Stream을 동시에 소비하는 Consumer

    Strategy Manager처럼 여러 소스를 조합해야 할 때 사용.
    """

    def __init__(
        self,
        streams: dict[str, str],  # {stream_name: group_name}
        consumer_name: str | None = None,
    ):
        """
        Args:
            streams: {stream_name: group_name} 딕셔너리
            consumer_name: Consumer 이름
        """
        self.streams = streams
        self.consumer = consumer_name or "multi_consumer_1"
        self.client = RedisClient.get_client()
        self.running = False

        self._read_count = int(os.environ.get("REDIS_CONSUMER_READ_COUNT", "10"))
        self._block_ms = int(os.environ.get("REDIS_CONSUMER_BLOCK_MS", "1000"))

        for stream, group in streams.items():
            self._ensure_group_exists(stream, group)

    def _ensure_group_exists(self, stream: str, group: str) -> None:
        """Consumer Group이 없으면 생성"""
        try:
            self.client.xgroup_create(stream, group, id="0", mkstream=True)
            logger.info(f"Consumer Group 생성: {group} on {stream}")
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    @abstractmethod
    def process_message(self, message: StreamMessage) -> bool:
        """메시지 처리 로직"""
        pass

    def run(self) -> None:
        """메인 처리 루프"""
        self.running = True
        logger.info(f"MultiStreamConsumer 시작: {list(self.streams.keys())}")

        while self.running:
            try:
                stream_ids = {s: ">" for s in self.streams.keys()}
                result = self.client.xreadgroup(
                    list(self.streams.values())[0],  # 첫 번째 그룹 사용
                    self.consumer,
                    stream_ids,
                    count=self._read_count,
                    block=self._block_ms,
                )

                if result:
                    for stream_name, stream_msgs in result:
                        group = self.streams[stream_name]
                        for msg_id, fields in stream_msgs:
                            msg = StreamMessage.from_raw(stream_name, msg_id, fields)
                            try:
                                if self.process_message(msg):
                                    self.client.xack(stream_name, group, msg_id)
                            except Exception as e:
                                logger.error(f"메시지 처리 실패: {msg_id}, {e}")

            except KeyboardInterrupt:
                self.stop()
            except Exception as e:
                logger.error(f"MultiStreamConsumer 오류: {e}")

    def stop(self) -> None:
        """Consumer 종료"""
        self.running = False
        logger.info("MultiStreamConsumer 종료")
