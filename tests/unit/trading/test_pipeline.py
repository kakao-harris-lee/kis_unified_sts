"""Trading Pipeline 테스트"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch


class TestCircuitBreaker:
    """CircuitBreaker 클래스 테스트"""

    def test_initial_state_is_closed(self):
        """초기 상태는 CLOSED"""
        from shared.resilience import CircuitBreaker, CircuitState

        breaker = CircuitBreaker("test")
        assert breaker.state == CircuitState.CLOSED
        assert not breaker.is_open

    def test_opens_after_threshold_failures(self):
        """임계값 초과 실패 시 OPEN"""
        from shared.resilience import CircuitBreaker, CircuitState

        breaker = CircuitBreaker("test", failure_threshold=3)

        for _ in range(3):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open

    def test_success_resets_failure_count(self):
        """성공 시 실패 카운트 리셋"""
        from shared.resilience import CircuitBreaker, CircuitState

        breaker = CircuitBreaker("test", failure_threshold=3)

        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()

        assert breaker._failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    def test_reset_forces_closed(self):
        """reset() 호출 시 강제 CLOSED"""
        from shared.resilience import CircuitBreaker, CircuitState

        breaker = CircuitBreaker("test", failure_threshold=2)
        breaker.record_failure()
        breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

        breaker.reset()
        assert breaker.state == CircuitState.CLOSED

    def test_get_status(self):
        """상태 딕셔너리 반환"""
        from shared.resilience import CircuitBreaker

        breaker = CircuitBreaker("test")
        status = breaker.get_status()

        assert "state" in status
        assert "failure_count" in status
        assert status["state"] == "closed"


class TestPipelineMetrics:
    """PipelineMetrics 클래스 테스트"""

    def test_initial_metrics(self):
        """초기 메트릭 값"""
        from services.trading.pipeline import PipelineMetrics, PipelineStage

        metrics = PipelineMetrics()

        assert metrics.total_signals == 0
        assert metrics.total_orders == 0
        assert len(metrics.stages) == len(PipelineStage)

    def test_to_dict(self):
        """딕셔너리 변환"""
        from services.trading.pipeline import PipelineMetrics

        metrics = PipelineMetrics()
        result = metrics.to_dict()

        assert "stages" in result
        assert "total_signals" in result
        assert "collected_at" in result


class TestStageMetrics:
    """StageMetrics 클래스 테스트"""

    def test_avg_latency_zero_executions(self):
        """실행 없을 때 평균 지연 0"""
        from services.trading.pipeline import StageMetrics

        metrics = StageMetrics()
        assert metrics.avg_latency_ms == 0.0

    def test_avg_latency_calculation(self):
        """평균 지연 계산"""
        from services.trading.pipeline import StageMetrics

        metrics = StageMetrics(executions=10, total_latency_ms=100)
        assert metrics.avg_latency_ms == 10.0

    def test_success_rate(self):
        """성공률 계산"""
        from services.trading.pipeline import StageMetrics

        metrics = StageMetrics(executions=10, successes=7)
        assert metrics.success_rate == 70.0


class TestTradingPipeline:
    """TradingPipeline 클래스 테스트"""

    def test_init_with_default_config(self):
        """기본 설정으로 초기화"""
        from services.trading.pipeline import TradingPipeline, PipelineStage

        pipeline = TradingPipeline()

        # 기본 인터벌 확인
        assert pipeline.intervals[PipelineStage.REGIME] == 300.0
        assert pipeline.intervals[PipelineStage.ENTRY] == 1.0
        assert pipeline._retry_config["max_retries"] == 2

    def test_init_with_custom_config(self):
        """커스텀 설정으로 초기화"""
        from services.trading.pipeline import TradingPipeline, PipelineStage

        # Mock config
        mock_config = MagicMock()
        mock_config.intervals.regime = 600.0
        mock_config.intervals.entry = 2.0
        mock_config.intervals.monitoring = 0.2
        mock_config.intervals.exit = 1.0
        mock_config.circuit_breakers.regime.failure_threshold = 5
        mock_config.circuit_breakers.regime.reset_timeout = 120.0
        mock_config.circuit_breakers.regime.half_open_max_calls = 2
        mock_config.circuit_breakers.entry.failure_threshold = 10
        mock_config.circuit_breakers.entry.reset_timeout = 60.0
        mock_config.circuit_breakers.entry.half_open_max_calls = 2
        mock_config.circuit_breakers.monitoring.failure_threshold = 10
        mock_config.circuit_breakers.monitoring.reset_timeout = 60.0
        mock_config.circuit_breakers.monitoring.half_open_max_calls = 2
        mock_config.circuit_breakers.exit.failure_threshold = 3
        mock_config.circuit_breakers.exit.reset_timeout = 15.0
        mock_config.circuit_breakers.exit.half_open_max_calls = 1
        mock_config.retry.max_retries = 5
        mock_config.retry.delay = 2.0

        pipeline = TradingPipeline(config=mock_config)

        assert pipeline.intervals[PipelineStage.REGIME] == 600.0
        assert pipeline.intervals[PipelineStage.ENTRY] == 2.0
        assert pipeline._retry_config["max_retries"] == 5

    def test_is_running_property(self):
        """is_running 프로퍼티"""
        from services.trading.pipeline import TradingPipeline

        pipeline = TradingPipeline()
        assert pipeline.is_running is False

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        """시작 및 중지"""
        from services.trading.pipeline import TradingPipeline

        async def dummy_handler():
            return None

        pipeline = TradingPipeline(
            regime_handler=dummy_handler,
        )

        await pipeline.start()
        assert pipeline.is_running is True

        await pipeline.stop()
        assert pipeline.is_running is False

    def test_get_status(self):
        """상태 조회"""
        from services.trading.pipeline import TradingPipeline

        pipeline = TradingPipeline()
        status = pipeline.get_status()

        assert "is_running" in status
        assert "circuit_breakers" in status
        assert "metrics" in status


class TestWithRetry:
    """with_retry 함수 테스트"""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        """첫 시도에 성공"""
        from services.trading.pipeline import with_retry

        async def success_func():
            return "ok"

        result = await with_retry(success_func, max_retries=3)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_success_after_retry(self):
        """재시도 후 성공"""
        from services.trading.pipeline import with_retry

        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "ok"

        result = await with_retry(flaky_func, max_retries=3, delay=0.01)
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        """최대 재시도 후 예외 발생"""
        from services.trading.pipeline import with_retry

        async def always_fail():
            raise ValueError("always fails")

        with pytest.raises(ValueError, match="always fails"):
            await with_retry(always_fail, max_retries=2, delay=0.01)
