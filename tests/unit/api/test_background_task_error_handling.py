"""
tests/unit/api/test_background_task_error_handling.py

Background task 에러 핸들링 테스트
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_background_task_updates_state_on_error():
    """Background task 실패 시 상태가 ERROR로 업데이트되어야 함"""
    from services.trading.orchestrator import TradingState
    from services.api.routes import _create_session_runner

    mock_orchestrator = MagicMock()
    mock_orchestrator.run_session = AsyncMock(side_effect=RuntimeError("Connection lost"))
    mock_orchestrator.state = TradingState.RUNNING
    mock_orchestrator.last_error = None
    mock_orchestrator.last_error_time = None

    runner = _create_session_runner(mock_orchestrator)
    await runner()

    assert mock_orchestrator.state == TradingState.ERROR
    assert mock_orchestrator.last_error == "Connection lost"
    assert mock_orchestrator.last_error_time is not None


@pytest.mark.asyncio
async def test_background_task_sends_notification_on_error():
    """Background task 실패 시 알림 전송"""
    from services.trading.orchestrator import TradingState
    from services.api.routes import _create_session_runner

    mock_notify = AsyncMock()
    mock_orchestrator = MagicMock()
    mock_orchestrator.run_session = AsyncMock(side_effect=RuntimeError("Error"))
    mock_orchestrator.state = TradingState.RUNNING
    mock_orchestrator._notify = mock_notify

    runner = _create_session_runner(mock_orchestrator)
    await runner()

    mock_notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_background_task_handles_notification_failure():
    """알림 전송 실패해도 상태는 업데이트되어야 함"""
    from services.trading.orchestrator import TradingState
    from services.api.routes import _create_session_runner

    mock_orchestrator = MagicMock()
    mock_orchestrator.run_session = AsyncMock(side_effect=RuntimeError("Error"))
    mock_orchestrator.state = TradingState.RUNNING
    mock_orchestrator._notify = AsyncMock(side_effect=Exception("Notification failed"))

    runner = _create_session_runner(mock_orchestrator)
    await runner()  # Should not raise

    assert mock_orchestrator.state == TradingState.ERROR


@pytest.mark.asyncio
async def test_background_task_success_no_state_change():
    """Background task 성공 시 상태 유지"""
    from services.trading.orchestrator import TradingState
    from services.api.routes import _create_session_runner

    mock_orchestrator = MagicMock()
    mock_orchestrator.run_session = AsyncMock()  # Success
    mock_orchestrator.state = TradingState.RUNNING

    runner = _create_session_runner(mock_orchestrator)
    await runner()

    # State should NOT be changed to ERROR
    assert mock_orchestrator.state == TradingState.RUNNING
