"""API 상태 관리 모듈

전역 상태를 대체하는 스레드-세이프 상태 관리.

Usage:
    from services.api.state import AppState, get_app_state

    # FastAPI 앱에서
    app.state.app_state = AppState()

    # 라우트에서
    @router.get("/status")
    async def get_status(state: AppState = Depends(get_app_state)):
        orchestrator = await state.get_orchestrator()
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from services.trading.orchestrator import TradingOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class AppState:
    """애플리케이션 상태 관리

    전역 변수 대신 사용하는 스레드-세이프 상태 컨테이너.
    FastAPI의 app.state에 저장하여 요청 간 공유.

    Attributes:
        start_time: 서버 시작 시간
    """

    start_time: datetime = field(default_factory=datetime.now)
    _orchestrator: "TradingOrchestrator | None" = field(default=None, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def get_orchestrator(self) -> "TradingOrchestrator | None":
        """현재 오케스트레이터 반환

        스레드-세이프하게 오케스트레이터 조회.

        Returns:
            TradingOrchestrator 또는 None
        """
        async with self._lock:
            return self._orchestrator

    async def set_orchestrator(
        self, orchestrator: "TradingOrchestrator"
    ) -> bool:
        """오케스트레이터 설정

        이미 실행 중인 오케스트레이터가 있으면 실패.

        Args:
            orchestrator: 설정할 오케스트레이터

        Returns:
            성공 여부 (False면 이미 실행 중)
        """
        async with self._lock:
            if self._orchestrator is not None and self._orchestrator.is_running:
                logger.warning("Cannot set orchestrator: already running")
                return False
            self._orchestrator = orchestrator
            logger.info("Orchestrator set successfully")
            return True

    async def clear_orchestrator(self) -> None:
        """오케스트레이터 제거"""
        async with self._lock:
            self._orchestrator = None
            logger.info("Orchestrator cleared")

    @property
    def uptime_seconds(self) -> float:
        """서버 가동 시간 (초)"""
        return (datetime.now() - self.start_time).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """상태를 딕셔너리로 변환"""
        return {
            "start_time": self.start_time.isoformat(),
            "uptime_seconds": round(self.uptime_seconds, 2),
            "has_orchestrator": self._orchestrator is not None,
            "orchestrator_running": (
                self._orchestrator.is_running
                if self._orchestrator
                else False
            ),
        }


# =============================================================================
# FastAPI 의존성
# =============================================================================

try:
    from fastapi import Request

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


if HAS_FASTAPI:

    async def get_app_state(request: Request) -> AppState:
        """FastAPI 의존성: AppState 반환

        Usage:
            @router.get("/status")
            async def status(state: AppState = Depends(get_app_state)):
                ...
        """
        return request.app.state.app_state

    async def get_orchestrator_dep(request: Request):
        """FastAPI 의존성: Orchestrator 반환

        Usage:
            @router.get("/trading/status")
            async def status(orch = Depends(get_orchestrator_dep)):
                if orch is None:
                    raise HTTPException(404, "No trading session")
        """
        state: AppState = request.app.state.app_state
        return await state.get_orchestrator()
