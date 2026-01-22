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

from shared.resilience import CircuitBreaker

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
                    "failure_threshold": config.circuit_breakers.regime.failure_threshold,
                    "reset_timeout": config.circuit_breakers.regime.reset_timeout,
                    "half_open_max_calls": config.circuit_breakers.regime.half_open_max_calls,
                },
                PipelineStage.ENTRY: {
                    "failure_threshold": config.circuit_breakers.entry.failure_threshold,
                    "reset_timeout": config.circuit_breakers.entry.reset_timeout,
                    "half_open_max_calls": config.circuit_breakers.entry.half_open_max_calls,
                },
                PipelineStage.MONITORING: {
                    "failure_threshold": config.circuit_breakers.monitoring.failure_threshold,
                    "reset_timeout": config.circuit_breakers.monitoring.reset_timeout,
                    "half_open_max_calls": config.circuit_breakers.monitoring.half_open_max_calls,
                },
                PipelineStage.EXIT: {
                    "failure_threshold": config.circuit_breakers.exit.failure_threshold,
                    "reset_timeout": config.circuit_breakers.exit.reset_timeout,
                    "half_open_max_calls": config.circuit_breakers.exit.half_open_max_calls,
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
                PipelineStage.REGIME: {"failure_threshold": 3, "reset_timeout": 60.0, "half_open_max_calls": 2},
                PipelineStage.ENTRY: {"failure_threshold": 5, "reset_timeout": 30.0, "half_open_max_calls": 2},
                PipelineStage.MONITORING: {"failure_threshold": 5, "reset_timeout": 30.0, "half_open_max_calls": 2},
                PipelineStage.EXIT: {"failure_threshold": 2, "reset_timeout": 10.0, "half_open_max_calls": 1},
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
