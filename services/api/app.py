"""FastAPI 애플리케이션

REST API Gateway.

Endpoints:
    /health - 헬스 체크
    /api/v1/trading - 트레이딩 관리
    /api/v1/backtest - 백테스트 실행
    /api/v1/strategies - 전략 관리
    /metrics - Prometheus 메트릭

Usage:
    from services.api import create_app

    app = create_app()

    # CLI
    uvicorn services.api.app:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Optional FastAPI import
try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    FastAPI = None


# Global state
_orchestrator = None
_start_time = None


def get_orchestrator():
    """현재 오케스트레이터 반환"""
    return _orchestrator


def set_orchestrator(orchestrator):
    """오케스트레이터 설정"""
    global _orchestrator
    _orchestrator = orchestrator


def create_app(
    title: str = "KIS Unified Trading System",
    version: str = "0.1.0",
    debug: bool = False,
) -> FastAPI:
    """FastAPI 앱 생성

    Args:
        title: API 제목
        version: API 버전
        debug: 디버그 모드

    Returns:
        FastAPI 앱 인스턴스
    """
    if not HAS_FASTAPI:
        raise ImportError(
            "FastAPI is required. Install with: pip install fastapi uvicorn"
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """앱 생명주기 관리"""
        global _start_time
        _start_time = datetime.now()
        logger.info("API server starting...")
        yield
        logger.info("API server shutting down...")
        if _orchestrator:
            await _orchestrator.stop()

    app = FastAPI(
        title=title,
        version=version,
        description="KIS 통합 단기매매 시스템 API",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS 설정
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 예외 핸들러
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": type(exc).__name__},
        )

    # 라우터 등록
    from services.api.routes import router

    app.include_router(router)

    return app


# 기본 앱 인스턴스 (uvicorn 직접 실행용)
app = None
if HAS_FASTAPI:
    app = create_app()
