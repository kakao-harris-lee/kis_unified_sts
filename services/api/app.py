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
import os
from contextlib import asynccontextmanager
from typing import Any

logger = logging.getLogger(__name__)

# Optional FastAPI import
try:
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    FastAPI = None

# Rate limiting (optional)
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    HAS_SLOWAPI = True
except ImportError:
    HAS_SLOWAPI = False
    Limiter = None


# Allowed HTTP methods - explicit list for security
CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]

# Allowed headers - explicit list for security
CORS_ALLOWED_HEADERS = [
    "Content-Type",
    "Authorization",
    "X-API-Key",
    "X-Request-ID",
    "Accept",
    "Accept-Language",
]


def _load_api_config() -> dict[str, Any]:
    """API 설정 파일 로드

    Returns:
        API 설정 딕셔너리
    """
    try:
        from shared.config.loader import ConfigLoader

        config = ConfigLoader.load("api.yaml")

        # 환경에 따른 오버라이드
        env = os.getenv("ENVIRONMENT", "production")
        if env == "development" and "development" in config:
            # 개발 환경 설정 병합
            dev_config = config["development"].get("api", {})
            api_config = config.get("api", {})
            _deep_merge(api_config, dev_config)
            return api_config

        return config.get("api", {})
    except Exception as e:
        logger.warning(f"Failed to load api.yaml, using defaults: {e}")
        return {}


def _deep_merge(base: dict, override: dict) -> dict:
    """딕셔너리 깊은 병합"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _get_cors_config(api_config: dict) -> dict:
    """CORS 설정 추출

    환경변수 ENVIRONMENT=development 면 개발 모드 CORS 적용.
    Always uses explicit methods and headers for security.
    Config can override defaults if needed.
    """
    env = os.getenv("ENVIRONMENT", "production")
    cors = api_config.get("cors", {})

    if env == "development":
        # 개발 환경: localhost 허용, with config override capability
        return {
            "allow_origins": cors.get("allowed_origins", [
                "http://localhost:3000",
                "http://localhost:8080",
            ]),
            "allow_credentials": True,
            "allow_methods": cors.get("allowed_methods", CORS_ALLOWED_METHODS),
            "allow_headers": cors.get("allowed_headers", CORS_ALLOWED_HEADERS),
        }

    # 프로덕션: 명시적 도메인만 허용
    return {
        "allow_origins": cors.get("allowed_origins", []),
        "allow_credentials": cors.get("allow_credentials", True),
        "allow_methods": cors.get("allowed_methods", CORS_ALLOWED_METHODS),
        "allow_headers": cors.get("allowed_headers", CORS_ALLOWED_HEADERS),
    }


def create_app(
    title: str | None = None,
    version: str | None = None,
    debug: bool | None = None,
) -> FastAPI:
    """FastAPI 앱 생성

    Args:
        title: API 제목 (config에서 로드)
        version: API 버전 (config에서 로드)
        debug: 디버그 모드 (환경변수 또는 config)

    Returns:
        FastAPI 앱 인스턴스
    """
    if not HAS_FASTAPI:
        raise ImportError(
            "FastAPI is required. Install with: pip install fastapi uvicorn"
        )

    # 설정 로드
    api_config = _load_api_config()

    # 파라미터 오버라이드 또는 config 사용
    _title = title or api_config.get("title", "KIS Unified Trading System")
    _version = version or api_config.get("version", "0.1.0")
    _debug = debug if debug is not None else api_config.get("debug", False)

    # 환경변수 오버라이드
    if os.getenv("DEBUG", "").lower() in ("true", "1", "yes"):
        _debug = True

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """앱 생명주기 관리"""
        from services.api.state import AppState

        # 상태 초기화
        app.state.app_state = AppState()
        app.state.debug = _debug

        logger.info(f"API server starting... (debug={_debug})")

        # HTTP 클라이언트 풀 설정 (선택)
        http_config = api_config.get("http_client", {})
        if http_config:
            try:
                import aiohttp

                connector = aiohttp.TCPConnector(
                    limit=http_config.get("pool_limit", 100),
                    limit_per_host=http_config.get("pool_limit_per_host", 30),
                    ttl_dns_cache=http_config.get("dns_cache_ttl", 300),
                )
                timeout = aiohttp.ClientTimeout(
                    total=http_config.get("timeout_total", 30),
                    connect=http_config.get("timeout_connect", 10),
                )
                app.state.http_client = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                )
                logger.info("HTTP client pool initialized")
            except ImportError:
                logger.debug("aiohttp not available, skipping HTTP client pool")

        yield

        # 정리
        logger.info("API server shutting down...")

        # HTTP 클라이언트 정리
        if hasattr(app.state, "http_client"):
            await app.state.http_client.close()

        # 오케스트레이터 정리
        orchestrator = await app.state.app_state.get_orchestrator()
        if orchestrator:
            await orchestrator.stop()

    app = FastAPI(
        title=_title,
        version=_version,
        description="KIS 통합 단기매매 시스템 API",
        docs_url="/docs" if _debug else None,
        redoc_url="/redoc" if _debug else None,
        lifespan=lifespan,
    )

    # CORS 설정
    cors_config = _get_cors_config(api_config)
    if cors_config.get("allow_origins"):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_config["allow_origins"],
            allow_credentials=cors_config["allow_credentials"],
            allow_methods=cors_config["allow_methods"],
            allow_headers=cors_config["allow_headers"],
        )
        logger.info(f"CORS enabled for origins: {cors_config['allow_origins']}")
    else:
        logger.warning("CORS not configured - no origins allowed")

    # Rate Limiting 설정
    rate_limit_config = api_config.get("rate_limits", {})
    if HAS_SLOWAPI and rate_limit_config.get("enabled", True):
        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=[rate_limit_config.get("default", "60/minute")],
        )
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

        # routes.py에 limiter 전달
        from services.api.routes import set_limiter
        set_limiter(limiter)

        logger.info(f"Rate limiting enabled: {rate_limit_config.get('default', '60/minute')}")
    else:
        logger.debug("Rate limiting disabled or slowapi not installed")

    # 예외 핸들러
    error_config = api_config.get("errors", {})
    expose_details = error_config.get("expose_details", False) or _debug

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=error_config.get("log_stacktrace", True))

        if expose_details:
            # 개발 모드: 상세 정보 포함
            return JSONResponse(
                status_code=500,
                content={"detail": str(exc), "type": type(exc).__name__},
            )
        else:
            # 프로덕션: 일반 메시지만
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )

    # 라우터 등록
    from services.api.routes import router

    app.include_router(router)

    return app


# =============================================================================
# 하위 호환성 - 전역 함수 (Deprecated)
# =============================================================================


def get_orchestrator():
    """현재 오케스트레이터 반환

    DEPRECATED: 대신 Depends(get_orchestrator_dep) 사용
    """
    import warnings
    warnings.warn(
        "get_orchestrator() is deprecated, use Depends(get_orchestrator_dep)",
        DeprecationWarning,
        stacklevel=2,
    )
    # 앱이 초기화되지 않은 경우 None 반환
    if app and hasattr(app.state, "app_state"):
        import asyncio
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(app.state.app_state.get_orchestrator())
    return None


def set_orchestrator(orchestrator):
    """오케스트레이터 설정

    DEPRECATED: 대신 AppState.set_orchestrator() 사용
    """
    import warnings
    warnings.warn(
        "set_orchestrator() is deprecated, use AppState.set_orchestrator()",
        DeprecationWarning,
        stacklevel=2,
    )
    if app and hasattr(app.state, "app_state"):
        import asyncio
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(app.state.app_state.set_orchestrator(orchestrator))
    return False


# 기본 앱 인스턴스 (uvicorn 직접 실행용)
app = None
if HAS_FASTAPI:
    app = create_app()
