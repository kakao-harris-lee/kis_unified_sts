"""FastAPI dashboard application."""
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

# Allowed CORS origins
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

# Check if in development mode - allows any origin
_DEV_MODE = os.getenv("DASHBOARD_DEV_MODE", "false").lower() == "true"

# OpenAPI tags for documentation organization
OPENAPI_TAGS = [
    {
        "name": "trading",
        "description": "Trading operations and status management",
    },
    {
        "name": "signals",
        "description": "Trading signals and entry/exit alerts",
    },
    {
        "name": "trades",
        "description": "Trade history and performance statistics",
    },
    {
        "name": "backtest",
        "description": "Backtesting operations and results",
    },
    {
        "name": "experiments",
        "description": "MLflow experiment tracking",
    },
]


def create_app(
    title: str = "KIS Unified Trading Dashboard",
    debug: bool = False,
    require_auth: bool = False,
    api_key: Optional[str] = None,
    rate_limit: int = 0,
    rate_limit_window: int = 60,
) -> FastAPI:
    """Create FastAPI application.

    Args:
        title: Application title.
        debug: Enable debug mode.
        require_auth: If True, require API key authentication.
        api_key: The API key to use for authentication (required if require_auth=True).
        rate_limit: Maximum requests per window. 0 disables rate limiting.
        rate_limit_window: Rate limit window in seconds.
    """
    app = FastAPI(
        title=title,
        description="Real-time trading dashboard for KIS unified platform",
        version="1.0.0",
        debug=debug,
        openapi_tags=OPENAPI_TAGS,
    )

    # CORS middleware - configure allowed origins based on environment
    cors_origins = ["*"] if _DEV_MODE else ALLOWED_ORIGINS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )

    # Rate limiting middleware (add first so it runs before auth)
    if rate_limit > 0:
        from services.dashboard.middleware.rate_limit import RateLimitMiddleware

        app.add_middleware(
            RateLimitMiddleware,
            requests_per_window=rate_limit,
            window_seconds=rate_limit_window,
        )

    # API key authentication middleware
    if require_auth and api_key:
        from services.dashboard.middleware.auth import APIKeyMiddleware

        app.add_middleware(APIKeyMiddleware, api_key=api_key)

    # Register routes
    _register_routes(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register API routes."""
    from fastapi import WebSocket

    from services.dashboard.routes import backtest, experiments, signals, trades, trading
    from services.dashboard.websocket import websocket_endpoint

    # Include API routers
    app.include_router(trading.router)
    app.include_router(signals.router)
    app.include_router(trades.router)
    app.include_router(backtest.router)
    app.include_router(experiments.router)

    # WebSocket endpoint
    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        await websocket_endpoint(websocket)

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
        }

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {"message": "KIS Unified Trading Dashboard API"}
