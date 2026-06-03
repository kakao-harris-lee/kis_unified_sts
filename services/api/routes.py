"""API 라우터

REST API 엔드포인트 정의.

Endpoints:
    GET  /health              - 헬스 체크
    GET  /api/v1/status       - 시스템 상태

    POST /api/v1/trading/start    - 거래 시작 (인증 필요)
    POST /api/v1/trading/stop     - 거래 종료 (인증 필요)
    POST /api/v1/trading/pause    - 일시 정지 (인증 필요)
    POST /api/v1/trading/resume   - 재개 (인증 필요)
    GET  /api/v1/trading/status   - 거래 상태

    GET  /api/v1/strategies       - 전략 목록
    GET  /api/v1/strategies/{name} - 전략 상세

    POST /api/v1/backtest/run     - 백테스트 실행 (인증 필요)
    GET  /api/v1/backtest/results - 백테스트 결과

    GET  /metrics                 - Prometheus 메트릭 (조건부 인증: METRICS_REQUIRE_AUTH)
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any, Callable

from shared.api.error_sanitizer import sanitize_error_message
from shared.exceptions import (
    ConfigurationError,
    InfrastructureError,
    NetworkError,
    TradingSystemError,
)

logger = logging.getLogger(__name__)

# Optional imports
try:
    from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Request
    from fastapi.responses import Response
    from pydantic import BaseModel, Field, field_validator

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# Rate limiting (optional)
try:
    from slowapi import Limiter

    HAS_SLOWAPI = True
except ImportError:
    HAS_SLOWAPI = False
    Limiter = None  # type: ignore

if TYPE_CHECKING:
    from slowapi import Limiter


# =============================================================================
# Rate Limiter Setup
# =============================================================================

# Rate limiter singleton (app.py에서 설정)
_limiter: "Limiter | None" = None


def get_limiter() -> "Limiter | None":
    """Rate limiter 가져오기"""
    return _limiter


def set_limiter(limiter: "Limiter"):
    """Rate limiter 설정 (app.py에서 호출)"""
    global _limiter
    _limiter = limiter


def _create_rate_limit_dependency(limit_string: str):
    """Rate limit 의존성 생성

    Usage:
        @router.get("/api/v1/resource")
        async def handler(
            request: Request,
            _rate_limit: Annotated[None, Depends(_create_rate_limit_dependency("10/minute"))] = None,
        ):
            ...
    """
    async def rate_limit_check(request: Request):
        if not HAS_SLOWAPI or _limiter is None:
            return None

        # slowapi의 rate limit 체크 수행
        await _limiter._check_request_limit(request, func=None, limits=[limit_string])
        return None

    return rate_limit_check


# Pre-defined rate limit dependencies (config 기반)
def get_rate_limit_health():
    """Health 엔드포인트용 rate limit"""
    return _create_rate_limit_dependency("120/minute")


def get_rate_limit_status():
    """Status 엔드포인트용 rate limit (높음)"""
    return _create_rate_limit_dependency("120/minute")


def get_rate_limit_trading():
    """Trading read 엔드포인트용 rate limit (중간)"""
    return _create_rate_limit_dependency("60/minute")


def get_rate_limit_trading_write():
    """Trading write 엔드포인트용 rate limit (낮음)"""
    return _create_rate_limit_dependency("5/minute")


def get_rate_limit_strategies():
    """Strategies 엔드포인트용 rate limit (중간)"""
    return _create_rate_limit_dependency("30/minute")


def get_rate_limit_backtest():
    """Backtest 엔드포인트용 rate limit (낮음)"""
    return _create_rate_limit_dependency("10/minute")


# =============================================================================
# Metrics Authentication
# =============================================================================


def verify_metrics_api_key(request: Request) -> None:
    """Metrics 엔드포인트용 API 키 검증

    METRICS_REQUIRE_AUTH 환경 변수가 'true'일 때만 인증을 요구합니다.
    기본값은 false로, Prometheus 스크래퍼와의 호환성을 위해 인증을 비활성화합니다.

    Args:
        request: FastAPI Request 객체

    Raises:
        HTTPException: API 키가 유효하지 않거나 누락된 경우 401 에러

    Example:
        @router.get("/metrics")
        async def metrics(
            _auth: Annotated[None, Depends(verify_metrics_api_key)] = None
        ):
            ...
    """
    from services.api.auth import get_api_key, validate_api_key

    # 환경 변수 체크 - 기본값은 false (인증 비활성화)
    require_auth = os.environ.get("METRICS_REQUIRE_AUTH", "false").lower() == "true"

    if not require_auth:
        return None

    # API 키가 설정되지 않은 경우 - 보안 경고
    if not get_api_key():
        logger.warning(
            "METRICS_REQUIRE_AUTH is enabled but API_KEY is not set. "
            "Metrics endpoint is protected but has no valid key configured."
        )
        raise HTTPException(
            status_code=401,
            detail="Authentication required but not configured",
        )

    # API 키 검증 (reuse existing auth module with timing-safe comparison)
    api_key = request.headers.get("X-API-Key")
    if not validate_api_key(api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
        )

    return None


# Dummy classes for when FastAPI is not available
if not HAS_FASTAPI:

    class APIRouter:
        def __init__(self, **kwargs):
            pass

        def get(self, *_args, **_kwargs):
            def decorator(func):
                return func

            return decorator

        def post(self, *_args, **_kwargs):
            def decorator(func):
                return func

            return decorator

    class BaseModel:
        pass


router = APIRouter()


# =============================================================================
# Root
# =============================================================================


@router.get("/", tags=["Root"])
async def root(request: Request):
    """API 루트 — 사용 가능한 엔드포인트 안내"""
    debug = getattr(request.app.state, "debug", False)
    return {
        "service": "KIS Unified Trading System API",
        "docs": "/docs" if debug else None,
        "endpoints": {
            "health": "/health",
            "status": "/api/v1/status",
            "trading": "/api/v1/trading/status",
            "strategies": "/api/v1/strategies",
            "metrics": "/metrics",
        },
    }


# =============================================================================
# Enums & Validators
# =============================================================================


class AssetClass(str, Enum):
    """자산 클래스"""
    STOCK = "stock"
    FUTURES = "futures"


# 전략 이름 패턴: 영문 소문자, 숫자, 언더스코어만 허용
STRATEGY_NAME_PATTERN = re.compile(r"^[a-z0-9_]+$")

# 주식 코드 패턴: 6자리 숫자
STOCK_CODE_PATTERN = re.compile(r"^\d{6}$")


# =============================================================================
# Request/Response Models
# =============================================================================


if HAS_FASTAPI:

    class HealthResponse(BaseModel):
        status: str = "ok"
        timestamp: str
        uptime_seconds: float
        version: str

    class StatusResponse(BaseModel):
        trading: dict[str, Any]
        system: dict[str, Any]

    class TradingStartRequest(BaseModel):
        asset_class: AssetClass = Field(default=AssetClass.STOCK, description="stock or futures")
        strategy: str = Field(
            default="bb_reversion",
            min_length=1,
            max_length=50,
            description="전략 이름 (영문 소문자, 숫자, 언더스코어만)",
        )
        capital: float = Field(default=10_000_000, gt=0, description="초기 자본금")
        symbols: list[str] = Field(default_factory=list, description="거래 대상 종목 코드")
        paper_trading: bool = Field(default=True, description="모의투자 모드")

        @field_validator("strategy")
        @classmethod
        def validate_strategy_name(cls, v: str) -> str:
            if not STRATEGY_NAME_PATTERN.match(v):
                raise ValueError("전략 이름은 영문 소문자, 숫자, 언더스코어만 허용됩니다")
            return v

        @field_validator("symbols")
        @classmethod
        def validate_symbols(cls, v: list[str]) -> list[str]:
            for symbol in v:
                if not STOCK_CODE_PATTERN.match(symbol):
                    raise ValueError(f"잘못된 종목 코드 형식: {symbol} (6자리 숫자 필요)")
            return v

    class TradingResponse(BaseModel):
        success: bool
        message: str
        state: str | None = None

    class StrategyInfo(BaseModel):
        name: str
        asset_class: str
        description: str | None = None
        enabled: bool = True

    class BacktestRequest(BaseModel):
        strategy: str = Field(..., min_length=1, max_length=50)
        asset_class: AssetClass = AssetClass.STOCK
        start_date: str | None = None
        end_date: str | None = None
        capital: float = Field(default=10_000_000, gt=0)
        data_path: str | None = None

        @field_validator("strategy")
        @classmethod
        def validate_strategy(cls, v: str) -> str:
            if not STRATEGY_NAME_PATTERN.match(v):
                raise ValueError("전략 이름은 영문 소문자, 숫자, 언더스코어만 허용됩니다")
            return v

    class BacktestResponse(BaseModel):
        success: bool
        run_id: str | None = None
        result: dict[str, Any] | None = None
        error: str | None = None


# =============================================================================
# Dependencies
# =============================================================================


if HAS_FASTAPI:
    from services.api.auth import require_trading_permission
    from services.api.state import AppState, get_app_state


# =============================================================================
# Health & Status
# =============================================================================


@router.get("/health", tags=["Health"])
async def health_check(request: Request):
    """헬스 체크"""
    state: AppState = request.app.state.app_state

    try:
        # shared 버전 사용 시도
        from shared import __version__
        version = __version__
    except ImportError:
        version = "0.1.0"

    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": state.uptime_seconds,
        "version": version,
    }


@router.get("/health/live", tags=["Health"])
async def liveness_probe():
    """Liveness probe - 프로세스 생존 확인

    Kubernetes liveness probe용.
    프로세스가 살아있으면 200 반환.
    """
    from services.monitoring.health import liveness_check

    result = await liveness_check()
    return result.to_dict()


@router.get("/health/ready", tags=["Health"])
async def readiness_probe():
    """Readiness probe - 서비스 준비 상태 확인

    Kubernetes readiness probe용.
    모든 의존성이 준비되면 200, 아니면 503 반환.
    """
    from services.monitoring.health import HealthChecker, readiness_check

    checker = HealthChecker()
    status = await readiness_check(checker)

    if not status.is_healthy:
        raise HTTPException(
            status_code=503,
            detail={
                "status": status.status.value,
                "unhealthy": status.unhealthy_components,
            },
        )

    return status.to_dict()


@router.get(
    "/api/v1/status",
    tags=["Status"],
    dependencies=[Depends(get_rate_limit_status())],
)
async def get_status(
    state: Annotated[AppState, Depends(get_app_state)],
):
    """시스템 상태 조회"""
    orchestrator = await state.get_orchestrator()

    trading_status = {}
    if orchestrator:
        trading_status = orchestrator.get_status()

    return {
        "trading": trading_status,
        "system": {
            "timestamp": datetime.now().isoformat(),
            **state.to_dict(),
        },
    }


# =============================================================================
# Trading Management (인증 필요)
# =============================================================================


def _create_session_runner(orchestrator: "TradingOrchestrator") -> Callable:
    """Create background task runner with proper error handling.

    Args:
        orchestrator: Trading orchestrator to run

    Returns:
        Async callable for background task execution
    """
    from services.trading.orchestrator import TradingState

    async def run_with_error_handling():
        try:
            await orchestrator.run_session()
        except TradingSystemError as e:
            # Catch all trading system errors (network, API, infrastructure, etc.)
            logger.error(f"Trading session failed: {e}", exc_info=True)

            # Update orchestrator state to reflect failure
            orchestrator.state = TradingState.ERROR
            orchestrator.last_error = sanitize_error_message(e)
            orchestrator.last_error_time = datetime.now()

            # Send notification if notifier available
            # Internal alerts get the full error for on-call debugging
            if hasattr(orchestrator, '_notify') and callable(orchestrator._notify):
                try:
                    await orchestrator._notify(
                        f"⚠️ Trading Session Failed\n"
                        f"Error: {e}"
                    )
                except NetworkError as notify_error:
                    # Telegram notification failures are network errors
                    logger.error(f"Failed to send error notification: {notify_error}")

    return run_with_error_handling


@router.post(
    "/api/v1/trading/start",
    tags=["Trading"],
    dependencies=[Depends(get_rate_limit_trading_write())],
)
async def start_trading(
    request_body: "TradingStartRequest",
    background_tasks: BackgroundTasks,
    state: Annotated[AppState, Depends(get_app_state)],
    _api_key: Annotated[str | None, Depends(require_trading_permission)] = None,
):
    """거래 시작 (인증 필요)"""
    from services.trading import TradingConfig, TradingOrchestrator

    orchestrator = await state.get_orchestrator()

    if orchestrator and orchestrator.is_running:
        raise HTTPException(status_code=400, detail="Trading already running")

    # 설정 생성
    if request_body.asset_class == AssetClass.STOCK:
        config = TradingConfig.stock(
            strategy_name=request_body.strategy,
            symbols=request_body.symbols,
            initial_capital=request_body.capital,
        )
    else:
        config = TradingConfig.futures(
            strategy_name=request_body.strategy,
            initial_capital=request_body.capital,
        )

    config.paper_trading = request_body.paper_trading

    # 오케스트레이터 생성 및 설정
    orchestrator = TradingOrchestrator(config)
    success = await state.set_orchestrator(orchestrator)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to set orchestrator")

    # 백그라운드에서 실행 (with proper error handling)
    runner = _create_session_runner(orchestrator)
    background_tasks.add_task(runner)

    logger.info(f"Trading started: {request_body.strategy} ({request_body.asset_class.value})")

    return {
        "success": True,
        "message": "Trading started",
        "state": "running",
    }


@router.post(
    "/api/v1/trading/stop",
    tags=["Trading"],
    dependencies=[Depends(get_rate_limit_trading_write())],
)
async def stop_trading(
    state: Annotated[AppState, Depends(get_app_state)],
    _api_key: Annotated[str | None, Depends(require_trading_permission)] = None,
):
    """거래 종료 (인증 필요)"""
    orchestrator = await state.get_orchestrator()

    if not orchestrator:
        raise HTTPException(status_code=400, detail="No trading session")

    await orchestrator.stop()
    await state.clear_orchestrator()

    logger.info("Trading stopped")

    return {
        "success": True,
        "message": "Trading stopped",
        "state": "stopped",
    }


@router.post(
    "/api/v1/trading/pause",
    tags=["Trading"],
    dependencies=[Depends(get_rate_limit_trading_write())],
)
async def pause_trading(
    state: Annotated[AppState, Depends(get_app_state)],
    _api_key: Annotated[str | None, Depends(require_trading_permission)] = None,
):
    """거래 일시 정지 (인증 필요)"""
    orchestrator = await state.get_orchestrator()

    if not orchestrator:
        raise HTTPException(status_code=400, detail="No trading session")

    await orchestrator.pause()

    logger.info("Trading paused")

    return {
        "success": True,
        "message": "Trading paused",
        "state": "paused",
    }


@router.post(
    "/api/v1/trading/resume",
    tags=["Trading"],
    dependencies=[Depends(get_rate_limit_trading_write())],
)
async def resume_trading(
    state: Annotated[AppState, Depends(get_app_state)],
    _api_key: Annotated[str | None, Depends(require_trading_permission)] = None,
):
    """거래 재개 (인증 필요)"""
    orchestrator = await state.get_orchestrator()

    if not orchestrator:
        raise HTTPException(status_code=400, detail="No trading session")

    await orchestrator.resume()

    logger.info("Trading resumed")

    return {
        "success": True,
        "message": "Trading resumed",
        "state": "running",
    }


@router.get(
    "/api/v1/trading/status",
    tags=["Trading"],
    dependencies=[Depends(get_rate_limit_trading())],
)
async def get_trading_status(
    state: Annotated[AppState, Depends(get_app_state)],
):
    """거래 상태 조회"""
    orchestrator = await state.get_orchestrator()

    if not orchestrator:
        return {
            "state": "idle",
            "message": "No trading session",
        }

    return orchestrator.get_status()


@router.get(
    "/api/v1/trading/metrics",
    tags=["Trading"],
    dependencies=[Depends(get_rate_limit_trading())],
)
async def get_trading_metrics(
    state: Annotated[AppState, Depends(get_app_state)],
):
    """거래 메트릭 조회"""
    orchestrator = await state.get_orchestrator()

    if not orchestrator:
        return {}

    return orchestrator.get_metrics()


# =============================================================================
# Strategies
# =============================================================================


@router.get(
    "/api/v1/strategies",
    tags=["Strategies"],
    dependencies=[Depends(get_rate_limit_strategies())],
)
async def list_strategies(asset_class: AssetClass | None = None):
    """전략 목록 조회"""
    try:
        from shared.config.loader import ConfigLoader

        ac = asset_class.value if asset_class else None
        strategies = ConfigLoader.load_all_strategies(ac)

        return {
            "strategies": [
                {
                    "name": (strat := s["strategy"])["name"],
                    "asset_class": strat.get("asset_class", "unknown"),
                    "enabled": strat.get("enabled", True),
                }
                for s in strategies
            ]
        }
    except (ConfigurationError, FileNotFoundError, ValueError) as e:
        # ConfigurationError: invalid config files
        # FileNotFoundError: missing strategy files
        # ValueError: malformed YAML or invalid data
        logger.error(f"Failed to load strategies: {e}", exc_info=True)
        return {"strategies": [], "error": sanitize_error_message(e)}


@router.get(
    "/api/v1/strategies/{name}",
    tags=["Strategies"],
    dependencies=[Depends(get_rate_limit_strategies())],
)
async def get_strategy(
    name: Annotated[
        str,
        Path(
            min_length=1,
            max_length=50,
            pattern=r"^[a-z0-9_]+$",
            description="전략 이름",
        ),
    ],
    asset_class: AssetClass = AssetClass.STOCK,
):
    """전략 상세 조회"""
    try:
        from shared.config.loader import ConfigLoader

        config = ConfigLoader.load_strategy(asset_class.value, name)
        return config
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Strategy not found: {asset_class.value}/{name}"
        )
    except (ConfigurationError, ValueError) as e:
        # ConfigurationError: invalid config file
        # ValueError: malformed YAML or invalid data
        logger.error(f"Failed to load strategy {asset_class.value}/{name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=sanitize_error_message(e))


# =============================================================================
# Backtest (인증 필요)
# =============================================================================


@router.post(
    "/api/v1/backtest/run",
    tags=["Backtest"],
    dependencies=[Depends(get_rate_limit_backtest())],
)
async def run_backtest(
    request_body: "BacktestRequest",
    _background_tasks: BackgroundTasks,
    _api_key: Annotated[str | None, Depends(require_trading_permission)] = None,
):
    """백테스트 실행 (인증 필요).

    Phase 5 (dashboard redesign): the ad-hoc HTTP backtest pathway was
    removed alongside the dashboard's deprecated backtest UI. Backtests
    now run exclusively through the CLI (``sts backtest run``) so that
    runs are reproducible from version-controlled inputs and tracked in
    MLflow. The endpoint is preserved as a 410 stub to surface a clear
    error to any lingering API client.
    """
    logger.info(
        "Backtest HTTP endpoint invoked but is disabled: %s", request_body.strategy
    )
    raise HTTPException(
        status_code=410,
        detail=(
            "HTTP backtest endpoint removed in dashboard Phase 5. "
            "Use the CLI instead: 'sts backtest run --strategy <name> "
            "--asset <stock|futures> --data <path>'."
        ),
    )


@router.get(
    "/api/v1/backtest/results",
    tags=["Backtest"],
    dependencies=[Depends(get_rate_limit_backtest())],
)
async def get_backtest_results(experiment: str | None = None, limit: int = 10):
    """백테스트 결과 조회"""
    try:
        from shared.backtest import MLflowTracker

        if experiment:
            runs = MLflowTracker.search_runs(
                experiment_name=experiment,
                order_by=["start_time DESC"],
                max_results=limit,
            )
            return {"runs": runs.to_dict(orient="records")}
        else:
            return {"runs": [], "message": "Specify experiment name"}
    except ImportError:
        return {"runs": [], "error": "MLflow not installed"}
    except (InfrastructureError, RuntimeError) as e:
        # InfrastructureError: MLflow tracking server connection issues
        # RuntimeError: MLflow API errors
        logger.error(f"Failed to get backtest results: {e}", exc_info=True)
        return {"runs": [], "error": sanitize_error_message(e)}


# =============================================================================
# Metrics (조건부 인증 — METRICS_REQUIRE_AUTH 환경 변수 기반)
# =============================================================================


@router.get("/metrics", tags=["Monitoring"])
async def prometheus_metrics(
    _auth: Annotated[None, Depends(verify_metrics_api_key)] = None,
):
    """Prometheus 메트릭 (조건부 인증)

    METRICS_REQUIRE_AUTH=true 환경 변수 설정 시 X-API-Key 헤더 필요.
    기본값은 false로, Prometheus 스크래퍼 호환성을 위해 인증 비활성화.
    """
    try:
        from services.monitoring import MetricsCollector

        collector = MetricsCollector()
        content = collector.export_prometheus()
        return Response(content=content, media_type="text/plain")
    except (InfrastructureError, ImportError, RuntimeError) as e:
        # InfrastructureError: Redis/ClickHouse connection issues
        # ImportError: missing monitoring dependencies
        # RuntimeError: metrics collection errors
        logger.error(f"Failed to export metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to export metrics")
