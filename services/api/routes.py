"""API 라우터

REST API 엔드포인트 정의.

Endpoints:
    GET  /health              - 헬스 체크
    GET  /api/v1/status       - 시스템 상태

    POST /api/v1/trading/start    - 거래 시작
    POST /api/v1/trading/stop     - 거래 종료
    POST /api/v1/trading/pause    - 일시 정지
    POST /api/v1/trading/resume   - 재개
    GET  /api/v1/trading/status   - 거래 상태

    GET  /api/v1/strategies       - 전략 목록
    GET  /api/v1/strategies/{name} - 전략 상세

    POST /api/v1/backtest/run     - 백테스트 실행
    GET  /api/v1/backtest/results - 백테스트 결과
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Optional imports
try:
    from fastapi import APIRouter, HTTPException, BackgroundTasks
    from pydantic import BaseModel, Field

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

    # Dummy classes
    class APIRouter:
        def __init__(self, **kwargs):
            pass

        def get(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def post(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    class BaseModel:
        pass


router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


if HAS_FASTAPI:

    class HealthResponse(BaseModel):
        status: str = "ok"
        timestamp: str
        uptime_seconds: float
        version: str = "0.1.0"

    class StatusResponse(BaseModel):
        trading: dict[str, Any]
        system: dict[str, Any]

    class TradingStartRequest(BaseModel):
        asset_class: str = Field(default="stock", description="stock or futures")
        strategy: str = Field(default="bb_reversion")
        capital: float = Field(default=10_000_000)
        symbols: list[str] = Field(default_factory=list)
        paper_trading: bool = Field(default=True)

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
        strategy: str
        asset_class: str = "stock"
        start_date: str | None = None
        end_date: str | None = None
        capital: float = 10_000_000
        data_path: str | None = None

    class BacktestResponse(BaseModel):
        success: bool
        run_id: str | None = None
        result: dict[str, Any] | None = None
        error: str | None = None


# =============================================================================
# Health & Status
# =============================================================================


@router.get("/health", tags=["Health"])
async def health_check():
    """헬스 체크"""
    from services.api.app import _start_time

    now = datetime.now()
    uptime = (now - _start_time).total_seconds() if _start_time else 0

    return {
        "status": "ok",
        "timestamp": now.isoformat(),
        "uptime_seconds": uptime,
        "version": "0.1.0",
    }


@router.get("/api/v1/status", tags=["Status"])
async def get_status():
    """시스템 상태 조회"""
    from services.api.app import get_orchestrator

    orchestrator = get_orchestrator()

    trading_status = {}
    if orchestrator:
        trading_status = orchestrator.get_status()

    return {
        "trading": trading_status,
        "system": {
            "timestamp": datetime.now().isoformat(),
        },
    }


# =============================================================================
# Trading Management
# =============================================================================


@router.post("/api/v1/trading/start", tags=["Trading"])
async def start_trading(request: "TradingStartRequest", background_tasks: "BackgroundTasks"):
    """거래 시작"""
    from services.api.app import get_orchestrator, set_orchestrator
    from services.trading import TradingOrchestrator, TradingConfig

    orchestrator = get_orchestrator()

    if orchestrator and orchestrator.is_running:
        raise HTTPException(status_code=400, detail="Trading already running")

    # 설정 생성
    if request.asset_class == "stock":
        config = TradingConfig.stock(
            strategy_name=request.strategy,
            symbols=request.symbols,
            initial_capital=request.capital,
        )
    else:
        config = TradingConfig.futures(
            strategy_name=request.strategy,
            initial_capital=request.capital,
        )

    config.paper_trading = request.paper_trading

    # 오케스트레이터 생성 및 시작
    orchestrator = TradingOrchestrator(config)
    set_orchestrator(orchestrator)

    # 백그라운드에서 실행
    background_tasks.add_task(orchestrator.run_session)

    return {
        "success": True,
        "message": "Trading started",
        "state": "running",
    }


@router.post("/api/v1/trading/stop", tags=["Trading"])
async def stop_trading():
    """거래 종료"""
    from services.api.app import get_orchestrator

    orchestrator = get_orchestrator()

    if not orchestrator:
        raise HTTPException(status_code=400, detail="No trading session")

    await orchestrator.stop()

    return {
        "success": True,
        "message": "Trading stopped",
        "state": "stopped",
    }


@router.post("/api/v1/trading/pause", tags=["Trading"])
async def pause_trading():
    """거래 일시 정지"""
    from services.api.app import get_orchestrator

    orchestrator = get_orchestrator()

    if not orchestrator:
        raise HTTPException(status_code=400, detail="No trading session")

    await orchestrator.pause()

    return {
        "success": True,
        "message": "Trading paused",
        "state": "paused",
    }


@router.post("/api/v1/trading/resume", tags=["Trading"])
async def resume_trading():
    """거래 재개"""
    from services.api.app import get_orchestrator

    orchestrator = get_orchestrator()

    if not orchestrator:
        raise HTTPException(status_code=400, detail="No trading session")

    await orchestrator.resume()

    return {
        "success": True,
        "message": "Trading resumed",
        "state": "running",
    }


@router.get("/api/v1/trading/status", tags=["Trading"])
async def get_trading_status():
    """거래 상태 조회"""
    from services.api.app import get_orchestrator

    orchestrator = get_orchestrator()

    if not orchestrator:
        return {
            "state": "idle",
            "message": "No trading session",
        }

    return orchestrator.get_status()


@router.get("/api/v1/trading/metrics", tags=["Trading"])
async def get_trading_metrics():
    """거래 메트릭 조회"""
    from services.api.app import get_orchestrator

    orchestrator = get_orchestrator()

    if not orchestrator:
        return {}

    return orchestrator.get_metrics()


# =============================================================================
# Strategies
# =============================================================================


@router.get("/api/v1/strategies", tags=["Strategies"])
async def list_strategies(asset_class: str | None = None):
    """전략 목록 조회"""
    try:
        from shared.config.loader import ConfigLoader

        strategies = ConfigLoader.load_all_strategies(asset_class)

        return {
            "strategies": [
                {
                    "name": s["strategy"]["name"],
                    "asset_class": s["strategy"].get("asset_class", "unknown"),
                    "enabled": s["strategy"].get("enabled", True),
                }
                for s in strategies
            ]
        }
    except Exception as e:
        logger.error(f"Failed to load strategies: {e}")
        return {"strategies": [], "error": str(e)}


@router.get("/api/v1/strategies/{name}", tags=["Strategies"])
async def get_strategy(name: str, asset_class: str = "stock"):
    """전략 상세 조회"""
    try:
        from shared.config.loader import ConfigLoader

        config = ConfigLoader.load_strategy(asset_class, name)
        return config
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Strategy not found: {asset_class}/{name}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Backtest
# =============================================================================


@router.post("/api/v1/backtest/run", tags=["Backtest"])
async def run_backtest(request: "BacktestRequest", background_tasks: "BackgroundTasks"):
    """백테스트 실행"""
    # TODO: 실제 백테스트 실행 구현
    return {
        "success": True,
        "message": "Backtest started",
        "run_id": None,
        "result": None,
    }


@router.get("/api/v1/backtest/results", tags=["Backtest"])
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
    except Exception as e:
        return {"runs": [], "error": str(e)}
