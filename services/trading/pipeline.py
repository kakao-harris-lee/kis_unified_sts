"""Trading Pipeline

4-Stage 트레이딩 파이프라인.

Stages:
    1. Regime Detection - 시장 상태 감지
    2. Entry Signal - 진입 시그널 생성
    3. Position Monitoring - 포지션 모니터링
    4. Exit Signal - 청산 시그널 생성

Usage:
    pipeline = TradingPipeline(config, redis)
    await pipeline.start()
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Coroutine

if TYPE_CHECKING:
    from shared.config.schema import PipelineConfig

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    """파이프라인 스테이지"""

    REGIME = "regime"
    ENTRY = "entry"
    MONITORING = "monitoring"
    EXIT = "exit"


@dataclass
class StageMetrics:
    """스테이지별 메트릭"""

    executions: int = 0
    successes: int = 0
    failures: int = 0
    total_latency_ms: float = 0.0
    last_execution: datetime | None = None

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.executions if self.executions > 0 else 0.0

    @property
    def success_rate(self) -> float:
        return self.successes / self.executions * 100 if self.executions > 0 else 0.0


@dataclass
class PipelineMetrics:
    """파이프라인 전체 메트릭"""

    stages: dict[str, StageMetrics] = field(default_factory=dict)
    open_breakers: list[str] = field(default_factory=list)
    total_signals: int = 0
    total_orders: int = 0
    collected_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        for stage in PipelineStage:
            self.stages[stage.value] = StageMetrics()

    @property
    def total_errors(self) -> int:
        return sum(s.failures for s in self.stages.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "stages": {
                name: {
                    "executions": s.executions,
                    "successes": s.successes,
                    "failures": s.failures,
                    "avg_latency_ms": round(s.avg_latency_ms, 2),
                }
                for name, s in self.stages.items()
            },
            "open_breakers": self.open_breakers,
            "total_signals": self.total_signals,
            "total_orders": self.total_orders,
            "total_errors": self.total_errors,
            "collected_at": self.collected_at.isoformat(),
        }


class CircuitBreaker:
    """회로 차단기

    연속 실패 시 일시적으로 실행 중단.

    States:
        CLOSED: 정상 동작
        OPEN: 실패 임계값 초과, 실행 중단
        HALF_OPEN: 테스트 실행 허용

    Usage:
        breaker = CircuitBreaker("entry", fail_threshold=5)

        if breaker.is_open:
            # 실행 건너뛰기
            return

        try:
            result = await do_work()
            breaker.record_success()
        except Exception:
            breaker.record_failure()
    """

    class State(Enum):
        CLOSED = "closed"
        OPEN = "open"
        HALF_OPEN = "half_open"

    def __init__(
        self,
        name: str,
        fail_threshold: int = 5,
        reset_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        """
        Args:
            name: 회로 차단기 이름
            fail_threshold: 연속 실패 임계값
            reset_timeout: 차단 후 재시도까지 대기 시간 (초)
            half_open_max_calls: 반열림 상태에서 허용할 최대 호출 수
        """
        self.name = name
        self.fail_threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = self.State.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._half_open_calls = 0

    @property
    def state(self) -> State:
        return self._state

    @property
    def is_open(self) -> bool:
        """실행 가능 여부 (CLOSED 또는 HALF_OPEN 시 실행 가능)"""
        if self._state == self.State.CLOSED:
            return False

        if self._state == self.State.OPEN:
            # 타임아웃 경과 시 HALF_OPEN으로 전환
            if self._last_failure_time:
                elapsed = (datetime.now() - self._last_failure_time).total_seconds()
                if elapsed >= self.reset_timeout:
                    self._transition_to_half_open()
                    return False
            return True

        if self._state == self.State.HALF_OPEN:
            return self._half_open_calls >= self.half_open_max_calls

        return True

    def record_success(self):
        """성공 기록"""
        self._success_count += 1

        if self._state == self.State.HALF_OPEN:
            self._half_open_calls += 1
            # 충분한 성공 시 CLOSED로 전환
            if self._half_open_calls >= self.half_open_max_calls:
                self._transition_to_closed()
        else:
            self._failure_count = 0

    def record_failure(self):
        """실패 기록"""
        self._failure_count += 1
        self._last_failure_time = datetime.now()

        if self._state == self.State.HALF_OPEN:
            # 반열림 상태에서 실패 시 다시 OPEN
            self._transition_to_open()
        elif self._failure_count >= self.fail_threshold:
            self._transition_to_open()

    def _transition_to_open(self):
        """OPEN 상태로 전환"""
        self._state = self.State.OPEN
        logger.warning(f"Circuit breaker '{self.name}' OPENED (failures: {self._failure_count})")

    def _transition_to_half_open(self):
        """HALF_OPEN 상태로 전환"""
        self._state = self.State.HALF_OPEN
        self._half_open_calls = 0
        logger.info(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN")

    def _transition_to_closed(self):
        """CLOSED 상태로 전환"""
        self._state = self.State.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        logger.info(f"Circuit breaker '{self.name}' CLOSED")

    def reset(self):
        """강제 리셋"""
        self._transition_to_closed()

    def get_status(self) -> dict[str, Any]:
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "last_failure": (
                self._last_failure_time.isoformat() if self._last_failure_time else None
            ),
        }


async def with_retry(
    func: Callable[[], Coroutine[Any, Any, Any]],
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
) -> Any:
    """재시도 래퍼

    Args:
        func: 실행할 비동기 함수
        max_retries: 최대 재시도 횟수
        delay: 초기 대기 시간 (초)
        backoff: 대기 시간 증가 배율

    Returns:
        함수 실행 결과

    Raises:
        마지막 시도에서 발생한 예외
    """
    last_error = None
    current_delay = delay

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(
                    f"Retry {attempt + 1}/{max_retries} after {current_delay}s: {e}"
                )
                await asyncio.sleep(current_delay)
                current_delay *= backoff

    raise last_error


class TradingPipeline:
    """트레이딩 파이프라인

    4-Stage 파이프라인을 관리하고 실행.

    Usage:
        from shared.config.loader import ConfigLoader

        pipeline_config = ConfigLoader.load("pipeline.yaml")
        pipeline = TradingPipeline(
            config=pipeline_config,
            regime_handler=regime_detector.detect,
            entry_handler=entry_manager.scan,
            monitoring_handler=position_tracker.update,
            exit_handler=exit_manager.evaluate,
        )

        await pipeline.start()
    """

    def __init__(
        self,
        regime_handler: Callable | None = None,
        entry_handler: Callable | None = None,
        monitoring_handler: Callable | None = None,
        exit_handler: Callable | None = None,
        config: "PipelineConfig | None" = None,
    ):
        """
        Args:
            regime_handler: Regime 감지 핸들러
            entry_handler: Entry 시그널 핸들러
            monitoring_handler: Monitoring 핸들러
            exit_handler: Exit 시그널 핸들러
            config: 파이프라인 설정 (None이면 기본값 사용)
        """
        self.handlers = {
            PipelineStage.REGIME: regime_handler,
            PipelineStage.ENTRY: entry_handler,
            PipelineStage.MONITORING: monitoring_handler,
            PipelineStage.EXIT: exit_handler,
        }

        # 설정에서 인터벌 로드 (없으면 기본값)
        if config is not None:
            self.intervals = {
                PipelineStage.REGIME: config.intervals.regime,
                PipelineStage.ENTRY: config.intervals.entry,
                PipelineStage.MONITORING: config.intervals.monitoring,
                PipelineStage.EXIT: config.intervals.exit,
            }
            self._breaker_config = {
                PipelineStage.REGIME: {
                    "fail_threshold": config.circuit_breakers.regime.fail_threshold,
                    "reset_timeout": config.circuit_breakers.regime.reset_timeout,
                },
                PipelineStage.ENTRY: {
                    "fail_threshold": config.circuit_breakers.entry.fail_threshold,
                    "reset_timeout": config.circuit_breakers.entry.reset_timeout,
                },
                PipelineStage.MONITORING: {
                    "fail_threshold": config.circuit_breakers.monitoring.fail_threshold,
                    "reset_timeout": config.circuit_breakers.monitoring.reset_timeout,
                },
                PipelineStage.EXIT: {
                    "fail_threshold": config.circuit_breakers.exit.fail_threshold,
                    "reset_timeout": config.circuit_breakers.exit.reset_timeout,
                },
            }
            self._retry_config = {
                "max_retries": config.retry.max_retries,
                "delay": config.retry.delay,
            }
        else:
            # 기본값 (하위 호환성)
            self.intervals = {
                PipelineStage.REGIME: 300.0,
                PipelineStage.ENTRY: 1.0,
                PipelineStage.MONITORING: 0.1,
                PipelineStage.EXIT: 0.5,
            }
            self._breaker_config = {
                PipelineStage.REGIME: {"fail_threshold": 3, "reset_timeout": 60.0},
                PipelineStage.ENTRY: {"fail_threshold": 5, "reset_timeout": 30.0},
                PipelineStage.MONITORING: {"fail_threshold": 5, "reset_timeout": 30.0},
                PipelineStage.EXIT: {"fail_threshold": 2, "reset_timeout": 10.0},
            }
            self._retry_config = {"max_retries": 2, "delay": 1.0}

        # 회로 차단기 초기화
        self.breakers = {
            stage: CircuitBreaker(stage.value, **self._breaker_config[stage])
            for stage in PipelineStage
        }

        self.metrics = PipelineMetrics()
        self._is_running = False
        self._tasks: list[asyncio.Task] = []

    @property
    def is_running(self) -> bool:
        return self._is_running

    async def start(self):
        """파이프라인 시작"""
        if self._is_running:
            logger.warning("Pipeline already running")
            return

        self._is_running = True
        logger.info("Starting trading pipeline...")

        # 스테이지별 태스크 생성
        for stage in PipelineStage:
            if self.handlers[stage]:
                task = asyncio.create_task(
                    self._run_stage_loop(stage), name=f"{stage.value}_loop"
                )
                self._tasks.append(task)

        logger.info(f"Pipeline started with {len(self._tasks)} stages")

    async def stop(self):
        """파이프라인 중지"""
        if not self._is_running:
            return

        logger.info("Stopping trading pipeline...")
        self._is_running = False

        # 태스크 취소
        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        logger.info("Pipeline stopped")

    async def _run_stage_loop(self, stage: PipelineStage):
        """스테이지 실행 루프"""
        handler = self.handlers[stage]
        interval = self.intervals[stage]
        breaker = self.breakers[stage]
        metrics = self.metrics.stages[stage.value]

        logger.info(f"{stage.value} loop started (interval: {interval}s)")

        while self._is_running:
            # 회로 차단기 체크
            if breaker.is_open:
                logger.warning(f"{stage.value} circuit OPEN, waiting...")
                await asyncio.sleep(5)
                continue

            try:
                start_time = datetime.now()

                # 핸들러 실행
                result = await with_retry(
                    handler,
                    max_retries=self._retry_config["max_retries"],
                    delay=self._retry_config["delay"],
                )

                # 메트릭 업데이트
                latency = (datetime.now() - start_time).total_seconds() * 1000
                metrics.executions += 1
                metrics.successes += 1
                metrics.total_latency_ms += latency
                metrics.last_execution = datetime.now()

                breaker.record_success()

                if result:
                    logger.debug(f"{stage.value}: {result}")

            except Exception as e:
                metrics.executions += 1
                metrics.failures += 1
                breaker.record_failure()
                logger.error(f"{stage.value} failed: {e}")

            await asyncio.sleep(interval)

    def get_status(self) -> dict[str, Any]:
        """파이프라인 상태"""
        self.metrics.open_breakers = [
            name for name, breaker in self.breakers.items() if breaker.is_open
        ]
        self.metrics.collected_at = datetime.now()

        return {
            "is_running": self._is_running,
            "tasks": [t.get_name() for t in self._tasks if not t.done()],
            "circuit_breakers": {
                stage.value: self.breakers[stage].get_status()
                for stage in PipelineStage
            },
            "metrics": self.metrics.to_dict(),
        }

    def reset_breaker(self, stage: PipelineStage):
        """특정 스테이지 회로 차단기 리셋"""
        self.breakers[stage].reset()
