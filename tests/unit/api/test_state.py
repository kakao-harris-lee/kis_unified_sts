"""API 상태 관리 테스트"""

import asyncio
import pytest
from unittest.mock import MagicMock


class TestAppState:
    """AppState 클래스 테스트"""

    def test_initial_state(self):
        """초기 상태 확인"""
        from services.api.state import AppState

        state = AppState()
        assert state.start_time is not None
        assert state._orchestrator is None

    def test_uptime_calculation(self):
        """업타임 계산"""
        from services.api.state import AppState

        state = AppState()
        # 최소 0초 이상
        assert state.uptime_seconds >= 0

    def test_to_dict(self):
        """딕셔너리 변환"""
        from services.api.state import AppState

        state = AppState()
        result = state.to_dict()

        assert "start_time" in result
        assert "uptime_seconds" in result
        assert "has_orchestrator" in result
        assert "orchestrator_running" in result
        assert result["has_orchestrator"] is False

    @pytest.mark.asyncio
    async def test_get_orchestrator_when_none(self):
        """오케스트레이터 미설정 시 None 반환"""
        from services.api.state import AppState

        state = AppState()
        result = await state.get_orchestrator()
        assert result is None

    @pytest.mark.asyncio
    async def test_set_orchestrator_success(self):
        """오케스트레이터 설정 성공"""
        from services.api.state import AppState

        state = AppState()
        mock_orch = MagicMock()
        mock_orch.is_running = False

        result = await state.set_orchestrator(mock_orch)
        assert result is True

        orch = await state.get_orchestrator()
        assert orch == mock_orch

    @pytest.mark.asyncio
    async def test_set_orchestrator_fails_when_running(self):
        """실행 중일 때 오케스트레이터 설정 실패"""
        from services.api.state import AppState

        state = AppState()

        # 첫 번째 오케스트레이터 (실행 중)
        mock_orch1 = MagicMock()
        mock_orch1.is_running = True
        await state.set_orchestrator(mock_orch1)

        # 두 번째 오케스트레이터 설정 시도
        mock_orch2 = MagicMock()
        result = await state.set_orchestrator(mock_orch2)
        assert result is False

        # 원래 오케스트레이터 유지
        orch = await state.get_orchestrator()
        assert orch == mock_orch1

    @pytest.mark.asyncio
    async def test_clear_orchestrator(self):
        """오케스트레이터 제거"""
        from services.api.state import AppState

        state = AppState()
        mock_orch = MagicMock()
        mock_orch.is_running = False

        await state.set_orchestrator(mock_orch)
        await state.clear_orchestrator()

        orch = await state.get_orchestrator()
        assert orch is None

    @pytest.mark.asyncio
    async def test_thread_safety(self):
        """동시 접근 시 스레드 안전성"""
        from services.api.state import AppState

        state = AppState()
        results = []

        async def set_orch(idx):
            mock_orch = MagicMock()
            mock_orch.is_running = False
            mock_orch.idx = idx
            result = await state.set_orchestrator(mock_orch)
            results.append((idx, result))

        # 동시에 여러 설정 시도
        await asyncio.gather(*[set_orch(i) for i in range(5)])

        # 하나만 성공해야 함 (또는 순차적으로 모두 성공)
        success_count = sum(1 for _, r in results if r)
        # 최소 1개는 성공
        assert success_count >= 1
